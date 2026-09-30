from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.bid import Bid
from app.models.bid_event import BidEvent


def _visible_to(user_id: int):
    """A bid is visible to its bidder and to the creator of the event it was placed on."""
    event_is_mine = exists().where(BidEvent.id == Bid.bid_event_id, BidEvent.created_by_id == user_id)
    return or_(Bid.bidder_id == user_id, event_is_mine)


class BidRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _base_query():
        return select(Bid).options(joinedload(Bid.bid_event), joinedload(Bid.bidder))

    async def get_event_for_bidding(self, event_public_id: UUID, user_id: int, open_status: str) -> BidEvent | None:
        """The event if this user may see it (open, or their own). Share-locked so the creator can't
        delete or edit it while this bid is being placed."""
        result = await self.db.execute(
            select(BidEvent)
            .options(joinedload(BidEvent.listing))
            .where(
                BidEvent.public_id == event_public_id,
                or_(BidEvent.status == open_status, BidEvent.created_by_id == user_id),
            )
            .with_for_update(read=True, of=BidEvent)
        )
        return result.unique().scalar_one_or_none()

    async def get_visible_by_public_id(self, public_id: UUID, user_id: int) -> Bid | None:
        result = await self.db.execute(
            self._base_query().where(Bid.public_id == public_id, _visible_to(user_id))
        )
        return result.unique().scalar_one_or_none()

    @staticmethod
    def _visible_condition(user_id: int, bid_event_public_id: UUID | None):
        conditions = [_visible_to(user_id)]
        if bid_event_public_id is not None:
            conditions.append(
                Bid.bid_event_id == select(BidEvent.id).where(BidEvent.public_id == bid_event_public_id).scalar_subquery()
            )
        return conditions

    async def list_visible(
        self, *, user_id: int, bid_event_public_id: UUID | None = None, offset: int = 0, limit: int = 100
    ) -> list[Bid]:
        result = await self.db.execute(
            self._base_query()
            .where(*self._visible_condition(user_id, bid_event_public_id))
            .order_by(Bid.created_at.desc(), Bid.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique().scalars().all())

    async def count_visible(self, *, user_id: int, bid_event_public_id: UUID | None = None) -> int:
        result = await self.db.execute(
            select(func.count(Bid.id)).where(*self._visible_condition(user_id, bid_event_public_id))
        )
        return int(result.scalar_one())

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Bid]:
        result = await self.db.execute(select(Bid).order_by(Bid.created_at.desc(), Bid.id.desc()).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Bid))
        return int(result.scalar_one())

    async def create(self, **values: Any) -> Bid:
        entity = Bid(**values)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        await self.db.refresh(entity, ["bid_event", "bidder"])
        return entity
