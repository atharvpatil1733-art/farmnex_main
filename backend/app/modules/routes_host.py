"""FarmNex glue for the route optimizer (docs/integration/route-optimizer.md).

Loaded by `wiring.py` when ENABLE_ROUTE_OPTIMIZER=true. `farmnex_routes` reads its settings the
moment it is imported, so it is imported inside `mount` (after the database URL check), never at
the top of this file: a bad ROUTES_* setting only disables the route optimizer, never the backend.
It also registers the delivery listener (Slip 3, in logistics_host.py) once.

What is exposed (everything else in the package is left out on purpose):
  * guarded routes  -> /api/v2/routes/...  login + ownership guard, "not yours" is a 404
  * public tracking -> /api/v2/routes/track/{trip_id}[/view]  (private share link, no login)
  * /api/v2/logistics/...  our own vehicle endpoints (app/modules/logistics_host.py)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.engine import make_url

from app.api.dependencies.current_user import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

# Staff who may use every guarded route.
_STAFF_ROLES = frozenset({"LOGISTICS_MANAGER", "ADMIN", "SUPER_ADMIN"})

# Routes we expose behind login + guard. Anything not listed here or in _PUBLIC is NOT mounted,
# so a route added to the component later stays unreachable until someone adds it here.
# (Not exposed at all: PUT /vehicles/{id}, GET /vehicles, POST /loads, GET /loads,
#  POST /loads/{id}/cancel, POST /orders/{id}/cancel-delivery.)
_GUARDED = frozenset(
    {
        ("/vehicles/{vehicle_id}", "GET"),
        ("/vehicles/{vehicle_id}/status", "PATCH"),
        ("/vehicles/{vehicle_id}/location", "POST"),
        ("/vehicles/{vehicle_id}/current-trip", "GET"),
        ("/vehicles/{vehicle_id}/backhaul", "GET"),
        ("/vehicles/{vehicle_id}/notifications", "GET"),
        ("/vehicles/{vehicle_id}/accept-load/{load_id}", "POST"),
        ("/notifications/{notification_id}/read", "POST"),
        ("/trips/plan", "POST"),
        ("/trips/{trip_id}", "GET"),
        ("/trips/{trip_id}/start", "POST"),
        ("/trips/{trip_id}/cancel", "POST"),
        ("/trips/{trip_id}/stops/{stop_id}/complete", "POST"),
        ("/loads/{load_id}", "GET"),
        ("/loads/{load_id}/track", "GET"),
        ("/orders/{order_id}/delivery", "GET"),
    }
)
# The live map opens in a WebView whose JavaScript polls the JSON without our token. Trip ids are
# random UUIDs, so the link works like a private share link (prototype trade-off, see the guide).
_PUBLIC = frozenset({("/track/{trip_id}", "GET"), ("/track/{trip_id}/view", "GET")})


def _check_database_url() -> None:
    """The component is synchronous: it needs its own URL, never our async DATABASE_URL or SQLite."""
    raw = os.getenv("ROUTES_DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "ROUTES_DATABASE_URL is not set. Use the Supabase session pooler URL: "
            "postgresql://...:5432/postgres?sslmode=require"
        )
    try:
        url = make_url(raw)
    except Exception:  # SQLAlchemy's message would quote the URL (and the password)
        raise RuntimeError("ROUTES_DATABASE_URL is not a valid database URL.") from None
    if url.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}:
        raise RuntimeError(
            "ROUTES_DATABASE_URL must be a plain PostgreSQL URL (postgresql://... or "
            "postgresql+psycopg://...), not SQLite or asyncpg."
        )


# --------------------------------------------------------------------- ownership checks (sync)
# These run in a worker thread with the component's own sync session.


def _driver_of_vehicle(session: Any, vehicle_id: Any, me: str) -> bool:
    from farmnex_routes.models import RtVehicle

    if not isinstance(vehicle_id, str) or not vehicle_id:
        return False
    vehicle = session.get(RtVehicle, vehicle_id)
    return vehicle is not None and vehicle.driver_user_id == me


def _driver_of_trip(session: Any, trip_id: str, me: str) -> bool:
    from farmnex_routes.models import RtTrip

    trip = session.get(RtTrip, trip_id)
    return trip is not None and _driver_of_vehicle(session, trip.vehicle_id, me)


def _driver_of_notification(session: Any, notification_id: str, me: str) -> bool:
    from farmnex_routes.models import RtNotification

    note = session.get(RtNotification, notification_id)
    return note is not None and _driver_of_vehicle(session, note.vehicle_id, me)


def _party_of_load(session: Any, load_id: str, me: str) -> bool:
    """The load's farmer or buyer, or the driver of the trip it is on."""
    from farmnex_routes.models import RtLoad

    load = session.get(RtLoad, load_id)
    if load is None:
        return False
    if me in (load.farmer_id, load.buyer_id):
        return True
    return bool(load.trip_id) and _driver_of_trip(session, load.trip_id, me)


