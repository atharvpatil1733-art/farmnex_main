from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.product_listing import ProductListing
from app.models.user import User
from app.repositories.product_listing_repository import ProductListingRepository

# The only fields a seller may change after creation (the schema already limits this; kept as a safety net).
_UPDATABLE = {"title", "description", "price", "minimum_order_quantity", "starts_at", "ends_at"}


class ProductListingService:
    def __init__(self, repository: ProductListingRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    @staticmethod
    def _validate_window(starts_at: Any, ends_at: Any) -> None:
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise ValidationError("ends_at must be after starts_at.")

    async def create(self, data: dict[str, Any], current_user: User) -> ProductListing:
        farm = await self.repository.get_farm_owned_by_user(data.pop("farm_id"), current_user.id)
        if farm is None:
            raise NotFoundError("Farm not found.")

        found = await self.repository.get_crop_batch_owned_by_user(data.pop("crop_batch_id"), current_user.id)
        if found is None:
            raise NotFoundError("CropBatch not found.")
        batch, farm_crop = found
        if farm_crop.farm_id != farm.id:
            raise ValidationError("This crop batch does not belong to that farm.")
        if batch.status != "ACTIVE":
            raise ValidationError("This crop batch is not active.")
        if data["quantity"] > batch.available_quantity:
            raise ValidationError("The quantity is more than the crop batch has available.")

        self._validate_window(data.get("starts_at"), data.get("ends_at"))
        minimum = data.get("minimum_order_quantity")
        if minimum is not None and minimum > data["quantity"]:
            raise ValidationError("minimum_order_quantity cannot be more than the quantity.")

        values = {
            **data,
            "seller_id": current_user.id,  # from the login, never the body
            "farm_id": farm.id,
            "crop_batch_id": batch.id,
            "available_quantity": data["quantity"],  # server-owned
            "status": "ACTIVE",  # server-owned
        }
        return await self.repository.create(**values)

    async def get(self, public_id: UUID, current_user: User) -> ProductListing:
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("ProductListing not found.")
        return entity

    async def list(
        self, *, current_user: User, only_mine: bool = False, offset: int = 0, limit: int = 100
    ) -> tuple[list[ProductListing], int]:
        self._validate_paging(offset, limit)
        return (
            await self.repository.list_visible(user_id=current_user.id, only_mine=only_mine, offset=offset, limit=limit),
            await self.repository.count_visible(user_id=current_user.id, only_mine=only_mine),
        )

    async def _get_owned(self, public_id: UUID, current_user: User) -> ProductListing:
        entity = await self.repository.get_owned_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("ProductListing not found.")
        return entity

    async def update(self, public_id: UUID, data: dict[str, Any], current_user: User) -> ProductListing:
        entity = await self._get_owned(public_id, current_user)
        if entity.status == "CLOSED":
            raise ConflictError("This listing is closed and can no longer be changed.")
        clean = {key: value for key, value in data.items() if key in _UPDATABLE}
        self._validate_window(clean.get("starts_at", entity.starts_at), clean.get("ends_at", entity.ends_at))
        minimum = clean.get("minimum_order_quantity")
        if minimum is not None and minimum > entity.quantity:
            raise ValidationError("minimum_order_quantity cannot be more than the quantity.")
        return await self.repository.update(entity, **clean)

    async def delete(self, public_id: UUID, current_user: User) -> None:
        """Take the listing off sale. The row stays (bids and orders may point at it), status becomes CLOSED."""
        entity = await self._get_owned(public_id, current_user)
        if entity.status != "CLOSED":
            await self.repository.update(entity, status="CLOSED")
