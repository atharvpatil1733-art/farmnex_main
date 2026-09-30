# FarmNex status

Short, current picture of where the main app stands. **Only the coordinator session edits this file**
(see `docs/PARALLEL_SESSIONS.md`); other sessions put "Ticks:" / "Manual steps:" in their PR description.

## Fix plan progress (details in FIX_PLAN.md)

| Group | Items | Done |
|---|---|---|
| P0 security | F1 ownership · F2 request fields · F3 roles | **1 / 3** (F3 done; F1 fast path done — 9 modules unmounted, 13 left to fix in S09–S14) |
| P1 repo health | F4 junk files · F5 deps · F6 /db · F7 CORS · F8 middleware · F9 pooler · F10 entrypoint · F11 tests/CI · F17 load .env · F18 crop list | **9 / 10** (F4 F5 F6 F7 F9 F10 F11 F17 F18 done; F8 open — needs Atharv's choice) |
| P2 marketplace logic | F12 orders/bids/escrow/payments | 0 / 1 |
| P3 frontend | F13 connect screens · F14 secure tokens · F15 demo names · F16 READMEs | **3 / 4** (F14 F15 F16 done; F13 open) |

## Waiting for Atharv (manual steps from merged PRs) — updated 2026-09-30

1. 🧑 **Confirm in the FastAPI Cloud dashboard:** is GitHub connected (auto-deploy on merge to `main`)? Does it deploy from `backend/`, and does it run `app.main:app`? *(Still unconfirmed — treat every merge to `main` as a possible live deploy. Now more important: S06 deleted `main_complete.py` / `domain_router.py`; if the live app was started from one of those, it would break on the next deploy.)*
2. 🧑 **M1:** deploy the forecaster to Render (free plan) + keep-awake ping, then have the coordinator record its public URL in "Verified facts → Forecaster URL". **Blocks S16.**
3. S06 (PR 16): look at the port at the end of the production `DATABASE_URL` (6543 = transaction pooler, 5432 = session pooler; informational — the code now works with both). Set `CORS_ORIGINS` on FastAPI Cloud only if a browser client is ever used.
4. S01: after the backend next starts (or deploys), 7 rows appear in `crop_types` (Spinach, Okra, Brinjal, Cauliflower, Grapes, Capsicum, Cucumber). No SQL. Glance at Supabase Table Editor.
5. S02: on a phone — log in, restart the app, still logged in (proves the token migration; not tested on a device). Later, Android location permissions for `geolocator`.
6. S05: for database tests locally, start a throwaway Postgres and set `TEST_DATABASE_URL` (example in PR 11 description). With branch protection, mark "Backend tests" (and "Flutter check") as required.
7. Decision: `backend/tests/test_crops.py` and `test_wiring.py` (S01's row) are **still not on `main`** — F18's Check isn't proven by tests. Add them in a small session before S15–S17?
8. Decision: F8 (settings that do nothing) — remove the unused settings + add security headers (recommended in the 40–50 h build), or implement rate limiting?
9. Housekeeping: PR 17 ("C: status update") is an older, superseded draft of the S08 update (that content already merged via PR 18) — close it without merging.
10. Optional: Flutter analyze shows 49 issues (0 errors, 3 warnings in `profile_screen.dart`) — a tiny cleanup PR.

## Components

| Component | Repo state (checked 2026-09-30) — **the one place for source commit hashes** | Integrated here? |
|---|---|---|
| Crop Rescue | latest `93704f3` (2026-09-29; its PR #4 added Phases 5–6: Flutter client, `INTEGRATION.md`, stored lot temperature, host wiring) — **S03 done**. Earlier `25844b8`/`93eec60` only differ in docs and the Phase 5–6 additions | No |
| AI forecaster | latest `b859f69` (code and kit unchanged since `2f6f170`; later commits changed only `CLAUDE.md` and `integration/INTEGRATION.md`): service + integration kit ready (kit assumes Supabase Auth — adapt per guide) | No |
| Route optimizer | latest `8ae63de` (`farmnex_route_optimization`; code unchanged since `22d4859`, later commits are docs only). The pip pin in `docs/integration/route-optimizer.md` stays `22d4859`. Package `farmnex_routes` ready; needs host guard, vehicle endpoints, own DB URL | No |
| Voice assistant | `483599b` (`Farmnex-Voice-Assistant`): M4 done (speech, agent, confirmations); **login adapter, real tools, Flutter client missing** — stretch goal | No |

## Decisions log

- 2026-09-29 — Components plug into `backend/app/modules/<name>/` and are mounted under `/api/v2`.
  Component tables use a prefix (`cr_`, `fc_`, `rt_`, `va_`), are created by hand-run SQL in
  `backend/migrations/`, and store the user as `public_id` (UUID text) with no foreign keys to core
  tables.
- 2026-09-29 — Rule: never alter/delete existing tables in the main Supabase DB; only add tables.
- 2026-09-29 — Demo story uses Tomato (only crop supported everywhere).
- 2026-09-29 — Build window is 40–50 h; scope and order follow `docs/FINALE_PLAN.md`. Voice = stretch.
- 2026-09-29 — **Confirmed by Atharv:** (1) unmount the 9 unused modules (F1 fast path);
  (2) the route optimizer's `rt_loads` replaces core `deliveries` and `rt_vehicles` is the vehicle
  source of truth; (3) the live-tracking link works without login (private-link style) for the
  prototype; (4) pre-bid winner: the **farmer accepts** a bid; (5) the voice assistant uses a
  separate free Supabase project.
- 2026-09-29 — **Confirmed by Atharv (wave 0 pre-flight):** (1) F18 may add the 7 missing Crop Rescue
  crops (Spinach, Okra, Brinjal, Cauliflower, Grapes, Capsicum, Cucumber) to `DEFAULT_CROP_TYPES`;
  the startup seeder only inserts missing rows, nothing existing is renamed, changed or deleted;
  (2) the forecaster runs on the Render free plan with a keep-awake ping (option 1 in
  `docs/integration/ai-forecaster.md`), not the paid Starter plan.
- 2026-09-30 — **Confirmed by Atharv (wave 2 pre-flight):** (1) the F1 rules table in
  `docs/FIX_PLAN.md` is **approved as written** for all 13 mounted modules — S09–S14 don't ask again;
  (2) until S18 adds server-side order creation, **S11 removes the public create routes** for `orders`
  and `order_items` (no screen uses them yet). Same idea for payments: no public create/update/delete.
- 2026-09-29 — S02 added `.github/workflows/flutter-check.yml` with Atharv's OK (first file outside its row; §4 now lists it).
- 2026-09-29 — Work runs as parallel Claude Code sessions per `docs/PARALLEL_SESSIONS.md`; only the
  coordinator session edits this file and `FIX_PLAN.md`.

## Verified facts (the single source — other docs link here)

| Fact | Value | Source / checked |
|---|---|---|
| Production dependency file | FastAPI Cloud installs from `backend/pyproject.toml` when it exists; `requirements.txt` only if there's no pyproject. Keep both in sync. | fastapicloud.com docs "Install Dependencies", 2026-09-29 |
| Deploys | With FastAPI Cloud's GitHub integration, every push to the default branch (`main`) deploys; no PR previews. **Unconfirmed:** whether this project has GitHub connected, and that it deploys from `backend/`. | fastapicloud.com docs "GitHub Integration", 2026-09-29 |
| Entrypoint | FastAPI Cloud auto-detects `app/main.py` (`app.main:app`). | fastapicloud.com docs "Migrate an Existing Project" |
| Crop-name map | `backend/app/modules/crops.py` | decision 2026-09-29 |
| Main crop names | `crop_types.name`, capitalised (`Tomato`, `Onion`, …) | `app/main.py` DEFAULT_CROP_TYPES |
| Crop Rescue crop codes | lowercase: tomato, spinach, okra, brinjal, cauliflower, grapes, capsicum, cucumber | `farmnex_crop_rescue` `crop_rescue/data/crops.json` @ 6f90439 |
| Forecaster crops | `Onion`, `Tomato`, `Potato` (exact case) | `farmnex_ai_forecaster` `config.yaml` @ 2f6f170 |
| Voice crop ids | **Target:** lowercase (`tomato`, `onion`, `potato`, + Crop Rescue codes after its FARMNEX_HOST change 3). **Today's pack:** `onion, tomato, soybean, pomegranate` | voice repo `docs/FARMNEX_HOST.md` |
| User id given to components | `str(user.public_id)` (UUID string) | decision |
| Component host files | `app/modules/<name>_host.py`, loaded by `app/modules/wiring.py` via its `ENABLE_*` flag | PARALLEL_SESSIONS §7 |
| `wallet_ledger` | new core model, created by the startup `create_all` (no SQL file) | FIX_PLAN F12 |
| Render free plan | Spins down after 15 min without requests; ~1 min to wake; 750 free instance hours/month per workspace | render.com/docs/free, 2026-09-29 |
| FastAPI Cloud ↔ GitHub | Dashboard → app → **Settings** → **Source Repository** → **Connect** → pick the repo. App in a subfolder: Settings → **Application Directory** → `backend` → Update | fastapicloud.com docs, 2026-09-29 |
| Forecaster hosting | Render free plan + keep-awake ping (uptime monitor opens `/health` every 10 min, switched on a day before judging). The key is generated by Atharv and set only on Render (variable `FARMNEX_FORECASTER_API_KEY`) and on FastAPI Cloud (variable `FORECASTER_API_KEY`, **same value**) — never pasted into a chat or file. | decision 2026-09-29 |
| Forecaster URL | **Not deployed yet.** M1 fills this in (public URL only, no key): `<not set>`. B4 / S16 read it from here. | M1 |
| Marked sections | Format of the per-component sections in shared files: `PARALLEL_SESSIONS.md` §7 | decision 2026-09-29 |
| CI | `.github/workflows/backend-tests.yml` (pytest + Postgres service; green on `main` at `edf315d`) and `.github/workflows/flutter-check.yml` (pub get, analyze, test on PRs touching `frontend/`). No Flutter SDK or Docker on Atharv's dev machine — CI is how Flutter is checked. | PR 10, PR 11 |
| Package pins | `flutter_secure_storage ^10.0.0`, `geolocator ^14.0.2` (newer versions need `win32 ^6`, clashing with `file_picker ^8`); `webview_flutter ^4.14.1`; backend `uvicorn 0.54.0` in `requirements.txt` (`>=0.53` in `pyproject.toml`) | PR 9, PR 10 |
| Token storage | Login tokens in `flutter_secure_storage` (kept in memory); old plain keys migrated once and deleted. User name/mobile/address still in `shared_preferences`. | PR 10, PR 12 |
| Known gap (owner: S02/`api_client.dart`) | A failed token refresh clears tokens on any error (even a network blip) and two refreshes can race. Needs an owner session. | PR 12 |
| Test helpers | `backend/tests/conftest.py`: `make_user(role)`, `make_token(user)`, `client`, DB fixture from `TEST_DATABASE_URL` (skipped if unset; refuses Supabase or non-local non-`*test*` URLs) | PR 11 |
| Public sign-up roles today | FARMER, BUYER, VENDOR (`public_registration_roles`). It is a list, so the env var is JSON: `PUBLIC_REGISTRATION_ROLES=["FARMER","BUYER","VENDOR","DELIVERY_AGENT"]` (S17 adds DELIVERY_AGENT this way; Atharv sets it on FastAPI Cloud) | `app/core/config.py` |
| F1 rules table | Approved as written (`docs/FIX_PLAN.md` F1 "Approved rules"). Orders/order items: no public create route until S18. | Atharv, 2026-09-30 |
| Unmounted modules (F1 fast path) | 9, approved: `ai_prediction, ai_recommendation, delivery, delivery_tracking_event, delivery_proof, audit_log, order_dispute, review, farm_crop_activity`. S08 unmounts them; nobody fixes them in wave 2. | decision 2026-09-29 |
| Component tests | `conftest.py` forces every `ENABLE_*` flag off and sets `TEST_DATABASE_URL`. Recipe for component tests (own app, test DB, SQL file): `docs/integration/README.md` → "Testing a component". Component test DB variable is `TEST_DATABASE_URL` only (no `CR_TEST_DATABASE_URL`). | `backend/tests/conftest.py` |
| Git install on FastAPI Cloud | **Unconfirmed:** whether its build can `pip install` a `git+https://` dependency (the route optimizer pin). S17's PR shows the fallback if the build log fails; first real answer comes from the first deploy. | route-optimizer guide |
| Legacy entrypoint files | `backend/app/main_complete.py` and `backend/app/api/v2/domain_router.py` are **deleted on `main`** (S06, F10; PR 16's description said "kept" but its squash commit removed them). Only `app.main:app` exists. `app/main.py` imports `app.domain_model_registry`. | `git show 120b6a3` |
| DB engine behind a pooler | asyncpg statement cache off + unique statement names, safe on both 6543 (transaction pooler) and 5432. Not exercised against a real pooler. | PR 16 |
| CORS | `CORS_ORIGINS` env (comma list); `*` is ignored with a warning; credentials off; falls back to localhost dev origins. `config.py` still defaults `cors_origins` to `*` (core file, harmless because `main.py` ignores `*`). Android-only, so no browser origin is needed. | PR 16, Atharv |
| `/db` | Returns only `{"status":"error","database":"disconnected"}` on failure; details go to the server log. | PR 16 |
| Test run on `main` | `pytest -q` in a fresh venv (Python 3.14, `requirements.txt` + pytest): 50 passed, 9 skipped (DB tests, no `TEST_DATABASE_URL`). App imports and `/docs` + `/openapi.json` return 200 (56 paths, none of the 9 unmounted modules) — checked with placeholder env values, no `.env`. | coordinator, 2026-09-30 |


## Log

- 2026-09-30 — Coordinator update (S06 + S08b): merged PR 16 (S06: F9, F6, F7 done; F10 done — the two legacy files are deleted on `main`) and PR 19 (S08b: HTTP tests, 9 unmounted → 404, kept modules → 401). `pytest` on main: 50 passed, 9 skipped; `/check`: app imports, `/docs` and `/openapi.json` 200, no DROP/TRUNCATE/ALTER in migrations, no `.env`/`.pem` tracked; Flutter checks not run (no SDK on this machine; CI covers them; no frontend changes in these PRs). Doc conflicts fixed: PR 16 description vs `main` (files were deleted, not kept) → `CLAUDE.md` repo map and FIX_PLAN F10 updated. Wave 2 is now open: S09–S15 and S17 can start (S16 waits for M1).
- 2026-09-30 — Coordinator update for S08 (PR 14, merged, CI green: 36 passed): F3 `require_roles` added (`backend/app/api/dependencies/roles.py`, not used by any controller yet — S09–S14 use it per module); F1 fast path done (9 approved modules unmounted in `router.py`; code and tables untouched). `security-reviewer`: no exploitable issue on `app.main:app`; LOW: `main_complete.py` / `domain_router.py` still mount the 9 modules (production doesn't run them) — S06/F10 deletes them. The crop-types BUYER→403 test moved to S14. Manual steps: none; the live `/docs` loses the 9 modules if a merge to `main` deploys (still unconfirmed).
- 2026-09-30 — Coordinator update: merged S01 (PR 9: F4 F5 F17 F18 + wiring/crops slots), S05 (PR 11: F11 tests + CI), S02 (PR 10: F14 F15 F16 + packages + api_config sections + Flutter CI), S02b (PR 12: token hardening). S03 done in the Crop Rescue repo (PR 4). Backend `pytest` on main: 3 passed, 7 skipped (no test DB here); CI green. M1 (forecaster on Render) not reported.
- 2026-09-30 — Docs pre-flight for wave 2 (S08–S17; Wave 1's S06/S07 not covered): F1 rules approved once;
  order/payment create routes removed until S18/F12; S08 vs F3 check clarified (audit-logs is unmounted);
  cross-module rule, test naming and component test recipe added; S17 file list completed; component
  guides aligned (test DB variable, request-transport moves to S26, forecaster log repository location).
  **Found:** `backend/tests/test_crops.py` and `test_wiring.py` (S01's row) are **not on `main`** — S01's
  Check for F18 isn't proven; ask Atharv whether to add them in a small session before S15–S17.

- 2026-09-29 — Docs pre-flight for wave 0 (S01, S02, S03, M1; S04 skipped in three-lane mode): commit hashes
  unified here, `requirements.txt` advice fixed, S01/S02 file lists completed, marked-section format defined,
  three questions answered (crops, deploy, forecaster hosting).

- 2026-09-29 — Reviewed Farmnex-Voice-Assistant@483599b; voice guide rewritten; crop overlap found
  (only Tomato in all four) → F18; unmount-vs-delete reasoning added to F1; open decisions listed.
- 2026-09-29 — Checked the three component repos; route optimizer guide rewritten from the real repo;
  failure-mode tables added; FINALE_PLAN.md and PROMPTS.md added; F17 added.

- 2026-09-29 — Code review done; Claude Code setup added (CLAUDE.md files, fix plan, integration
  guides, commands).
