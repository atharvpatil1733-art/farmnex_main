from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_item import OrderItem


def _visible_to(user_id: int):
    """An item is visible to the order's buyer and to the item's own seller (not other sellers)."""
    return or_(Order.buyer_id == user_id, OrderItem.seller_id == user_id)


class OrderItemRepository:
    """Queries return (item, order public id) so responses never need the internal order id."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, entity_id: int) -> OrderItem | None:
        result = await self.db.execute(select(OrderItem).where(OrderItem.id == entity_id))
        return result.scalar_one_or_none()

    async def get_visible_by_public_id(
        self, public_id: UUID, user_id: int
    ) -> tuple[OrderItem, UUID] | None:
        result = await self.db.execute(
            select(OrderItem, Order.public_id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(OrderItem.public_id == public_id, _visible_to(user_id))
        )
        row = result.one_or_none()
        return (row[0], row[1]) if row else None

    async def list_visible(
        self,
        *,
        user_id: int,
        order_public_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[tuple[OrderItem, UUID]]:
        query = (
            select(OrderItem, Order.public_id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(_visible_to(user_id))
        )
        if order_public_id is not None:
            query = query.where(Order.public_id == order_public_id)
        result = await self.db.execute(
            query.order_by(OrderItem.created_at.desc(), OrderItem.id.desc()).offset(offset).limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def update(self, entity: OrderItem, **values: Any) -> OrderItem:
        for field, value in values.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