def _party_of_order_load(session: Any, order_id: str, me: str) -> bool:
    """The farmer or buyer of the load created for this order."""
    from farmnex_routes.models import RtLoad
    from sqlalchemy import or_, select

    found = session.scalar(
        select(RtLoad.id)
        .where(RtLoad.order_id == order_id, or_(RtLoad.farmer_id == me, RtLoad.buyer_id == me))
        .limit(1)
    )
    return found is not None


def _driver_is_party(session: Any, me: str, *, load_ids: Any = None, trip_id: str | None = None) -> bool:
    """True if `me` is the farmer or buyer of the loads involved (or of any load, when none are named).

    A farmer/buyer who also drives a vehicle must not plan or complete a delivery of their own load,
    or they could "deliver" it to themselves and release the held money (S33).
    """
    from farmnex_routes.models import RtLoad
    from sqlalchemy import or_, select

    query = select(RtLoad.id).where(or_(RtLoad.farmer_id == me, RtLoad.buyer_id == me))
    if trip_id is not None:
        query = query.where(RtLoad.trip_id == trip_id)
    elif isinstance(load_ids, list) and load_ids:
        query = query.where(RtLoad.id.in_([str(x) for x in load_ids]))
    elif load_ids is not None and not isinstance(load_ids, list):
        query = query.where(RtLoad.id == str(load_ids))
    else:  # "plan with whatever is pending": refuse if the driver has any load of their own
        query = query.where(RtLoad.trip_id.is_(None))
    return session.scalar(query.limit(1)) is not None


def _allowed(path: str, params: dict[str, Any], body: Any, me: str) -> bool:
    from farmnex_routes.db import session_scope

    with session_scope() as session:
        # Order matters: accept-load has both ids and must be checked as the vehicle's driver.
        if "{vehicle_id}" in path:
            if not _driver_of_vehicle(session, params.get("vehicle_id"), me):
                return False
            if "{load_id}" in path:  # accept-load
                return not _driver_is_party(session, me, load_ids=params.get("load_id"))
            return True
        if "{trip_id}" in path:
            return _driver_of_trip(session, params["trip_id"], me) and not _driver_is_party(
                session, me, trip_id=params["trip_id"]
            )
        if "{notification_id}" in path:
            return _driver_of_notification(session, params["notification_id"], me)
        if "{load_id}" in path:
            return _party_of_load(session, params["load_id"], me)
        if "{order_id}" in path:
            return _party_of_order_load(session, params["order_id"], me)
        if path.endswith("/trips/plan"):
            vehicle_id = body.get("vehicle_id") if isinstance(body, dict) else None
            return _driver_of_vehicle(session, vehicle_id, me) and not _driver_is_party(
                session, me, load_ids=body.get("load_ids") if isinstance(body, dict) else None
            )
        return False  # unknown route -> deny by default


async def routes_guard(request: Request, user: User = Depends(get_current_user)) -> None:
    """Login is not enough: only the people involved (or staff) may use a guarded route."""
    if user.role is not None and user.role.name.upper() in _STAFF_ROLES:
        return

    # The route's own template, e.g. ".../trips/{trip_id}/start": only use "contains"/"endswith".
    path = request.scope["route"].path
    body = None
    if path.endswith("/trips/plan"):
        try:
            body = await request.json()  # the endpoint still receives the body
        except ValueError:
            body = None

    allowed = await run_in_threadpool(_allowed, path, dict(request.path_params), body, str(user.public_id))
    if not allowed:
        raise HTTPException(404, "Not found.")


def _build_routers() -> tuple[APIRouter, APIRouter]:
    """Pick the allowed routes out of the component's router (matching on path + method)."""
    from farmnex_routes import router as component_router

    guarded = APIRouter()
    public = APIRouter()
    for route in component_router.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if any((path, m) in _PUBLIC for m in methods):
            public.routes.append(route)
        elif any((path, m) in _GUARDED for m in methods):
            guarded.routes.append(route)
    return guarded, public


_listener_registered = False


def _register_delivery_listener(listener: Any) -> None:
    """Slip 3: the component calls `listener(load, status)` after each delivery step. Registered once
    per process, even if mount() runs again (tests build fresh apps)."""
    global _listener_registered
    if _listener_registered:
        return
    from farmnex_routes import on_delivery_update

    on_delivery_update(listener)
    _listener_registered = True


def mount(app: FastAPI) -> None:
    _check_database_url()

    guarded, public = _build_routers()  # imports farmnex_routes here on purpose (shared rule 3)
    from . import logistics_host

    _register_delivery_listener(logistics_host.on_delivery)
    app.include_router(
        guarded,
        prefix="/api/v2/routes",
        dependencies=[Depends(get_current_user), Depends(routes_guard)],
    )
    app.include_router(public, prefix="/api/v2/routes")
    app.include_router(
        logistics_host.router,
        prefix="/api/v2/logistics",
        dependencies=[Depends(get_current_user)],
    )
