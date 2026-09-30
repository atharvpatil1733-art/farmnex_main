"""F1 + F2 for payments (S09).

Rule (FIX_PLAN F1 approved table): readable by the payer, by the sellers in the payment's order,
and by ADMIN. Create/update/delete are server only — no public POST, PATCH or DELETE.
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
# No database: routes and shapes (F2)
# ---------------------------------------------------------------------------


def test_payments_are_read_only():
    paths = main_module.app.openapi()["paths"]
    assert set(paths["/api/v2/payments"]) == {"get"}
    assert set(paths["/api/v2/payments/{public_id}"]) == {"get"}


def test_response_has_no_internal_ids():
    props = main_module.app.openapi()["components"]["schemas"]["PaymentResponse"]["properties"]
    assert "payer_id" not in props and "id" not in props
    assert props["order_id"]["anyOf"][0]["format"] == "uuid"


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
async def test_write_methods_are_gone(method):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        path = "/api/v2/payments" if method == "post" else f"/api/v2/payments/{uuid.uuid4()}"
        body = {"payer_id": 1, "amount": "1", "status": "PAID"}
        response = await client.request(method.upper(), path, json=body if method != "delete" else None)
    assert response.status_code in (404, 405)


def test_response_uses_order_public_id():
    from app.api.v2.endpoints.payment_controller import _to_response
    from app.models.payment import Payment

    order_public_id = uuid.uuid4()
    payment = Payment(
        public_id=uuid.uuid4(), order_id=5, payer_id=7, provider="demo", amount=Decimal("100"),
        currency="INR", status="PAID",
    )
    response = _to_response(payment, order_public_id)
    assert response.order_id == order_public_id


# ---------------------------------------------------------------------------
# Database: who can read
# ---------------------------------------------------------------------------


async def _insert_paid_order(buyer, seller):
    """An order by `buyer` with one item from `seller`, and a payment by `buyer`."""
    from app.core.database import AsyncSessionLocal
    from app.models.farm import Farm
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.payment import Payment

    async with AsyncSessionLocal() as session:
        farm = Farm(
            user_id=seller.id, farm_name="Test farm", address_line_1="Road 1",
            state="Maharashtra", postal_code="411001",
        )
        order = Order(
            buyer_id=buyer.id, order_number=f"T-{uuid.uuid4().hex[:10]}", status="PLACED",
            subtotal=Decimal("100"), total_amount=Decimal("100"),
        )
        session.add_all([farm, order])
        await session.flush()
        session.add(OrderItem(
            order_id=order.id, seller_id=seller.id, farm_id=farm.id, title_snapshot="Tomato",
            unit_price=Decimal("20"), quantity=Decimal("5"), unit="kg", line_total=Decimal("100"),
            status="PLACED",
        ))
        payment = Payment(
            order_id=order.id, payer_id=buyer.id, provider="demo", amount=Decimal("100"),
            currency="INR", status="PAID",
        )
        session.add(payment)
        await session.commit()
        return payment.public_id, order.public_id


@pytest.fixture
async def people(make_user, make_token):
    buyer, seller = await make_user("BUYER"), await make_user("FARMER")
    other_buyer, other_seller = await make_user("BUYER"), await make_user("FARMER")
    admin = await make_user("ADMIN")
    payment_id, order_id = await _insert_paid_order(buyer, seller)
    tokens = {name: make_token(u) for name, u in {
        "buyer": buyer, "seller": seller, "other_buyer": other_buyer,
        "other_seller": other_seller, "admin": admin,
    }.items()}
    return {"tokens": tokens, "payment": payment_id, "order": order_id}


@pytest.mark.parametrize("who", ["buyer", "seller", "admin"])
async def test_allowed_readers(client, people, who):
    token, payment = people["tokens"][who], people["payment"]
    response = await client.get(f"/api/v2/payments/{payment}", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["order_id"] == str(people["order"])
    listed = await client.get("/api/v2/payments", headers=_auth(token))
    assert [p["public_id"] for p in listed.json()] == [str(payment)]


@pytest.mark.parametrize("who", ["other_buyer", "other_seller"])
async def test_others_get_404_and_empty_list(client, people, who):
    token, payment = people["tokens"][who], people["payment"]
    assert (await client.get(f"/api/v2/payments/{payment}", headers=_auth(token))).status_code == 404
    assert (await client.get("/api/v2/payments", headers=_auth(token))).json() == []


async def test_no_write_even_for_the_payer(client, people):
    token, payment = people["tokens"]["buyer"], people["payment"]
    response = await client.patch(
        f"/api/v2/payments/{payment}", json={"status": "REFUNDED"}, headers=_auth(token)
    )
    assert response.status_code == 405
    assert (await client.delete(f"/api/v2/payments/{payment}", headers=_auth(token))).status_code == 405
    response = await client.get(f"/api/v2/payments/{payment}", headers=_auth(token))
    assert response.json()["status"] == "PAID"
