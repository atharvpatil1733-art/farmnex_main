from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.crop_batch import CropBatch
from app.models.farm import Farm
from app.models.farm_crop import FarmCrop
from app.models.product_listing import ProductListing

_RELATIONS = ("seller", "farm", "crop_batch")


class ProductListingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _base_query(self):
        return select(ProductListing).options(
            joinedload(ProductListing.seller),
            joinedload(ProductListing.farm),
            joinedload(ProductListing.crop_batch),
        )

    @staticmethod
    def _visible_to(user_id: int):
        """ACTIVE listings are public to any logged-in user; a seller also sees their own in any status."""
        return or_(ProductListing.status == "ACTIVE", ProductListing.seller_id == user_id)

    async def get_farm_owned_by_user(self, farm_public_id: UUID, user_id: int) -> Farm | None:
        result = await self.db.execute(
            select(Farm).where(Farm.public_id == farm_public_id, Farm.user_id == user_id, Farm.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_crop_batch_owned_by_user(self, batch_public_id: UUID, user_id: int) -> tuple[CropBatch, FarmCrop] | None:
        result = await self.db.execute(
            select(CropBatch, FarmCrop)
            .join(FarmCrop, FarmCrop.id == CropBatch.farm_crop_id)
            .where(CropBatch.public_id == batch_public_id, FarmCrop.farmer_id == user_id)
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    async def get_visible_by_public_id(self, public_id: UUID, user_id: int) -> ProductListing | None:
        result = await self.db.execute(
            self._base_query().where(ProductListing.public_id == public_id, self._visible_to(user_id))
        )
        return result.unique().scalar_one_or_none()

    async def get_owned_by_public_id(self, public_id: UUID, user_id: int) -> ProductListing | None:
        result = await self.db.execute(
            self._base_query().where(ProductListing.public_id == public_id, ProductListing.seller_id == user_id)
        )
        return result.unique().scalar_one_or_none()

    async def list_visible(self, *, user_id: int, only_mine: bool, offset: int, limit: int) -> list[ProductListing]:
        query = self._base_query().where(
            ProductListing.seller_id == user_id if only_mine else self._visible_to(user_id)
        )
        result = await self.db.execute(
            query.order_by(ProductListing.created_at.desc(), ProductListing.id.desc()).offset(offset).limit(limit)
        )
        return list(result.unique().scalars().all())

    async def count_visible(self, *, user_id: int, only_mine: bool) -> int:
        result = await self.db.execute(
            select(func.count(ProductListing.id)).where(
                ProductListing.seller_id == user_id if only_mine else self._visible_to(user_id)
            )
        )
        return int(result.scalar_one())

    async def create(self, **values: Any) -> ProductListing:
        entity = ProductListing(**values)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, list(_RELATIONS))
        return entity

    async def update(self, entity: ProductListing, **values: Any) -> ProductListing:
        for field, value in values.items():
            setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, list(_RELATIONS))
        return entity
