from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import exists, or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_item import OrderItem


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

    async def cancel_open_items(self, order_id: int, *, final_statuses: set[str]) -> None:
        """Set every item of the order that isn't already final to CANCELLED."""
        await self.db.execute(
            update(OrderItem)
            .where(OrderItem.order_id == order_id, OrderItem.status.not_in(final_statuses))
            .values(status="CANCELLED")
        )

    async def update(self, entity: Order, **values: Any) -> Order:
        for field, value in values.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
