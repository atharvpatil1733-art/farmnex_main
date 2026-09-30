from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.core.database import get_db
from app.models.order_item import OrderItem
from app.models.user import User
from app.repositories.order_item_repository import OrderItemRepository
from app.schemas.order_item_schema import OrderItemUpdate, OrderItemResponse
from app.services.order_item_service import OrderItemService

# No POST or DELETE: items are created by the server with their order (F12 / S18), never deleted.
router = APIRouter(prefix="/order-items", tags=["OrderItem"])

def _service(db: AsyncSession) -> OrderItemService:
    return OrderItemService(OrderItemRepository(db))

def _to_response(entity: OrderItem, order_public_id: UUID) -> OrderItemResponse:
    response = OrderItemResponse.model_validate(entity)
    response.order_id = order_public_id
    return response

@router.get("", response_model=list[OrderItemResponse])
async def list_all(order_id: UUID | None = None, offset: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[OrderItemResponse]:
    """Items you can see; pass `order_id` (the order's public id) to get one order's items."""
    rows = await _service(db).list(current_user=current_user, order_public_id=order_id, offset=offset, limit=limit)
    return [_to_response(item, order_public_id) for item, order_public_id in rows]

@router.get("/{public_id}", response_model=OrderItemResponse)
async def get_one(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderItemResponse:
    return _to_response(*await _service(db).get(public_id, current_user))

@router.patch("/{public_id}", response_model=OrderItemResponse)
async def update(public_id: UUID, payload: OrderItemUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderItemResponse:
    """The item's seller sets its status."""
    return _to_response(*await _service(db).update(public_id, payload.model_dump(), current_user))
