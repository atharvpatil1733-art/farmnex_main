# Route optimizer → main app

**Source repo:** `atharvpatil1733-art/farmnex_route_optimization` (commit: see `docs/STATUS.md` → Components;
the pip pin below is the one to install). Package name **`farmnex_routes`**, tables **`rt_*`**.
**What it does:** keeps a copy of each vehicle, turns an order into a "load", pools nearby loads
into one truck, finds the best pickup/drop order (Crop Rescue loads first), quotes each farmer's fare
(road km × tonnes × vehicle rate), offers return-trip loads (backhaul), and shows live GPS tracking
with ETAs while the driver app is open.
**Time budget (prototype):** ~10–14 h total — backend 5–6 h, Flutter 5–7 h, demo seeding 1 h.

Read the component's own `docs/LINKING_ORDERS.md` for the idea ("four slips of paper"). **This file
overrides it where they differ**, because that guide was written before it could see this repo. The
differences are marked ⚠️.

Follow the shared rules in `README.md` in this folder.

---

## ⚠️ What's different in FarmNex (read first)

| Component guide assumes | Reality in farmnex_main | What we do |
|---|---|---|
| The main app has a vehicles table and a "register vehicle" endpoint | **No vehicles table in the backend.** Vehicles exist only as demo data in Flutter `logistics_provider.dart` | `rt_vehicles` becomes the source of truth. We add 3 small host endpoints (below) that call `upsert_vehicle`. No new core table. |
| `DATABASE_URL` works for both | Ours is `postgresql+asyncpg://…` (async). The component is **sync** (`psycopg`). Its URL fixer only rewrites `postgres://`/`postgresql://`, so our URL breaks it. If no URL is found it **silently uses a local SQLite file** — on FastAPI Cloud that file is wiped on every redeploy. | Always set **`ROUTES_DATABASE_URL`** (Supabase **session pooler**, port 5432, `postgresql://…?sslmode=require`). `routes_host.py` refuses to mount if it's missing, empty, `sqlite…` or `+asyncpg`. |
| Mount at `/routes`, "protect with your auth" | Login alone isn't enough: any logged-in user could mark someone's load **delivered** (which will release payment) or read driver phones and live locations. | Mount at `/api/v2/routes` with an **allow-list + ownership guard** (below). Endpoints only our server should call are not exposed at all. |
| ids like `order.id`, `driver.id` | Our internal ids are ints; the app only knows `public_id` UUIDs | Always pass `str(x.public_id)` for `order_id`, `farmer_id`, `buyer_id`, `driver_user_id`. Vehicle id = new `uuid4()` string. |
| Listener `@on_delivery_update` calls "your existing wallet release" | Our DB code is **async** while the listener is **sync** | Listener hands off to async code with `anyio.from_thread.run(...)` (explained below). The wallet release exists since S20 (PR 46): module function `release_for_order(order_public_id)` in `app/services/wallet_service.py` — opens its own DB session, needs the order `DELIVERED` first (else `ConflictError`), pays once (a repeat returns `None`). |
| Order confirmation creates the load | The farmer confirms (S18), but confirming does **not** create the load | Slip 2 is a separate call, `request-transport`, made after confirming (decided in S26 — STATUS → Verified facts → "Wave 4 decisions"). |
| Main `deliveries` table | We have `deliveries`, `delivery_tracking_events`, `delivery_proofs` (unused by the app) | **Decision (confirm with Atharv):** for the prototype `rt_loads` is the delivery system; unmount those 3 controllers (FIX_PLAN F1 fast path) so there aren't two competing delivery systems. |

---

## How to install it (pick one, in this order)

1. **pip from GitHub, pinned to a commit** (keeps the import name `farmnex_routes`, which its
   tracking page needs):
   ```
   farmnex-route-optimizer @ git+https://github.com/atharvpatil1733-art/farmnex_route_optimization.git@22d4859
   ```
   Pin a **commit hash**, never `@main` — otherwise a push to the component repo can break the main
   app on its next deploy without anyone changing this repo.
   Put this line in the `dependencies` of **`backend/pyproject.toml`** (that's what FastAPI Cloud
   installs) and the same line in `requirements.txt` (local installs).
