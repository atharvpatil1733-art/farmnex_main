# Crop Rescue → main app

**Source repo:** `atharvpatil1733-art/farmnex_crop_rescue` (commit: see `docs/STATUS.md` → Components).
**What it does:** tracks harvested lots, estimates remaining shelf life (Q10 temperature rule), runs a
check every 12 hours, alerts the farmer 48 hours before spoilage, and suggests the best nearby
rescue buyers.
**Priority:** top feature — integrate first (after P0 security fixes).
**Time budget (prototype):** ~6–8 h — its Phase 5 (1 h, done), backend wiring +
tests (2–3 h, done — S15), Flutter screens (3–4 h — S22).

Follow the shared rules in `README.md` in this folder. This file lists what's specific.

## What the component gives us

- Package `crop_rescue/` with public names only:
  `router, start_scheduler, stop_scheduler, settings, configure, current_farmer_id`.
- Router prefix `/rescue`, tag `crop-rescue` → mounted here at **`/api/v2/rescue/...`**.
- Sync SQLAlchemy **Core** + `psycopg` (v3); `apscheduler<4`; relative imports only (works at
  `app/modules/crop_rescue/`).
- SQL: `migrations/001_crop_rescue.sql` (tables/views, all `cr_`), `002_demo_seed.sql` (demo buyers).
- Buyers come only from the `cr_buyer_pool` view.
- Env vars all start with `CR_` (see its `.env.example`). `CR_ENABLE_SIMULATE` turns on a demo
  endpoint that fast-forwards time — set `false` after the demo.

**Phase 5 is done in that repo** (S03; commit in `docs/STATUS.md` → Components): the Flutter client is
`integration/flutter/crop_rescue_api.dart`, next to `INTEGRATION.md`. S22 copies the client into
`frontend/lib/core/network/` (add the repo folder to the session); without the folder, write it from
`backend/app/modules/crop_rescue/api.py` + `schemas.py` — the endpoint list is in STATUS.

## FarmNex-specific decisions (these differ from the component's generic docs)

1. **Farmer id = `str(user.public_id)`**, not `str(user.id)` as its SPEC example shows. Also require the
   FARMER role:
   ```python
   async def rescue_farmer_id(user: User = Depends(get_current_user)) -> str:
       if user.role is None or user.role.name != "FARMER":
           raise HTTPException(403, "Only farmers can use Crop Rescue.")
       return str(user.public_id)
   app.dependency_overrides[crop_rescue.current_farmer_id] = rescue_farmer_id
   ```
2. **Do NOT call `crop_rescue.configure(engine=engine)` with our engine.** Ours is an *async* asyncpg
   engine; Crop Rescue needs a *sync* engine. Instead set **`CR_DATABASE_URL`** to the Supabase
   *session pooler* URL in psycopg form:
   `postgresql+psycopg://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require`.
   (S01's `.env.example` comment says "plain `postgresql://`"; this guide wins — S15 fixes that comment
   inside its own section.)
   If `CR_DATABASE_URL` is missing, Crop Rescue falls back to `DATABASE_URL`, which is an asyncpg URL
   and will fail — so `crop_rescue_host.py` must refuse to mount it (log a clear error) when `CR_DATABASE_URL`
   is unset.
3. **Scheduler:** call `crop_rescue.start_scheduler()` / `stop_scheduler()` from our `lifespan` via
   `start_components()` / `stop_components()`. FastAPI Cloud may run more than one instance or sleep;
   check the job is safe to run twice (its `test_scheduler_safety.py` covers overlap in one process —
   for multiple instances, run it on one only via `CR_ENABLE_SCHEDULER`).
4. **Alerts → FarmNex notifications (optional):** `crop_rescue.configure(on_alert=callback)`. The
   callback can insert a row into our `notifications` table **through our notification service** (not
   raw SQL from the component). Needs a mapping from `farmer_id` (public_id) back to `users.id`.
5. **Real buyers (later):** replace the demo `cr_buyer_pool` with a view over our real data —
   `users` with role BUYER + their default `addresses` (lat/lon) + open `buyer_demand_requests`. Write
   it as `backend/migrations/0xx_cr_buyer_pool_real.sql` using `CREATE OR REPLACE VIEW` (keep the
   exact column names/types the component expects — read them from its `001_crop_rescue.sql`).
6. **Crops:** Crop Rescue has its own list (`crop_rescue/data/crops.json`, max 8 crops). Our
   `crop_types` table has 12. Use the crop map in `app/modules/crops.py` (F18) so the
   farmer can only pick supported crops for rescue.

