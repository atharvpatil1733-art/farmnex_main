from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.models.product_image import ProductImage
from app.models.user import User
from app.repositories.product_image_repository import ProductImageRepository
from app.services.storage_service import StorageService, StorageValidationError

_UPDATABLE = {"sort_order", "is_primary"}
_PRODUCT_FOLDER = "product-images"


class ProductImageService:
    def __init__(self, repository: ProductImageRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    @staticmethod
    def _validate_storage_path(path: str) -> str:
        """The file must sit directly in the product-images folder of our storage."""
        try:
            value = StorageService.validate_managed_path(path)
        except StorageValidationError as exc:
            raise ValidationError("Invalid storage path.") from exc
        if value.split("/")[0] != _PRODUCT_FOLDER:
            raise ValidationError("Product images must be stored in the product-images folder.")
        return value

    async def create(self, data: dict[str, Any], current_user: User) -> ProductImage:
        listing = await self.repository.get_listing_owned_by_user(data.pop("listing_id"), current_user.id)
        if listing is None:
            raise NotFoundError("ProductListing not found.")
        data["storage_path"] = self._validate_storage_path(data["storage_path"])
        return await self.repository.create(**data, listing_id=listing.id)

    async def get(self, public_id: UUID, current_user: User) -> ProductImage:
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("ProductImage not found.")
        return entity

    async def list(
        self, *, current_user: User, listing_public_id: UUID | None = None, offset: int = 0, limit: int = 100
    ) -> tuple[list[ProductImage], int]:
        self._validate_paging(offset, limit)
        return (
            await self.repository.list_visible(
                user_id=current_user.id, listing_public_id=listing_public_id, offset=offset, limit=limit
            ),
            await self.repository.count_visible(user_id=current_user.id, listing_public_id=listing_public_id),
        )

    async def _get_owned(self, public_id: UUID, current_user: User) -> ProductImage:
        entity = await self.repository.get_owned_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("ProductImage not found.")
        return entity

    async def update(self, public_id: UUID, data: dict[str, Any], current_user: User) -> ProductImage:
        entity = await self._get_owned(public_id, current_user)
        clean = {key: value for key, value in data.items() if key in _UPDATABLE}
        return await self.repository.update(entity, **clean)

    async def delete(self, public_id: UUID, current_user: User) -> None:
        entity = await self._get_owned(public_id, current_user)
        await self.repository.delete(entity)