2. **If FastAPI Cloud's build can't install from git** (build log shows a git/clone error — whether
   it can is unconfirmed, see STATUS → Verified facts): copy the
   `farmnex_routes/` folder to **`backend/farmnex_routes/`** (top level, next to `app/`, **not** in
   `app/modules/`). Its tracking page loads `static/track.html` with
   `importlib.resources.files("farmnex_routes")`, so the folder must stay importable as exactly
   `farmnex_routes`. Add `psycopg[binary]>=3.1` to `pyproject.toml` and `requirements.txt`, remove the
   git line, and add `"farmnex_routes*"` to `include` under `[tool.setuptools.packages.find]` in
   `pyproject.toml` (today it lists only `app*`, so `pip install .` would leave the folder out).

Check: `python -c "import farmnex_routes, importlib.resources as r; print(r.files('farmnex_routes').joinpath('static/track.html').is_file())"` prints `True`.

---

## Database

- Copy `sql/001_create_route_tables.sql` → `backend/migrations/030_rt_route_tables.sql` (wrapped in `begin; … commit;` as `backend/migrations/README.md` requires, otherwise unchanged;
  it only creates `rt_*` tables and turns on RLS for them). Atharv runs it in the Supabase SQL editor.
- Set `ROUTES_AUTO_CREATE_TABLES=false` (tables come from the SQL file, like every component).
- `ROUTES_DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require`
  (the component converts it to `psycopg` itself and disables prepared statements, so pooler ports
  work).
- **Settings are read when `farmnex_routes` is first imported.** So `load_dotenv()` must run at the
  very top of `app/main.py` (see `README.md` rule 12), and `routes_host.py` must import `farmnex_routes`
  **inside** the mount function, after the flag check — never at the top of a file.

---

## Security: allow-list + ownership guard

Build two sub-routers in `backend/app/modules/routes_host.py` (inside its `mount(app)`) by picking routes out of
`farmnex_routes.router.routes` (match on the route's `path` and `methods`):

**A. Not exposed at all** (our server calls the Python helpers instead):
`PUT /vehicles/{vehicle_id}`, `GET /vehicles` (list), `POST /loads`, `GET /loads` (list),
`POST /loads/{load_id}/cancel`, `POST /orders/{order_id}/cancel-delivery`.

**B. Mounted with login + guard** at `/api/v2/routes` — `dependencies=[Depends(get_current_user), Depends(routes_guard)]`:

| Route (component path) | Who may call |
|---|---|
| `GET /vehicles/{vehicle_id}`, `PATCH /vehicles/{vehicle_id}/status`, `POST /vehicles/{vehicle_id}/location`, `GET /vehicles/{vehicle_id}/current-trip`, `GET /vehicles/{vehicle_id}/backhaul`, `GET /vehicles/{vehicle_id}/notifications`, `POST /vehicles/{vehicle_id}/accept-load/{load_id}` | the vehicle's driver (`rt_vehicles.driver_user_id == str(user.public_id)`) |
| `POST /notifications/{notification_id}/read` | driver of that notification's vehicle |
| `POST /trips/plan` | driver of `body.vehicle_id` (read the JSON body in the guard) |
| `GET /trips/{trip_id}`, `POST /trips/{trip_id}/start`, `POST /trips/{trip_id}/cancel`, `POST /trips/{trip_id}/stops/{stop_id}/complete` | driver of the trip's vehicle |
| `GET /loads/{load_id}`, `GET /loads/{load_id}/track` | the load's farmer or buyer, or the driver of its trip's vehicle |
| `GET /orders/{order_id}/delivery` | the load's farmer or buyer (look up the load by `order_id`) |
| everything above | also LOGISTICS_MANAGER / ADMIN |

Not allowed → **404** (same as "not found"), never 403, so ids can't be probed.

**C. Mounted without login:** `GET /track/{trip_id}` and `GET /track/{trip_id}/view` — the live map
opens in a WebView, and its JavaScript polls the JSON without our token. Trip ids are random UUIDs,
so the link works like a private share link. **Prototype trade-off:** anyone with the link sees the
truck and the driver's phone. Only show the link to that order's farmer/buyer. (Later: short-lived
signed links.)

How the guard works (sketch — keep it this simple):
```python
async def routes_guard(request: Request, user: User = Depends(get_current_user)) -> None:
    if user.role and user.role.name in {"LOGISTICS_MANAGER", "ADMIN", "SUPER_ADMIN"}:
        return
    me = str(user.public_id)
    # The route's own path, WITHOUT our prefix on FastAPI 0.141 (e.g. "/trips/{trip_id}/start"),
    # so only use "contains"/"endswith" checks, never an exact full path.
    path = request.scope["route"].path
    params = dict(request.path_params)
    body = await request.json() if path.endswith("/trips/plan") else None   # endpoint still gets the body (tested)
    ok = await run_in_threadpool(_allowed, path, params, body, me)          # sync DB check off the event loop
    if not ok:
        raise HTTPException(404, "Not found.")

def _allowed(path, p, body, me) -> bool:
    with session_scope() as s:                            # component's sync session
        if "{vehicle_id}" in path:        return _driver_of_vehicle(s, p["vehicle_id"], me)
        if "{trip_id}" in path:           return _driver_of_trip(s, p["trip_id"], me)
        if "{notification_id}" in path:   return _driver_of_notification(s, p["notification_id"], me)
        if "{load_id}" in path:           return _party_of_load(s, p["load_id"], me)
        if "{order_id}" in path:          return _party_of_order_load(s, p["order_id"], me)
        if path.endswith("/trips/plan"):  return _driver_of_vehicle(s, (body or {}).get("vehicle_id"), me)
        return False                                      # unknown route → deny by default
```
Deny by default: a new route added to the component later stays blocked until someone adds a rule.
Check order matters: `/vehicles/{vehicle_id}/accept-load/{load_id}` must be checked as the
**vehicle's driver** (it's listed first above), not as a party of the load.

