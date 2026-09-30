from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class BidCreate(BaseModel):
    """What the app may send. The bidder comes from the login; status and placed_at are set by the server."""

    bid_event_id: UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)


class BidResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    bid_event_id: UUID = Field(validation_alias=AliasPath("bid_event", "public_id"))
    bidder_id: UUID = Field(validation_alias=AliasPath("bidder", "public_id"))
    amount: Decimal
    quantity: Decimal | None = None
    status: str
    placed_at: datetime
    created_at: datetime
    updated_at: datetime
