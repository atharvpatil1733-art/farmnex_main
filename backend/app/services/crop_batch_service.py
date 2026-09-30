from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.crop_batch import CropBatch
from app.models.user import User
from app.repositories.crop_batch_repository import CropBatchRepository

# The only fields an owner may change after creation (the schema already limits this; kept as a safety net).
_UPDATABLE = {"harvest_date", "quality_grade", "organic_certified", "notes"}


class CropBatchService:
    def __init__(self, repository: CropBatchRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    async def create(self, data: dict[str, Any], current_user: User) -> CropBatch:
        farm_crop = await self.repository.get_farm_crop_owned_by_user(data.pop("farm_crop_id"), current_user.id)
        if farm_crop is None:
            raise NotFoundError("FarmCrop not found.")

        batch_code = data.pop("batch_code", None)
        if batch_code is None:
            batch_code = f"B-{secrets.token_hex(5).upper()}"
        if await self.repository.batch_code_exists(batch_code):
            raise ConflictError("This batch code is already in use.")

        values = {
            "harvest_date": data.get("harvest_date"),
            "quantity": data["quantity"],
            "unit": data["unit"],
            "quality_grade": data.get("quality_grade"),
            "organic_certified": data.get("organic_certified", False),
            "notes": data.get("notes"),
            "farm_crop_id": farm_crop.id,
            "batch_code": batch_code,
            "available_quantity": data["quantity"],  # server-owned: starts equal to the quantity
            "status": "ACTIVE",  # server-owned
        }
        return await self.repository.create(**values)

    async def get(self, public_id: UUID, current_user: User) -> CropBatch:
        entity = await self.repository.get_owned_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("CropBatch not found.")
        return entity

    async def list(self, *, current_user: User, offset: int = 0, limit: int = 100) -> tuple[list[CropBatch], int]:
        self._validate_paging(offset, limit)
        return (
            await self.repository.list_owned(user_id=current_user.id, offset=offset, limit=limit),
            await self.repository.count_owned(user_id=current_user.id),
        )

    async def update(self, public_id: UUID, data: dict[str, Any], current_user: User) -> CropBatch:
        entity = await self.get(public_id, current_user)
        clean = {key: value for key, value in data.items() if key in _UPDATABLE}
        return await self.repository.update(entity, **clean)

    async def delete(self, public_id: UUID, current_user: User) -> None:
        entity = await self.get(public_id, current_user)
        if await self.repository.count_listings(entity.id) > 0:
            raise ConflictError("This batch is used by a listing. Close the listing first.")
        await self.repository.delete(entity)
