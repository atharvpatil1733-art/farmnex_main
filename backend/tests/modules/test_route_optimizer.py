"""Route optimizer (S17 part 1): wiring checks, the allow-list + ownership guard, vehicle endpoints.

No Postgres needed: the login is faked (like test_forecast.py) and the component's own sync
database is a throw-away SQLite file swapped in after mounting. The real SQL file
(migrations/030_rt_route_tables.sql) is checked by a plain-text test. Slips 2/3 (orders) are part 2.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "030_rt_route_tables.sql"
GOOD_URL = "postgresql://user:pw@localhost:5432/postgres?sslmode=require"


def _fresh_app(monkeypatch, *, flag: bool = True, url: str | None = GOOD_URL) -> FastAPI:
    from app.modules import wiring

    monkeypatch.setenv("ENABLE_ROUTE_OPTIMIZER", "true" if flag else "false")
    if url is None:
        monkeypatch.delenv("ROUTES_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("ROUTES_DATABASE_URL", url)
    app = FastAPI()
    wiring.mount_components(app)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _paths(app: FastAPI) -> dict:
    return app.openapi()["paths"]


def _person(role: str) -> SimpleNamespace:
    return SimpleNamespace(
        public_id=uuid.uuid4(),
        role=SimpleNamespace(name=role),
        first_name="Test",
        surname=role.title(),
        phone_number="9" + str(uuid.uuid4().int)[:9],
    )


# --- flag and config ----------------------------------------------------------------


def test_routes_exist_when_flag_on(monkeypatch):
    paths = _paths(_fresh_app(monkeypatch))
    for path in (
        "/api/v2/routes/vehicles/{vehicle_id}",
        "/api/v2/routes/trips/plan",
        "/api/v2/routes/trips/{trip_id}/stops/{stop_id}/complete",
        "/api/v2/routes/orders/{order_id}/delivery",
        "/api/v2/routes/track/{trip_id}",
        "/api/v2/routes/track/{trip_id}/view",
        "/api/v2/logistics/vehicles",
        "/api/v2/logistics/vehicles/{vehicle_id}",
        "/api/v2/logistics/my-vehicles",
    ):
        assert path in paths, path


def test_routes_absent_when_flag_off(monkeypatch):
    paths = _paths(_fresh_app(monkeypatch, flag=False))
    assert not any("/routes" in p or "/logistics" in p for p in paths)


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "sqlite:///./farmnex_routes_dev.db",
        "postgresql+asyncpg://user:pw@localhost:5432/postgres",
        "not a url",
    ],
)
def test_bad_database_url_leaves_it_unmounted_but_app_starts(monkeypatch, caplog, url):
    with caplog.at_level(logging.ERROR):
        app = _fresh_app(monkeypatch, url=url)
    assert not any("/routes" in p or "/logistics" in p for p in _paths(app))
    assert "NOT mounted" in caplog.text
    assert "pw" not in caplog.text  # the password is never logged


@pytest.mark.parametrize(
    "url",
    ["postgresql://u:p@h:5432/db", "postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"],
)
def test_postgres_url_forms_are_accepted(monkeypatch, url):
    assert "/api/v2/routes/trips/plan" in _paths(_fresh_app(monkeypatch, url=url))


def test_blocked_routes_are_not_mounted(monkeypatch):
    paths = _paths(_fresh_app(monkeypatch))
    assert "/api/v2/routes/loads" not in paths  # POST + GET list
    assert "/api/v2/routes/vehicles" not in paths  # GET list
    assert "/api/v2/routes/loads/{load_id}/cancel" not in paths
    assert "/api/v2/routes/orders/{order_id}/cancel-delivery" not in paths
    assert set(paths["/api/v2/routes/vehicles/{vehicle_id}"]) == {"get"}  # no PUT


def test_sql_file_only_adds_rt_tables():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert sql.count("create table if not exists rt_") == 6
    for word in ("drop ", "truncate", "delete from"):
        assert word not in sql
    assert sql.strip().splitlines()[-1] == "commit;" and "begin;" in sql
    assert "references users" not in sql  # no foreign keys to core tables


# --- a mounted app with a throw-away database -----------------------------------------


@pytest.fixture
def world(monkeypatch, tmp_path):
    """Mounted app, SQLite rt_* tables, and: driver A (vehicle + trip + 2 stops + notification), driver B,
    a farmer and a buyer of a load, another buyer, a manager. Users are chosen with the X-Test-User header."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api.dependencies.current_user import get_current_user

    app = _fresh_app(monkeypatch)
    import farmnex_routes.db as rdb
    from farmnex_routes.models import RtLoad, RtNotification, RtTrip, RtTripStop, RtVehicle

    engine = create_engine(f"sqlite:///{tmp_path / 'rt.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(rdb, "_engine", engine)
    monkeypatch.setattr(rdb, "_SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    rdb.Base.metadata.create_all(engine)

    people = {
        "driver_a": _person("DELIVERY_AGENT"),
        "driver_b": _person("DELIVERY_AGENT"),
        "farmer": _person("FARMER"),
        "buyer": _person("BUYER"),
        "other_buyer": _person("BUYER"),
        "manager": _person("LOGISTICS_MANAGER"),
    }

    def fake_login(request: Request):
        who = request.headers.get("x-test-user")
        if who is None:
            raise HTTPException(401, "Authentication required.")
        return people[who]

    app.dependency_overrides[get_current_user] = fake_login

    ids = SimpleNamespace(vehicle_a=str(uuid.uuid4()), vehicle_b=str(uuid.uuid4()), trip="", stop_pickup="",
                          stop_drop="", load="", loose_load="", note="")
    with rdb.session_scope() as s:
        for vid, who in ((ids.vehicle_a, "driver_a"), (ids.vehicle_b, "driver_b")):
            s.add(RtVehicle(id=vid, driver_user_id=str(people[who].public_id), vehicle_number="MH12AB1234",
                            capacity_kg=1000, rate_per_ton_km=8, base_lat=18.5, base_lng=73.8))
        s.flush()

        def load(order_id, farmer, buyer, trip_id=None):
            row = RtLoad(order_id=order_id, farmer_id=str(people[farmer].public_id),
                         buyer_id=str(people[buyer].public_id), farmer_name="F", buyer_name="B", crop="Tomato",
                         weight_kg=100, pickup_lat=18.5, pickup_lng=73.8, pickup_address="farm",
                         drop_lat=18.6, drop_lng=73.9, drop_address="shop", trip_id=trip_id, status="assigned"
                         if trip_id else "pending")
            s.add(row)
            s.flush()
            return row

        trip = RtTrip(vehicle_id=ids.vehicle_a, start_lat=18.5, start_lng=73.8)
        s.add(trip)
        s.flush()
        main_load = load("order-1", "farmer", "buyer", trip.id)
        loose = load("order-2", "farmer", "buyer")
        pickup = RtTripStop(trip_id=trip.id, load_id=main_load.id, seq=1, kind="pickup", lat=18.5, lng=73.8,
                            label="p", leg_distance_km=1, leg_duration_min=1, planned_arrival_min=1)
        drop = RtTripStop(trip_id=trip.id, load_id=main_load.id, seq=2, kind="drop", lat=18.6, lng=73.9,
                          label="d", leg_distance_km=1, leg_duration_min=1, planned_arrival_min=2)
        note = RtNotification(vehicle_id=ids.vehicle_a, kind="backhaul", title="t", message="m")
        s.add_all([pickup, drop, note])
        s.commit()
        ids.trip, ids.load, ids.loose_load = trip.id, main_load.id, loose.id
        ids.stop_pickup, ids.stop_drop, ids.note = pickup.id, drop.id, note.id

    async def call(who, method, path, **kwargs):
        headers = ({"x-test-user": who} if who else {}) | kwargs.pop("headers", {})
        async with _client(app) as http:
            return await http.request(method, path, headers=headers, **kwargs)

    return SimpleNamespace(app=app, call=call, ids=ids, people=people, rdb=rdb)


R = "/api/v2/routes"
L = "/api/v2/logistics"


def _vehicle_state(world, vehicle_id):
    from farmnex_routes.models import RtVehicle

    with world.rdb.session_scope() as s:
        return s.get(RtVehicle, vehicle_id).status


def _stop_state(world, stop_id):
    from farmnex_routes.models import RtTripStop

    with world.rdb.session_scope() as s:
        return s.get(RtTripStop, stop_id).status


# --- login ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_token_gives_401_on_guarded_and_logistics_routes(monkeypatch):
    app = _fresh_app(monkeypatch)  # real login dependency, no override
    async with _client(app) as http:
        for method, path in (
            ("GET", f"{R}/vehicles/x"),
            ("GET", f"{R}/trips/x"),
            ("POST", f"{R}/trips/x/stops/y/complete"),
            ("GET", f"{R}/loads/x"),
            ("GET", f"{R}/orders/x/delivery"),
            ("GET", f"{L}/my-vehicles"),
            ("PATCH", f"{L}/vehicles/x"),
        ):
            response = await http.request(method, path, json={} if method != "GET" else None)
            assert response.status_code == 401, (method, path)
        response = await http.post(f"{L}/vehicles", json={})
        assert response.status_code == 401


def test_guard_denies_unknown_routes_by_default(world):
    from app.modules import routes_host

    assert routes_host._allowed("/something/new", {}, None, "anyone") is False


@pytest.mark.anyio
async def test_tracking_works_without_a_token(world):
    data = await world.call(None, "GET", f"{R}/track/{world.ids.trip}")
    assert data.status_code == 200
    assert data.json()["stops"]
    page = await world.call(None, "GET", f"{R}/track/{world.ids.trip}/view")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert (await world.call(None, "GET", f"{R}/track/{uuid.uuid4()}")).status_code == 404


# --- ownership: another driver, a buyer -----------------------------------------------


@pytest.mark.anyio
async def test_driver_b_cannot_touch_driver_a(world):
    i = world.ids
    attempts = [
        ("GET", f"{R}/vehicles/{i.vehicle_a}", None),
        ("PATCH", f"{R}/vehicles/{i.vehicle_a}/status", {"status": "offline"}),
        ("POST", f"{R}/vehicles/{i.vehicle_a}/location", {"lat": 18.5, "lng": 73.8}),
        ("GET", f"{R}/vehicles/{i.vehicle_a}/current-trip", None),
        ("GET", f"{R}/vehicles/{i.vehicle_a}/backhaul", None),
        ("GET", f"{R}/vehicles/{i.vehicle_a}/notifications", None),
        ("POST", f"{R}/vehicles/{i.vehicle_a}/accept-load/{i.loose_load}", None),
        ("POST", f"{R}/notifications/{i.note}/read", None),
        ("POST", f"{R}/trips/plan", {"vehicle_id": i.vehicle_a, "load_ids": [i.loose_load]}),
        ("GET", f"{R}/trips/{i.trip}", None),
        ("POST", f"{R}/trips/{i.trip}/start", None),
        ("POST", f"{R}/trips/{i.trip}/cancel", None),
        ("POST", f"{R}/trips/{i.trip}/stops/{i.stop_pickup}/complete", None),
    ]
    for method, path, body in attempts:
        response = await world.call("driver_b", method, path, json=body)
        assert response.status_code == 404, (method, path, response.text)
        assert response.json()["detail"] == "Not found."

    # ...and nothing changed.
    assert _vehicle_state(world, i.vehicle_a) == "available"
    assert _stop_state(world, i.stop_pickup) == "pending"


@pytest.mark.anyio
async def test_driver_b_cannot_use_own_trip_with_a_stop_of_another_trip(world):
    """The guard passes (B's own vehicle/trip); the component itself rejects a foreign stop."""
    from farmnex_routes.models import RtTrip

    with world.rdb.session_scope() as s:
        trip_b = RtTrip(vehicle_id=world.ids.vehicle_b, start_lat=18.5, start_lng=73.8)
        s.add(trip_b)
        s.commit()
        trip_b_id = trip_b.id
    response = await world.call("driver_b", "POST", f"{R}/trips/{trip_b_id}/stops/{world.ids.stop_pickup}/complete")
    assert response.status_code == 404
    assert _stop_state(world, world.ids.stop_pickup) == "pending"


@pytest.mark.anyio
async def test_buyer_and_farmer_cannot_complete_stops_or_drive(world):
    i = world.ids
    for who in ("buyer", "farmer", "other_buyer"):
        response = await world.call(who, "POST", f"{R}/trips/{i.trip}/stops/{i.stop_drop}/complete")
        assert response.status_code == 404, who
        response = await world.call(who, "POST", f"{R}/trips/{i.trip}/start")
        assert response.status_code == 404, who
        response = await world.call(who, "GET", f"{R}/vehicles/{i.vehicle_a}")
        assert response.status_code == 404, who
    assert _stop_state(world, i.stop_drop) == "pending"


@pytest.mark.anyio
async def test_driver_a_can_use_own_vehicle_and_trip(world):
    i = world.ids
    assert (await world.call("driver_a", "GET", f"{R}/vehicles/{i.vehicle_a}")).status_code == 200
    assert (await world.call("driver_a", "GET", f"{R}/vehicles/{i.vehicle_a}/notifications")).status_code == 200
    assert (await world.call("driver_a", "POST", f"{R}/notifications/{i.note}/read")).status_code == 200
    assert (await world.call("driver_a", "GET", f"{R}/trips/{i.trip}")).status_code == 200

    done = await world.call("driver_a", "POST", f"{R}/trips/{i.trip}/stops/{i.stop_pickup}/complete")
    assert done.status_code == 200, done.text
    assert done.json()["load_status"] == "picked_up"
    assert _stop_state(world, i.stop_pickup) == "done"


@pytest.mark.anyio
async def test_trips_plan_passes_the_body_on_for_the_owner(world):
    """Owner: the guard lets it through and the endpoint still gets the JSON body (its own error, not the guard's)."""
    from farmnex_routes.models import RtVehicle

    with world.rdb.session_scope() as s:  # a vehicle of driver A without a trip
        s.add(RtVehicle(id="veh-a2", driver_user_id=str(world.people["driver_a"].public_id),
                        vehicle_number="MH12AB9999", capacity_kg=1000, base_lat=18.5, base_lng=73.8))
        s.commit()
    response = await world.call("driver_a", "POST", f"{R}/trips/plan", json={"vehicle_id": "veh-a2", "load_ids": ["nope"]})
    assert response.status_code == 404
    assert "Loads not found" in response.json()["detail"]

    # no vehicle / bad body -> denied by the guard, never a 500
    for body in ({}, {"vehicle_id": None}, {"vehicle_id": 5}, ["x"]):
        response = await world.call("driver_a", "POST", f"{R}/trips/plan", json=body)
        assert response.status_code == 404, body
    response = await world.call("driver_a", "POST", f"{R}/trips/plan", content=b"not json",
                                headers={"content-type": "application/json"})
    assert response.status_code in (404, 422)  # never a 500, never allowed through


# --- loads and order delivery ---------------------------------------------------------


@pytest.mark.anyio
async def test_load_and_delivery_visible_to_its_people_only(world):
    i = world.ids
    for who in ("farmer", "buyer", "manager"):
        assert (await world.call(who, "GET", f"{R}/loads/{i.load}")).status_code == 200, who
        assert (await world.call(who, "GET", f"{R}/loads/{i.load}/track")).status_code == 200, who
        response = await world.call(who, "GET", f"{R}/orders/order-1/delivery")
        assert response.status_code == 200, who
        assert response.json()["load_id"] == i.load

    # the driver of the trip may read the load, but not an unrelated one
    assert (await world.call("driver_a", "GET", f"{R}/loads/{i.load}")).status_code == 200
    assert (await world.call("driver_a", "GET", f"{R}/loads/{i.loose_load}")).status_code == 404

    for who in ("other_buyer", "driver_b"):
        assert (await world.call(who, "GET", f"{R}/loads/{i.load}")).status_code == 404, who
        assert (await world.call(who, "GET", f"{R}/loads/{i.load}/track")).status_code == 404, who
        assert (await world.call(who, "GET", f"{R}/orders/order-1/delivery")).status_code == 404, who


@pytest.mark.anyio
async def test_staff_can_read_but_missing_things_are_404(world):
    assert (await world.call("manager", "GET", f"{R}/vehicles/{world.ids.vehicle_b}")).status_code == 200
    assert (await world.call("manager", "GET", f"{R}/vehicles/missing")).status_code == 404


@pytest.mark.anyio
async def test_blocked_routes_are_unreachable_even_for_staff(world):
    for who in ("manager", "driver_a"):
        for method, path in (
            ("POST", f"{R}/loads"),
            ("GET", f"{R}/loads"),
            ("GET", f"{R}/vehicles"),
            ("PUT", f"{R}/vehicles/{world.ids.vehicle_a}"),
            ("POST", f"{R}/loads/{world.ids.loose_load}/cancel"),
            ("POST", f"{R}/orders/order-2/cancel-delivery"),
        ):
            response = await world.call(who, method, path, json={})
            assert response.status_code in (404, 405), (who, method, path)
    from farmnex_routes.models import RtLoad

    with world.rdb.session_scope() as s:
        assert s.get(RtLoad, world.ids.loose_load).status == "pending"


# --- vehicle endpoints (logistics_host) -----------------------------------------------

VEHICLE = {
    "vehicle_number": "MH12 AB 1234",
    "vehicle_type": "tempo",
    "capacity_kg": 1500,
    "rate_per_ton_km": 9.5,
    "base_lat": 18.52,
    "base_lng": 73.85,
    "base_label": "Pune",
}


@pytest.mark.anyio
async def test_driver_registers_vehicle_identity_from_token(world):
    body = VEHICLE | {"driver_user_id": "someone-else", "owner_role": "farmer", "status": "on_trip", "id": "hack"}
    response = await world.call("driver_a", "POST", f"{L}/vehicles", json=body)
    assert response.status_code == 201, response.text
    out = response.json()
    driver = world.people["driver_a"]
    assert out["driver_user_id"] == str(driver.public_id)
    assert out["driver_phone"] == driver.phone_number
    assert out["driver_name"] == "Test Delivery_Agent"
    assert out["owner_role"] == "transporter" and out["status"] == "available"
    assert out["id"] != "hack" and out["vehicle_number"] == "MH12AB1234"

    mine = await world.call("driver_a", "GET", f"{L}/my-vehicles")
    assert out["id"] in [v["id"] for v in mine.json()]
    theirs = await world.call("driver_b", "GET", f"{L}/my-vehicles")
    assert out["id"] not in [v["id"] for v in theirs.json()]


@pytest.mark.anyio
async def test_farmer_can_register_own_vehicle_but_buyer_cannot(world):
    farmer = await world.call("farmer", "POST", f"{L}/vehicles", json=VEHICLE)
    assert farmer.status_code == 201 and farmer.json()["owner_role"] == "farmer"
    assert (await world.call("buyer", "POST", f"{L}/vehicles", json=VEHICLE)).status_code == 403
    assert (await world.call("manager", "POST", f"{L}/vehicles", json=VEHICLE)).status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        {"vehicle_type": "spaceship"},
        {"capacity_kg": 0},
        {"capacity_kg": -5},
        {"rate_per_ton_km": 0},
        {"base_lat": 123},
        {"base_lng": None},
        {"vehicle_number": "AB"},
        {"del": "rate_per_ton_km"},
        {"del": "base_lat"},
    ],
)
async def test_vehicle_input_is_validated(world, change):
    body = dict(VEHICLE)
    if "del" in change:
        body.pop(change["del"])
    else:
        body.update(change)
    response = await world.call("driver_a", "POST", f"{L}/vehicles", json=body)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_only_the_driver_can_edit_a_vehicle(world):
    created = (await world.call("driver_a", "POST", f"{L}/vehicles", json=VEHICLE)).json()
    path = f"{L}/vehicles/{created['id']}"

    assert (await world.call("driver_b", "PATCH", path, json={"rate_per_ton_km": 1})).status_code == 404
    assert (await world.call("manager", "PATCH", path, json={"rate_per_ton_km": 1})).status_code == 404
    assert (await world.call("driver_a", "PATCH", f"{L}/vehicles/missing", json={"capacity_kg": 5})).status_code == 404

    changed = await world.call(
        "driver_a", "PATCH", path,
        json={"rate_per_ton_km": 11, "driver_user_id": "someone-else", "status": "offline", "capacity_kg": 900},
    )
    assert changed.status_code == 200, changed.text
    out = changed.json()
    assert out["rate_per_ton_km"] == 11 and out["capacity_kg"] == 900
    assert out["driver_user_id"] == str(world.people["driver_a"].public_id)
    assert out["status"] == "available"
    assert out["vehicle_number"] == "MH12AB1234"  # untouched

    bad = await world.call("driver_a", "PATCH", path, json={"vehicle_type": "spaceship"})
    assert bad.status_code == 422


