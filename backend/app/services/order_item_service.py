from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.order_item import OrderItem
from app.models.user import User
from app.repositories.order_item_repository import OrderItemRepository

# An item only moves forward along this path (steps may be skipped). New items are PLACED (S18);
# "ACTIVE" (the table's default) is treated like PLACED.
ITEM_FLOW = ["PLACED", "CONFIRMED", "PACKED", "SHIPPED", "DELIVERED"]
START_STATUSES = {"ACTIVE", "PLACED"}
# The seller may cancel an item only before it ships.
CANCELLABLE_ITEM_STATUSES = {"ACTIVE", "PLACED", "CONFIRMED", "PACKED"}


def _step(status: str) -> int:
    return 0 if status in START_STATUSES else ITEM_FLOW.index(status) if status in ITEM_FLOW else -1


def _check_transition(current: str, new: str) -> None:
    if new == "CANCELLED":
        if current not in CANCELLABLE_ITEM_STATUSES:
            raise ConflictError("This item can no longer be cancelled.")
        return
    if current == "CANCELLED" or _step(current) < 0 or _step(new) <= _step(current):
        raise ConflictError(f"An item can't move from {current} to {new}.")


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
        item, order = row
        return item, order.public_id

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
        row = await self.repository.get_visible_by_public_id(
            public_id, current_user.id, for_update=True
        )
        if row is None:
            raise NotFoundError("OrderItem not found.")
        item, order = row
        if item.seller_id != current_user.id:
            raise ForbiddenError("Only the seller of this item can change it.")
        if order.status == "CANCELLED":
            raise ConflictError("The buyer cancelled this order.")

        _check_transition(item.status, data["status"])
        if data["status"] == "CANCELLED":
            await self.repository.give_back_stock(item)  # the crop is for sale again
        updated = await self.repository.update(item, status=data["status"])
        if data["status"] == "CANCELLED":
            await self.repository.recompute_order_totals(order)  # the buyer no longer pays for it
        return updated, order.public_id
