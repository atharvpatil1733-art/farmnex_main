from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.api.dependencies.roles import require_roles
from app.core.database import get_db
from app.models.user import User
from app.repositories.bid_event_repository import BidEventRepository
from app.schemas.bid_event_schema import BidEventCreate, BidEventUpdate, BidEventResponse
from app.services.bid_event_service import BidEventService

router = APIRouter(prefix="/bid-events", tags=["BidEvent"])

def _service(db: AsyncSession) -> BidEventService:
    return BidEventService(BidEventRepository(db))

@router.post("", response_model=BidEventResponse, status_code=status.HTTP_201_CREATED)
async def create(payload: BidEventCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles("FARMER", "VENDOR"))) -> BidEventResponse:
    """Open pre-bidding on one of my listings."""
    entity = await _service(db).create(payload.model_dump(), current_user)
    return BidEventResponse.model_validate(entity)

@router.get("", response_model=list[BidEventResponse])
async def list_all(
    mine: bool = Query(False, description="Only events I created (any status)."),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BidEventResponse]:
    entities, _ = await _service(db).list(current_user=current_user, only_mine=mine, offset=offset, limit=limit)
    return [BidEventResponse.model_validate(x) for x in entities]

@router.get("/{public_id}", response_model=BidEventResponse)
async def get_one(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BidEventResponse:
    entity = await _service(db).get(public_id, current_user)
    return BidEventResponse.model_validate(entity)

@router.patch("/{public_id}", response_model=BidEventResponse)
async def update(public_id: UUID, payload: BidEventUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BidEventResponse:
    """Creator only, and only while the event is open and has no bids."""
    entity = await _service(db).update(public_id, payload.model_dump(exclude_unset=True), current_user)
    return BidEventResponse.model_validate(entity)

@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    """Creator only, and only while the event has no bids."""
    await _service(db).delete(public_id, current_user)