@pytest.mark.anyio
async def test_vehicle_cap_and_no_edit_during_a_trip(world):
    from app.modules.logistics_host import MAX_VEHICLES_PER_USER
    from farmnex_routes.models import RtVehicle

    first = None
    for _ in range(MAX_VEHICLES_PER_USER):
        response = await world.call("farmer", "POST", f"{L}/vehicles", json=VEHICLE)
        assert response.status_code == 201
        first = first or response.json()["id"]
    assert (await world.call("farmer", "POST", f"{L}/vehicles", json=VEHICLE)).status_code == 409

    with world.rdb.session_scope() as s:
        s.get(RtVehicle, first).status = "on_trip"
        s.commit()
    response = await world.call("farmer", "PATCH", f"{L}/vehicles/{first}", json={"capacity_kg": 10})
    assert response.status_code == 409


def test_driver_cannot_handle_their_own_load(world, tmp_path):
    """S33: a farmer/buyer who also drives must not plan, accept or complete a delivery of their own load."""
    from farmnex_routes.db import session_scope
    from farmnex_routes.models import RtLoad

    from app.modules import routes_host

    def load(**kw):
        return RtLoad(id=str(uuid.uuid4()), farmer_name="F", buyer_name="B", crop="Tomato", weight_kg=10,
                      pickup_lat=1, pickup_lng=1, pickup_address="a", drop_lat=2, drop_lng=2, drop_address="b", **kw)

    with session_scope() as session:
        mine = load(farmer_id="me", buyer_id="x")
        theirs = load(farmer_id="other", buyer_id="y")
        on_trip = load(farmer_id="me", buyer_id="x", trip_id="trip-1")
        session.add_all([mine, theirs, on_trip])
        session.flush()
        assert routes_host._driver_is_party(session, "me", load_ids=mine.id)
        assert routes_host._driver_is_party(session, "me", load_ids=[theirs.id, mine.id])
        assert not routes_host._driver_is_party(session, "me", load_ids=[theirs.id])
        assert routes_host._driver_is_party(session, "me")  # "plan whatever is pending" would pick mine
        assert routes_host._driver_is_party(session, "me", trip_id="trip-1")
        assert not routes_host._driver_is_party(session, "someone-else", trip_id="trip-1")
