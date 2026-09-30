from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import exists, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment


def _visible_to(user_id: int, *, is_admin: bool):
    """A payment is visible to its payer, to every seller with an item in its order, and to ADMIN."""
    if is_admin:
        return true()
    seller_in_order = exists().where(
        OrderItem.order_id == Payment.order_id, OrderItem.seller_id == user_id
    )
    return or_(Payment.payer_id == user_id, seller_in_order)


class PaymentRepository:
    """Read queries return (payment, order public id) so responses never need internal ids.

    There is no public create/update/delete; `create` and `update` stay for the server-side
    payment flow (F12 / S20).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _visible_query(self, user_id: int, is_admin: bool):
        return (
            select(Payment, Order.public_id)
            .join(Order, Payment.order_id == Order.id)
            .where(_visible_to(user_id, is_admin=is_admin))
        )

    async def get_visible_by_public_id(
        self, public_id: UUID, user_id: int, *, is_admin: bool = False
    ) -> tuple[Payment, UUID] | None:
        result = await self.db.execute(
            self._visible_query(user_id, is_admin).where(Payment.public_id == public_id)
        )
        row = result.one_or_none()
        return (row[0], row[1]) if row else None

    async def list_visible(
        self, *, user_id: int, is_admin: bool = False, offset: int = 0, limit: int = 100
    ) -> list[tuple[Payment, UUID]]:
        result = await self.db.execute(
            self._visible_query(user_id, is_admin)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def create(self, **values: Any) -> Payment:
        entity = Payment(**values)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: Payment, **values: Any) -> Payment:
        for field, value in values.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
