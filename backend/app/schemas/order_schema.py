from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderLineIn(BaseModel):
    """One line of a checkout: which listing and how much. Prices come from the listing, not the app."""

    model_config = ConfigDict(extra="forbid")

    listing_id: UUID  # the listing's public id
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class OrderCreate(BaseModel):
    """What the buyer sends to check out. Buyer, prices, totals and status are set by the server.

    Lines from several farmers are split into one order per farmer (all or nothing).
    """

    model_config = ConfigDict(extra="forbid")

    items: list[OrderLineIn] = Field(min_length=1, max_length=20)
    address_id: UUID | None = None  # one of your own addresses; empty = your default address

    @field_validator("items")
    @classmethod
    def _no_repeated_listing(cls, items: list[OrderLineIn]) -> list[OrderLineIn]:
        ids = [line.listing_id for line in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each listing may appear only once.")
        return items


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


class CheckoutResponse(BaseModel):
    """One checkout = one order per farmer, all sharing `checkout_number` (the start of each order_number)."""

    checkout_number: str
    orders: list[OrderResponse]
