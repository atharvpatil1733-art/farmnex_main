"""Vehicle and order-delivery endpoints (docs/integration/route-optimizer.md, "Host endpoints we add",
"Slip 2" and "Slip 3").

Mounted at /api/v2/logistics by `routes_host.mount()` (with login), so this file is only imported
once the route optimizer is switched on and its database URL is valid. `rt_vehicles` is the
source of truth for vehicles; there is no core vehicles table.

Identity comes only from the login token: the driver is always the logged-in user, and clients
can't send driver ids, owner role or status. Loads are made only here, from the order's own rows.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from farmnex_routes import create_delivery_for_order, find_load_for_order, upsert_vehicle
from farmnex_routes.db import session_scope
from farmnex_routes.models import RtLoad, RtVehicle
from farmnex_routes.schemas import LoadCreated, VehicleOut
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.current_user import get_current_user
from app.api.dependencies.roles import require_roles
from app.core.database import AsyncSessionLocal, get_db
from app.models.farm import Farm
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from app.services import wallet_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Logistics"])

STAFF_ROLES = ("LOGISTICS_MANAGER", "ADMIN", "SUPER_ADMIN")

MAX_VEHICLES_PER_USER = 5

VehicleType = Literal["pickup", "tempo", "mini_truck", "truck"]


class VehicleCreate(BaseModel):
    vehicle_number: str = Field(min_length=4, max_length=20, examples=["MH12AB1234"])
    vehicle_type: VehicleType
    capacity_kg: float = Field(gt=0, le=40000)
    refrigerated: bool = False
    rate_per_ton_km: float = Field(gt=0, description="Rs per tonne per km")
    base_lat: float = Field(ge=-90, le=90)
    base_lng: float = Field(ge=-180, le=180)
    base_label: str | None = Field(None, max_length=200)


class VehicleUpdate(BaseModel):
    """Only these fields can change; leave a field out to keep it."""

    vehicle_number: str | None = Field(None, min_length=4, max_length=20)
    vehicle_type: VehicleType | None = None
    capacity_kg: float | None = Field(None, gt=0, le=40000)
    refrigerated: bool | None = None
    rate_per_ton_km: float | None = Field(None, gt=0)
    base_lat: float | None = Field(None, ge=-90, le=90)
    base_lng: float | None = Field(None, ge=-180, le=180)
    base_label: str | None = Field(None, max_length=200)


def _driver_name(user: User) -> str | None:
    name = " ".join(part for part in (user.first_name, user.surname) if part)
    return name[:120] or None


def _create_vehicle(fields: dict) -> RtVehicle | None:
    with session_scope() as session:
        owned = session.scalar(
            select(func.count()).select_from(RtVehicle).where(RtVehicle.driver_user_id == fields["driver_user_id"])
        )
        if owned >= MAX_VEHICLES_PER_USER:
            return None
        return upsert_vehicle(session, str(uuid4()), **fields)


def _update_vehicle(vehicle_id: str, me: str, fields: dict) -> RtVehicle | None:
    with session_scope() as session:
        vehicle = session.get(RtVehicle, vehicle_id)
        if vehicle is None or vehicle.driver_user_id != me:
            return None
        if vehicle.status == "on_trip":
            raise HTTPException(409, "Finish or cancel the current trip before editing the vehicle.")
        return upsert_vehicle(session, vehicle_id, **fields)


def _list_vehicles(me: str) -> list[RtVehicle]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(RtVehicle).where(RtVehicle.driver_user_id == me).order_by(RtVehicle.created_at)
            )
        )


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
async def register_vehicle(
    body: VehicleCreate,
    user: User = Depends(require_roles("DELIVERY_AGENT", "FARMER")),
):
    """A driver registers a truck. A farmer can register their own (self-delivery)."""
    fields = body.model_dump()
    fields.update(
        driver_user_id=str(user.public_id),
        driver_name=_driver_name(user),
        driver_phone=user.phone_number,
        owner_role="farmer" if user.role.name.upper() == "FARMER" else "transporter",
    )
    vehicle = await run_in_threadpool(_create_vehicle, fields)
    if vehicle is None:
        raise HTTPException(409, f"You can register at most {MAX_VEHICLES_PER_USER} vehicles.")
    return vehicle


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: str,
    body: VehicleUpdate,
    user: User = Depends(get_current_user),
):
    """Change rate, capacity, base... Only that vehicle's driver; anyone else gets 404."""
    fields = body.model_dump(exclude_none=True)
    vehicle = await run_in_threadpool(_update_vehicle, vehicle_id, str(user.public_id), fields)
    if vehicle is None:
        raise HTTPException(404, "Vehicle not found.")
    return vehicle


