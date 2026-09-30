"""F1 + F2 for orders and order items (S11).

Rules (FIX_PLAN F1 approved table):
- orders: the buyer and the sellers of its items can read; only the buyer may cancel, only while
  PLACED; no public create or delete.
- order items: the order's buyer or that item's seller can read; only that seller sets the status;
  no public create or delete.
Not yours → 404. The first tests need no database; the rest need TEST_DATABASE_URL.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
import pytest

import app.main as main_module

pytestmark = pytest.mark.anyio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# No database: routes and request bodies (F2)
# ---------------------------------------------------------------------------


def _openapi() -> dict:
    return main_module.app.openapi()


def test_no_public_create_or_delete_routes():
    # S18 added POST /orders (server-computed checkout, tests/test_order_flow.py); items are still
    # only created by the server together with their order.
    paths = _openapi()["paths"]
    assert "post" not in paths.get("/api/v2/order-items", {}), "public create still on order-items"
    for prefix in ("/api/v2/orders", "/api/v2/order-items"):
        assert "delete" not in paths.get(prefix + "/{public_id}", {}), f"delete still on {prefix}"


def test_update_bodies_have_no_owner_ids_or_totals():
    schemas = _openapi()["components"]["schemas"]
    assert set(schemas["OrderUpdate"]["properties"]) == {"status"}
    assert set(schemas["OrderItemUpdate"]["properties"]) == {"status"}


def test_responses_have_no_internal_int_ids():
    schemas = _openapi()["components"]["schemas"]
    for name in ("OrderResponse", "OrderItemResponse"):
        props = schemas[name]["properties"]
        for field in ("id", "buyer_id", "seller_id", "farm_id", "listing_id", "crop_batch_id"):
            assert field not in props, f"{name} exposes {field}"


async def test_post_orders_needs_login():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v2/orders", json={"buyer_id": 1, "total_amount": "1"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Database: ownership
# ---------------------------------------------------------------------------


async def _insert_order(buyer, seller, other_seller, *, status: str = "PLACED"):
    """An order by `buyer` with one item from `seller` and one from `other_seller`."""
    from app.core.database import AsyncSessionLocal
    from app.models.farm import Farm
    from app.models.order import Order
    from app.models.order_item import OrderItem

    async with AsyncSessionLocal() as session:
        farms = []
        for owner in (seller, other_seller):
            farm = Farm(
                user_id=owner.id, farm_name="Test farm", address_line_1="Road 1",
                state="Maharashtra", postal_code="411001",
            )
            session.add(farm)
            farms.append(farm)
        order = Order(
            buyer_id=buyer.id, order_number=f"T-{uuid.uuid4().hex[:10]}", status=status,
            subtotal=Decimal("200"), total_amount=Decimal("200"),
        )
        session.add(order)
        await session.flush()

        items = []
        for owner, farm in zip((seller, other_seller), farms):
            item = OrderItem(
                order_id=order.id, seller_id=owner.id, farm_id=farm.id, title_snapshot="Tomato",
                unit_price=Decimal("20"), quantity=Decimal("5"), unit="kg",
                line_total=Decimal("100"), status="PLACED",
            )
            session.add(item)
            items.append(item)
        await session.commit()
        return order.public_id, items[0].public_id, items[1].public_id


@pytest.fixture
async def people(make_user, make_token):
    buyer = await make_user("BUYER")
    seller = await make_user("FARMER")
    other_seller = await make_user("FARMER")
    stranger = await make_user("BUYER")
    tokens = {name: make_token(u) for name, u in
              {"buyer": buyer, "seller": seller, "other_seller": other_seller, "stranger": stranger}.items()}
    order_id, item_id, other_item_id = await _insert_order(buyer, seller, other_seller)
    return {"tokens": tokens, "order": order_id, "item": item_id, "other_item": other_item_id,
            "users": (buyer, seller, other_seller)}


async def test_order_visible_to_buyer_and_its_sellers(client, people):
    t, order = people["tokens"], people["order"]
    for who in ("buyer", "seller", "other_seller"):
        response = await client.get(f"/api/v2/orders/{order}", headers=_auth(t[who]))
        assert response.status_code == 200, who
        listed = await client.get("/api/v2/orders", headers=_auth(t[who]))
        assert [o["public_id"] for o in listed.json()] == [str(order)], who


async def test_order_hidden_from_stranger(client, people):
    t, order = people["tokens"], people["order"]
    assert (await client.get(f"/api/v2/orders/{order}", headers=_auth(t["stranger"]))).status_code == 404
    assert (await client.get("/api/v2/orders", headers=_auth(t["stranger"]))).json() == []
    response = await client.patch(
        f"/api/v2/orders/{order}", json={"status": "CANCELLED"}, headers=_auth(t["stranger"])
    )
    assert response.status_code == 404


async def test_only_buyer_can_cancel(client, people):
    t, order = people["tokens"], people["order"]
    response = await client.patch(
        f"/api/v2/orders/{order}", json={"status": "CANCELLED"}, headers=_auth(t["seller"])
    )
    assert response.status_code == 403

    response = await client.patch(
        f"/api/v2/orders/{order}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"

    # Already cancelled → not PLACED any more.
    response = await client.patch(
        f"/api/v2/orders/{order}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"])
    )
    assert response.status_code == 409


async def test_buyer_cannot_set_other_fields(client, people):
    t, order = people["tokens"], people["order"]
    for body in ({"status": "DELIVERED"}, {"status": "CANCELLED", "total_amount": "1"},
                 {"buyer_id": 999}):
        response = await client.patch(f"/api/v2/orders/{order}", json=body, headers=_auth(t["buyer"]))
        assert response.status_code == 422, body


async def test_cannot_cancel_after_placed(client, make_user, make_token):
    buyer, seller, other = await make_user("BUYER"), await make_user("FARMER"), await make_user("FARMER")
    order, _, _ = await _insert_order(buyer, seller, other, status="SHIPPED")
    response = await client.patch(
        f"/api/v2/orders/{order}", json={"status": "CANCELLED"}, headers=_auth(make_token(buyer))
    )
    assert response.status_code == 409


async def test_item_visible_to_buyer_and_its_own_seller_only(client, people):
    t, item, order = people["tokens"], people["item"], people["order"]
    for who in ("buyer", "seller"):
        response = await client.get(f"/api/v2/order-items/{item}", headers=_auth(t[who]))
        assert response.status_code == 200, who
        assert response.json()["order_id"] == str(order)
    for who in ("other_seller", "stranger"):
        response = await client.get(f"/api/v2/order-items/{item}", headers=_auth(t[who]))
        assert response.status_code == 404, who


async def test_item_lists(client, people):
    t = people["tokens"]

    async def ids(who, **params):
        response = await client.get("/api/v2/order-items", params=params, headers=_auth(t[who]))
        return {i["public_id"] for i in response.json()}

    both = {str(people["item"]), str(people["other_item"])}
    assert await ids("buyer") == both
    assert await ids("buyer", order_id=str(people["order"])) == both
    assert await ids("seller") == {str(people["item"])}
    assert await ids("other_seller") == {str(people["other_item"])}
    assert await ids("stranger") == set()
    assert await ids("stranger", order_id=str(people["order"])) == set()


async def test_only_items_seller_sets_status(client, people):
    t, item = people["tokens"], people["item"]
    body = {"status": "PACKED"}
    assert (await client.patch(f"/api/v2/order-items/{item}", json=body, headers=_auth(t["buyer"]))).status_code == 403
    assert (await client.patch(f"/api/v2/order-items/{item}", json=body, headers=_auth(t["other_seller"]))).status_code == 404
    assert (await client.patch(f"/api/v2/order-items/{item}", json=body, headers=_auth(t["stranger"]))).status_code == 404

    response = await client.patch(f"/api/v2/order-items/{item}", json=body, headers=_auth(t["seller"]))
    assert response.status_code == 200
    assert response.json()["status"] == "PACKED"


async def test_seller_cannot_change_price_or_owner(client, people):
    t, item = people["tokens"], people["item"]
    for body in ({"status": "PACKED", "line_total": "1"}, {"seller_id": 1}, {"status": "FREE"}):
        response = await client.patch(f"/api/v2/order-items/{item}", json=body, headers=_auth(t["seller"]))
        assert response.status_code == 422, body


# ---------------------------------------------------------------------------
# Status rules (security review of S11)
# ---------------------------------------------------------------------------


async def _patch_item(client, item, status, token):
    return await client.patch(f"/api/v2/order-items/{item}", json={"status": status}, headers=_auth(token))


async def test_item_status_only_moves_forward(client, people):
    t, item = people["tokens"], people["item"]
    assert (await _patch_item(client, item, "SHIPPED", t["seller"])).status_code == 200  # skip ahead ok
    assert (await _patch_item(client, item, "CONFIRMED", t["seller"])).status_code == 409  # backwards
    assert (await _patch_item(client, item, "CANCELLED", t["seller"])).status_code == 409  # already shipped
    assert (await _patch_item(client, item, "DELIVERED", t["seller"])).status_code == 200
    assert (await _patch_item(client, item, "DELIVERED", t["seller"])).status_code == 409  # no repeat


async def test_cancelled_item_stays_cancelled(client, people):
    t, item = people["tokens"], people["item"]
    assert (await _patch_item(client, item, "CANCELLED", t["seller"])).status_code == 200
    assert (await _patch_item(client, item, "SHIPPED", t["seller"])).status_code == 409


async def test_buyer_cancel_cancels_items_and_freezes_them(client, people):
    t = people["tokens"]
    response = await client.patch(
        f"/api/v2/orders/{people['order']}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"])
    )
    assert response.status_code == 200

    items = (await client.get("/api/v2/order-items", headers=_auth(t["buyer"]))).json()
    assert {i["status"] for i in items} == {"CANCELLED"}
    assert (await _patch_item(client, people["item"], "DELIVERED", t["seller"])).status_code == 409


async def test_no_cancel_once_an_item_shipped(client, people):
    t = people["tokens"]
    assert (await _patch_item(client, people["item"], "SHIPPED", t["seller"])).status_code == 200
    response = await client.patch(
        f"/api/v2/orders/{people['order']}", json={"status": "CANCELLED"}, headers=_auth(t["buyer"])
    )
    assert response.status_code == 409


@pytest.mark.parametrize("current,new", [
    ("PLACED", "CONFIRMED"), ("ACTIVE", "SHIPPED"), ("PACKED", "CANCELLED"), ("SHIPPED", "DELIVERED"),
])
def test_allowed_item_transitions(current, new):
    from app.services.order_item_service import _check_transition

    _check_transition(current, new)


@pytest.mark.parametrize("current,new", [
    ("SHIPPED", "PACKED"), ("CANCELLED", "PLACED"), ("DELIVERED", "CANCELLED"),
    ("DELIVERED", "DELIVERED"), ("SOMETHING_ELSE", "SHIPPED"),
])
def test_blocked_item_transitions(current, new):
    from app.core.exceptions import ConflictError
    from app.services.order_item_service import _check_transition

    with pytest.raises(ConflictError):
        _check_transition(current, new)


def test_item_response_uses_order_public_id_not_internal_id():
    from app.api.v2.endpoints.order_item_controller import _to_response
    from app.models.order_item import OrderItem

    order_public_id = uuid.uuid4()
    item = OrderItem(
        public_id=uuid.uuid4(), order_id=5, seller_id=7, farm_id=9, title_snapshot="Tomato",
        unit_price=Decimal("20"), quantity=Decimal("5"), unit="kg", line_total=Decimal("100"),
        status="PLACED",
    )
    response = _to_response(item, order_public_id)
    assert response.order_id == order_public_id
    assert "seller_id" not in response.model_dump()
