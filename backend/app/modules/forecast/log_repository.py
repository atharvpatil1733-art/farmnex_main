"""Writes one row per forecast answer into fc_forecast_logs (migrations/020)."""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

_INSERT = text(
    "INSERT INTO public.fc_forecast_logs (user_public_id, kind, request, response, data_as_of) "
    "VALUES (:user_public_id, :kind, CAST(:request AS JSONB), CAST(:response AS JSONB), :data_as_of)"
)


def _as_of(response: dict) -> date | None:
    raw = response.get("as_of") or response.get("forecast_origin")
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


async def save_log(user_public_id: str, kind: str, request: dict, response: dict) -> None:
    """Insert one log row. Raises on failure; the caller decides to swallow it."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            _INSERT,
            {
                "user_public_id": UUID(user_public_id),
                "kind": kind,
                "request": json.dumps(request, default=str),
                "response": json.dumps(response, default=str),
                "data_as_of": _as_of(response),
            },
        )
        await session.commit()
