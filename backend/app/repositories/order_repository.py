from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import exists, or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address import Address
from app.models.bid_event import BidEvent
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product_listing import ProductListing


def _visible_to(user_id: int):
    """An order is visible to its buyer and to every seller with an item in it."""
    seller_has_item = exists().where(OrderItem.order_id == Order.id, OrderItem.seller_id == user_id)
    return or_(Order.buyer_id == user_id, seller_has_item)


class OrderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, entity_id: int) -> Order | None:
        result = await self.db.execute(select(Order).where(Order.id == entity_id))
        return result.scalar_one_or_none()

    async def get_by_public_id(self, public_id: UUID) -> Order | None:
        result = await self.db.execute(select(Order).where(Order.public_id == public_id))
        return result.scalar_one_or_none()

    async def get_visible_by_public_id(
        self, public_id: UUID, user_id: int, *, for_update: bool = False
    ) -> Order | None:
        query = select(Order).where(Order.public_id == public_id, _visible_to(user_id))
        if for_update:
            query = query.with_for_update(of=Order)  # serialises cancel vs. item status changes
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_visible(self, *, user_id: int, offset: int = 0, limit: int = 100) -> list[Order]:
        result = await self.db.execute(
            select(Order)
            .where(_visible_to(user_id))
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_visible(self, *, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Order).where(_visible_to(user_id))
        )
        return int(result.scalar_one())

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Order]:
        result = await self.db.execute(select(Order).order_by(Order.created_at.desc(), Order.id.desc()).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Order))
        return int(result.scalar_one())

    async def has_items_in(self, order_id: int, statuses: set[str]) -> bool:
        result = await self.db.execute(
            select(exists().where(OrderItem.order_id == order_id, OrderItem.status.in_(statuses)))
        )
        return bool(result.scalar())

    # --- Checkout (F12 / S18) -------------------------------------------------------------

    async def lock_listings(self, public_ids: list[UUID]) -> list[ProductListing]:
        """The listings, row-locked until the transaction ends, so two checkouts can't both take the
        last stock. Locked in id order so two checkouts never wait on each other forever."""
        result = await self.db.execute(
            select(ProductListing)
            .where(ProductListing.public_id.in_(public_ids))
            .order_by(ProductListing.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def listings_with_open_bid_event(self, listing_ids: list[int]) -> set[int]:
        """Listings that have a pre-bid event still open (bid events use ACTIVE for open)."""
        result = await self.db.execute(
            select(BidEvent.listing_id).where(
                BidEvent.listing_id.in_(listing_ids), BidEvent.status == "ACTIVE"
            )
        )
        return set(result.scalars().all())

    async def get_buyer_address(self, user_id: int, public_id: UUID | None) -> Address | None:
        """The buyer's own active address; with no id, their default one."""
        query = select(Address).where(Address.user_id == user_id, Address.is_active.is_(True))
        if public_id is None:
            query = query.where(Address.is_default.is_(True))
        else:
            query = query.where(Address.public_id == public_id)
        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def create_with_items(self, order_values: dict[str, Any], items: list[dict[str, Any]]) -> Order:
        order = Order(**order_values)
        self.db.add(order)
        await self.db.flush()
        self.db.add_all(OrderItem(order_id=order.id, **values) for values in items)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def give_back_stock_of_open_items(self, order_id: int, *, final_statuses: set[str]) -> None:
        """Add the quantity of every not-yet-final item back to its listing (before cancelling them)."""
        await self.db.execute(
            update(ProductListing)
            .where(
                ProductListing.id == OrderItem.listing_id,
                OrderItem.order_id == order_id,
                OrderItem.status.not_in(final_statuses),
            )
            .values(available_quantity=ProductListing.available_quantity + OrderItem.quantity)
            .execution_options(synchronize_session=False)
        )

    async def cancel_open_items(self, order_id: int, *, final_statuses: set[str]) -> None:
        """Set every item of the order that isn't already final to CANCELLED."""
        await self.db.execute(
            update(OrderItem)
            .where(OrderItem.order_id == order_id, OrderItem.status.not_in(final_statuses))
            .values(status="CANCELLED")
        )

    async def confirm_open_items(self, order_id: int, *, open_statuses: set[str]) -> int:
        """Move the order's open items to CONFIRMED. Returns how many moved."""
        result = await self.db.execute(
            update(OrderItem)
            .where(OrderItem.order_id == order_id, OrderItem.status.in_(open_statuses))
            .values(status="CONFIRMED")
        )
        return result.rowcount or 0

    async def update(self, entity: Order, **values: Any) -> Order:
        for field, value in values.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
