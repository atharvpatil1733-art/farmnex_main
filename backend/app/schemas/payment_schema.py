from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# No PaymentCreate / PaymentUpdate: payments are created and changed only by the server
# (F12 / S20 demo payment), never from a public request body.


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    public_id: UUID | None = None
    order_id: UUID | None = None  # the order's public id
    provider: str | None = None
    provider_payment_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    status: str | None = None
    payment_method: str | None = None
    paid_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