@router.get("/my-vehicles", response_model=list[VehicleOut])
async def my_vehicles(user: User = Depends(get_current_user)):
    return await run_in_threadpool(_list_vehicles, str(user.public_id))


# --------------------------------------------------------------------- Slip 2: order -> load (S26)
# A CONFIRMED order becomes one load (a job for a truck). Everything comes from the order's own rows;
# the client sends only the order id.

KG_PER_UNIT = {"kg": 1, "kgs": 1, "quintal": 100, "quintals": 100,
               "ton": 1000, "tons": 1000, "tonne": 1000, "tonnes": 1000}
# Items that haven't left the farm yet (the pickup moves them to SHIPPED).
BEFORE_PICKUP = ("ACTIVE", "PLACED", "CONFIRMED", "PACKED")


def weight_kg(quantity: Decimal, unit: str | None) -> float:
    factor = KG_PER_UNIT.get((unit or "").strip().lower())
    if factor is None:
        raise HTTPException(422, f"Transport needs the weight in kg, quintal or ton, not '{unit}'.")
    return float(quantity * factor)


def _point(lat: Any, lng: Any) -> tuple[float, float] | None:
    """A usable map point, or None (missing, out of range, or 0,0 - a trip to the ocean)."""
    if lat is None or lng is None:
        return None
    lat, lng = float(lat), float(lng)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return None
    return lat, lng


def _text(*parts: Any, limit: int = 255) -> str:
    return ", ".join(str(p) for p in parts if p)[:limit] or "-"


def _create_load(fields: dict) -> tuple[RtLoad, bool]:
    with session_scope() as session:
        return create_delivery_for_order(session, **fields)