---

## Driver and manager accounts

Public sign-up allows only FARMER, BUYER, VENDOR (`public_registration_roles` in
`app/core/config.py`, overridable by env). For the prototype: add `DELIVERY_AGENT` to that list via
the env var on FastAPI Cloud (a JSON list: `PUBLIC_REGISTRATION_ROLES=["FARMER","BUYER","VENDOR","DELIVERY_AGENT"]`) (drivers sign up in the app), and create LOGISTICS_MANAGER / ADMIN
accounts with a small one-off script (`backend/scripts/create_staff_user.py`, run by Atharv against
production with the phone number as input). Never make ADMIN or MANAGER a public sign-up role.

## Host endpoints we add (vehicles + demo)

In `backend/app/modules/logistics_host.py`, mounted at `/api/v2/logistics` with login (by `routes_host.mount()`, which also mounts the guarded `farmnex_routes` sub-routers):

| Endpoint | Role | Does |
|---|---|---|
| `POST /vehicles` | DELIVERY_AGENT, or FARMER (self-delivery → `owner_role="farmer"`) | new `str(uuid4())` id → `upsert_vehicle(..., driver_user_id=str(user.public_id), driver_name, driver_phone from the user)` |
| `PATCH /vehicles/{vehicle_id}` | that vehicle's driver | re-calls `upsert_vehicle` (rate/capacity/base change) |
| `GET /my-vehicles` | any | vehicles where `driver_user_id == me` |
| `POST /orders/{order_public_id}/request-transport` | the order's farmer, or LOGISTICS_MANAGER / ADMIN (others → 404; decided in S26) | CONFIRMED orders only; builds and calls `create_delivery_for_order` (Slip 2 below). **Part 2 (S26), not S17** |

Validate inputs here: `vehicle_type` ∈ `pickup | tempo | mini_truck | truck`; `capacity_kg > 0`;
`rate_per_ton_km > 0`; base lat/lng present. These are async endpoints, so call the sync helpers with
`await run_in_threadpool(fn)` — **never** call `session_scope()` directly inside `async def` (it
blocks the whole server while it waits for the database).

