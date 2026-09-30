"""F1 + F2 for bid_event and bid (S10).

A farmer opens a bid event (pre-bidding) on their own listing; buyers bid on it. Other users get 404
on rows that aren't theirs (or don't see them), wrong roles get 403, and fields the server owns
(creator, bidder, status, winner, placed_at) are ignored when the client sends them.
These tests need a database (TEST_DATABASE_URL); without one they are skipped.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.anyio

EVENTS = "/api/v2/bid-events"
BIDS = "/api/v2/bids"


def _auth(user, make_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user)}"}


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


async def _make_listing(client, make_token, user) -> str:
    """A farm, farm crop, crop batch and ACTIVE listing owned by `user`. Returns the listing public id."""
    from app.core.database import AsyncSessionLocal
    from app.models.crop_type import CropType
    from app.models.farm import Farm
    from app.models.farm_crop import FarmCrop

    async with AsyncSessionLocal() as session:
        farm = Farm(user_id=user.id, farm_name="Test farm", address_line_1="Road 1", state="Maharashtra", postal_code="411001")
        crop_type = CropType(name=f"Tomato-{uuid.uuid4().hex[:8]}", default_unit="kg")
        session.add_all([farm, crop_type])
        await session.flush()
        farm_crop = FarmCrop(farmer_id=user.id, farm_id=farm.id, crop_type_id=crop_type.id)
        session.add(farm_crop)
        await session.commit()
        farm_id, farm_crop_id = str(farm.public_id), str(farm_crop.public_id)

    headers = _auth(user, make_token)
    batch = await client.post(
        "/api/v2/crop-batches", json={"farm_crop_id": farm_crop_id, "quantity": "100", "unit": "kg"}, headers=headers
    )
    assert batch.status_code == 201, batch.text
    listing = await client.post(
        "/api/v2/product-listings",
        json={
            "farm_id": farm_id,
            "crop_batch_id": batch.json()["public_id"],
            "title": "Tomatoes, pre-harvest",
            "listing_type": "PRE_BID",
            "price": "20",
            "quantity": "100",
            "unit": "kg",
        },
        headers=headers,
    )
    assert listing.status_code == 201, listing.text
    return listing.json()["public_id"]


async def _make_event(client, make_token, user, listing_id: str, **extra) -> dict:
    body = {
        "listing_id": listing_id,
        "starts_at": _iso(timedelta(hours=-1)),
        "ends_at": _iso(timedelta(days=7)),
        "starting_price": "18.00",
        "minimum_increment": "0.50",
        **extra,
    }
    response = await client.post(EVENTS, json=body, headers=_auth(user, make_token))
    assert response.status_code == 201, response.text
    return response.json()


async def _bid(client, make_token, user, event_id: str, amount: str = "19.00", **extra):
    return await client.post(
        BIDS, json={"bid_event_id": event_id, "amount": amount, **extra}, headers=_auth(user, make_token)
    )


async def _set_event_status(public_id: str, status: str) -> None:
    from sqlalchemy import update

    from app.core.database import AsyncSessionLocal
    from app.models.bid_event import BidEvent

    async with AsyncSessionLocal() as session:
        await session.execute(update(BidEvent).where(BidEvent.public_id == uuid.UUID(public_id)).values(status=status))
        await session.commit()


@pytest.fixture
async def farmer_event(client, make_user, make_token):
    """A farmer with one open bid event on their own listing."""
    farmer = await make_user("FARMER")
    listing_id = await _make_listing(client, make_token, farmer)
    event = await _make_event(client, make_token, farmer, listing_id)
    return farmer, listing_id, event


# ---------------------------------------------------------------------------
# Bid events
# ---------------------------------------------------------------------------


async def test_event_create_uses_server_fields_and_public_ids(client, make_user, make_token) -> None:
    farmer = await make_user("FARMER")
    other = await make_user("FARMER")
    listing_id = await _make_listing(client, make_token, farmer)

    event = await _make_event(
        client, make_token, farmer, listing_id,
        created_by_id=other.id, status="CLOSED", winner_bid_id=1,  # server-owned: ignored
    )

    assert event["status"] == "ACTIVE"
    assert event["listing_id"] == listing_id
    assert "id" not in event and "winner_bid_id" not in event and "created_by_id" not in event
    assert [e["public_id"] for e in (await client.get(f"{EVENTS}?mine=true", headers=_auth(farmer, make_token))).json()] == [event["public_id"]]
    assert (await client.get(f"{EVENTS}?mine=true", headers=_auth(other, make_token))).json() == []


async def test_event_needs_own_listing_and_seller_role(client, make_user, make_token) -> None:
    farmer = await make_user("FARMER")
    listing_id = await _make_listing(client, make_token, farmer)
    intruder = await make_user("FARMER")
    buyer = await make_user("BUYER")
    body = {
        "listing_id": listing_id,
        "starts_at": _iso(timedelta(0)),
        "ends_at": _iso(timedelta(days=1)),
        "starting_price": "10",
        "minimum_increment": "1",
    }

    assert (await client.post(EVENTS, json=body, headers=_auth(intruder, make_token))).status_code == 404
    assert (await client.post(EVENTS, json=body, headers=_auth(buyer, make_token))).status_code == 403
    assert (await client.post(EVENTS, json={**body, "listing_id": 1}, headers=_auth(farmer, make_token))).status_code == 422
    bad_window = {**body, "ends_at": body["starts_at"]}
    assert (await client.post(EVENTS, json=bad_window, headers=_auth(farmer, make_token))).status_code == 422


async def test_open_event_is_public_but_only_creator_changes_it(client, make_user, make_token, farmer_event) -> None:
    _, _, event = farmer_event
    other = await make_user("FARMER")
    headers = _auth(other, make_token)
    url = f"{EVENTS}/{event['public_id']}"

    assert (await client.get(url, headers=headers)).status_code == 200
    assert [e["public_id"] for e in (await client.get(EVENTS, headers=headers)).json()] == [event["public_id"]]
    assert (await client.patch(url, json={"starting_price": "1"}, headers=headers)).status_code == 404
    assert (await client.delete(url, headers=headers)).status_code == 404


async def test_closed_event_is_private_to_its_creator(client, make_user, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event
    await _set_event_status(event["public_id"], "CLOSED")
    other = await make_user("BUYER")
    url = f"{EVENTS}/{event['public_id']}"

    assert (await client.get(url, headers=_auth(other, make_token))).status_code == 404
    assert (await client.get(EVENTS, headers=_auth(other, make_token))).json() == []
    assert (await client.get(url, headers=_auth(farmer, make_token))).status_code == 200
    # a closed event can't be edited, even by its creator
    assert (await client.patch(url, json={"starting_price": "30"}, headers=_auth(farmer, make_token))).status_code == 409


async def test_event_update_only_changes_allowed_fields(client, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event

    response = await client.patch(
        f"{EVENTS}/{event['public_id']}",
        json={"starting_price": "25.00", "status": "CLOSED", "winner_bid_id": 1, "listing_id": str(uuid.uuid4())},
        headers=_auth(farmer, make_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert float(body["starting_price"]) == 25
    assert body["status"] == "ACTIVE"
    assert body["listing_id"] == event["listing_id"]


async def test_event_without_bids_can_be_deleted(client, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event
    url = f"{EVENTS}/{event['public_id']}"

    assert (await client.delete(url, headers=_auth(farmer, make_token))).status_code == 204
    assert (await client.get(url, headers=_auth(farmer, make_token))).status_code == 404


async def test_event_with_bids_cannot_be_changed_or_deleted(client, make_user, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event
    buyer = await make_user("BUYER")
    assert (await _bid(client, make_token, buyer, event["public_id"])).status_code == 201
    url = f"{EVENTS}/{event['public_id']}"
    headers = _auth(farmer, make_token)

    assert (await client.patch(url, json={"starting_price": "50"}, headers=headers)).status_code == 409
    assert (await client.delete(url, headers=headers)).status_code == 409


# ---------------------------------------------------------------------------
# Bids
# ---------------------------------------------------------------------------


async def test_bid_create_uses_server_fields_and_public_ids(client, make_user, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event
    buyer = await make_user("BUYER")

    response = await _bid(
        client, make_token, buyer, event["public_id"], "19.50",
        bidder_id=farmer.id, status="WON", placed_at="2020-01-01T00:00:00Z",  # server-owned: ignored
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["bidder_id"] == str(buyer.public_id)
    assert body["bid_event_id"] == event["public_id"]
    assert body["status"] == "ACTIVE"
    assert not body["placed_at"].startswith("2020")
    assert "id" not in body


async def test_only_buyers_can_bid(client, make_user, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event
    other_farmer = await make_user("FARMER")

    assert (await _bid(client, make_token, farmer, event["public_id"])).status_code == 403
    assert (await _bid(client, make_token, other_farmer, event["public_id"])).status_code == 403
    assert (await client.post(BIDS, json={"bid_event_id": event["public_id"], "amount": "19"})).status_code == 401


async def test_bid_rules_price_window_and_status(client, make_user, make_token) -> None:
    farmer = await make_user("FARMER")
    buyer = await make_user("BUYER")
    listing_id = await _make_listing(client, make_token, farmer)
    open_event = await _make_event(client, make_token, farmer, listing_id)
    future_event = await _make_event(client, make_token, farmer, listing_id, starts_at=_iso(timedelta(days=1)))
    closed_event = await _make_event(client, make_token, farmer, listing_id)
    await _set_event_status(closed_event["public_id"], "CLOSED")

    assert (await _bid(client, make_token, buyer, open_event["public_id"], "5.00")).status_code == 422  # below start
    assert (await _bid(client, make_token, buyer, future_event["public_id"])).status_code == 409  # not started
    assert (await _bid(client, make_token, buyer, closed_event["public_id"])).status_code == 404  # hidden
    assert (await _bid(client, make_token, buyer, str(uuid.uuid4()))).status_code == 404


async def test_bid_on_closed_listing_is_rejected(client, make_user, make_token, farmer_event) -> None:
    farmer, listing_id, event = farmer_event
    buyer = await make_user("BUYER")
    await client.delete(f"/api/v2/product-listings/{listing_id}", headers=_auth(farmer, make_token))

    assert (await _bid(client, make_token, buyer, event["public_id"])).status_code == 409
    # and the event is no longer shown to others (the creator still sees it)
    assert (await client.get(EVENTS, headers=_auth(buyer, make_token))).json() == []
    assert (await client.get(f"{EVENTS}/{event['public_id']}", headers=_auth(farmer, make_token))).status_code == 200


async def test_event_times_need_a_timezone(client, make_token, farmer_event) -> None:
    farmer, listing_id, event = farmer_event
    headers = _auth(farmer, make_token)
    no_zone = {
        "listing_id": listing_id,
        "starts_at": "2026-10-01T00:00:00Z",
        "ends_at": "2026-10-08T00:00:00",  # no timezone
        "starting_price": "10",
        "minimum_increment": "1",
    }

    assert (await client.post(EVENTS, json=no_zone, headers=headers)).status_code == 422
    patch = await client.patch(f"{EVENTS}/{event['public_id']}", json={"starts_at": "2026-10-01T00:00:00"}, headers=headers)
    assert patch.status_code == 422


async def test_bid_is_seen_only_by_bidder_and_event_creator(client, make_user, make_token, farmer_event) -> None:
    farmer, _, event = farmer_event
    buyer = await make_user("BUYER")
    rival = await make_user("BUYER")
    other_farmer = await make_user("FARMER")
    bid = (await _bid(client, make_token, buyer, event["public_id"])).json()
    rival_bid = (await _bid(client, make_token, rival, event["public_id"], "20.00")).json()
    url = f"{BIDS}/{bid['public_id']}"

    # the bidder
    assert (await client.get(url, headers=_auth(buyer, make_token))).status_code == 200
    assert [b["public_id"] for b in (await client.get(BIDS, headers=_auth(buyer, make_token))).json()] == [bid["public_id"]]
    # the event creator sees every bid on their event
    creator_list = await client.get(f"{BIDS}?bid_event_id={event['public_id']}", headers=_auth(farmer, make_token))
    assert {b["public_id"] for b in creator_list.json()} == {bid["public_id"], rival_bid["public_id"]}
    assert (await client.get(url, headers=_auth(farmer, make_token))).status_code == 200
    # everyone else
    for intruder in (rival, other_farmer):
        assert (await client.get(url, headers=_auth(intruder, make_token))).status_code == 404
    assert (await client.get(BIDS, headers=_auth(other_farmer, make_token))).json() == []
    assert (await client.get(f"{BIDS}?bid_event_id={event['public_id']}", headers=_auth(other_farmer, make_token))).json() == []


async def test_bids_cannot_be_edited_or_deleted(client, make_user, make_token, farmer_event) -> None:
    _, _, event = farmer_event
    buyer = await make_user("BUYER")
    bid = (await _bid(client, make_token, buyer, event["public_id"])).json()
    url = f"{BIDS}/{bid['public_id']}"
    headers = _auth(buyer, make_token)

    assert (await client.patch(url, json={"amount": "1"}, headers=headers)).status_code == 405
    assert (await client.delete(url, headers=headers)).status_code == 405


async def test_dashboard_still_shows_only_my_bids(client, make_user, make_token, farmer_event) -> None:
    _, _, event = farmer_event
    buyer = await make_user("BUYER")
    rival = await make_user("BUYER")
    await _bid(client, make_token, buyer, event["public_id"])
    await _bid(client, make_token, rival, event["public_id"], "20.00")

    response = await client.get("/api/v2/me/dashboard", headers=_auth(buyer, make_token))

    assert response.status_code == 200
    assert len(response.json()["bids"]) == 1
