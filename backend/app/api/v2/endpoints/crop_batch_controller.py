from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.repositories.crop_batch_repository import CropBatchRepository
from app.schemas.crop_batch_schema import CropBatchCreate, CropBatchResponse, CropBatchUpdate
from app.services.crop_batch_service import CropBatchService

router = APIRouter(prefix="/crop-batches", tags=["CropBatch"])


def get_crop_batch_service(db: AsyncSession = Depends(get_db)) -> CropBatchService:
    return CropBatchService(CropBatchRepository(db))


def _raise_http(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("", response_model=CropBatchResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: CropBatchCreate,
    current_user: User = Depends(get_current_user),
    service: CropBatchService = Depends(get_crop_batch_service),
) -> CropBatchResponse:
    try:
        entity = await service.create(payload.model_dump(exclude_unset=True), current_user)
        return CropBatchResponse.model_validate(entity)
    except AppException as exc:
        _raise_http(exc)


@router.get("", response_model=list[CropBatchResponse])
async def list_all(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: CropBatchService = Depends(get_crop_batch_service),
) -> list[CropBatchResponse]:
    try:
        entities, _ = await service.list(current_user=current_user, offset=offset, limit=limit)
        return [CropBatchResponse.model_validate(entity) for entity in entities]
    except AppException as exc:
        _raise_http(exc)


@router.get("/{public_id}", response_model=CropBatchResponse)
async def get_one(
    public_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CropBatchService = Depends(get_crop_batch_service),
) -> CropBatchResponse:
    try:
        return CropBatchResponse.model_validate(await service.get(public_id, current_user))
    except AppException as exc:
        _raise_http(exc)


@router.patch("/{public_id}", response_model=CropBatchResponse)
async def update(
    public_id: UUID,
    payload: CropBatchUpdate,
    current_user: User = Depends(get_current_user),
    service: CropBatchService = Depends(get_crop_batch_service),
) -> CropBatchResponse:
    try:
        entity = await service.update(public_id, payload.model_dump(exclude_unset=True), current_user)
        return CropBatchResponse.model_validate(entity)
    except AppException as exc:
        _raise_http(exc)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    public_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CropBatchService = Depends(get_crop_batch_service),
) -> None:
    try:
        await service.delete(public_id, current_user)
    except AppException as exc:
        _raise_http(exc)
