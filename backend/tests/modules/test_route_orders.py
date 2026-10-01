"""Route optimizer part 2 (S26): Slip 2 (CONFIRMED order -> load) and Slip 3 (driver's stops -> order).

Rules (docs/integration/route-optimizer.md "Slip 2" / "Slip 3"; STATUS Decisions log):
- `POST /api/v2/logistics/orders/{id}/request-transport`: the order's farmer or logistics staff (anyone
  else 404); only CONFIRMED orders; pickup = the farm's location, drop = the order's address snapshot;
  either missing -> 422 and no load; weight in kg from kg / quintal / ton, anything else -> 422;
  calling twice returns the same load.
- The driver's pickup moves the order's items to SHIPPED; the drop only marks the load delivered; the BUYER's
  `POST .../confirm-delivery` (after the driver) marks the order DELIVERED and gives the held money to
  the farmer - once, even if called twice. Anyone but the buyer gets 404.
- `POST /api/v2/logistics/orders/{id}/resync`: staff only.
The first tests need no database; the rest need TEST_DATABASE_URL (the component's own tables use a
throw-away SQLite file, like test_route_optimizer.py).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

pytestmark = pytest.mark.anyio

GOOD_URL = "postgresql://user:pw@localhost:5432/postgres?sslmode=require"
L = "/api/v2/logistics"
R = "/api/v2/routes"


def _fresh_app(monkeypatch, *, flag: bool = True) -> FastAPI:
    from app.modules import wiring

    monkeypatch.setenv("ENABLE_ROUTE_OPTIMIZER", "true" if flag else "false")
    monkeypatch.setenv("ROUTES_DATABASE_URL", GOOD_URL)
    app = FastAPI()
    wiring.mount_components(app)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# --- no database ----------------------------------------------------------------------


def test_order_routes_exist_only_when_flag_on(monkeypatch):
    on = _fresh_app(monkeypatch).openapi()["paths"]
    assert "post" in on[f"{L}/orders/{{order_public_id}}/request-transport"]
    assert "post" in on[f"{L}/orders/{{order_public_id}}/resync"]
    operation = on[f"{L}/orders/{{order_public_id}}/request-transport"]["post"]
    assert "requestBody" not in operation  # only the order id: everything else comes from the order
    off = _fresh_app(monkeypatch, flag=False).openapi()["paths"]
    assert not any("/logistics" in path for path in off)


async def test_order_routes_need_login(monkeypatch):
    app = _fresh_app(monkeypatch)
    async with _client(app) as http:
        for path in ("request-transport", "resync"):
            response = await http.post(f"{L}/orders/{uuid.uuid4()}/{path}")
            assert response.status_code == 401, path


def test_weight_in_kg():
    from app.modules.logistics_host import weight_kg

    assert weight_kg(Decimal("4"), "kg") == 4
    assert weight_kg(Decimal("2.5"), "Quintal") == 250
    assert weight_kg(Decimal("1.2"), "ton") == 1200
    for unit in ("crate", "dozen", "", None):
        with pytest.raises(HTTPException) as error:
            weight_kg(Decimal("1"), unit)
        assert error.value.status_code == 422


def test_listener_is_registered_once(monkeypatch):
    from farmnex_routes import hooks

    from app.modules import logistics_host

    _fresh_app(monkeypatch)
    _fresh_app(monkeypatch)
    assert hooks._listeners.count(logistics_host.on_delivery) == 1


def test_listener_ignores_loads_that_are_not_our_orders(monkeypatch):
    from app.modules import logistics_host

    def must_not_run(*_):
        raise AssertionError("order update should not run")

    monkeypatch.setattr(logistics_host, "apply_delivery_status", must_not_run)
    for order_id, status in ((None, "delivered"), ("demo-load-1", "delivered"), (str(uuid.uuid4()), "assigned"),
                             (str(uuid.uuid4()), "pending")):
        logistics_host.on_delivery(SimpleNamespace(id="l", order_id=order_id), status)


# --- with the database ----------------------------------------------------------------


def _auth(user, make_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user)}"}


async def _seed_listing(farmer, *, lat="18.6000", lng="73.9000") -> tuple[uuid.UUID, int]:
    from app.core.database import AsyncSessionLocal
    from app.models.crop_batch import CropBatch
    from app.models.crop_type import CropType
    from app.models.farm import Farm
    from app.models.farm_crop import FarmCrop
    from app.models.product_listing import ProductListing

    async with AsyncSessionLocal() as session:
        farm = Farm(user_id=farmer.id, farm_name="Patil farm", address_line_1="Road 1", village="Wagholi",
                    state="Maharashtra", postal_code="411001",
                    latitude=Decimal(lat) if lat else None, longitude=Decimal(lng) if lng else None)
        crop_type = CropType(name=f"Tomato-{uuid.uuid4().hex[:8]}", default_unit="kg")
        session.add_all([farm, crop_type])
        await session.flush()
        farm_crop = FarmCrop(farmer_id=farmer.id, farm_id=farm.id, crop_type_id=crop_type.id)
        session.add(farm_crop)
        await session.flush()
        batch = CropBatch(farm_crop_id=farm_crop.id, batch_code=f"B-{uuid.uuid4().hex[:10]}",
                          quantity=Decimal("100"), available_quantity=Decimal("100"), unit="kg")
        session.add(batch)
        await session.flush()
        listing = ProductListing(
            seller_id=farmer.id, farm_id=farm.id, crop_batch_id=batch.id, title="Tomatoes",
            listing_type="FIXED_PRICE", price=Decimal("25.00"), quantity=Decimal("100"),
            available_quantity=Decimal("100"), unit="kg", status="ACTIVE",
        )
        session.add(listing)
        await session.commit()
        return listing.public_id, farm.id


async def _seed_address(user) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.address import Address

    async with AsyncSessionLocal() as session:
        session.add(Address(user_id=user.id, address_line_1="Market Road 5", city="Pune", state="Maharashtra",
                            postal_code="411002", latitude=Decimal("18.5204"), longitude=Decimal("73.8567"),
                            is_default=True))
        await session.commit()


async def _set_rows(model_name: str, where: dict, **values) -> None:
    """Test-only shortcut to set up an edge case (farm without location, odd unit, ...)."""
    from sqlalchemy import update

    import app.models.farm as farm_models
    import app.models.order as order_models
    import app.models.order_item as item_models
    from app.core.database import AsyncSessionLocal

    model = {"Farm": farm_models.Farm, "Order": order_models.Order, "OrderItem": item_models.OrderItem}[model_name]
    async with AsyncSessionLocal() as session:
        statement = update(model)
        for column, value in where.items():
            statement = statement.where(getattr(model, column) == value)
        await session.execute(statement.values(**values))
        await session.commit()


async def _order_state(order_id) -> tuple[str, list[str]]:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.order import Order
    from app.models.order_item import OrderItem

    async with AsyncSessionLocal() as session:
        order = await session.scalar(select(Order).where(Order.public_id == uuid.UUID(str(order_id))))
        items = await session.scalars(select(OrderItem.status).where(OrderItem.order_id == order.id))
        return order.status, list(items)


async def _order_row_id(order_id) -> int:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.order import Order

    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Order.id).where(Order.public_id == uuid.UUID(str(order_id))))


async def _ledger(order_id) -> list[tuple[str, Decimal]]:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.wallet_ledger import WalletLedgerEntry

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WalletLedgerEntry.entry_type, WalletLedgerEntry.amount)
            .where(WalletLedgerEntry.order_public_id == uuid.UUID(str(order_id)))
            .order_by(WalletLedgerEntry.id)
        )
        return [(entry_type, amount) for entry_type, amount in result.all()]


async def _checkout(client, make_token, buyer, listing_id) -> str:
    response = await client.post("/api/v2/orders", json={"items": [{"listing_id": str(listing_id), "quantity": "4"}]},
                                 headers=_auth(buyer, make_token))
    assert response.status_code == 201, response.text
    return response.json()["orders"][0]["public_id"]


@pytest.fixture
async def shop(monkeypatch, tmp_path, client, make_user, make_token):
    """A buyer ordered 4 kg of a farmer's tomatoes (100.00), the farmer confirmed, the buyer paid (demo).
    `routes` is the app with the route optimizer on (its tables in SQLite); `client` is the main app."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    app = _fresh_app(monkeypatch)
    import farmnex_routes.db as rdb

    engine = create_engine(f"sqlite:///{tmp_path / 'rt.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(rdb, "_engine", engine)
    monkeypatch.setattr(rdb, "_SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    rdb.Base.metadata.create_all(engine)

    farmer, buyer = await make_user("FARMER"), await make_user("BUYER")
    await _seed_address(buyer)
    listing, farm_id = await _seed_listing(farmer)
    order = await _checkout(client, make_token, buyer, listing)
    confirmed = await client.post(f"/api/v2/orders/{order}/confirm", headers=_auth(farmer, make_token))
    assert confirmed.status_code == 200, confirmed.text
    paid = await client.post(f"/api/v2/payments/orders/{order}/pay-demo", headers=_auth(buyer, make_token))
    assert paid.status_code in (200, 201), paid.text

    async def call(who, method, path):
        headers = _auth(who, make_token) if who is not None else {}
        async with _client(app) as http:
            return await http.request(method, path, headers=headers)

    return SimpleNamespace(call=call, rdb=rdb, farmer=farmer, buyer=buyer, listing=listing, farm_id=farm_id,
                           order=order, make_user=make_user)


def _loads(shop) -> list:
    from farmnex_routes.models import RtLoad

    with shop.rdb.session_scope() as session:
        return list(session.query(RtLoad).all())


async def test_farmer_books_transport_from_the_order_once(shop):
    first = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert first.status_code == 200, first.text
    load = first.json()
    assert load["order_id"] == shop.order
    assert load["farmer_id"] == str(shop.farmer.public_id)
    assert load["buyer_id"] == str(shop.buyer.public_id)
    assert load["weight_kg"] == 4.0 and load["status"] == "pending" and load["priority"] == 0
    assert (load["pickup_lat"], load["pickup_lng"]) == (18.6, 73.9)  # the farm
    assert (load["drop_lat"], load["drop_lng"]) == (18.5204, 73.8567)  # the order's address snapshot
    assert "Wagholi" in load["pickup_address"] and "Market Road 5" in load["drop_address"]
    assert load["already_existed"] is False

    again = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert again.status_code == 200
    assert again.json()["id"] == load["id"] and again.json()["already_existed"] is True
    assert len(_loads(shop)) == 1


async def test_only_the_farmer_or_staff_can_book(shop):
    for role in ("FARMER", "BUYER", "DELIVERY_AGENT"):
        stranger = await shop.make_user(role)
        response = await shop.call(stranger, "POST", f"{L}/orders/{shop.order}/request-transport")
        assert response.status_code == 404, role
    buyer = await shop.call(shop.buyer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert buyer.status_code == 404
    missing = await shop.call(shop.farmer, "POST", f"{L}/orders/{uuid.uuid4()}/request-transport")
    assert missing.status_code == 404
    assert _loads(shop) == []

    manager = await shop.make_user("LOGISTICS_MANAGER")
    response = await shop.call(manager, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert response.status_code == 200, response.text
    assert response.json()["farmer_id"] == str(shop.farmer.public_id)  # never the caller


async def test_only_confirmed_orders_get_transport(shop, client, make_token):
    placed = await _checkout(client, make_token, shop.buyer, shop.listing)
    response = await shop.call(shop.farmer, "POST", f"{L}/orders/{placed}/request-transport")
    assert response.status_code == 409
    assert _loads(shop) == []


async def test_missing_farm_location_makes_no_load(shop):
    await _set_rows("Farm", {"id": shop.farm_id}, latitude=None, longitude=None)
    response = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert response.status_code == 422
    assert "farm location" in response.json()["detail"]
    assert _loads(shop) == []


async def test_missing_drop_location_makes_no_load(shop):
    await _set_rows("Order", {"public_id": uuid.UUID(shop.order)},
                    delivery_address_snapshot={"address_line_1": "Market Road 5", "latitude": None, "longitude": None})
    response = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert response.status_code == 422
    assert _loads(shop) == []


async def test_unknown_unit_makes_no_load(shop):
    await _set_rows("OrderItem", {"order_id": await _order_row_id(shop.order)}, unit="crate")
    response = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert response.status_code == 422
    assert _loads(shop) == []


async def _on_a_trip(shop) -> SimpleNamespace:
    """Book the order's load and put it on a trip of a new driver (as the planner would)."""
    from farmnex_routes.models import RtLoad, RtTrip, RtTripStop, RtVehicle

    booked = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    assert booked.status_code == 200, booked.text
    driver = await shop.make_user("DELIVERY_AGENT")
    with shop.rdb.session_scope() as s:
        vehicle = RtVehicle(id=str(uuid.uuid4()), driver_user_id=str(driver.public_id), vehicle_number="MH12AB1234",
                            capacity_kg=1000, rate_per_ton_km=8, base_lat=18.5, base_lng=73.8, status="on_trip")
        s.add(vehicle)
        s.flush()
        trip = RtTrip(vehicle_id=vehicle.id, start_lat=18.5, start_lng=73.8)
        s.add(trip)
        s.flush()
        load = s.get(RtLoad, booked.json()["id"])
        load.status, load.trip_id = "assigned", trip.id
        pickup = RtTripStop(trip_id=trip.id, load_id=load.id, seq=1, kind="pickup", lat=18.6, lng=73.9, label="p",
                            leg_distance_km=1, leg_duration_min=1, planned_arrival_min=1)
        drop = RtTripStop(trip_id=trip.id, load_id=load.id, seq=2, kind="drop", lat=18.52, lng=73.86, label="d",
                          leg_distance_km=1, leg_duration_min=1, planned_arrival_min=2)
        s.add_all([pickup, drop])
        s.commit()
        return SimpleNamespace(driver=driver, trip=trip.id, pickup=pickup.id, drop=drop.id)


async def test_driver_and_buyer_both_confirm_before_money_moves(shop):
    trip = await _on_a_trip(shop)
    url = f"{L}/orders/{shop.order}/confirm-delivery"
    picked = await shop.call(trip.driver, "POST", f"{R}/trips/{trip.trip}/stops/{trip.pickup}/complete")
    assert picked.status_code == 200, picked.text
    assert await _order_state(shop.order) == ("CONFIRMED", ["SHIPPED"])
    assert (await shop.call(shop.buyer, "POST", url)).status_code == 409  # driver not done yet

    dropped = await shop.call(trip.driver, "POST", f"{R}/trips/{trip.trip}/stops/{trip.drop}/complete")
    assert dropped.status_code == 200, dropped.text
    # The driver alone is not enough: still not delivered, nothing released.
    assert await _order_state(shop.order) == ("CONFIRMED", ["SHIPPED"])
    assert [kind for kind, _ in await _ledger(shop.order)] == ["HOLD"]

    for who in (shop.farmer, trip.driver, await shop.make_user("BUYER")):  # only the buyer may confirm
        assert (await shop.call(who, "POST", url)).status_code == 404
    done = await shop.call(shop.buyer, "POST", url)
    assert done.status_code == 200, done.text
    assert done.json()["order_status"] == "DELIVERED" and Decimal(done.json()["released"]) == Decimal("100.00")
    assert await _order_state(shop.order) == ("DELIVERED", ["DELIVERED"])
    assert await _ledger(shop.order) == [("HOLD", Decimal("100.00")), ("RELEASE", Decimal("100.00"))]

    again = await shop.call(shop.buyer, "POST", url)  # a retry: still DELIVERED, money moves once
    assert again.status_code == 200 and again.json()["released"] is None
    assert await _ledger(shop.order) == [("HOLD", Decimal("100.00")), ("RELEASE", Decimal("100.00"))]


async def test_a_cancelled_order_is_never_marked_delivered(shop):
    from app.modules.logistics_host import apply_delivery_status

    await _set_rows("Order", {"public_id": uuid.UUID(shop.order)}, status="CANCELLED")
    assert await apply_delivery_status(uuid.UUID(shop.order), "delivered") == ("CANCELLED", None)
    from app.modules.logistics_host import confirm_delivery

    with pytest.raises(HTTPException):  # and the buyer's confirmation is refused too
        await confirm_delivery(uuid.UUID(shop.order))
    assert (await _order_state(shop.order))[0] == "CANCELLED"
    assert [kind for kind, _ in await _ledger(shop.order)] == ["HOLD"]


async def test_resync_is_staff_only_and_never_releases_money(shop):
    from farmnex_routes.models import RtLoad

    booked = await shop.call(shop.farmer, "POST", f"{L}/orders/{shop.order}/request-transport")
    with shop.rdb.session_scope() as s:  # delivered, but the automatic order update "failed"
        s.get(RtLoad, booked.json()["id"]).status = "delivered"
        s.commit()

    for who in (shop.farmer, shop.buyer, await shop.make_user("DELIVERY_AGENT")):
        assert (await shop.call(who, "POST", f"{L}/orders/{shop.order}/resync")).status_code == 403
    assert (await _order_state(shop.order))[0] == "CONFIRMED"

    manager = await shop.make_user("LOGISTICS_MANAGER")
    first = await shop.call(manager, "POST", f"{L}/orders/{shop.order}/resync")
    assert first.status_code == 200, first.text
    assert first.json()["order_status"] == "CONFIRMED" and first.json()["released"] is None  # buyer must confirm
    assert [kind for kind, _ in await _ledger(shop.order)] == ["HOLD"]
    no_load = await shop.call(manager, "POST", f"{L}/orders/{uuid.uuid4()}/resync")
    assert no_load.status_code == 404
