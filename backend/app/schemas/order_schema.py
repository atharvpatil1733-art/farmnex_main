from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# No OrderCreate: orders are created by the server (F12 / S18), never from a public request body.


class OrderUpdate(BaseModel):
    """The only change a buyer may make: cancel the order while it is PLACED."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["CANCELLED"]


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    public_id: UUID | None = None
    order_number: str | None = None
    status: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    delivery_fee: Decimal | None = None
    tax_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    total_amount: Decimal | None = None
    delivery_address_snapshot: dict | None = None
    placed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
