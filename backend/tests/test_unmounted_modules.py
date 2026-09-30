"""F1 fast path: the 9 unused modules are not reachable, the rest still are. No database needed."""

from __future__ import annotations

import pytest

UNMOUNTED_PREFIXES = [
    "/api/v2/ai-predictions",
    "/api/v2/ai-recommendations",
    "/api/v2/deliverys",
    "/api/v2/delivery-tracking-events",
    "/api/v2/delivery-proofs",
    "/api/v2/audit-logs",
    "/api/v2/order-disputes",
    "/api/v2/reviews",
    "/api/v2/farm-crop-activitys",
]

STILL_MOUNTED_PREFIXES = [
    "/api/v2/farm-crops",
    "/api/v2/crop-types",
    "/api/v2/product-listings",
    "/api/v2/orders",
    "/api/v2/payments",
    "/api/v2/bids",
]


@pytest.fixture(scope="module")
def openapi_paths() -> list[str]:
    from app.main import app

    return list(app.openapi()["paths"])


@pytest.mark.parametrize("prefix", UNMOUNTED_PREFIXES)
def test_unmounted_module_is_not_in_docs(openapi_paths: list[str], prefix: str) -> None:
    assert not [path for path in openapi_paths if path.startswith(prefix)]


@pytest.mark.parametrize("prefix", STILL_MOUNTED_PREFIXES)
def test_other_modules_are_still_in_docs(openapi_paths: list[str], prefix: str) -> None:
    assert [path for path in openapi_paths if path.startswith(prefix)]


# --- what a caller actually gets over HTTP (no database needed: no login, so nothing is queried) -----

pytestmark = pytest.mark.anyio


async def _call(method: str, path: str):
    import httpx

    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        return await c.request(method, path, json={} if method == "POST" else None)


@pytest.mark.parametrize("prefix", UNMOUNTED_PREFIXES)
async def test_unmounted_module_answers_404_to_reads(prefix: str) -> None:
    assert (await _call("GET", prefix)).status_code == 404


@pytest.mark.parametrize("prefix", ["/api/v2/reviews", "/api/v2/order-disputes", "/api/v2/delivery-proofs"])
async def test_unmounted_module_answers_404_to_writes(prefix: str) -> None:
    assert (await _call("POST", prefix)).status_code == 404
    assert (await _call("DELETE", f"{prefix}/00000000-0000-0000-0000-000000000000")).status_code == 404


@pytest.mark.parametrize("prefix", STILL_MOUNTED_PREFIXES)
async def test_other_modules_still_need_a_login(prefix: str) -> None:
    assert (await _call("GET", prefix)).status_code == 401
