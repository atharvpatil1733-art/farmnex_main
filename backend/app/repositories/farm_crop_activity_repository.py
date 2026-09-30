from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.farm_crop import FarmCrop
from app.models.farm_crop_activity import FarmCropActivity


class FarmCropActivityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, entity_id: int) -> FarmCropActivity | None:
        result = await self.db.execute(select(FarmCropActivity).where(FarmCropActivity.id == entity_id))
        return result.scalar_one_or_none()

    async def get_by_public_id(self, public_id: UUID) -> FarmCropActivity | None:
        result = await self.db.execute(select(FarmCropActivity).where(FarmCropActivity.public_id == public_id))
        return result.scalar_one_or_none()

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[FarmCropActivity]:
        result = await self.db.execute(select(FarmCropActivity).order_by(FarmCropActivity.created_at.desc(), FarmCropActivity.id.desc()).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def list_for_farmer(self, farmer_id: int, *, offset: int = 0, limit: int = 100) -> list[FarmCropActivity]:
        result = await self.db.execute(
            select(FarmCropActivity)
            .join(FarmCrop, FarmCrop.id == FarmCropActivity.farm_crop_id)
            .where(FarmCrop.farmer_id == farmer_id)
            .order_by(FarmCropActivity.created_at.desc(), FarmCropActivity.id.desc())
            .offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(FarmCropActivity))
        return int(result.scalar_one())

    async def create(self, **values: Any) -> FarmCropActivity:
        entity = FarmCropActivity(**values)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: FarmCropActivity, **values: Any) -> FarmCropActivity:
        for field, value in values.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: FarmCropActivity) -> None:
        await self.db.delete(entity)
        await self.db.flush()
