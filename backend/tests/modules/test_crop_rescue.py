"""Crop Rescue host (S15): flag on/off, login, roles, ownership.

Flag/config tests need no database. The rest need TEST_DATABASE_URL and skip without it.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
FAKE_URL = "postgresql+psycopg://user:pw@localhost:5432/none"


def _fresh_app(monkeypatch, *, flag: bool = True, url: str | None = FAKE_URL) -> FastAPI:
    from app.modules import wiring

    monkeypatch.setenv("ENABLE_CROP_RESCUE", "true" if flag else "false")
    if url is None:
        monkeypatch.delenv("CR_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("CR_DATABASE_URL", url)
    app = FastAPI()
    wiring.mount_components(app)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _paths(app: FastAPI) -> set[str]:
    return set(app.openapi()["paths"])


# --- flag and config (no database) -----------------------------------------------------


def test_routes_exist_when_flag_on(monkeypatch):
    paths = _paths(_fresh_app(monkeypatch))
    assert "/api/v2/rescue/lots" in paths
    assert "/api/v2/rescue/check" in paths


def test_routes_absent_when_flag_off(monkeypatch):
    assert not any("/rescue" in p for p in _paths(_fresh_app(monkeypatch, flag=False)))


@pytest.mark.parametrize(
    "bad_url",
    [None, "", "postgresql+asyncpg://u:p@localhost/db", "sqlite:///x.db", "postgresql://u:p@localhost/db", "not a url"],
)
def test_bad_database_url_leaves_it_unmounted_but_app_starts(monkeypatch, caplog, bad_url):
    with caplog.at_level(logging.ERROR):
        app = _fresh_app(monkeypatch, url=bad_url)
    assert not any("/rescue" in p for p in _paths(app))
    assert "NOT mounted" in caplog.text


def test_password_never_logged(monkeypatch, caplog):
    with caplog.at_level(logging.ERROR):
        _fresh_app(monkeypatch, url="postgresql+asyncpg://user:SECRETPW@localhost/db")
    assert "SECRETPW" not in caplog.text


@pytest.mark.anyio
async def test_no_token_gives_401(monkeypatch):
    app = _fresh_app(monkeypatch)
    async with _client(app) as http:
        for method, path in [("GET", "/api/v2/rescue/lots"), ("POST", "/api/v2/rescue/check")]:
            response = await http.request(method, path)
            assert response.status_code == 401


# --- with a database ------------------------------------------------------------------


@pytest.fixture(scope="module")
def cr_tables(test_database):
    """Create the cr_ tables by running the real SQL files (safe to run twice)."""
    from sqlalchemy import create_engine

    url = test_database.replace("+asyncpg", "+psycopg", 1)
    engine = create_engine(url)
    with engine.begin() as connection:
        raw = connection.connection
        for name in ("010_cr_crop_rescue.sql", "011_cr_demo_seed.sql"):
            raw.cursor().execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    yield engine
    engine.dispose()


@pytest.fixture
async def rescue(monkeypatch, cr_tables, db):
    """A fresh app with Crop Rescue on, using the test database."""
    from app.modules.crop_rescue import configure, db as cr_db

    configure(engine=cr_tables)
    app = _fresh_app(monkeypatch)
    async with _client(app) as http:
        yield http
    cr_db.configure(engine=None)


def _auth(make_token, user) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user)}"}


def _lot_body() -> dict:
    return {
        "crop_code": "tomato",
        "quantity_kg": 500,
        "harvested_at": datetime.now(timezone.utc).isoformat(),
        "lat": 18.5204,
        "lng": 73.8567,
        "temperature_c": 30,
    }


@pytest.mark.anyio
async def test_farmer_creates_and_reads_own_lot(rescue, make_user, make_token):
    farmer = await make_user("FARMER")
    headers = _auth(make_token, farmer)
    created = await rescue.post("/api/v2/rescue/lots", json=_lot_body(), headers=headers)
    assert created.status_code in (200, 201), created.text
    lot_id = created.json()["id"]
    assert (await rescue.get(f"/api/v2/rescue/lots/{lot_id}", headers=headers)).status_code == 200


@pytest.mark.anyio
async def test_buyer_gets_403(rescue, make_user, make_token):
    buyer = await make_user("BUYER")
    response = await rescue.post("/api/v2/rescue/lots", json=_lot_body(), headers=_auth(make_token, buyer))
    assert response.status_code == 403


@pytest.mark.anyio
async def test_other_farmer_gets_404(rescue, make_user, make_token):
    owner = await make_user("FARMER")
    other = await make_user("FARMER")
    created = await rescue.post("/api/v2/rescue/lots", json=_lot_body(), headers=_auth(make_token, owner))
    lot_id = created.json()["id"]
    other_headers = _auth(make_token, other)

    assert (await rescue.get(f"/api/v2/rescue/lots/{lot_id}", headers=other_headers)).status_code == 404
    assert (await rescue.post(f"/api/v2/rescue/lots/{lot_id}/sold", headers=other_headers)).status_code == 404
    listed = await rescue.get("/api/v2/rescue/lots", headers=other_headers)
    assert listed.json() == []


@pytest.mark.anyio
async def test_farmer_id_in_query_is_ignored(rescue, make_user, make_token):
    owner = await make_user("FARMER")
    other = await make_user("FARMER")
    created = await rescue.post("/api/v2/rescue/lots", json=_lot_body(), headers=_auth(make_token, owner))
    lot_id = created.json()["id"]
    response = await rescue.get(
        f"/api/v2/rescue/lots/{lot_id}",
        params={"farmer_id": str(owner.public_id)},
        headers=_auth(make_token, other),
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_check_is_staff_only(rescue, make_user, make_token):
    farmer = await make_user("FARMER")
    admin = await make_user("ADMIN")
    assert (await rescue.post("/api/v2/rescue/check", headers=_auth(make_token, farmer))).status_code == 403
    assert (await rescue.post("/api/v2/rescue/check", headers=_auth(make_token, admin))).status_code == 200


def test_simulate_is_off_by_default_and_hours_are_capped():
    """From `farmnex_crop_rescue` 617a4f0: simulate defaults to off; `hours` is capped at 720."""
    from app.modules.crop_rescue.config import Settings
    from app.modules.crop_rescue.schemas import SimulateRequest

    assert Settings.model_fields["enable_simulate"].default is False
    assert SimulateRequest(hours=720).hours == 720
    with pytest.raises(ValueError):
        SimulateRequest(hours=721)
