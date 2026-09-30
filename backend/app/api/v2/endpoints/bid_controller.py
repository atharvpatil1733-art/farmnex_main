from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.api.dependencies.roles import require_roles
from app.core.database import get_db
from app.models.user import User
from app.repositories.bid_repository import BidRepository
from app.schemas.bid_schema import BidCreate, BidResponse
from app.services.bid_service import BidService

# No PATCH or DELETE: a placed bid is changed only by the server (withdraw / win, F12 / S19).
router = APIRouter(prefix="/bids", tags=["Bid"])

def _service(db: AsyncSession) -> BidService:
    return BidService(BidRepository(db))

@router.post("", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def create(payload: BidCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles("BUYER"))) -> BidResponse:
    entity = await _service(db).create(payload.model_dump(), current_user)
    return BidResponse.model_validate(entity)

@router.get("", response_model=list[BidResponse])
async def list_all(
    bid_event_id: UUID | None = Query(None, description="Only bids on this event."),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BidResponse]:
    """My own bids, plus the bids placed on events I created."""
    entities, _ = await _service(db).list(offset, limit, current_user=current_user, bid_event_id=bid_event_id)
    return [BidResponse.model_validate(x) for x in entities]

@router.get("/{public_id}", response_model=BidResponse)
async def get_one(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BidResponse:
    entity = await _service(db).get(public_id, current_user)
    return BidResponse.model_validate(entity)
