# FarmNex fix plan

From the code review on 2026-09-29. Work top to bottom: **P0 before any demo**, then P1, then the
rest. Use `/fix <ID>` in Claude Code to work one item. Only the coordinator session ticks boxes here
and updates `docs/STATUS.md`; other sessions write "Ticks:" in their PR description.

Each item says **why** (in plain words), **what to do**, and **how to check** it's really fixed.

**Order to work in** (tests must exist before the security fixes can be proven):
F4 → F5 → F11 → F3 → F1 + F2 (module by module) → F9 → F6, F7, F10, F17, F18 → F12 → F13–F16 → F8.
Time budgets and who does what: `docs/FINALE_PLAN.md`. Copy-paste prompts: `docs/PROMPTS.md`.

---

## P0 — Security (must fix before any demo or judging)

### - [ ] F1. Ownership checks on 22 modules

**Why:** these modules only check that someone is logged in, not *whose* data it is. Any logged-in
user can list every payment, edit anyone's bid, delete other people's orders, or read the audit log.

**Affected controllers** (all in `backend/app/api/v2/endpoints/`, all generated from one template —
they contain the comment "Ownership/authorization rules beyond the direct actor field belong in the
domain service"):
`ai_prediction, ai_recommendation, audit_log, bid, bid_event, buyer_demand_request, crop_batch,
crop_type, delivery, delivery_proof, delivery_tracking_event, farm_crop_activity, notification,
order, order_dispute, order_item, payment, product_image, product_listing, review, waste_record,
waste_utilization_listing`.

Already correct (use as the pattern): `farm_crop` (best example), `farm`, `address`, `user`, `me`.

**What to do:** follow the ownership pattern in `backend/CLAUDE.md`. Do **one module per commit**, in
this order (demo-critical first): payment → bid → bid_event → order → order_item → product_listing →
product_image → delivery → delivery_tracking_event → delivery_proof → crop_batch →
farm_crop_activity → waste_record → waste_utilization_listing → buyer_demand_request → review →
order_dispute → notification → ai_prediction → ai_recommendation → crop_type → audit_log.

**Prototype fast path — DONE by S08 (PR 14): the 9 modules below are unmounted; 13 modules remain to fix.** (Original note: saves ~4–5 h.) modules that no screen or demo
step will use can be **unmounted** instead of fixed: remove them from the `modules` list in
`backend/app/api/v2/router.py` (the code files and tables stay; nothing is deleted). Candidates:
`ai_prediction`, `ai_recommendation` (the forecaster replaces them), `delivery`,
`delivery_tracking_event`, `delivery_proof` (the route optimizer's `rt_loads` replaces them),
`audit_log`, `order_dispute`, `review`, `farm_crop_activity`. An unmounted endpoint can't be
attacked. That leaves 13 modules to fix. Re-mount one later only together with its F1 fix.

*Why unmount now instead of "fix them last" or delete them:*
- **Leaving them mounted to fix at the end is the risky option.** The backend is live on the internet
  (`/docs` is public), so every unfixed endpoint stays open to any logged-in user for the whole build,
  and "the end" is exactly when time runs out. Anyone testing can also create junk rows (fake
  payments, reviews) that show up in the demo.
- **Deleting costs more than it saves.** Unmounting takes one line per module and is reversed in one
  line; deleting code throws away finished models/services, makes the git history noisy, and to
  bring a feature back you rebuild it. The tables stay either way (we never drop tables).
- **So: unmount now → fix + re-mount later as add-ons** (F1 per module, then add it back to the
  `modules` list), only if time is left after the demo story works. In the pitch, call them
  "next release" features; judges see only working, safe endpoints in `/docs`.

**Approved rules** (Atharv approved this whole table on 2026-09-30 — sessions apply their rows without asking again):

| Resource | Owner field(s) | Who can read | Create | Update | Delete |
|---|---|---|---|---|---|
| product_listings | `seller_id` | any logged-in user sees ACTIVE; seller sees all own | FARMER/VENDOR; farm + crop batch must be theirs | seller | seller (prefer status=CLOSED) |
| product_images | via listing `seller_id` | same as listing | seller of the listing | seller | seller |
| crop_batches | via `farm_crop.farmer_id` | owner | owner of the farm crop | owner | owner |
| farm_crop_activities | via `farm_crop.farmer_id` | owner | owner | owner | owner |
| crop_types | reference data | any logged-in user | ADMIN | ADMIN | ADMIN (prefer deactivate) |
| buyer_demand_requests | `buyer_id` | owner; FARMERs see OPEN ones | BUYER | owner | owner |
| bid_events | `created_by_id` | anyone sees OPEN; creator sees own | seller of the listing | creator (not `status`/`winner_bid_id`) | creator, only if no bids |
| bids | `bidder_id` | bidder sees own; event creator sees bids on their event | BUYER, event OPEN, not own listing | none (withdraw = status change by server) | none |
| orders | `buyer_id` (+ sellers via order_items) | buyer; sellers of its items | BUYER; totals computed by server (F12). **Until S18 (F12a) adds it, remove the public create route** — nothing creates orders in the meantime | buyer may cancel while PLACED | none |
| order_items | order buyer / item `seller_id` | buyer or that seller | only by the server with the order — **remove the public create route** | seller: item status | none |
| payments | `payer_id` | payer; seller of the order (read); ADMIN | **server only** — remove public POST/PATCH/DELETE (F12) | server only | never |
| deliveries | `seller_id`, `delivery_agent_id`, order buyer | those three + LOGISTICS_MANAGER | seller or LOGISTICS_MANAGER | agent: status; manager: assign agent | none |
| delivery_tracking_events | via delivery | delivery parties | assigned agent | none | none |
| delivery_proofs | `uploaded_by_id`, via delivery | delivery parties | assigned agent | none | none |
| order_disputes | `raised_by_id`, `against_user_id` | both parties + SUPPORT/ADMIN | a party of the order | raiser: text; SUPPORT/ADMIN: status | none |
| reviews | `reviewer_id`, `reviewee_id` | any logged-in user (published) | buyer of a DELIVERED order, once per order | reviewer | reviewer |
| waste_records | `recorded_by_id`, farm | owner | FARMER; farm must be theirs | owner | owner |
| waste_utilization_listings | `seller_id` | anyone sees ACTIVE; owner sees own | owner of the waste record | owner | owner |
| notifications | `user_id` | own only | server only | own: mark read | own |
| ai_predictions | `user_id` | own; ADMIN | server only | none | none |
| ai_recommendations | `user_id` | own | server only | own: accept/dismiss | own |
| audit_logs | — | ADMIN/SUPER_ADMIN | server only | never | never |

"Server only" = remove that route from the public controller; the action happens inside another
service (e.g. a notification is created when a bid is placed).

**Working across modules:** you may *call* another module's existing service or repository functions
(read-only use, e.g. payments looking up an order), but you may not *edit* another module's files. If
you need a query that doesn't exist there, add it to your own repository file. Put your tests in a new
file `backend/tests/test_<module>.py` (never in `conftest.py`, which S05 owns).

**How to check:** for each module, a pytest test where user A creates a row and user B gets **404**
on get/update/delete and does not see it in the list; wrong role gets **403**. Then ask the
`security-reviewer` agent to review the module.

### - [ ] F2. Server-owned fields and public ids in request bodies

**Why:** request bodies accept fields the phone must never control, e.g. `PaymentCreate` accepts
`payer_id`, `status`, `paid_at`; bids accept `bidder_id`; orders accept `buyer_id` and totals. They
also take internal integer ids (`order_id: int`), which the app never receives (responses only show
`public_id`).

**What to do:** do it together with F1, per module: remove owner ids, status, timestamps, totals and
winner fields from `*Create`/`*Update` in `backend/app/schemas/`; take related rows as public UUIDs
and resolve them in the service (like `farm_crop_service.create`). Remove internal int ids from
`*Response` (use related `public_id`s). Also remove the duplicated import blocks inside the generated
schema files.
While no app uses them yet, also fix the misspelled URL prefixes: `/crop-batchs` → `/crop-batches`
(done by S12 with `crop_batch`). `/deliverys` → `/deliveries` and `/farm-crop-activitys` →
`/farm-crop-activities` belong to modules that are unmounted (F1 fast path): fix them when those
modules are re-mounted, not before.

**How to check:** OpenAPI (`/docs`) shows no `*_id: integer` in request bodies and no owner/status
fields in create bodies; sending `payer_id` in a body is ignored or rejected.

### - [x] F3. Role checks (dependency done by S08, PR 14; per-module use comes with S09–S14)

**Why:** nothing checks roles today — a BUYER could create crop types or read audit logs.

**What to do:** **S08** adds `app/api/dependencies/roles.py` with `require_roles(...)` (sketch in
`backend/CLAUDE.md`). Each of S09–S14 then uses it in its own modules per the F1 table (e.g. S14 for
`crop_type`). Keep `role_controller` and `otp_controller` unmounted as they are now (they're commented
out in `api/v2/router.py`) unless Atharv asks.

**How to check:** S08 tests `require_roles` on its own (`backend/tests/test_roles.py`: a tiny test
app with one guarded route — wrong role → 403, right role → 200, no token → 401). The per-endpoint
checks belong to the module that owns the endpoint: BUYER → 403 and ADMIN → allowed on
`POST /api/v2/crop-types` (S14). `GET /api/v2/audit-logs` is unmounted by the F1 fast path, so it has
no role test until it is re-mounted.

---

## P1 — Repo health and deployment

### - [x] F4. Delete junk files
`backend/app.zip` (1.1 MB old copy of the backend with `__pycache__` and an old `api/v1`) and
`backend/0.141` (empty file created by an unquoted `pip install fastapi>=0.141`). Use `git rm`.
Add `*.zip` to `.gitignore`.
**Check:** `git ls-files | grep -E "app.zip|0.141"` prints nothing.

### - [x] F5. Fix dependencies
`requirements.txt` has `psycopg2` (fails to build without Postgres dev tools — likely to break
deploys) and `PyMySQL` (unused, the DB is Postgres). It pins `uvicorn==0.52.4` but `pyproject.toml`
requires `uvicorn>=0.53` — they conflict. Remove `psycopg2` and `PyMySQL`, align uvicorn, and move
`pytest` to a dev section. **FastAPI Cloud installs from `pyproject.toml` when it exists** (it only
uses `requirements.txt` when there's no `pyproject.toml` — see its "Install Dependencies" docs), so
`backend/pyproject.toml` is the source of truth for production; keep `requirements.txt` matching it
for local `pip install -r`. Manual step: confirm FastAPI Cloud deploys from the `backend/` folder.
**Check:** fresh venv: `pip install .` (pyproject) **and** `pip install -r requirements.txt` both succeed; `python -c "import app.main"` works.

### - [x] F6. `/db` leaks error details
`GET /db` returns `str(exc)`, which can include the database host/user. Return only
`{"status":"error","database":"disconnected"}` and log the details server-side.
**Check:** with a bad `DATABASE_URL`, the response has no hostnames.

### - [x] F7. CORS
`main.py` uses `allow_origins=["*"]` with `allow_credentials=True` and ignores the `CORS_ORIGINS`
setting. Use the settings value; credentials `False` (we use bearer tokens, not cookies). Mobile apps
don't need CORS; Flutter **web** builds do — include their origin.
**Check:** a request with `Origin: https://evil.example` gets no `Access-Control-Allow-Origin`.

### - [ ] F8. Settings that do nothing
`.env.example` lists rate limits and security headers, but `app/core/middleware.py`, `jwt.py`,
`logging.py`, `constants.py` are empty files. Either implement the minimum — security headers +
a simple in-memory rate limit on `/api/v2/auth/*` (fine for one instance; note it resets on restart)
— or remove the unused settings so nobody thinks they're active. Ask Atharv which. (In the 40–50 h
build: remove them + add only the security headers — 30 min. Rate limiting is stretch.)
**Check:** 6 rapid `login/request-otp` calls from one IP → the 6th gets 429 (if implemented).

### - [x] F9. Supabase pooler + asyncpg check
`.env.example` uses port **6543** (Supabase *transaction* pooler). asyncpg's prepared-statement cache
breaks behind a transaction pooler (errors like `prepared statement "__asyncpg_stmt_1__" already
exists`). If production uses 6543, add `connect_args={"statement_cache_size": 0}` to
`create_async_engine` (and `prepared_statement_cache_size=0` in the URL query for SQLAlchemy), or use
the session pooler (5432). Ask Atharv what the production URL uses (don't read `.env`).
**Check:** 50 quick requests to `/api/v2/home` → no prepared-statement errors in logs.

### - [x] F10. One entrypoint (done by S06, PR 16: legacy files deleted, registry imported in `main.py`; still confirm FastAPI Cloud runs `app.main:app`)
`app/main_complete.py` + `app/api/v2/domain_router.py` mount the same controllers a second time
(duplicate routes/operation ids). Confirm FastAPI Cloud runs `app.main:app`; then delete those two
files. Keep `app/domain_model_registry.py` but import it from `app/main.py` so `create_all` always sees
every model.
S08 review: those two files still mount the 9 unmounted F1 modules, so running `main_complete` would re-expose them — another reason to delete them.
**Check:** `/docs` lists each route once; `grep -r main_complete` finds nothing.

### - [x] F11. Test setup + CI
Add `backend/tests/conftest.py` with a `TEST_DATABASE_URL` fixture (skip DB tests when unset), a
test-user + token factory, and an `httpx.AsyncClient` against the app. Add
`.github/workflows/backend-tests.yml` running pytest with a Postgres service container.
**Check:** CI is green on a PR.

---

## P2 — Core marketplace logic (plan with Atharv first; these are features)

### - [ ] F12. Real rules for orders, bids, pre-bidding and payments
Today these services are plain save/edit/delete. Needed:
- **Orders:** buyer from token; items reference listings; server computes prices, subtotal, fees,
  total; reduces `available_quantity` in the same transaction; status machine
  (PLACED → CONFIRMED → SHIPPED → DELIVERED / CANCELLED).
- **Bids / pre-bidding (7-day window):** bid only while the event is OPEN and within its time window;
  amount must beat the current highest by a minimum step; no bidding on your own listing; the server
  closes the event and sets `winner_bid_id`; write `bid_events` history; lock rows
  (`SELECT ... FOR UPDATE`) so two bids at once can't both "win".
- **Escrow:** winning pre-bidder pays a **20% advance** into the wallet; released to the farmer with
  the remainder only after the buyer confirms delivery (kept separate from direct sales).
- **Payments:** created only by the server from an order/bid flow; status machine
  (PENDING → HELD → RELEASED / REFUNDED / FAILED); idempotency key per attempt. For the prototype a
  clearly labelled "demo payment provider" is fine — never mark money as paid because the client said so.
**Prototype minimum (≈8 h — build this, not more):**
1. Orders: server-computed totals from listings, stock decrease, statuses
   PLACED → CONFIRMED → DELIVERED / CANCELLED (skip SHIPPED — the route optimizer tracks movement).
   On CONFIRMED → create the delivery load (route optimizer Slip 2).
2. Pre-bidding: bid rules above; **the farmer accepts a bid** (decided 2026-09-29) — accepting
   closes the event and sets `winner_bid_id`. No timer needed.
3. Escrow: one new **core** table `wallet_ledger` — a new model in `app/models/` registered in
   `domain_model_registry.py`, so the backend's startup `create_all` creates it (no SQL file; nothing
   existing changes) ( user_public_id, order/bid public id, amount,
   type HOLD/RELEASE/REFUND, idempotency key, created_at). Balance = sum of entries. HOLD 20% on
   bid win, RELEASE on DELIVERED (route optimizer Slip 3), each exactly once.
4. Payments: a clearly labelled demo provider ("Pay (demo)") that writes the ledger — no real
   gateway in the prototype.
5. **Decided:** the farmer accepts a bid (any time during the 7 days). Accepting = close the event +
   set `winner_bid_id` + HOLD 20%.
6. Write endpoints the voice assistant calls (create pre-bid listing, accept bid) accept an
   `Idempotency-Key` header and return the same result for the same key.
Skip for the prototype: refunds UI, partial deliveries, disputes, multiple currencies.

**Check:** tests for each rule (double bid race, own-listing bid, total tampering, early release,
release called twice pays once).

### - [x] F17. Load `.env` first and list component settings
**Why:** our settings read `.env` themselves, but Crop Rescue, the route optimizer and the forecaster
connector read the process environment directly. Locally they would silently miss their settings
(the route optimizer then quietly uses a SQLite file). **What to do:** first two lines of
`backend/app/main.py`: `from dotenv import load_dotenv` / `load_dotenv()`. In `backend/.env.example`
add one marked section per component (format: `PARALLEL_SESSIONS.md` §7) holding its `ENABLE_*` flag
(default `false`) and every env var its guide in `docs/integration/` already names, one-line comment
each. Component sessions add any further variables inside their own section.
**Check:** with `ROUTES_DATABASE_URL` only in `.env`, `python -c "import app.main, os; print(bool(os.getenv('ROUTES_DATABASE_URL')))"` prints `True`.

### - [x] F18. One crop list across the app and components
**Why:** each part supports different crops (the exact lists are in `docs/STATUS.md` → Verified
facts). **Only tomato is in all four.** A demo with any other crop
breaks halfway (e.g. an onion lot can't go into Crop Rescue).
**What to do (1 h):** add the 7 missing Crop Rescue crops to `DEFAULT_CROP_TYPES` in `app/main.py`
(approved by Atharv 2026-09-29; the seeder only inserts missing rows — nothing is renamed or deleted); add one mapping dict in
`app/modules/crops.py` (`crop_types.name` → Crop Rescue `crop_code` / forecaster crop / voice id);
component calls use it and answer "not available for this crop yet" instead of erroring. Demo story
uses **Tomato**.
**Check (S01):** a small unit test `backend/tests/test_crops.py` — Tomato maps to all four; Spinach maps
to Crop Rescue only and the others return `None`; every `crop_types.name` in the map exists in
`DEFAULT_CROP_TYPES`. **Check (later, when the components are plugged in):** a tomato listing works end
to end (rescue lot, forecast, voice); a spinach lot works in Crop Rescue and says "forecast not
available" politely.

---

## P3 — Frontend

### - [ ] F13. Connect screens to the backend
Only login, profile and farm-file upload use the backend. Connect one provider per PR with
`/connect-screen <name>`, in this order: `listing` + `market` (marketplace) → `cart` + `payment`
(checkout, after F12) → `bidding` → `rescue` (after Crop Rescue integration) → `logistics` (after
route optimizer) → `waste` → `admin` → `verification` / `crop_media`.
Remove dead URLs from `api_config.dart` (`/api/crops`, `/api/ai/*`, `/api/rescue/request`,
`/api/waste/listings`, `/ws/bidding/*`) as each feature gets its real endpoint. The fake
`core/payments/payment_gateway.dart` must not stay the default once real payments exist.
**Check:** the screen shows backend data; airplane mode shows a friendly error + retry.

### - [x] F14. Store tokens securely
Move access/refresh tokens from `shared_preferences` to `flutter_secure_storage` (keep language and
onboarding flags in shared_preferences). Migrate: read old keys once, save securely, delete old.
**Check:** log in, restart the app → still logged in; old prefs keys are gone.

### - [x] F15. Made-up names in demo data
`bidding_provider.dart` (and possibly others) uses real company names like "Godrej Agrovet" and
"Adani Wilmar" as "verified buyers". Replace with fictional names across `lib/`.
**Check:** `grep -rniwE "godrej|adani|reliance|tata|itc|mahindra" frontend/lib` finds nothing.

### - [x] F16. One README per app
*(Done 2026-09-29, S02: `CHANGES.md` content was judged stale and dropped.)* `frontend/` had `README.md`, `README_original.md`, `README_FINAL.md`, `README_HTML_REBUILD.md`,
`CHANGES.md`, `LANGUAGE_AND_API_UPDATE.md`, `FARMNEX_V2_INTEGRATION.md`. Merge what's still true
into `frontend/README.md`; delete the rest. Update the root `README.md` "run locally" section.
**Check:** one README per folder; setup steps work on a fresh clone.

---

## Not checked in the review

- `flutter analyze` / `flutter test` were not run (no Flutter SDK in the review environment).
  Run them once and add any errors here as new items.
- Production config on FastAPI Cloud (which entrypoint, which DB port) — ask Atharv.
