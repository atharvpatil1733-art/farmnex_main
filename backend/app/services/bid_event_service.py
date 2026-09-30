from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.bid_event import BidEvent
from app.models.user import User
from app.repositories.bid_event_repository import OPEN_STATUS, BidEventRepository

# The only fields the creator may change (the schema already limits this; kept as a safety net).
# status and winner_bid_id are server-owned: accepting a bid comes with F12 (S19).
_UPDATABLE = {"starts_at", "ends_at", "starting_price", "minimum_increment"}


class BidEventService:
    def __init__(self, repository: BidEventRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    @staticmethod
    def _validate_window(starts_at: Any, ends_at: Any) -> None:
        if ends_at <= starts_at:
            raise ValidationError("ends_at must be after starts_at.")

    async def create(self, data: dict[str, Any], current_user: User) -> BidEvent:
        listing = await self.repository.get_listing_owned_by_user(data.pop("listing_id"), current_user.id)
        if listing is None:
            raise NotFoundError("ProductListing not found.")
        if listing.status != "ACTIVE":
            raise ConflictError("This listing is not active.")
        self._validate_window(data["starts_at"], data["ends_at"])

        values = {
            **data,
            "listing_id": listing.id,
            "created_by_id": current_user.id,  # from the login, never the body
            "status": OPEN_STATUS,  # server-owned
        }
        return await self.repository.create(**values)

    async def get(self, public_id: UUID, current_user: User) -> BidEvent:
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("BidEvent not found.")
        return entity

    async def list(
        self, *, current_user: User, only_mine: bool = False, offset: int = 0, limit: int = 100
    ) -> tuple[list[BidEvent], int]:
        self._validate_paging(offset, limit)
        return (
            await self.repository.list_visible(user_id=current_user.id, only_mine=only_mine, offset=offset, limit=limit),
            await self.repository.count_visible(user_id=current_user.id, only_mine=only_mine),
        )

    async def _get_owned_without_bids(self, public_id: UUID, current_user: User) -> BidEvent:
        entity = await self.repository.get_owned_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("BidEvent not found.")
        if await self.repository.has_bids(entity.id):
            raise ConflictError("This event already has bids and can no longer be changed or deleted.")
        return entity

    async def update(self, public_id: UUID, data: dict[str, Any], current_user: User) -> BidEvent:
        entity = await self._get_owned_without_bids(public_id, current_user)
        if entity.status != OPEN_STATUS:
            raise ConflictError("This event is closed and can no longer be changed.")
        clean = {key: value for key, value in data.items() if key in _UPDATABLE and value is not None}
        self._validate_window(clean.get("starts_at", entity.starts_at), clean.get("ends_at", entity.ends_at))
        return await self.repository.update(entity, **clean)

    async def delete(self, public_id: UUID, current_user: User) -> None:
        entity = await self._get_owned_without_bids(public_id, current_user)
        await self.repository.delete(entity)
