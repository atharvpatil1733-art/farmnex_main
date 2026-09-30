"""AI forecaster connector (S16): flag on/off, login, failures, logging, key secrecy.

The forecaster is faked with httpx.MockTransport (no network). Only the log-row test needs
TEST_DATABASE_URL and skips without it.
"""

from __future__ import annotations

import importlib
import logging
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
SECRET_KEY = "SECRET-FORECASTER-KEY-123"
PRICE = {"market": "Pune", "crop": "Onion", "as_of": "2026-09-28", "forecast": [{"expected": 1800}]}


def _fresh_app(monkeypatch, *, flag: bool = True, url: str | None = "https://forecaster.test",
               key: str | None = SECRET_KEY) -> FastAPI:
    from app.modules import wiring

    monkeypatch.setenv("ENABLE_FORECAST", "true" if flag else "false")
    for name, value in (("FORECASTER_URL", url), ("FORECASTER_API_KEY", key)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    app = FastAPI()
    wiring.mount_components(app)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _paths(app: FastAPI) -> set[str]:
    return set(app.openapi()["paths"])


def _fake_forecaster(monkeypatch, handler) -> list[httpx.Request]:
    """Replace the connector's HTTP client with one that answers via `handler`."""
    fc = importlib.import_module("app.modules.forecast.router")  # the package also exports `router`

    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(fc, "_http", httpx.AsyncClient(transport=httpx.MockTransport(record)))
    monkeypatch.setitem(fc._meta_cache, "data", None)
    return seen


def _logged_in(app: FastAPI, public_id: uuid.UUID | None = None) -> uuid.UUID:
    """Skip the database login: pretend this user is logged in."""
    from app.api.dependencies.current_user import get_current_user

    public_id = public_id or uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(public_id=public_id)
    return public_id


@pytest.fixture
def saved_logs(monkeypatch) -> list[tuple]:
    from app.modules.forecast import log_repository

    rows: list[tuple] = []

    async def fake_save(user_public_id, kind, request, response):
        rows.append((user_public_id, kind, request, response))

    monkeypatch.setattr(log_repository, "save_log", fake_save)
    return rows


# --- flag and config ----------------------------------------------------------------


def test_routes_exist_when_flag_on(monkeypatch):
    paths = _paths(_fresh_app(monkeypatch))
    for name in ("meta", "price", "demand", "sell-options", "crops", "health"):
        assert f"/api/v2/forecast/{name}" in paths


def test_routes_absent_when_flag_off(monkeypatch):
    assert not any("/forecast" in p for p in _paths(_fresh_app(monkeypatch, flag=False)))


@pytest.mark.parametrize("url,key", [(None, SECRET_KEY), ("https://forecaster.test", None), ("", "")])
def test_missing_config_leaves_it_unmounted_but_app_starts(monkeypatch, caplog, url, key):
    with caplog.at_level(logging.ERROR):
        app = _fresh_app(monkeypatch, url=url, key=key)
    assert not any("/forecast" in p for p in _paths(app))
    assert "NOT mounted" in caplog.text


# --- login ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_token_gives_401_on_every_route(monkeypatch):
    seen = _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json={}))
    app = _fresh_app(monkeypatch)
    async with _client(app) as http:
        calls = [
            ("GET", "/api/v2/forecast/meta", None),
            ("GET", "/api/v2/forecast/health", None),
            ("GET", "/api/v2/forecast/price?market=Pune&crop=Onion", None),
            ("GET", "/api/v2/forecast/demand?district=Pune", None),
            ("GET", "/api/v2/forecast/crops?district=Pune&sowing_month=6", None),
            ("POST", "/api/v2/forecast/sell-options", {"lat": 18.5, "lon": 73.8, "crop": "Onion", "qty_quintal": 5}),
        ]
        for method, path, body in calls:
            response = await http.request(method, path, json=body)
            assert response.status_code == 401, path
    assert seen == []  # the forecaster was never contacted


# --- forwarding, failures, secrecy ----------------------------------------------------


@pytest.mark.anyio
async def test_price_is_forwarded_with_key_and_logged_for_the_caller(monkeypatch, saved_logs):
    seen = _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json=PRICE))
    app = _fresh_app(monkeypatch)
    caller = _logged_in(app)

    async with _client(app) as http:
        response = await http.get("/api/v2/forecast/price", params={"market": "Pune", "crop": "Onion"})

    assert response.status_code == 200
    assert response.json() == PRICE
    assert seen[0].headers["x-api-key"] == SECRET_KEY
    assert seen[0].url.path == "/forecast/price"
    assert saved_logs == [(str(caller), "price", {"market": "Pune", "crop": "Onion", "days": 3}, PRICE)]
    assert SECRET_KEY not in response.text


@pytest.mark.anyio
async def test_user_id_in_the_query_is_ignored(monkeypatch, saved_logs):
    _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json=PRICE))
    app = _fresh_app(monkeypatch)
    caller = _logged_in(app)
    other = uuid.uuid4()

    async with _client(app) as http:
        await http.get("/api/v2/forecast/price", params={"market": "Pune", "crop": "Onion", "user_id": str(other)})

    assert saved_logs[0][0] == str(caller)


