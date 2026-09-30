from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class ProductImageCreate(BaseModel):
    """What the app may send. Which listing it belongs to is given as its public id."""

    listing_id: UUID
    storage_path: str = Field(min_length=1, max_length=1024)
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    sort_order: int = Field(default=0, ge=0)
    is_primary: bool = False


class ProductImageUpdate(BaseModel):
    """Only the order and the primary flag can change. The file and its listing cannot."""

    sort_order: int | None = Field(default=None, ge=0)
    is_primary: bool | None = None


class ProductImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    listing_id: UUID = Field(validation_alias=AliasPath("listing", "public_id"))
    storage_path: str
    content_type: str
    sort_order: int
    is_primary: bool
    created_at: datetime
    updated_at: datetime
