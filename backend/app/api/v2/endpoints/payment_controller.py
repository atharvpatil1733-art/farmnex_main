from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.core.database import get_db
from app.models.payment import Payment
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment_schema import PaymentResponse
from app.services.payment_service import PaymentService

# Read-only: no POST, PATCH or DELETE. Payments are created and updated by the server (F12 / S20).
router = APIRouter(prefix="/payments", tags=["Payment"])

def _service(db: AsyncSession) -> PaymentService:
    return PaymentService(PaymentRepository(db))

def _to_response(entity: Payment, order_public_id: UUID) -> PaymentResponse:
    # entity.order_id is the internal int; the response uses the order's public id instead.
    fields = {name: getattr(entity, name) for name in PaymentResponse.model_fields if name != "order_id"}
    return PaymentResponse(**fields, order_id=order_public_id)

@router.get("", response_model=list[PaymentResponse])
async def list_all(offset: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[PaymentResponse]:
    rows = await _service(db).list(current_user=current_user, offset=offset, limit=limit)
    return [_to_response(payment, order_public_id) for payment, order_public_id in rows]

@router.get("/{public_id}", response_model=PaymentResponse)
async def get_one(public_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PaymentResponse:
    return _to_response(*await _service(db).get(public_id, current_user))
