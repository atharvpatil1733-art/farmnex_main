from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class CropBatchCreate(BaseModel):
    """What the app may send. Status and available quantity are set by the server."""

    farm_crop_id: UUID
    batch_code: str | None = Field(default=None, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    harvest_date: date | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)
    quality_grade: str | None = Field(default=None, max_length=50)
    organic_certified: bool = False
    notes: str | None = None


class CropBatchUpdate(BaseModel):
    """Only descriptive fields can change. Quantity, status and the crop it belongs to cannot."""

    harvest_date: date | None = None
    quality_grade: str | None = Field(default=None, max_length=50)
    organic_certified: bool | None = None
    notes: str | None = None


class CropBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    farm_crop_id: UUID = Field(validation_alias=AliasPath("farm_crop", "public_id"))
    batch_code: str
    harvest_date: date | None = None
    quantity: Decimal
    available_quantity: Decimal
    unit: str
    quality_grade: str | None = None
    organic_certified: bool
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