@pytest.mark.anyio
async def test_forecaster_down_gives_friendly_503(monkeypatch, saved_logs, caplog):
    def down(request):
        raise httpx.ConnectError("connection refused", request=request)

    _fake_forecaster(monkeypatch, down)
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    with caplog.at_level(logging.DEBUG):
        async with _client(app) as http:
            response = await http.get("/api/v2/forecast/price", params={"market": "Pune", "crop": "Onion"})

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    assert saved_logs == []
    assert SECRET_KEY not in response.text
    assert SECRET_KEY not in caplog.text


@pytest.mark.anyio
async def test_forecaster_refusing_our_key_gives_503_without_leaking_it(monkeypatch, caplog):
    _fake_forecaster(monkeypatch, lambda r: httpx.Response(401, json={"detail": "bad key"}))
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    with caplog.at_level(logging.DEBUG):
        async with _client(app) as http:
            response = await http.get("/api/v2/forecast/health")

    assert response.status_code == 503
    assert SECRET_KEY not in response.text
    assert SECRET_KEY not in caplog.text


@pytest.mark.anyio
async def test_forecaster_errors_pass_through(monkeypatch, saved_logs):
    _fake_forecaster(monkeypatch, lambda r: httpx.Response(422, json={"detail": "unknown market"}))
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    async with _client(app) as http:
        response = await http.get("/api/v2/forecast/price", params={"market": "Nowhere", "crop": "Onion"})

    assert response.status_code == 422
    assert response.json()["detail"] == "unknown market"
    assert saved_logs == []


@pytest.mark.anyio
async def test_a_failing_log_write_does_not_break_the_answer(monkeypatch):
    from app.modules.forecast import log_repository

    async def broken(*args, **kwargs):
        raise RuntimeError("relation fc_forecast_logs does not exist")

    monkeypatch.setattr(log_repository, "save_log", broken)
    _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json=PRICE))
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    async with _client(app) as http:
        response = await http.get("/api/v2/forecast/price", params={"market": "Pune", "crop": "Onion"})

    assert response.status_code == 200
    assert response.json() == PRICE


@pytest.mark.anyio
@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(500, text="Traceback (most recent call last): File /srv/app/secret.py"),
        httpx.Response(403, json={"detail": "internal host detail"}),
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["not", "a", "dict"]),
    ],
)
async def test_odd_upstream_answers_give_a_generic_503(monkeypatch, saved_logs, answer):
    _fake_forecaster(monkeypatch, lambda r: answer)
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    async with _client(app) as http:
        response = await http.get("/api/v2/forecast/price", params={"market": "Pune", "crop": "Onion"})

    assert response.status_code == 503
    assert "Traceback" not in response.text and "internal host" not in response.text
    assert saved_logs == []


@pytest.mark.anyio
async def test_overlong_names_are_rejected_before_calling_the_forecaster(monkeypatch):
    seen = _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json={}))
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    async with _client(app) as http:
        response = await http.get("/api/v2/forecast/price", params={"market": "x" * 101, "crop": "Onion"})

    assert response.status_code == 422
    assert seen == []


@pytest.mark.anyio
async def test_meta_is_cached(monkeypatch):
    seen = _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json={"markets": ["Pune"]}))
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    async with _client(app) as http:
        first = await http.get("/api/v2/forecast/meta")
        second = await http.get("/api/v2/forecast/meta")

    assert first.json() == second.json() == {"markets": ["Pune"]}
    assert len(seen) == 1


@pytest.mark.anyio
async def test_sell_options_validates_the_body(monkeypatch):
    seen = _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json={}))
    app = _fresh_app(monkeypatch)
    _logged_in(app)

    async with _client(app) as http:
        response = await http.post(
            "/api/v2/forecast/sell-options", json={"lat": 200, "lon": 73.8, "crop": "Onion", "qty_quintal": 5}
        )

    assert response.status_code == 422
    assert seen == []


# --- with a database ------------------------------------------------------------------


@pytest.fixture(scope="module")
def fc_table(test_database):
    """Create fc_forecast_logs by running the real SQL file (safe to run twice)."""
    from sqlalchemy import create_engine

    engine = create_engine(test_database.replace("+asyncpg", "+psycopg", 1))
    with engine.begin() as connection:
        connection.connection.cursor().execute((MIGRATIONS / "020_fc_forecast_logs.sql").read_text(encoding="utf-8"))
    yield
    engine.dispose()


@pytest.mark.anyio
async def test_a_log_row_is_written_with_the_callers_public_id(monkeypatch, fc_table, db, make_user, make_token):
    from sqlalchemy import text

    from app.core.database import AsyncSessionLocal

    _fake_forecaster(monkeypatch, lambda r: httpx.Response(200, json=PRICE))
    app = _fresh_app(monkeypatch)
    farmer = await make_user("FARMER")

    async with _client(app) as http:
        response = await http.get(
            "/api/v2/forecast/price",
            params={"market": "Pune", "crop": "Onion"},
            headers={"Authorization": f"Bearer {make_token(farmer)}"},
        )
    assert response.status_code == 200

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text("SELECT kind, data_as_of, response FROM public.fc_forecast_logs WHERE user_public_id = :u"),
                {"u": farmer.public_id},
            )
        ).all()
        await session.execute(
            text("DELETE FROM public.fc_forecast_logs WHERE user_public_id = :u"), {"u": farmer.public_id}
        )
        await session.commit()

    assert len(rows) == 1
    kind, data_as_of, logged = rows[0]
    assert kind == "price"
    assert str(data_as_of) == "2026-09-28"
    assert logged == PRICE
