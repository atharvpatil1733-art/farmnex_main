"""FarmNex backend <-> forecaster connector.

Adapted from `integration/backend/farmnex_forecast.py` in farmnex_ai_forecaster @ 0f1f6a3:
same routes, request/response shapes, timeouts and meta cache. Three changes for FarmNex:
login is our own JWT (`get_current_user`, not Supabase Auth), and each answer is logged to
`fc_forecast_logs` through our async DB session (not the Supabase REST API).

The app only calls us; the forecaster's key (`FORECASTER_API_KEY`) never leaves the server.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies.current_user import get_current_user
from app.models.user import User

from . import log_repository

log = logging.getLogger("farmnex_forecast")

router = APIRouter(prefix="/forecast", tags=["forecast"])

# The free host sleeps when idle and takes ~1 minute to wake up, hence the long read timeout.
TIMEOUT = httpx.Timeout(90.0, connect=10.0)
META_CACHE_SECONDS = 600
_meta_cache: dict = {"at": 0.0, "data": None}
_http: httpx.AsyncClient | None = None  # one shared client, created on first use


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=TIMEOUT)
    return _http


async def _user_public_id(user: User = Depends(get_current_user)) -> str:
    """Identity comes only from the login token."""
    return str(user.public_id)


async def _call(method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
    """Forward one call to the forecaster and return its JSON, passing its errors through."""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    base = os.environ.get("FORECASTER_URL", "").rstrip("/")
    key = os.environ.get("FORECASTER_API_KEY", "")
    try:
        r = await _client().request(
            method, f"{base}{path}", params=params, json=body, headers={"X-API-Key": key}
        )
    except httpx.HTTPError as exc:
        log.error("forecaster unreachable: %s", type(exc).__name__)
        raise HTTPException(503, "price forecasts are temporarily unavailable, try again soon")
    if r.status_code == 401:
        log.error("forecaster refused our key: check FORECASTER_API_KEY")
        raise HTTPException(503, "price forecasts are temporarily unavailable")
    if r.status_code >= 400:
        is_json = r.headers.get("content-type", "").startswith("application/json")
        detail = r.json().get("detail", r.text) if is_json else r.text
        raise HTTPException(r.status_code, detail)
    return r.json()


async def _save_log(user_public_id: str, kind: str, request: dict, response: dict) -> None:
    """Never breaks the user's request."""
    try:
        await log_repository.save_log(user_public_id, kind, request, response)
    except Exception as exc:
        log.warning("could not save forecast log: %s", type(exc).__name__)


@router.get("/meta")
async def meta():
    """Dropdown lists for the app (markets, crops, districts), data date and the CEDA credit.
    Cached for 10 minutes."""
    if _meta_cache["data"] is None or time.time() - _meta_cache["at"] > META_CACHE_SECONDS:
        _meta_cache.update(data=await _call("GET", "/meta"), at=time.time())
    return _meta_cache["data"]


@router.get("/price")
async def price(
    market: str,
    crop: str,
    days: int = Query(3, ge=1, le=3),
    user_id: str = Depends(_user_public_id),
):
    """Price forecast (low / expected / high, Rs per quintal) for the next 1-3 days."""
    req = {"market": market, "crop": crop, "days": days}
    res = await _call("GET", "/forecast/price", req)
    await _save_log(user_id, "price", req, res)
    return res


@router.get("/demand")
async def demand(
    district: str,
    on: date | None = Query(None, alias="date"),
    user_id: str = Depends(_user_public_id),
):
    """HIGH / NORMAL / LOW demand signal per crop for a district."""
    req = {"district": district, "date": on.isoformat() if on else None}
    res = await _call("GET", "/forecast/demand", req)
    await _save_log(user_id, "demand", req, res)
    return res


class SellRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    crop: str
    qty_quintal: float = Field(gt=0)
    radius_km: float | None = Field(default=None, gt=0)


@router.post("/sell-options")
async def sell_options(body: SellRequest, user_id: str = Depends(_user_public_id)):
    """Best market and day to sell, after transport cost."""
    req = body.model_dump()
    res = await _call("POST", "/forecast/sell-options", body=req)
    await _save_log(user_id, "sell_options", req, res)
    return res


@router.get("/crops")
async def crops(
    district: str,
    sowing_month: int = Query(ge=1, le=12),
    k: int = Query(5, ge=1, le=20),
    user_id: str = Depends(_user_public_id),
):
    """Which crop to sow this month, ranked by expected price at harvest."""
    req = {"district": district, "sowing_month": sowing_month, "k": k}
    res = await _call("GET", "/forecast/crops", req)
    await _save_log(user_id, "crops", req, res)
    return res


@router.get("/health")
async def health():
    """Is the forecaster up, and how fresh is its data?"""
    return await _call("GET", "/health")