7. **`POST /rescue/check` runs the spoilage check for every farmer** and has no farmer check of its
   own. Allow it only for ADMIN, SUPER_ADMIN or MANAGER with a small host guard on that one path (the scheduler
   already runs it every 12 h). Farmers use `/rescue/simulate` (their own lots) in the demo.
8. **Settings file:** its settings read `.env` from the **current folder**, so run the backend from
   `backend/` (as the commands in `CLAUDE.md` do). Settings are validated when the package is first
   imported, so import it inside `mount_components` (shared rule 3) — a typo like `CR_Q10=abc` then
   only disables Crop Rescue instead of crashing the backend.

## Steps

1. Copy `crop_rescue/` into `backend/app/modules/` (the folder exists). Use the commit recorded in
   `docs/STATUS.md` → Components (after S03 merged; if it still says Phase 5 is not done, stop).
   Record the commit hash in the PR.
2. Add to `backend/pyproject.toml` **and** `backend/requirements.txt` (Crop Rescue section): `psycopg[binary]>=3.1`, `apscheduler>=3.10,<4`
   (`sqlalchemy`, `pydantic-settings`, `httpx` are already there).
3. Copy its `migrations/001_crop_rescue.sql` → `backend/migrations/010_cr_crop_rescue.sql` and
   `002_demo_seed.sql` → `backend/migrations/011_cr_demo_seed.sql` (unchanged). Atharv runs them in
   the Supabase SQL editor.
4. Host file `backend/app/modules/crop_rescue_host.py` (loaded by `wiring.py` when `ENABLE_CROP_RESCUE=true`;
   don't edit `wiring.py`): check `CR_DATABASE_URL`,
   identity override (above), `app.include_router(crop_rescue.router, prefix="/api/v2",
   dependencies=[Depends(get_current_user)])`, scheduler start/stop.
5. `.env.example`: `ENABLE_CROP_RESCUE=false`, `CR_DATABASE_URL=`, `CR_ENABLE_SIMULATE=true`,
   `CR_ENABLE_SCHEDULER=true`.
6. Tests `backend/tests/modules/test_crop_rescue.py`: routes under `/api/v2/rescue`; no token → 401;
   BUYER token → 403; farmer A can't see farmer B's lot (404). Test database and flag handling:
   `README.md` → "Testing a component" (variable: `TEST_DATABASE_URL`; the SQL files 010/011 create the tables).
7. Flutter: `CropRescueApi(ApiClient().dio)` with paths `/api/v2/rescue/...`; switch
   `lib/providers/rescue_provider.dart` from demo data to it; screens in `lib/screens/rescue/`
   (`crop_rescue_screen.dart`, `publish_rescue_sheet.dart`, `rescue_detail_screen.dart`). Poll
   alerts every 30 s on the farmer home screen, only while it's visible — put the polling in your own
   widget and add **one line** for it to `home_screen.dart` (S21 owns that file; `PARALLEL_SESSIONS.md` §6 Wave 3).
   Lot `lat`/`lng`: STATUS → Verified facts → Pre-flight defaults.

## What can go wrong (and how you'll notice)

| Symptom | Cause | Fix |
|---|---|---|
| `MissingGreenlet` / asyncpg errors from `crop_rescue` | `CR_DATABASE_URL` unset → fell back to our async `DATABASE_URL` | Set `CR_DATABASE_URL` (`postgresql+psycopg://…:5432/postgres?sslmode=require`) |
| `relation "cr_lots" does not exist` | SQL file not run on this database | Run `010_cr_crop_rescue.sql` in Supabase |
| `SSL connection is required` / connection refused | Missing `?sslmode=require`, or used the direct host that needs IPv6 | Use the **session pooler** URL from Supabase → Connect |
| Every call 401 | App not sending our token | Build the client on `ApiClient().dio` |
| Every call 403 | Logged in as BUYER/VENDOR | Farmer account only (by design) |
| No matches for a lot | Demo buyers not seeded, or all farther than `CR_RADIUS_KM` (50 km) | Run `011_cr_demo_seed.sql`; create lots near Pune |
| No alerts appear | Scheduler off / not yet 12 h | Use `/rescue/simulate` in the demo; check `CR_ENABLE_SCHEDULER` |
| Alerts sent twice | Backend runs 2+ instances, each with a scheduler | `CR_ENABLE_SCHEDULER=true` on one instance only (or keep 1 instance for the demo) |
| Backend won't start after adding it | Bad `CR_*` value + top-level import | Import inside `mount_components`; fix the variable named in the error |

## Done when

- `/docs` shows the **crop-rescue** section under `/api/v2/rescue`.
- A farmer creates a lot, runs simulate, sees an alert and 3 buyer matches in the app.
- Another farmer cannot see that lot (404). A buyer gets 403.
- Backend still starts with `ENABLE_CROP_RESCUE=false`.