---

## Slip 2 — order → load (S26: `request-transport`)

Called by hand after the farmer **confirms** the order (not automatic; there is no "platform transport" field, so every booked order is a normal load):
- `order_id=str(order.public_id)`, `farmer_id=str(seller.public_id)`, `buyer_id=str(buyer.public_id)`.
- Pickup = the listing's farm `latitude/longitude`; drop = `order.delivery_address_snapshot`
  lat/lng. **If either is missing, don't create the load** — return a clear error ("Add your farm
  location") instead of sending 0,0 (the optimizer would plan a trip to the ocean).
- `weight_kg` from quantity + unit: kg ×1, quintal ×100, ton ×1000. Anything else → error.
- `priority=2` for Crop Rescue sales, `1` urgent, else `0`.
- It's idempotent per `order_id` (calling twice returns the same load), so a retry is safe.
- On order cancel → `cancel_delivery_for_order` (only works while the load is `pending`; after that,
  show "contact support").

## Slip 3 — load status → order (listener)

```python
@on_delivery_update
def _on_delivery(load, status):                       # sync, called by the component
    if not load.order_id:
        return
    anyio.from_thread.run(handle_delivery_update, load.order_id, status)   # our async code
```
- This works because the component's endpoints are sync and run in FastAPI's worker threads. Don't
  call it from any other thread.
- `handle_delivery_update` opens its **own** `AsyncSessionLocal()` session, updates the order
  status, and (after F12) releases escrow **only if not already released** (`release_for_order` already guarantees this) — it can be called twice.
- The component logs and swallows listener errors, so a failure here does not undo the delivery.
  Log it clearly and add a manager-only "re-sync order from load" endpoint so it can be fixed by hand
  during the demo.

---

## Flutter

- `RouteApi(ApiClient().dio)` in `lib/core/network/route_api.dart`; all paths `/api/v2/routes/...`
  and `/api/v2/logistics/...`.
- Driver sign-up/log-in: the app must send `DELIVERY_AGENT` (it sends `LOGISTIC` today) and map `DELIVERY_AGENT` / `LOGISTICS_MANAGER` back to its logistics role — S24 fixes `user_model.dart` and the role tile in `auth_dialog.dart`.
- Driver screens (`lib/screens/logistics/logistics_screens.dart`): my vehicle → go online →
  current trip / plan trip → start → stop "picked up / delivered" buttons → notifications + backhaul
  offers. Switch `logistics_provider.dart` off demo data.
- GPS: `geolocator` is already in `pubspec.yaml` (S02); S24 adds the Android location permissions to `AndroidManifest.xml`. Send a ping
  every ~10 s **only while the trip screen is open** (no background GPS). Stop the timer in
  `dispose()`.
- Tracking: order card shows status/ETA from `GET /orders/{id}/delivery`; a **Track** button opens
  `tracking_url` in a WebView (`webview_flutter` is already in `pubspec.yaml`). S24 builds the button as a reusable widget (`screens/logistics/track_delivery_button.dart`); **S28** puts it on the order card, because the orders screen is connected there.
- Farmer **Confirm** + **Book truck** (`request-transport`): no app screen in the prototype — STATUS →
  Verified facts → "Wave 4 decisions".
- Set `ROUTES_PUBLIC_BASE_URL=https://farmnex-a.fastapicloud.dev` (origin only, no path) so tracking
  links are `https` — Android WebViews block `http`.

## Demo seed (S34)

The component repo's `demo/seed_demo.py` and `demo/simulate_driver.py` **don't work here**: they call
`PUT /vehicles`, `POST /loads` and unguarded trip routes under `/routes`, which our backend doesn't
expose (or protects with login + guard). No host endpoint creates a bare load either: a pending load
only comes from `request-transport` on a **CONFIRMED** order. So the demo data is made through the
real flow, with **tokens from environment variables** (no session can log in — STATUS → Verified facts
→ "Wave 5 decisions"):

1. **Driver** (`DELIVERY_AGENT`): `POST /logistics/vehicles` with a base near Pune — the trip planner
   only pools pending loads within 30 km of the vehicle, so put the base near the farms.
