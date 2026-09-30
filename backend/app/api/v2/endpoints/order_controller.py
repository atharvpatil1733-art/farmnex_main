from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.api.dependencies.roles import require_roles
from app.core.database import get_db
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.order_schema import CheckoutResponse, OrderCreate, OrderUpdate, OrderResponse
from app.services.order_service import OrderService

# No DELETE: orders are never deleted. POST only takes listing ids + quantities; prices and totals
# are worked out by the server (F12 / S18).
router = APIRouter(prefix="/orders", tags=["Order"])

def _service(db: AsyncSession) -> OrderService:
    return OrderService(OrderRepository(db))

@router.get("", response_model=list[OrderResponse])
async def list_all(offset: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[OrderResponse]:
    entities, _ = await _service(db).list(offset, limit, current_user=current_user)
    return [OrderResponse.model_validate(x) for x in entities]

@router.post("", response_model=CheckoutResponse, status_code=201)
async def checkout(payload: OrderCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles("BUYER"))) -> CheckoutResponse:
    """Buyer checks out a cart. One order per farmer (shared checkout number), all or nothing."""
    checkout_number, orders = await _service(db).checkout(payload.model_dump(), current_user)
    return CheckoutResponse(checkout_number=checkout_number, orders=[OrderResponse.model_validate(x) for x in orders])

@router.post("/{public_id}/confirm", response_model=OrderResponse)
async def confirm(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderResponse:
    """The farmer selling this order confirms it (PLACED → CONFIRMED)."""
    entity = await _service(db).confirm(public_id, current_user)
    return OrderResponse.model_validate(entity)

@router.get("/{public_id}", response_model=OrderResponse)
async def get_one(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderResponse:
    entity = await _service(db).get(public_id, current_user)
    return OrderResponse.model_validate(entity)

@router.patch("/{public_id}", response_model=OrderResponse)
async def update(public_id: UUID, payload: OrderUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderResponse:
    """Buyer cancels the order (only while it is PLACED)."""
    entity = await _service(db).update(public_id, payload.model_dump(), current_user)
    return OrderResponse.model_validate(entity)
