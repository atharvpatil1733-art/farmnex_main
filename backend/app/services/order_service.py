from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.order import Order
from app.models.user import User
from app.repositories.order_repository import OrderRepository

# Orders the buyer may still cancel (F1 rule: "buyer may cancel while PLACED").
CANCELLABLE_STATUSES = {"PLACED"}
# Once any item has left the farm, the order can't be cancelled any more.
SHIPPED_ITEM_STATUSES = {"SHIPPED", "DELIVERED"}


class OrderService:
    """Orders: the buyer and the sellers of its items can read; only the buyer can cancel.

    No create or delete here — orders are created by the server (F12 / S18) and never deleted.
    """

    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    async def get(self, public_id: UUID, current_user: User) -> Order:
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("Order not found.")
        return entity

    async def list(
        self, offset: int = 0, limit: int = 100, *, current_user: User | None = None
    ) -> tuple[list[Order], int]:
        self._validate_paging(offset, limit)
        if current_user is None:
            # Internal callers only (me_service filters the result by buyer itself). The HTTP
            # controller always passes current_user.
            return await self.repository.list(offset=offset, limit=limit), await self.repository.count()
        return (
            await self.repository.list_visible(user_id=current_user.id, offset=offset, limit=limit),
            await self.repository.count_visible(user_id=current_user.id),
        )

    async def update(self, public_id: UUID, data: dict[str, Any], current_user: User) -> Order:
        # Lock the order row so a seller can't move an item forward while we cancel.
        entity = await self.repository.get_visible_by_public_id(
            public_id, current_user.id, for_update=True
        )
        if entity is None:
            raise NotFoundError("Order not found.")
        if entity.buyer_id != current_user.id:
            raise ForbiddenError("Only the buyer can change this order.")

        if data.get("status") == "CANCELLED":
            if entity.status not in CANCELLABLE_STATUSES or await self.repository.has_items_in(
                entity.id, SHIPPED_ITEM_STATUSES
            ):
                raise ConflictError("This order can no longer be cancelled.")
            await self.repository.cancel_open_items(
                entity.id, final_statuses=SHIPPED_ITEM_STATUSES | {"CANCELLED"}
            )
            return await self.repository.update(entity, status="CANCELLED")

        raise ValidationError("Nothing to change.")