@router.post("/orders/{order_public_id}/request-transport", response_model=LoadCreated)
async def request_transport(
    order_public_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Book a truck for a CONFIRMED order: the order's farmer (or logistics staff). Anyone else gets
    404. Safe to call twice - the same load comes back (`already_existed`)."""
    order = await db.scalar(select(Order).where(Order.public_id == order_public_id))
    items = [] if order is None else list(
        await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id))
    )
    is_staff = user.role is not None and user.role.name.upper() in STAFF_ROLES
    if order is None or not (is_staff or any(item.seller_id == user.id for item in items)):
        raise HTTPException(404, "Order not found.")
    if order.status != "CONFIRMED":
        raise HTTPException(409, "Only a confirmed order can get transport.")
    live = [item for item in items if item.status != "CANCELLED"]
    if not live:
        raise HTTPException(409, "Every item in this order was cancelled.")
    if len({item.farm_id for item in live}) != 1 or len({item.seller_id for item in live}) != 1:
        raise HTTPException(409, "This order's crops come from more than one farm; book them one by one.")

    farm = await db.get(Farm, live[0].farm_id)
    pickup = _point(farm.latitude, farm.longitude) if farm else None
    if pickup is None:
        raise HTTPException(422, "Add your farm location first: the truck needs a pickup point.")
    address = order.delivery_address_snapshot or {}
    drop = _point(address.get("latitude"), address.get("longitude"))
    if drop is None:
        raise HTTPException(422, "The buyer's delivery address has no map location.")
    weight = sum(weight_kg(item.quantity, item.unit) for item in live)

    farmer = await db.get(User, live[0].seller_id)
    buyer = await db.get(User, order.buyer_id)
    if farmer is None or buyer is None:  # only very old rows can miss a user
        raise HTTPException(409, "This order's farmer or buyer account no longer exists.")
    fields = {
        "order_id": str(order.public_id),
        "farmer_id": str(farmer.public_id),
        "farmer_name": _driver_name(farmer) or "Farmer",
        "farmer_phone": (farmer.phone_number or "")[:20] or None,
        "buyer_id": str(buyer.public_id),
        "buyer_name": _driver_name(buyer) or "Buyer",
        "buyer_phone": (buyer.phone_number or "")[:20] or None,
        "crop": _text(*dict.fromkeys(item.title_snapshot for item in live), limit=60),
        "weight_kg": round(weight, 3),
        "pickup_lat": pickup[0],
        "pickup_lng": pickup[1],
        "pickup_address": _text(farm.farm_name, farm.address_line_1, farm.village, farm.city, farm.district,
                                farm.state, farm.postal_code),
        "drop_lat": drop[0],
        "drop_lng": drop[1],
        "drop_address": _text(*(address.get(key) for key in (
            "address_line_1", "address_line_2", "landmark", "village", "city", "district", "state",
            "postal_code"))),
        "priority": 0,  # Crop Rescue sales are not core orders, so every order load is "normal"
    }
    load, created = await run_in_threadpool(_create_load, fields)
    return LoadCreated.model_validate(load).model_copy(update={"already_existed": not created})


# --------------------------------------------------------------------- Slip 3: load -> order (S26)
# The driver's pickup moves the order's items to SHIPPED. The driver's drop only records "delivered" on
# the load. The order becomes DELIVERED, and the held money goes to the farmer (S20's release, which
# pays out only once), when the BUYER also confirms receipt (S33: two-party confirmation).


def on_delivery(load: RtLoad, status: str) -> None:
    """Listener registered by `routes_host.mount()`. The component calls it (sync) inside the driver's
    request, which runs in one of FastAPI's worker threads, so we can hop back to async code."""
    if not load.order_id or status not in ("picked_up", "delivered"):
        return
    try:
        order_public_id = UUID(load.order_id)
    except ValueError:
        return  # not one of our orders (e.g. a hand-made demo load)
    try:
        anyio.from_thread.run(apply_delivery_status, order_public_id, status)
    except Exception:
        # The delivery itself is already saved; fix the order by hand with POST .../resync.
        logger.exception("Order %s was NOT updated to '%s'; use POST /api/v2/logistics/orders/%s/resync",
                         order_public_id, status, order_public_id)


async def apply_delivery_status(order_public_id: UUID, status: str) -> tuple[str | None, Decimal | None]:
    """Copy a load's status onto its order. Safe to run twice. Returns (order status, money released)."""
    async with AsyncSessionLocal() as session:
        order = await session.scalar(
            select(Order).where(Order.public_id == order_public_id).with_for_update()
        )
        if order is None or order.status in ("PLACED", "CANCELLED"):
            logger.warning("Load for order %s is %s, but the order is %s: not changed.",
                           order_public_id, status, order.status if order else "missing")
            return (order.status if order else None), None
        items = update(OrderItem).where(OrderItem.order_id == order.id)
        if status == "picked_up":
            await session.execute(items.where(OrderItem.status.in_(BEFORE_PICKUP)).values(status="SHIPPED"))
        # "delivered": nothing to change here - the buyer's confirmation finishes the order.
        await session.commit()
        return order.status, None


def _driver_marked_delivered(order_id: str) -> bool:
    with session_scope() as session:
        return session.scalar(
            select(RtLoad.id).where(RtLoad.order_id == order_id, RtLoad.status == "delivered").limit(1)
        ) is not None


async def confirm_delivery(order_public_id: UUID) -> tuple[str, Decimal | None]:
    """The buyer's confirmation: items and order become DELIVERED, then the held money is released
    (once). Safe to run twice."""
    async with AsyncSessionLocal() as session:
        order = await session.scalar(
            select(Order).where(Order.public_id == order_public_id).with_for_update()
        )
        if order is None or order.status in ("PLACED", "CANCELLED"):
            raise HTTPException(409, "This order cannot be marked delivered.")
        await session.execute(
            update(OrderItem)
            .where(OrderItem.order_id == order.id, OrderItem.status.not_in(("CANCELLED", "DELIVERED")))
            .values(status="DELIVERED")
        )
        order.status = "DELIVERED"
        await session.commit()
    # after the commit: release checks the order is DELIVERED
    return "DELIVERED", await wallet_service.release_for_order(order_public_id)


class ConfirmOut(BaseModel):
    order_status: str
    released: Decimal | None


@router.post("/orders/{order_public_id}/confirm-delivery", response_model=ConfirmOut)
async def confirm_delivery_endpoint(
    order_public_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The order's buyer says the goods arrived. Needs the driver to have marked the drop as done
    first. Anyone but the buyer gets 404. Calling twice is fine; the money moves once."""
    order = await db.scalar(select(Order).where(Order.public_id == order_public_id))
    if order is None or order.buyer_id != user.id:
        raise HTTPException(404, "Order not found.")
    if not await run_in_threadpool(_driver_marked_delivered, str(order_public_id)):
        raise HTTPException(409, "The driver has not marked this delivery as done yet.")
    order_status, released = await confirm_delivery(order_public_id)
    return ConfirmOut(order_status=order_status, released=released)


class ResyncOut(BaseModel):
    load_status: str
    order_status: str | None
    released: Decimal | None


def _find_load(order_id: str) -> RtLoad | None:
    with session_scope() as session:
        return find_load_for_order(session, order_id)


@router.post("/orders/{order_public_id}/resync", response_model=ResyncOut)
async def resync_order(
    order_public_id: UUID,
    user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Staff fix for the demo: copy the delivery's status onto the order again (if the automatic
    update failed - see the logs). Releasing money still happens only once."""
    load = await run_in_threadpool(_find_load, str(order_public_id))
    if load is None:
        raise HTTPException(404, "This order has no delivery.")
    order_status, released = None, None
    if load.status in ("picked_up", "delivered"):
        order_status, released = await apply_delivery_status(order_public_id, load.status)
    return ResyncOut(load_status=load.status, order_status=order_status, released=released)
