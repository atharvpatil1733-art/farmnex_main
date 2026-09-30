from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.bid import Bid
from app.models.user import User
from app.repositories.bid_event_repository import OPEN_STATUS
from app.repositories.bid_repository import BidRepository


class BidService:
    """Bids can only be placed and read over HTTP. There is no edit or delete: withdrawing or
    winning a bid is a status change made by the server (F12 / S19)."""

    def __init__(self, repository: BidRepository) -> None:
        self.repository = repository

    @staticmethod
    def _validate_paging(offset: int, limit: int) -> None:
        if offset < 0:
            raise ValidationError("Offset cannot be negative.")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100.")

    async def create(self, data: dict[str, Any], current_user: User) -> Bid:
        event = await self.repository.get_event_for_bidding(data.pop("bid_event_id"), current_user.id, OPEN_STATUS)
        if event is None:
            raise NotFoundError("BidEvent not found.")
        if event.created_by_id == current_user.id or event.listing.seller_id == current_user.id:
            raise ForbiddenError("You cannot bid on your own listing.")
        now = datetime.now(timezone.utc)
        if event.status != OPEN_STATUS or event.listing.status != "ACTIVE" or not (event.starts_at <= now <= event.ends_at):
            raise ConflictError("This event is not open for bids right now.")
        if data["amount"] < event.starting_price:
            raise ValidationError("The bid is below the starting price.")
        # TODO(F12 / S19): the bid must beat the current highest bid by minimum_increment (with row locking).

        values = {
            **data,
            "bid_event_id": event.id,
            "bidder_id": current_user.id,  # from the login, never the body
            "status": "ACTIVE",  # server-owned
            "placed_at": now,  # server-owned
        }
        return await self.repository.create(**values)

    async def get(self, public_id: UUID, current_user: User) -> Bid:
        entity = await self.repository.get_visible_by_public_id(public_id, current_user.id)
        if entity is None:
            raise NotFoundError("Bid not found.")
        return entity

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        *,
        current_user: User | None = None,
        bid_event_id: UUID | None = None,
    ) -> tuple[list[Bid], int]:
        self._validate_paging(offset, limit)
        if current_user is None:
            # Internal callers only (me_service filters the result by bidder itself). The HTTP
            # controller always passes current_user.
            return await self.repository.list(offset=offset, limit=limit), await self.repository.count()
        return (
            await self.repository.list_visible(
                user_id=current_user.id, bid_event_public_id=bid_event_id, offset=offset, limit=limit
            ),
            await self.repository.count_visible(user_id=current_user.id, bid_event_public_id=bid_event_id),
        )
