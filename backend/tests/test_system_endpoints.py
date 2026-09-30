"""F6 (/db leaks nothing) and F7 (CORS). These need no database."""

import httpx
import pytest

import app.main as main_module

pytestmark = pytest.mark.anyio


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
    )


async def test_db_error_does_not_leak_details(monkeypatch):
    async def broken():
        raise RuntimeError("could not connect to db.secret-host.example as user admin")

    monkeypatch.setattr(main_module, "check_database_connection", broken)

    async with _client() as client:
        response = await client.get("/db")

    assert response.json() == {"status": "error", "database": "disconnected"}
    assert "secret-host" not in response.text


async def test_cors_blocks_unknown_origin():
    async with _client() as client:
        response = await client.get("/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_allows_local_dev_origin():
    async with _client() as client:
        response = await client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers


def test_wildcard_origin_is_ignored(monkeypatch):
    monkeypatch.setattr(main_module.settings, "cors_origins", "*")
    assert "*" not in main_module.get_cors_origins()

    monkeypatch.setattr(main_module.settings, "cors_origins", "https://a.example, *")
    assert main_module.get_cors_origins() == ["https://a.example"]


def test_wildcard_warning_only_when_set_on_purpose(monkeypatch, caplog):
    monkeypatch.setattr(main_module.settings, "cors_origins", "*")

    monkeypatch.setattr(type(main_module.settings), "model_fields_set", property(lambda self: set()))
    with caplog.at_level("WARNING"):
        main_module.get_cors_origins()
    assert "CORS_ORIGINS" not in caplog.text

    monkeypatch.setattr(
        type(main_module.settings), "model_fields_set", property(lambda self: {"cors_origins"})
    )
    with caplog.at_level("WARNING"):
        main_module.get_cors_origins()
    assert "CORS_ORIGINS" in caplog.text
