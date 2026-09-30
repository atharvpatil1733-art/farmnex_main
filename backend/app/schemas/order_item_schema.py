from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# No OrderItemCreate: items are created by the server together with their order (F12 / S18).

# SHIPPED and DELIVERED are set only by the delivery listener (pickup / drop), never by the seller (S33).
SellerItemStatus = Literal["CONFIRMED", "PACKED", "CANCELLED"]


class OrderItemUpdate(BaseModel):
    """The only change the item's seller may make: its status."""

    model_config = ConfigDict(extra="forbid")

    status: SellerItemStatus


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    public_id: UUID | None = None
    order_id: UUID | None = None  # the order's public id
    title_snapshot: str | None = None
    unit_price: Decimal | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    line_total: Decimal | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
