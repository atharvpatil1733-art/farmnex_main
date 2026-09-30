from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.repositories.product_image_repository import ProductImageRepository
from app.schemas.product_image_schema import ProductImageCreate, ProductImageResponse, ProductImageUpdate
from app.services.product_image_service import ProductImageService

router = APIRouter(prefix="/product-images", tags=["ProductImage"])


def get_product_image_service(db: AsyncSession = Depends(get_db)) -> ProductImageService:
    return ProductImageService(ProductImageRepository(db))


def _raise_http(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: ProductImageCreate,
    current_user: User = Depends(get_current_user),
    service: ProductImageService = Depends(get_product_image_service),
) -> ProductImageResponse:
    try:
        entity = await service.create(payload.model_dump(exclude_unset=True), current_user)
        return ProductImageResponse.model_validate(entity)
    except AppException as exc:
        _raise_http(exc)


@router.get("", response_model=list[ProductImageResponse])
async def list_all(
    listing_id: UUID | None = Query(None, description="Only the images of this listing."),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ProductImageService = Depends(get_product_image_service),
) -> list[ProductImageResponse]:
    try:
        entities, _ = await service.list(
            current_user=current_user, listing_public_id=listing_id, offset=offset, limit=limit
        )
        return [ProductImageResponse.model_validate(entity) for entity in entities]
    except AppException as exc:
        _raise_http(exc)


@router.get("/{public_id}", response_model=ProductImageResponse)
async def get_one(
    public_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProductImageService = Depends(get_product_image_service),
) -> ProductImageResponse:
    try:
        return ProductImageResponse.model_validate(await service.get(public_id, current_user))
    except AppException as exc:
        _raise_http(exc)


@router.patch("/{public_id}", response_model=ProductImageResponse)
async def update(
    public_id: UUID,
    payload: ProductImageUpdate,
    current_user: User = Depends(get_current_user),
    service: ProductImageService = Depends(get_product_image_service),
) -> ProductImageResponse:
    try:
        entity = await service.update(public_id, payload.model_dump(exclude_unset=True), current_user)
        return ProductImageResponse.model_validate(entity)
    except AppException as exc:
        _raise_http(exc)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    public_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProductImageService = Depends(get_product_image_service),
) -> None:
    try:
        await service.delete(public_id, current_user)
    except AppException as exc:
        _raise_http(exc)
