from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bid_event import BidEvent
from app.models.crop_batch import CropBatch
from app.models.farm import Farm
from app.models.product_listing import ProductListing
from app.models.waste_record import WasteRecord
from app.models.waste_utilization_listing import WasteUtilizationListing


class HomeService:
    """Build the public FarmNex home feed.

    Location is optional:
    - coordinates: nearby farms and related listings
    - city/area: textual location fallback
    - no location: generalized active feed

    This service intentionally does not change existing domain services.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_home(
        self,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        city: str | None = None,
        area: str | None = None,
        radius_km: float = 25.0,
        limit: int = 20,
    ) -> dict[str, Any]:
        self._validate_location(latitude, longitude, radius_km)
        limit = min(max(limit, 1), 100)

        farms = await self._get_farms(
            latitude=latitude,
            longitude=longitude,
            city=city,
            area=area,
            radius_km=radius_km,
            limit=limit,
        )

        farm_ids = [farm.id for farm in farms]

        products = await self._get_products(farm_ids=farm_ids, limit=limit)
        pre_bidding = await self._get_pre_bidding(farm_ids=farm_ids, limit=limit)
        waste_to_wealth = await self._get_waste_listings(
            farm_ids=farm_ids,
            limit=limit,
        )

        farm_public = await self._public_ids(Farm, [p.farm_id for p in products])
        batch_public = await self._public_ids(
            CropBatch, [p.crop_batch_id for p in products if p.crop_batch_id is not None]
        )
        listing_public = await self._public_ids(ProductListing, [e.listing_id for e in pre_bidding])

        return {
            "location": {
                "mode": self._location_mode(latitude, longitude, city, area),
                "latitude": latitude,
                "longitude": longitude,
                "city": city,
                "area": area,
                "radius_km": radius_km if latitude is not None else None,
            },
            "sections": {
                "featured_farmers": [self._farm_item(farm) for farm in farms],
                "products": [self._product_item(item, farm_public, batch_public) for item in products],
                "pre_bidding": [self._bid_event_item(item, listing_public) for item in pre_bidding],
                "waste_to_wealth": [
                    self._waste_item(item) for item in waste_to_wealth
                ],
            },
        }

    async def _public_ids(self, model: Any, ids: list[int]) -> dict[int, str]:
        """Map internal ids to public UUID strings (the app never sees internal ids)."""
        if not ids:
            return {}
        result = await self.db.execute(select(model.id, model.public_id).where(model.id.in_(set(ids))))
        return {row.id: str(row.public_id) for row in result}

    @staticmethod
    def _validate_location(
        latitude: float | None,
        longitude: float | None,
        radius_km: float,
    ) -> None:
        if (latitude is None) != (longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90.")
        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180.")
        if not 0 < radius_km <= 200:
            raise ValueError("Radius must be greater than 0 and at most 200 km.")

    @staticmethod
    def _location_mode(
        latitude: float | None,
        longitude: float | None,
        city: str | None,
        area: str | None,
    ) -> str:
        if latitude is not None and longitude is not None:
            return "coordinates"
        if city or area:
            return "text"
        return "general"

    async def _get_farms(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        city: str | None,
        area: str | None,
        radius_km: float,
        limit: int,
    ) -> list[Farm]:
        query: Select[tuple[Farm]] = select(Farm).where(Farm.is_active.is_(True))

        # Text filtering is a fallback when GPS coordinates are not supplied.
        if latitude is None and longitude is None:
            if city:
                query = query.where(Farm.city.ilike(f"%{city.strip()}%"))
            if area:
                area_value = area.strip()
                query = query.where(
                    or_(
                        Farm.village.ilike(f"%{area_value}%"),
                        Farm.city.ilike(f"%{area_value}%"),
                        Farm.district.ilike(f"%{area_value}%"),
                    )
                )
        else:
            # Haversine distance in kilometres. This works without PostGIS.
            # Coordinates are cast to numeric SQL expressions for PostgreSQL.
            distance = (
                6371
                * 2
                * func.asin(
                    func.sqrt(
                        func.pow(
                            func.sin(
                                (func.radians(Farm.latitude) - func.radians(latitude))
                                / 2
                            ),
                            2,
                        )
                        + func.cos(func.radians(latitude))
                        * func.cos(func.radians(Farm.latitude))
                        * func.pow(
                            func.sin(
                                (func.radians(Farm.longitude) - func.radians(longitude))
                                / 2
                            ),
                            2,
                        )
                    )
                )
            )
            query = query.where(
                Farm.latitude.is_not(None),
                Farm.longitude.is_not(None),
                distance <= radius_km,
            ).order_by(distance.asc())

        query = query.order_by(Farm.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_products(
        self,
        *,
        farm_ids: list[int],
        limit: int,
    ) -> list[ProductListing]:
        query = select(ProductListing).where(
            ProductListing.status == "ACTIVE",
            ProductListing.available_quantity > 0,
            or_(
                ProductListing.starts_at.is_(None),
                ProductListing.starts_at <= func.now(),
            ),
            or_(
                ProductListing.ends_at.is_(None),
                ProductListing.ends_at >= func.now(),
            ),
        )
        if farm_ids:
            query = query.where(ProductListing.farm_id.in_(farm_ids))
        query = query.order_by(ProductListing.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_pre_bidding(
        self,
        *,
        farm_ids: list[int],
        limit: int,
    ) -> list[BidEvent]:
        query = (
            select(BidEvent)
            .join(ProductListing, ProductListing.id == BidEvent.listing_id)
            .where(
                BidEvent.status == "ACTIVE",
                BidEvent.starts_at <= func.now(),
                BidEvent.ends_at >= func.now(),
                ProductListing.status == "ACTIVE",
            )
        )
        if farm_ids:
            query = query.where(ProductListing.farm_id.in_(farm_ids))
        query = query.order_by(BidEvent.ends_at.asc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_waste_listings(
        self,
        *,
        farm_ids: list[int],
        limit: int,
    ) -> list[WasteUtilizationListing]:
        query = (
            select(WasteUtilizationListing)
            .join(
                WasteRecord,
                WasteRecord.id == WasteUtilizationListing.waste_record_id,
            )
            .where(WasteUtilizationListing.status == "ACTIVE")
        )
        if farm_ids:
            query = query.where(WasteRecord.farm_id.in_(farm_ids))
        query = query.order_by(WasteUtilizationListing.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _farm_item(farm: Farm) -> dict[str, Any]:
        return {
            "public_id": str(farm.public_id),
            "farm_name": farm.farm_name,
            "description": farm.description,
            "village": farm.village,
            "city": farm.city,
            "district": farm.district,
            "state": farm.state,
            "country": farm.country,
            "latitude": float(farm.latitude) if farm.latitude is not None else None,
            "longitude": float(farm.longitude) if farm.longitude is not None else None,
        }

    @staticmethod
    def _product_item(
        item: ProductListing, farm_public: dict[int, str], batch_public: dict[int, str]
    ) -> dict[str, Any]:
        return {
            "public_id": str(item.public_id),
            "title": item.title,
            "description": item.description,
            "listing_type": item.listing_type,
            "price": str(item.price),
            "currency": item.currency,
            "quantity": str(item.quantity),
            "available_quantity": str(item.available_quantity),
            "unit": item.unit,
            "minimum_order_quantity": (
                str(item.minimum_order_quantity)
                if item.minimum_order_quantity is not None
                else None
            ),
            "farm_id": farm_public.get(item.farm_id),
            "crop_batch_id": batch_public.get(item.crop_batch_id),
            "starts_at": item.starts_at,
            "ends_at": item.ends_at,
        }

    @staticmethod
    def _bid_event_item(item: BidEvent, listing_public: dict[int, str]) -> dict[str, Any]:
        return {
            "public_id": str(item.public_id),
            "listing_id": listing_public.get(item.listing_id),
            "starts_at": item.starts_at,
            "ends_at": item.ends_at,
            "starting_price": str(item.starting_price),
            "minimum_increment": str(item.minimum_increment),
            "status": item.status,
        }

    @staticmethod
    def _waste_item(item: WasteUtilizationListing) -> dict[str, Any]:
        return {
            "public_id": str(item.public_id),
            "title": item.title,
            "description": item.description,
            "utilization_type": item.utilization_type,
            "quantity": str(item.quantity),
            "unit": item.unit,
            "price": str(item.price),
            "status": item.status,
        }
