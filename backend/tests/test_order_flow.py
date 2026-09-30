"""F12a orders (S18): checkout with server totals, stock, one order per farmer, farmer confirms.

Rules (FIX_PLAN F12 prototype minimum + STATUS "Wave 3 decisions" / "Pre-flight defaults"):
- `POST /orders` (BUYER): only listing ids, quantities and an own address are accepted; prices and
  totals come from the listings. Stock (`available_quantity`) drops under a row lock; a refused
  checkout changes nothing. Several farmers → one PLACED order each, shared checkout number.
- `POST /orders/{id}/confirm`: only the order's farmer; PLACED → CONFIRMED.
- Cancelling (whole order by the buyer, or one item by the farmer) gives the stock back.
The first tests need no database; the rest need TEST_DATABASE_URL.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

import app.main as main_module

pytestmark = pytest.mark.anyio

ORDERS = "/api/v2/orders"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# No database: request shapes
# ---------------------------------------------------------------------------


def test_checkout_body_has_no_prices_or_owner_ids():
    schemas = main_module.app.openapi()["components"]["schemas"]
    assert set(schemas["OrderCreate"]["properties"]) == {"items", "address_id"}
    assert set(schemas["OrderLineIn"]["properties"]) == {"listing_id", "quantity"}


def test_confirm_route_exists():
    assert "post" in main_module.app.openapi()["paths"]["/api/v2/orders/{public_id}/confirm"]


@pytest.mark.parametrize("body", [
    {"items": []},
    {"items": [{"listing_id": str(uuid.uuid4()), "quantity": "0"}]},
    {"items": [{"listing_id": str(uuid.uuid4()), "quantity": "-1"}]},
    {"items": [{"listing_id": str(uuid.uuid4()), "quantity": "1", "unit_price": "1"}]},
    {"items": [{"listing_id": str(uuid.uuid4()), "quantity": "1"}], "total_amount": "1"},
    {"items": [{"listing_id": str(uuid.uuid4()), "quantity": "1"}], "buyer_id": 1},
])
def test_checkout_body_rejects_bad_or_extra_fields(body):
    from app.schemas.order_schema import OrderCreate

    with pytest.raises(ValidationError):
        OrderCreate.model_validate(body)


def test_same_listing_twice_is_rejected():
    from app.schemas.order_schema import OrderCreate

    same = str(uuid.uuid4())
    with pytest.raises(ValidationError):
        OrderCreate.model_validate({"items": [{"listing_id": same, "quantity": "1"},
                                              {"listing_id": same, "quantity": "2"}]})


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def _seed_listing(farmer, *, price="25.50", quantity="100", **extra) -> uuid.UUID:
    """A farm, crop, batch and ACTIVE listing owned by `farmer`. Returns the listing public id."""
    from app.core.database import AsyncSessionLocal
    from app.models.crop_batch import CropBatch
    from app.models.crop_type import CropType
    from app.models.farm import Farm
    from app.models.farm_crop import FarmCrop
    from app.models.product_listing import ProductListing

    async with AsyncSessionLocal() as session:
        farm = Farm(user_id=farmer.id, farm_name="Test farm", address_line_1="Road 1",
                    state="Maharashtra", postal_code="411001")
        crop_type = CropType(name=f"Tomato-{uuid.uuid4().hex[:8]}", default_unit="kg")
        session.add_all([farm, crop_type])
        await session.flush()
        farm_crop = FarmCrop(farmer_id=farmer.id, farm_id=farm.id, crop_type_id=crop_type.id)
        session.add(farm_crop)
        await session.flush()
        batch = CropBatch(farm_crop_id=farm_crop.id, batch_code=f"B-{uuid.uuid4().hex[:10]}",
                          quantity=Decimal(quantity), available_quantity=Decimal(quantity), unit="kg")
        session.add(batch)
        await session.flush()
        listing = ProductListing(
            seller_id=farmer.id, farm_id=farm.id, crop_batch_id=batch.id, title="Fresh tomatoes",
            listing_type="FIXED_PRICE", price=Decimal(price), quantity=Decimal(quantity),
            available_quantity=Decimal(quantity), unit="kg", status="ACTIVE", **extra,
        )
        session.add(listing)
        await session.commit()
        return listing.public_id


async def _seed_address(user, *, is_default=True) -> uuid.UUID:
    from app.core.database import AsyncSessionLocal
    from app.models.address import Address

    async with AsyncSessionLocal() as session:
        address = Address(user_id=user.id, address_line_1="Market Road 5", city="Pune",
                          state="Maharashtra", postal_code="411002", latitude=Decimal("18.5204"),
                          longitude=Decimal("73.8567"), is_default=is_default)
        session.add(address)
        await session.commit()
        return address.public_id


async def _available(listing_id) -> Decimal:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.product_listing import ProductListing

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProductListing.available_quantity).where(ProductListing.public_id == listing_id)
        )
        return result.scalar_one()


async def _order_count() -> int:
    from sqlalchemy import func, select

    from app.core.database import AsyncSessionLocal
    from app.models.order import Order

    async with AsyncSessionLocal() as session:
        return int((await session.execute(select(func.count()).select_from(Order))).scalar_one())


def _cart(*lines, address_id=None) -> dict:
    body = {"items": [{"listing_id": str(listing), "quantity": qty} for listing, qty in lines]}
    if address_id is not None:
        body["address_id"] = str(address_id)
    return body


@pytest.fixture
async def shop(make_user, make_token):
    buyer = await make_user("BUYER")
    farmer = await make_user("FARMER")
    other_farmer = await make_user("FARMER")
    stranger = await make_user("BUYER")
    await _seed_address(buyer)
    return {
        "users": {"buyer": buyer, "farmer": farmer, "other_farmer": other_farmer, "stranger": stranger},
        "t": {name: make_token(u) for name, u in
              {"buyer": buyer, "farmer": farmer, "other_farmer": other_farmer, "stranger": stranger}.items()},
        "listing": await _seed_listing(farmer),
        "other_listing": await _seed_listing(other_farmer, price="10.00", quantity="50"),
    }


async def _checkout(client, token, *lines, **kw):
    return await client.post(ORDERS, json=_cart(*lines, **kw), headers=_auth(token))


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


async def test_checkout_uses_listing_price_and_lowers_stock(client, shop):
    response = await _checkout(client, shop["t"]["buyer"], (shop["listing"], "4"))
    assert response.status_code == 201, response.text
    body = response.json()
    [order] = body["orders"]
    assert order["order_number"] == body["checkout_number"] + "-1"
    assert order["status"] == "PLACED"
    assert Decimal(order["subtotal"]) == Decimal("102.00")  # 4 kg x 25.50
    assert Decimal(order["total_amount"]) == Decimal("102.00")
    snapshot = order["delivery_address_snapshot"]
    assert snapshot["city"] == "Pune" and snapshot["latitude"] == pytest.approx(18.5204)
    assert snapshot["longitude"] == pytest.approx(73.8567)
    assert await _available(shop["listing"]) == Decimal("96")

    items = (await client.get("/api/v2/order-items", params={"order_id": order["public_id"]},
                              headers=_auth(shop["t"]["buyer"]))).json()
    assert [(i["status"], Decimal(i["unit_price"]), Decimal(i["line_total"])) for i in items] == [
        ("PLACED", Decimal("25.50"), Decimal("102.00"))
    ]


async def test_client_cannot_send_prices_or_totals(client, shop):
    for extra in ({"total_amount": "1"}, {"buyer_id": 1}, {"status": "CONFIRMED"}):
        body = {**_cart((shop["listing"], "4")), **extra}
        response = await client.post(ORDERS, json=body, headers=_auth(shop["t"]["buyer"]))
        assert response.status_code == 422, extra
    body = {"items": [{"listing_id": str(shop["listing"]), "quantity": "4", "unit_price": "0.01"}]}
    response = await client.post(ORDERS, json=body, headers=_auth(shop["t"]["buyer"]))
    assert response.status_code == 422
    assert await _available(shop["listing"]) == Decimal("100")


async def test_two_farmers_make_two_orders_with_one_checkout_number(client, shop):
    t = shop["t"]
    response = await _checkout(client, t["buyer"], (shop["listing"], "2"), (shop["other_listing"], "3"))
    assert response.status_code == 201, response.text
    body = response.json()
    numbers = sorted(o["order_number"] for o in body["orders"])
    assert numbers == [body["checkout_number"] + "-1", body["checkout_number"] + "-2"]
    totals = sorted(Decimal(o["total_amount"]) for o in body["orders"])
    assert totals == [Decimal("30.00"), Decimal("51.00")]

    # Each farmer sees only their own order.
    for who in ("farmer", "other_farmer"):
        mine = (await client.get(ORDERS, headers=_auth(t[who]))).json()
        assert len(mine) == 1, who
    assert len((await client.get(ORDERS, headers=_auth(t["buyer"]))).json()) == 2


async def test_refused_checkout_changes_nothing(client, shop):
    response = await _checkout(client, shop["t"]["buyer"], (shop["listing"], "5"), (shop["other_listing"], "51"))
    assert response.status_code == 409
    assert await _available(shop["listing"]) == Decimal("100")
    assert await _available(shop["other_listing"]) == Decimal("50")
    assert await _order_count() == 0


async def test_two_buyers_racing_for_the_last_stock(client, shop, make_user, make_token):
    second_buyer = await make_user("BUYER")
    await _seed_address(second_buyer)
    small = await _seed_listing(shop["users"]["farmer"], quantity="10")

    responses = await asyncio.gather(
        _checkout(client, shop["t"]["buyer"], (small, "7")),
        _checkout(client, make_token(second_buyer), (small, "7")),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert await _available(small) == Decimal("3")


async def test_only_buyers_check_out(client, shop):
    response = await _checkout(client, shop["t"]["farmer"], (shop["other_listing"], "1"))
    assert response.status_code == 403


async def test_address_must_be_your_own(client, shop):
    t, users = shop["t"], shop["users"]
    someone_elses = await _seed_address(users["stranger"])
    response = await _checkout(client, t["buyer"], (shop["listing"], "1"), address_id=someone_elses)
    assert response.status_code == 404
    assert await _available(shop["listing"]) == Decimal("100")


async def test_buyer_without_address_is_asked_to_add_one(client, shop, make_user, make_token):
    new_buyer = await make_user("BUYER")
    response = await _checkout(client, make_token(new_buyer), (shop["listing"], "1"))
    assert response.status_code == 422
    assert "address" in response.text.lower()


async def test_listing_rules(client, shop):
    from app.core.database import AsyncSessionLocal
    from app.models.bid_event import BidEvent
    from app.models.product_listing import ProductListing
    from sqlalchemy import select

    t, farmer = shop["t"], shop["users"]["farmer"]
    now = datetime.now(timezone.utc)

    assert (await _checkout(client, t["buyer"], (uuid.uuid4(), "1"))).status_code == 404
    closed = await _seed_listing(farmer)
    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(ProductListing).where(ProductListing.public_id == closed))).scalar_one()
        row.status = "CLOSED"
        await session.commit()
    assert (await _checkout(client, t["buyer"], (closed, "1"))).status_code == 404

    minimum = await _seed_listing(farmer, minimum_order_quantity=Decimal("10"))
    assert (await _checkout(client, t["buyer"], (minimum, "5"))).status_code == 422
    assert (await _checkout(client, t["buyer"], (minimum, "10"))).status_code == 201

    later = await _seed_listing(farmer, starts_at=now + timedelta(days=2))
    assert (await _checkout(client, t["buyer"], (later, "1"))).status_code == 409
    ended = await _seed_listing(farmer, ends_at=now - timedelta(hours=1))
    assert (await _checkout(client, t["buyer"], (ended, "1"))).status_code == 409

    pre_bid = await _seed_listing(farmer)
    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(ProductListing).where(ProductListing.public_id == pre_bid))).scalar_one()
        session.add(BidEvent(listing_id=row.id, created_by_id=farmer.id, starts_at=now,
                             ends_at=now + timedelta(days=7), starting_price=Decimal("20"),
                             minimum_increment=Decimal("1"), status="ACTIVE"))
        await session.commit()
    response = await _checkout(client, t["buyer"], (pre_bid, "1"))
    assert response.status_code == 409 and "pre-bid" in response.text


# ---------------------------------------------------------------------------
# Farmer confirms
# ---------------------------------------------------------------------------


async def _one_order(client, shop) -> str:
    response = await _checkout(client, shop["t"]["buyer"], (shop["listing"], "4"))
    assert response.status_code == 201, response.text
    return response.json()["orders"][0]["public_id"]


async def test_only_the_farmer_confirms(client, shop):
    t = shop["t"]
    order = await _one_order(client, shop)
    assert (await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t["buyer"]))).status_code == 403
    for who in ("other_farmer", "stranger"):
        assert (await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t[who]))).status_code == 404, who

    response = await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t["farmer"]))
    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMED"
    items = (await client.get("/api/v2/order-items", params={"order_id": order},
                              headers=_auth(t["buyer"]))).json()
    assert {i["status"] for i in items} == {"CONFIRMED"}

    # No second confirm, and the buyer can no longer cancel.
    assert (await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t["farmer"]))).status_code == 409
    response = await client.patch(f"{ORDERS}/{order}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"]))
    assert response.status_code == 409


async def test_cancelled_order_cannot_be_confirmed(client, shop):
    t = shop["t"]
    order = await _one_order(client, shop)
    await client.patch(f"{ORDERS}/{order}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"]))
    assert (await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t["farmer"]))).status_code == 409


# ---------------------------------------------------------------------------
# Stock comes back on cancel
# ---------------------------------------------------------------------------


async def test_buyer_cancel_gives_stock_back(client, shop):
    order = await _one_order(client, shop)
    assert await _available(shop["listing"]) == Decimal("96")
    response = await client.patch(f"{ORDERS}/{order}", json={"status": "CANCELLED"},
                                  headers=_auth(shop["t"]["buyer"]))
    assert response.status_code == 200
    assert await _available(shop["listing"]) == Decimal("100")


async def test_farmer_cancelling_an_item_gives_stock_back_once(client, shop):
    t = shop["t"]
    order = await _one_order(client, shop)
    [item] = (await client.get("/api/v2/order-items", params={"order_id": order}, headers=_auth(t["farmer"]))).json()
    url = f"/api/v2/order-items/{item['public_id']}"
    assert (await client.patch(url, json={"status": "CANCELLED"}, headers=_auth(t["farmer"]))).status_code == 200
    assert await _available(shop["listing"]) == Decimal("100")

    # Cancelling the whole order afterwards doesn't add the same stock again.
    await client.patch(f"{ORDERS}/{order}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"]))
    assert await _available(shop["listing"]) == Decimal("100")
    # Nothing left to confirm.
    assert (await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t["farmer"]))).status_code == 409


# ---------------------------------------------------------------------------
# Server callers (S19: farmer accepts a bid → the winner's order)
# ---------------------------------------------------------------------------


async def test_accepted_bid_order_uses_the_given_price(shop):
    from app.core.database import AsyncSessionLocal
    from app.repositories.order_repository import OrderRepository
    from app.services.order_service import OrderLine, OrderService

    async with AsyncSessionLocal() as session:
        service = OrderService(OrderRepository(session))
        _, [order] = await service.create_orders(
            shop["users"]["buyer"],
            [OrderLine(shop["listing"], Decimal("10"), unit_price=Decimal("30.00"))],
            from_accepted_bid=True,
        )
        await session.commit()
        assert order.status == "PLACED"
        assert order.total_amount == Decimal("300.00")
    assert await _available(shop["listing"]) == Decimal("90")


# ---------------------------------------------------------------------------
# Security review of S18
# ---------------------------------------------------------------------------


async def test_cancelled_item_is_taken_off_the_total(client, shop, make_token):
    t, farmer = shop["t"], shop["users"]["farmer"]
    second = await _seed_listing(farmer, price="10.00")
    response = await _checkout(client, t["buyer"], (shop["listing"], "4"), (second, "2"))
    [order] = response.json()["orders"]
    assert Decimal(order["total_amount"]) == Decimal("122.00")

    items = (await client.get("/api/v2/order-items", params={"order_id": order["public_id"]},
                              headers=_auth(t["farmer"]))).json()
    cheap = next(i for i in items if Decimal(i["unit_price"]) == Decimal("10.00"))
    await client.patch(f"/api/v2/order-items/{cheap['public_id']}", json={"status": "CANCELLED"},
                       headers=_auth(t["farmer"]))
    after = (await client.get(f"{ORDERS}/{order['public_id']}", headers=_auth(t["buyer"]))).json()
    assert Decimal(after["subtotal"]) == Decimal("102.00")
    assert Decimal(after["total_amount"]) == Decimal("102.00")


async def test_confirm_works_after_the_farmer_packed_items(client, shop):
    t = shop["t"]
    order = await _one_order(client, shop)
    [item] = (await client.get("/api/v2/order-items", params={"order_id": order}, headers=_auth(t["farmer"]))).json()
    await client.patch(f"/api/v2/order-items/{item['public_id']}", json={"status": "PACKED"}, headers=_auth(t["farmer"]))
    response = await client.post(f"{ORDERS}/{order}/confirm", headers=_auth(t["farmer"]))
    assert response.status_code == 200 and response.json()["status"] == "CONFIRMED"
    [item] = (await client.get("/api/v2/order-items", params={"order_id": order}, headers=_auth(t["farmer"]))).json()
    assert item["status"] == "PACKED"  # not moved backwards


async def test_confirm_refuses_an_old_order_with_two_farmers(client, shop):
    """Rows made before S18 may mix farmers in one order: one farmer can't confirm the other's."""
    from app.core.database import AsyncSessionLocal
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.product_listing import ProductListing
    from sqlalchemy import select

    users = shop["users"]
    async with AsyncSessionLocal() as session:
        order = Order(buyer_id=users["buyer"].id, order_number=f"OLD-{uuid.uuid4().hex[:10]}",
                      status="PLACED", subtotal=Decimal("200"), total_amount=Decimal("200"))
        session.add(order)
        await session.flush()
        for listing_id in (shop["listing"], shop["other_listing"]):
            listing = (await session.execute(
                select(ProductListing).where(ProductListing.public_id == listing_id))).scalar_one()
            session.add(OrderItem(order_id=order.id, seller_id=listing.seller_id, farm_id=listing.farm_id,
                                  title_snapshot="Tomato", unit_price=Decimal("20"), quantity=Decimal("5"),
                                  unit="kg", line_total=Decimal("100"), status="PLACED"))
        await session.commit()
        order_id = order.public_id

    response = await client.post(f"{ORDERS}/{order_id}/confirm", headers=_auth(shop["t"]["farmer"]))
    assert response.status_code == 409


async def test_amount_that_rounds_to_zero_is_refused(client, shop):
    tiny = await _seed_listing(shop["users"]["farmer"], price="4.99")
    response = await _checkout(client, shop["t"]["buyer"], (tiny, "0.001"))
    assert response.status_code == 422
