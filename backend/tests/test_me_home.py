"""/me/dashboard and /home hide internal database numbers and scope bids and orders to the user.

Follow-up to S10 (review notes). The first test needs no database; the others need TEST_DATABASE_URL
and are skipped without one.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.services.me_service import MeService

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_dashboard_serializer_drops_internal_ids() -> None:
    row = SimpleNamespace(id=5, public_id="abc", farm_id=3, bidder_id=9, is_active=True, amount=4, title="x")

    assert MeService._serialize(row) == {"public_id": "abc", "is_active": True, "amount": 4, "title": "x"}


def _no_internal_ids(value) -> None:
    """Fail if any key ending in `_id` holds an integer (an internal database number)."""
    if isinstance(value, dict):
        for key, item in value.items():
            assert not (key.endswith("_id") and isinstance(item, int) and not isinstance(item, bool)), key
            _no_internal_ids(item)
    elif isinstance(value, list):
        for item in value:
            _no_internal_ids(item)


@pytest.mark.anyio
async def test_dashboard_and_home_show_public_ids_only(client, make_user, make_token) -> None:
    from test_bid import _auth, _bid, _make_event, _make_listing

    farmer = await make_user("FARMER")
    buyer = await make_user("BUYER")
    listing_id = await _make_listing(client, make_token, farmer)
    event = await _make_event(client, make_token, farmer, listing_id)
    assert (await _bid(client, make_token, buyer, event["public_id"])).status_code == 201

    dashboard = await client.get("/api/v2/me/dashboard", headers=_auth(buyer, make_token))
    assert dashboard.status_code == 200
    assert len(dashboard.json()["bids"]) == 1
    _no_internal_ids(dashboard.json())

    home = await client.get("/api/v2/home")
    assert home.status_code == 200
    sections = home.json()["sections"]
    _no_internal_ids(sections)
    mine = [e for e in sections["pre_bidding"] if e["public_id"] == event["public_id"]]
    assert mine and UUID_RE.match(mine[0]["listing_id"])
    products = [p for p in sections["products"] if p["public_id"] == listing_id]
    assert products and UUID_RE.match(products[0]["farm_id"]) and UUID_RE.match(products[0]["crop_batch_id"])


@pytest.mark.anyio
async def test_dashboard_activities_are_scoped_to_the_current_user() -> None:
    """S33: the dashboard must ask for this user's crop activities only, never the global list."""
    calls: dict = {}

    class Empty:
        async def get_my_profile(self, **_):
            return SimpleNamespace(id=7, public_id="u", role=None)

        async def list_farms(self, **_):
            return [], 0

        async def list(self, **_):
            return [], 0

    class Activities(Empty):
        async def list(self, **_):
            raise AssertionError("global activity list must not be used")

        async def list_mine(self, *, farmer_id, offset, limit):
            calls["farmer_id"] = farmer_id
            return []

    e = Empty()
    service = MeService(user_service=e, farm_service=e, product_listing_service=e, bid_service=e,
                        order_service=e, crop_batch_service=e, activity_service=Activities(),
                        waste_record_service=e, notification_service=e)
    result = await service.get_dashboard(current_user=SimpleNamespace(id=7, public_id="u"))

    assert calls == {"farmer_id": 7}
    assert result["farm_crop_activities"] == []
