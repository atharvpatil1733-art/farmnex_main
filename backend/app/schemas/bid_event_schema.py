from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class BidEventCreate(BaseModel):
    """What the app may send. The creator comes from the login; status and winner are set by the server."""

    listing_id: UUID
    starts_at: datetime
    ends_at: datetime
    starting_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    minimum_increment: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class BidEventUpdate(BaseModel):
    """Only these can change, and only while the event has no bids."""

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    starting_price: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    minimum_increment: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class BidEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    listing_id: UUID = Field(validation_alias=AliasPath("listing", "public_id"))
    starts_at: datetime
    ends_at: datetime
    starting_price: Decimal
    minimum_increment: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
