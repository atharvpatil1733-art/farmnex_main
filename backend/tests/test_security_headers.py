"""F8: every response carries the security headers, including /docs. No database needed."""

import httpx
import pytest

import app.main as main_module
from app.core.middleware import SECURITY_HEADERS

pytestmark = pytest.mark.anyio


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
    )


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json", "/api/v2/does-not-exist"])
async def test_security_headers_on_every_response(path):
    async with _client() as client:
        response = await client.get(path)

    for name, value in SECURITY_HEADERS.items():
        assert response.headers.get(name) == value, f"{name} missing on {path}"


async def test_docs_still_loads():
    async with _client() as client:
        response = await client.get("/docs")

    assert response.status_code == 200
    assert "swagger" in response.text.lower()
