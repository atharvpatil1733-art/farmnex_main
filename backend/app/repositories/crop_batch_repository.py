from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.crop_batch import CropBatch
from app.models.farm_crop import FarmCrop
from app.models.product_listing import ProductListing


class CropBatchRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_farm_crop_owned_by_user(self, farm_crop_public_id: UUID, user_id: int) -> FarmCrop | None:
        result = await self.db.execute(
            select(FarmCrop).where(FarmCrop.public_id == farm_crop_public_id, FarmCrop.farmer_id == user_id)
        )
        return result.scalar_one_or_none()

    async def batch_code_exists(self, batch_code: str) -> bool:
        result = await self.db.execute(select(func.count(CropBatch.id)).where(CropBatch.batch_code == batch_code))
        return int(result.scalar_one()) > 0

    async def count_listings(self, crop_batch_id: int) -> int:
        result = await self.db.execute(
            select(func.count(ProductListing.id)).where(ProductListing.crop_batch_id == crop_batch_id)
        )
        return int(result.scalar_one())

    async def get_owned_by_public_id(self, public_id: UUID, user_id: int) -> CropBatch | None:
        result = await self.db.execute(
            select(CropBatch)
            .join(FarmCrop, FarmCrop.id == CropBatch.farm_crop_id)
            .options(joinedload(CropBatch.farm_crop))
            .where(CropBatch.public_id == public_id, FarmCrop.farmer_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_owned(self, *, user_id: int, offset: int, limit: int) -> list[CropBatch]:
        result = await self.db.execute(
            select(CropBatch)
            .join(FarmCrop, FarmCrop.id == CropBatch.farm_crop_id)
            .options(joinedload(CropBatch.farm_crop))
            .where(FarmCrop.farmer_id == user_id)
            .order_by(CropBatch.created_at.desc(), CropBatch.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_owned(self, *, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(CropBatch.id))
            .join(FarmCrop, FarmCrop.id == CropBatch.farm_crop_id)
            .where(FarmCrop.farmer_id == user_id)
        )
        return int(result.scalar_one())

    async def create(self, **values: Any) -> CropBatch:
        entity = CropBatch(**values)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, ["farm_crop"])
        return entity

    async def update(self, entity: CropBatch, **values: Any) -> CropBatch:
        for field, value in values.items():
            setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, ["farm_crop"])
        return entity

    async def delete(self, entity: CropBatch) -> None:
        await self.db.delete(entity)
        await self.db.flush()