2. **Two farmers** (each with a farm that has latitude/longitude — the pickup point): farm → farm crop →
   crop batch → Tomato listing (the S21 rules, STATUS → "Listing / batch / image rules").
3. **One buyer** with a default address that has latitude/longitude (the drop point): a checkout with
   the listings of **both** farmers (`POST /orders` splits it into one order per farmer; do it twice,
   or use three listings, for three loads), then `POST /payments/orders/{id}/pay-demo` for each order.
4. Each **farmer** confirms their own order (`POST /orders/{id}/confirm`). Then the farmer or the
   **manager** (`LOGISTICS_MANAGER`) calls `POST /logistics/orders/{id}/request-transport` → a pending load.
5. **Driver**: go online, plan the trip (`POST /routes/trips/plan`), start it. `simulate_driver.py` does
   the GPS pings and stop completions with the driver's token, for when a real phone isn't used.

Re-running must not make duplicates (check for an existing listing/order first). Never print a token;
the phone numbers of the demo accounts are not written in any file.

## Env vars (`backend/.env.example` + FastAPI Cloud)

```
ENABLE_ROUTE_OPTIMIZER=false
ROUTES_DATABASE_URL=
ROUTES_AUTO_CREATE_TABLES=false
ROUTES_PUBLIC_BASE_URL=https://farmnex-a.fastapicloud.dev
ROUTING_PROVIDER=osrm        # switch to haversine if venue internet is bad
```

## What can go wrong (and how you'll notice)

| Symptom | Cause | Fix |
|---|---|---|
| Works locally, data gone after redeploy; or routes work but nothing appears in Supabase | `ROUTES_DATABASE_URL` not seen → SQLite fallback | Set it on FastAPI Cloud; `load_dotenv()` first in `main.py` for local runs; wiring must refuse SQLite |
| `MissingGreenlet: greenlet_spawn has not been called` from `farmnex_routes` | It got our asyncpg `DATABASE_URL` | Set `ROUTES_DATABASE_URL` (plain `postgresql://`) |
| Whole server slow/frozen when planning trips | Sync helper called inside `async def` | Wrap with `run_in_threadpool` |
| Tracking page 500 "No module named farmnex_routes" | Copied into `app/modules/` | Copy to `backend/farmnex_routes/` or pip-install |
| Tracking page blank on Android | `http` link, or no INTERNET permission | `ROUTES_PUBLIC_BASE_URL` with https; manifest permission |
| ETAs say "Estimated" | Public OSRM server slow/blocked | Fine for demo; or `ROUTING_PROVIDER=haversine` |
| "Plan trip" returns no loads | No `pending` loads within 30 km, or vehicle not `available` | Driver goes online first; seed loads near the vehicle base |
| Order never shows Delivered | Listener error (logged) | Check logs; manager "re-sync" endpoint |
| Main app breaks after a component push | Unpinned `@main` install | Pin the commit hash |

## Tests (`backend/tests/modules/test_route_optimizer.py`)

Set-up (flags, test database, running `030_rt_route_tables.sql`): `README.md` → "Testing a component".

- Flag off → no `/api/v2/routes` routes; flag on without `ROUTES_DATABASE_URL` → still unmounted,
  error logged, app starts.
- No token → 401 on guarded routes; `/track/{id}` works without token.
- Driver B can't read/modify driver A's vehicle, trip or stops (404); a buyer can't complete stops.
- Buyer and farmer of an order see `/orders/{id}/delivery`; another buyer gets 404.
- Blocked routes (`POST /loads`, `PUT /vehicles/{id}`) are absent (404/405).
- Listener: completing the last stop sets our order to DELIVERED once, even if called twice.

## Done when

- A driver registers a truck in the app, goes online, and gets a pooled trip for two nearby farmers'
  loads to the same buyer, with each farmer's fare.
- Buyer taps **Track** and sees the truck move (real phone, or `backend/scripts/simulate_driver.py` written by S34).
- Last drop → order shows Delivered; a return-trip offer appears for the driver.
- Another driver can't see or change that trip.
