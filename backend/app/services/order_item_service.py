from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.order_item import OrderItem
from app.models.user import User
from app.repositories.order_item_repository import OrderItemRepository


class OrderItemService:
    """Order items: the order's buyer and the item's seller can read; only the seller sets status.

    No create or delete here — items are created by the server with their order (F12 / S18).
    Methods return (item, order public id).
    """

    def __init__(self, repository: OrderItemRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    async def get(self, public_id: UUID, current_user: User) -> tuple[OrderItem, UUID]:
        row = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if row is None:
            raise NotFoundError("OrderItem not found.")
        return row

    async def list(
        self,
        *,
        current_user: User,
        order_public_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[tuple[OrderItem, UUID]]:
        self._validate_paging(offset, limit)
        return await self.repository.list_visible(
            user_id=current_user.id, order_public_id=order_public_id, offset=offset, limit=limit
        )

    async def update(
        self, public_id: UUID, data: dict[str, Any], current_user: User
    ) -> tuple[OrderItem, UUID]:
        entity, order_public_id = await self.get(public_id, current_user)
        if entity.seller_id != current_user.id:
            raise ForbiddenError("Only the seller of this item can change it.")
        updated = await self.repository.update(entity, status=data["status"])
        return updated, order_public_id
