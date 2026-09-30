"""F1 + F2 for crop_batch, product_listing and product_image (S12).

User A creates a row; user B must get 404 on it (or not see it); wrong role gets 403; fields the
server owns (seller, status, available quantity) are ignored when the client sends them.
These tests need a database (TEST_DATABASE_URL); without one they are skipped.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.anyio

BATCHES = "/api/v2/crop-batches"
LISTINGS = "/api/v2/product-listings"
IMAGES = "/api/v2/product-images"


def _auth(user, make_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user)}"}


async def _seed_farm_crop(user) -> dict:
    """Insert a farm, a crop type and a farm crop that belong to `user`. Returns their ids."""
    from app.core.database import AsyncSessionLocal
    from app.models.crop_type import CropType
    from app.models.farm import Farm
    from app.models.farm_crop import FarmCrop

    async with AsyncSessionLocal() as session:
        farm = Farm(
            user_id=user.id,
            farm_name="Test farm",
            address_line_1="Road 1",
            state="Maharashtra",
            postal_code="411001",
        )
        crop_type = CropType(name=f"Tomato-{uuid.uuid4().hex[:8]}", default_unit="kg")
        session.add_all([farm, crop_type])
        await session.flush()
        farm_crop = FarmCrop(farmer_id=user.id, farm_id=farm.id, crop_type_id=crop_type.id)
        session.add(farm_crop)
        await session.commit()
        return {
            "farm_id": str(farm.public_id),
            "farm_crop_id": str(farm_crop.public_id),
        }


async def _make_batch(client, make_token, user, farm_crop_id: str, **extra) -> dict:
    body = {"farm_crop_id": farm_crop_id, "quantity": "100", "unit": "kg", **extra}
    response = await client.post(BATCHES, json=body, headers=_auth(user, make_token))
    assert response.status_code == 201, response.text
    return response.json()


async def _make_listing(client, make_token, user, farm_id: str, batch_id: str, **extra) -> dict:
    body = {
        "farm_id": farm_id,
        "crop_batch_id": batch_id,
        "title": "Fresh tomatoes",
        "listing_type": "FIXED_PRICE",
        "price": "25.50",
        "quantity": "100",
        "unit": "kg",
        **extra,
    }
    response = await client.post(LISTINGS, json=body, headers=_auth(user, make_token))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def seller(make_user, client):
    """A farmer with a farm, a farm crop and one crop batch."""
    user = await make_user("FARMER")
    ids = await _seed_farm_crop(user)
    return user, ids


# ---------------------------------------------------------------------------
# Crop batches
# ---------------------------------------------------------------------------


async def test_batch_create_uses_server_fields_and_public_ids(client, make_token, seller) -> None:
    farmer, ids = seller
    other = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])  # no batch code sent

    response = await client.post(
        BATCHES,
        json={
            "farm_crop_id": ids["farm_crop_id"],
            "quantity": "50",
            "unit": "kg",
            "status": "SOLD",  # server-owned: ignored
            "available_quantity": "1",  # server-owned: ignored
        },
        headers=_auth(farmer, make_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert float(body["available_quantity"]) == 50
    assert body["farm_crop_id"] == ids["farm_crop_id"]
    assert body["batch_code"] and body["batch_code"] != other["batch_code"]  # server made a unique code
    assert "id" not in body


async def test_batch_is_private_to_its_owner(client, make_user, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    intruder = await make_user("FARMER")
    headers = _auth(intruder, make_token)
    url = f"{BATCHES}/{batch['public_id']}"

    assert (await client.get(url, headers=headers)).status_code == 404
    assert (await client.patch(url, json={"notes": "hacked"}, headers=headers)).status_code == 404
    assert (await client.delete(url, headers=headers)).status_code == 404
    assert (await client.get(BATCHES, headers=headers)).json() == []
    # the owner still has it, unchanged
    mine = await client.get(url, headers=_auth(farmer, make_token))
    assert mine.status_code == 200 and mine.json()["notes"] is None


async def test_batch_cannot_be_created_on_someone_elses_farm_crop(client, make_user, make_token, seller) -> None:
    _, ids = seller
    intruder = await make_user("FARMER")

    response = await client.post(
        BATCHES,
        json={"farm_crop_id": ids["farm_crop_id"], "quantity": "5", "unit": "kg"},
        headers=_auth(intruder, make_token),
    )

    assert response.status_code == 404


async def test_batch_update_only_changes_descriptive_fields(client, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])

    response = await client.patch(
        f"{BATCHES}/{batch['public_id']}",
        json={"notes": "dry", "status": "SOLD", "quantity": "1", "available_quantity": "0"},
        headers=_auth(farmer, make_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "dry"
    assert body["status"] == "ACTIVE"
    assert float(body["quantity"]) == 100 and float(body["available_quantity"]) == 100


async def test_batch_requires_login_and_old_route_is_gone(client) -> None:
    assert (await client.get(BATCHES)).status_code == 401
    assert (await client.get("/api/v2/crop-batchs")).status_code == 404


async def test_batch_used_by_a_listing_cannot_be_deleted(client, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    await _make_listing(client, make_token, farmer, ids["farm_id"], batch["public_id"])

    response = await client.delete(f"{BATCHES}/{batch['public_id']}", headers=_auth(farmer, make_token))

    assert response.status_code == 409


async def test_batch_with_only_a_closed_listing_also_cannot_be_deleted(client, make_token, seller) -> None:
    farmer, ids = seller
    headers = _auth(farmer, make_token)
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    made = await _make_listing(client, make_token, farmer, ids["farm_id"], batch["public_id"])
    await client.delete(f"{LISTINGS}/{made['public_id']}", headers=headers)

    assert (await client.delete(f"{BATCHES}/{batch['public_id']}", headers=headers)).status_code == 409


async def test_duplicate_batch_code_is_a_conflict(client, make_token, seller) -> None:
    farmer, ids = seller
    headers = _auth(farmer, make_token)
    await _make_batch(client, make_token, farmer, ids["farm_crop_id"], batch_code="TOMATO-001")

    again = await client.post(
        BATCHES, json={"farm_crop_id": ids["farm_crop_id"], "quantity": "1", "unit": "kg", "batch_code": "TOMATO-001"}, headers=headers
    )

    assert again.status_code == 409


async def test_dashboard_shows_only_my_batches(client, make_user, make_token, seller) -> None:
    farmer, ids = seller
    await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    other = await make_user("FARMER")

    mine = await client.get("/api/v2/me/dashboard", headers=_auth(farmer, make_token))
    theirs = await client.get("/api/v2/me/dashboard", headers=_auth(other, make_token))

    assert mine.status_code == 200 and theirs.status_code == 200
    assert len(mine.json()["crop_batches"]) == 1
    assert theirs.json()["crop_batches"] == []


# ---------------------------------------------------------------------------
# Product listings
# ---------------------------------------------------------------------------


@pytest.fixture
async def listing(client, make_token, seller):
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    created = await _make_listing(client, make_token, farmer, ids["farm_id"], batch["public_id"])
    return farmer, ids, batch, created


async def test_listing_create_takes_seller_and_status_from_the_server(client, make_user, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    victim = await make_user("FARMER")

    created = await _make_listing(
        client,
        make_token,
        farmer,
        ids["farm_id"],
        batch["public_id"],
        seller_id=str(victim.public_id),  # server-owned: ignored
        status="CLOSED",  # server-owned: ignored
        available_quantity="1",  # server-owned: ignored
    )

    assert created["seller_id"] == str(farmer.public_id)
    assert created["status"] == "ACTIVE"
    assert float(created["available_quantity"]) == 100
    assert created["farm_id"] == ids["farm_id"] and created["crop_batch_id"] == batch["public_id"]


async def test_listing_create_needs_farmer_or_vendor_role(client, make_user, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    buyer = await make_user("BUYER")

    response = await client.post(
        LISTINGS,
        json={
            "farm_id": ids["farm_id"],
            "crop_batch_id": batch["public_id"],
            "title": "x",
            "listing_type": "FIXED_PRICE",
            "price": "1",
            "quantity": "1",
            "unit": "kg",
        },
        headers=_auth(buyer, make_token),
    )

    assert response.status_code == 403


async def test_listing_needs_my_own_farm_and_my_own_batch(client, make_user, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    intruder = await make_user("FARMER")
    intruder_ids = await _seed_farm_crop(intruder)
    intruder_batch = await _make_batch(client, make_token, intruder, intruder_ids["farm_crop_id"])
    body = {"title": "x", "listing_type": "FIXED_PRICE", "price": "1", "quantity": "1", "unit": "kg"}
    headers = _auth(intruder, make_token)

    someone_elses_farm = await client.post(
        LISTINGS, json={**body, "farm_id": ids["farm_id"], "crop_batch_id": intruder_batch["public_id"]}, headers=headers
    )
    someone_elses_batch = await client.post(
        LISTINGS, json={**body, "farm_id": intruder_ids["farm_id"], "crop_batch_id": batch["public_id"]}, headers=headers
    )
    batch_from_another_farm = await client.post(
        LISTINGS, json={**body, "farm_id": (await _seed_farm_crop(intruder))["farm_id"], "crop_batch_id": intruder_batch["public_id"]},
        headers=headers,
    )

    assert someone_elses_farm.status_code == 404
    assert someone_elses_batch.status_code == 404
    assert batch_from_another_farm.status_code == 422  # my batch, but not from that farm


async def test_active_listing_is_visible_to_others_but_only_the_seller_can_change_it(
    client, make_user, make_token, listing
) -> None:
    farmer, _, _, created = listing
    buyer = await make_user("BUYER")
    rival = await make_user("FARMER")
    url = f"{LISTINGS}/{created['public_id']}"

    for viewer in (buyer, rival):
        headers = _auth(viewer, make_token)
        assert (await client.get(url, headers=headers)).status_code == 200
        assert [x["public_id"] for x in (await client.get(LISTINGS, headers=headers)).json()] == [created["public_id"]]
        assert (await client.patch(url, json={"title": "hacked"}, headers=headers)).status_code == 404
        assert (await client.delete(url, headers=headers)).status_code == 404

    still = await client.get(url, headers=_auth(farmer, make_token))
    assert still.json()["title"] == "Fresh tomatoes" and still.json()["status"] == "ACTIVE"


async def test_seller_update_ignores_server_fields(client, make_token, listing) -> None:
    farmer, _, _, created = listing

    response = await client.patch(
        f"{LISTINGS}/{created['public_id']}",
        json={"title": "Better tomatoes", "price": "30", "status": "CLOSED", "available_quantity": "0"},
        headers=_auth(farmer, make_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Better tomatoes" and float(body["price"]) == 30
    assert body["status"] == "ACTIVE" and float(body["available_quantity"]) == 100


async def test_delete_closes_the_listing_and_hides_it_from_others(client, make_user, make_token, listing) -> None:
    farmer, _, _, created = listing
    buyer = await make_user("BUYER")
    url = f"{LISTINGS}/{created['public_id']}"

    assert (await client.delete(url, headers=_auth(farmer, make_token))).status_code == 204

    own = await client.get(url, headers=_auth(farmer, make_token))
    assert own.status_code == 200 and own.json()["status"] == "CLOSED"
    assert [x["public_id"] for x in (await client.get(f"{LISTINGS}?mine=true", headers=_auth(farmer, make_token))).json()] == [
        created["public_id"]
    ]
    assert (await client.get(url, headers=_auth(buyer, make_token))).status_code == 404
    assert (await client.get(LISTINGS, headers=_auth(buyer, make_token))).json() == []


async def test_listing_cannot_offer_more_than_the_batch_has(client, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"], quantity="10")
    body = {
        "farm_id": ids["farm_id"],
        "crop_batch_id": batch["public_id"],
        "title": "x",
        "listing_type": "FIXED_PRICE",
        "price": "1",
        "quantity": "1000000",
        "unit": "kg",
    }

    response = await client.post(LISTINGS, json=body, headers=_auth(farmer, make_token))

    assert response.status_code == 422


async def test_closed_listing_cannot_be_changed(client, make_token, listing) -> None:
    farmer, _, _, created = listing
    headers = _auth(farmer, make_token)
    url = f"{LISTINGS}/{created['public_id']}"
    await client.delete(url, headers=headers)

    assert (await client.patch(url, json={"price": "1"}, headers=headers)).status_code == 409


async def test_mine_filter_and_login_required(client, make_user, make_token, listing) -> None:
    rival = await make_user("FARMER")

    assert (await client.get(f"{LISTINGS}?mine=true", headers=_auth(rival, make_token))).json() == []
    assert (await client.get(LISTINGS)).status_code == 401


async def test_listing_rejects_bad_numbers_and_dates(client, make_token, seller) -> None:
    farmer, ids = seller
    batch = await _make_batch(client, make_token, farmer, ids["farm_crop_id"])
    base = {
        "farm_id": ids["farm_id"],
        "crop_batch_id": batch["public_id"],
        "title": "x",
        "listing_type": "FIXED_PRICE",
        "price": "1",
        "quantity": "1",
        "unit": "kg",
    }
    headers = _auth(farmer, make_token)

    assert (await client.post(LISTINGS, json={**base, "price": "-5"}, headers=headers)).status_code == 422
    assert (await client.post(LISTINGS, json={**base, "farm_id": 7}, headers=headers)).status_code == 422
    backwards = {"starts_at": "2030-02-01T00:00:00Z", "ends_at": "2030-01-01T00:00:00Z"}
    assert (await client.post(LISTINGS, json={**base, **backwards}, headers=headers)).status_code == 422


# ---------------------------------------------------------------------------
# Product images
# ---------------------------------------------------------------------------


def _image(listing_id: str, **extra) -> dict:
    return {
        "listing_id": listing_id,
        "storage_path": f"product-images/{uuid.uuid4()}.webp",
        "content_type": "image/webp",
        **extra,
    }


async def test_only_the_seller_adds_images(client, make_user, make_token, listing) -> None:
    farmer, _, _, created = listing
    rival = await make_user("FARMER")

    mine = await client.post(IMAGES, json=_image(created["public_id"], sort_order=1), headers=_auth(farmer, make_token))
    theirs = await client.post(IMAGES, json=_image(created["public_id"]), headers=_auth(rival, make_token))

    assert mine.status_code == 201
    assert mine.json()["listing_id"] == created["public_id"] and "id" not in mine.json()
    assert theirs.status_code == 404


async def test_images_follow_the_listing_visibility(client, make_user, make_token, listing) -> None:
    farmer, _, _, created = listing
    buyer = await make_user("BUYER")
    image = (await client.post(IMAGES, json=_image(created["public_id"]), headers=_auth(farmer, make_token))).json()
    url = f"{IMAGES}/{image['public_id']}"
    headers = _auth(buyer, make_token)

    # the listing is ACTIVE: anyone logged in can see the image, but not change it
    assert (await client.get(url, headers=headers)).status_code == 200
    assert len((await client.get(f"{IMAGES}?listing_id={created['public_id']}", headers=headers)).json()) == 1
    assert (await client.patch(url, json={"is_primary": True}, headers=headers)).status_code == 404
    assert (await client.delete(url, headers=headers)).status_code == 404

    # once the seller closes the listing, other people no longer see it
    await client.delete(f"{LISTINGS}/{created['public_id']}", headers=_auth(farmer, make_token))
    assert (await client.get(url, headers=headers)).status_code == 404
    assert (await client.get(IMAGES, headers=headers)).json() == []
    assert (await client.get(url, headers=_auth(farmer, make_token))).status_code == 200


async def test_seller_can_reorder_and_delete_an_image(client, make_token, listing) -> None:
    farmer, _, _, created = listing
    headers = _auth(farmer, make_token)
    image = (await client.post(IMAGES, json=_image(created["public_id"]), headers=headers)).json()
    url = f"{IMAGES}/{image['public_id']}"

    patched = await client.patch(
        url, json={"sort_order": 3, "is_primary": True, "storage_path": "product-images/other.webp"}, headers=headers
    )

    assert patched.status_code == 200
    assert patched.json()["sort_order"] == 3 and patched.json()["is_primary"] is True
    assert patched.json()["storage_path"] == image["storage_path"]  # the file itself cannot be swapped
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (await client.get(url, headers=headers)).status_code == 404


async def test_image_path_and_type_are_checked(client, make_token, listing) -> None:
    farmer, _, _, created = listing
    headers = _auth(farmer, make_token)
    listing_id = created["public_id"]

    bad_paths = ["../secrets/key.pem", "kyc-documents/x.webp", "product-images/sub/x.webp", "/product-images/x.webp"]
    for path in bad_paths:
        response = await client.post(IMAGES, json={**_image(listing_id), "storage_path": path}, headers=headers)
        assert response.status_code == 422, path
    bad_type = await client.post(IMAGES, json={**_image(listing_id), "content_type": "text/html"}, headers=headers)
    assert bad_type.status_code == 422
    int_id = await client.post(IMAGES, json={**_image(listing_id), "listing_id": 1}, headers=headers)
    assert int_id.status_code == 422
