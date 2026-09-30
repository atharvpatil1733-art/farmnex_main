from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing


class ProductImageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _base_query(self):
        return (
            select(ProductImage)
            .join(ProductListing, ProductListing.id == ProductImage.listing_id)
            .options(joinedload(ProductImage.listing))
        )

    @staticmethod
    def _visible_to(user_id: int):
        """Same rule as the listing: ACTIVE listings' images are public to a logged-in user, the seller sees all own."""
        return or_(ProductListing.status == "ACTIVE", ProductListing.seller_id == user_id)

    async def get_listing_owned_by_user(self, listing_public_id: UUID, user_id: int) -> ProductListing | None:
        result = await self.db.execute(
            select(ProductListing).where(ProductListing.public_id == listing_public_id, ProductListing.seller_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_visible_by_public_id(self, public_id: UUID, user_id: int) -> ProductImage | None:
        result = await self.db.execute(
            self._base_query().where(ProductImage.public_id == public_id, self._visible_to(user_id))
        )
        return result.unique().scalar_one_or_none()

    async def get_owned_by_public_id(self, public_id: UUID, user_id: int) -> ProductImage | None:
        result = await self.db.execute(
            self._base_query().where(ProductImage.public_id == public_id, ProductListing.seller_id == user_id)
        )
        return result.unique().scalar_one_or_none()

    def _list_filter(self, user_id: int, listing_public_id: UUID | None):
        conditions = [self._visible_to(user_id)]
        if listing_public_id is not None:
            conditions.append(ProductListing.public_id == listing_public_id)
        return conditions

    async def list_visible(
        self, *, user_id: int, listing_public_id: UUID | None, offset: int, limit: int
    ) -> list[ProductImage]:
        result = await self.db.execute(
            self._base_query()
            .where(*self._list_filter(user_id, listing_public_id))
            .order_by(ProductImage.sort_order, ProductImage.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique().scalars().all())

    async def count_visible(self, *, user_id: int, listing_public_id: UUID | None) -> int:
        result = await self.db.execute(
            select(func.count(ProductImage.id))
            .join(ProductListing, ProductListing.id == ProductImage.listing_id)
            .where(*self._list_filter(user_id, listing_public_id))
        )
        return int(result.scalar_one())

    async def create(self, **values: Any) -> ProductImage:
        entity = ProductImage(**values)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, ["listing"])
        return entity

    async def update(self, entity: ProductImage, **values: Any) -> ProductImage:
        for field, value in values.items():
            setattr(entity, field, value)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, ["listing"])
        return entity

    async def delete(self, entity: ProductImage) -> None:
        await self.db.delete(entity)
        await self.db.flush()
