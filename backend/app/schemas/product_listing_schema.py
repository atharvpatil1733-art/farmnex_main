from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class ProductListingCreate(BaseModel):
    """What the app may send. The seller comes from the login; status and available quantity are set by the server."""

    farm_id: UUID
    crop_batch_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    listing_type: str = Field(min_length=1, max_length=30)
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", min_length=1, max_length=10)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=30)
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ProductListingUpdate(BaseModel):
    """Only these can change later. To take a listing off sale, delete it (that closes it)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ProductListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    seller_id: UUID = Field(validation_alias=AliasPath("seller", "public_id"))
    farm_id: UUID = Field(validation_alias=AliasPath("farm", "public_id"))
    crop_batch_id: UUID = Field(validation_alias=AliasPath("crop_batch", "public_id"))
    title: str
    description: str | None = None
    listing_type: str
    price: Decimal
    currency: str
    quantity: Decimal
    available_quantity: Decimal
    unit: str
    minimum_order_quantity: Decimal | None = None
    status: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
