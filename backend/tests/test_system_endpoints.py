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
