from __future__ import annotations

from typing import Any

from app.models.user import User
from app.services.user_service import UserService
from app.services.farm_service import FarmService
from app.services.product_listing_service import ProductListingService
from app.services.bid_service import BidService
from app.services.order_service import OrderService
from app.services.crop_batch_service import CropBatchService
from app.services.farm_crop_activity_service import FarmCropActivityService
from app.services.waste_record_service import WasteRecordService
from app.services.notification_service import NotificationService


class MeService:
    """Authenticated dashboard aggregator.

    This service must only return records owned by the current user. The
    current generic repositories are used as a compatibility layer; dedicated
    owner-scoped repository methods should replace broad list calls before
    high-volume production deployment.
    """

    def __init__(self, *, user_service: UserService, farm_service: FarmService,
                 product_listing_service: ProductListingService, bid_service: BidService,
                 order_service: OrderService, crop_batch_service: CropBatchService,
                 activity_service: FarmCropActivityService, waste_record_service: WasteRecordService,
                 notification_service: NotificationService) -> None:
        self.user_service = user_service
        self.farm_service = farm_service
        self.product_listing_service = product_listing_service
        self.bid_service = bid_service
        self.order_service = order_service
        self.crop_batch_service = crop_batch_service
        self.activity_service = activity_service
        self.waste_record_service = waste_record_service
        self.notification_service = notification_service

    @staticmethod
    def _serialize(entity: Any) -> dict[str, Any]:
        result = {}
        for key, value in vars(entity).items():
            if key.startswith("_") or key in {"id", "password_hash", "pin_hash"}:
                continue
            # Internal database numbers (farm_id, bidder_id, ...) never leave the server.
            if key.endswith("_id") and isinstance(value, int) and not isinstance(value, bool):
                continue
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            if hasattr(value, "value"):
                value = value.value
            if isinstance(value, (str, int, float, bool, type(None), list, dict)):
                result[key] = value
        return result

    @staticmethod
    def _owned(items: list[Any], user: User, *fields: str) -> list[Any]:
        return [item for item in items if any(getattr(item, field, None) in {user.id, user.public_id} for field in fields)]

    async def get_dashboard(self, *, current_user: User, limit: int = 20) -> dict[str, Any]:
        limit = min(max(limit, 1), 50)
        user = await self.user_service.get_my_profile(current_user=current_user)

        farms, _ = await self.farm_service.list_farms(user_id=user.id, offset=0, limit=limit)
        products, _ = await self.product_listing_service.list(current_user=current_user, only_mine=True, offset=0, limit=limit)
        bids, _ = await self.bid_service.list(offset=0, limit=limit, current_user=current_user)
        orders, _ = await self.order_service.list(offset=0, limit=limit, current_user=current_user)
        batches, _ = await self.crop_batch_service.list(current_user=current_user, offset=0, limit=limit)
        activities = await self.activity_service.list_mine(farmer_id=user.id, offset=0, limit=limit)
        waste, _ = await self.waste_record_service.list(offset=0, limit=limit)
        notifications, _ = await self.notification_service.list(offset=0, limit=limit)

        role = getattr(getattr(user, "role", None), "name", None)
        role = getattr(role, "value", role)
        role = str(role).upper() if role else None

        return {
            "profile": self._serialize(user),
            "roles": [role] if role else [],
            "farms": [self._serialize(x) for x in self._owned(farms, user, "user_id")],
            "products": [self._serialize(x) for x in self._owned(products, user, "seller_id")],
            "bids": [self._serialize(x) for x in self._owned(bids, user, "bidder_id")],
            "orders": [self._serialize(x) for x in self._owned(orders, user, "buyer_id")],
            "crop_batches": [self._serialize(x) for x in batches[:limit]],
            "farm_crop_activities": [self._serialize(x) for x in activities[:limit]],
            "waste_records": [self._serialize(x) for x in self._owned(waste, user, "recorded_by_id")],
            "notifications": [self._serialize(x) for x in self._owned(notifications, user, "user_id")],
        }
