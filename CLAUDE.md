# FarmNex — main app (SIH 2026)

FarmNex is an agricultural marketplace for Smart India Hackathon 2026 (Problem Statement 26033).
Farmers sell directly to buyers, get pre-harvest bids, rescue crops close to spoilage, sell crop
waste, see AI price/demand forecasts, and get optimized delivery routes.

This repo is the **main app**: a FastAPI backend + a Flutter frontend, both talking to one Supabase
PostgreSQL database. Four AI/logistics components are built in separate repos and plugged in here
(see "Components" below).

## Who you are working with

- Atharv (team lead) is not deeply technical. **Explain what you did and why in plain, simple
  language.** Avoid jargon; when you must use a term, explain it in one short sentence.
- Atharv wants to build components **with** you. When he is planning a component, discuss and
  propose first — do not jump ahead and build it.
- Before any change bigger than one file, say in 2–4 lines what you will change, then do it.
- Finish every task with: what changed, how you checked it, and what (if anything) he must do
  by hand (e.g. run SQL in Supabase, set an env var on FastAPI Cloud).

## Repo map

```
backend/                 FastAPI app (Python 3.11+, async SQLAlchemy 2 + asyncpg)
  app/main.py            THE (only) entrypoint — legacy main_complete.py was deleted (F10)
  app/api/v2/router.py   mounts every controller under /api/v2
  app/api/v2/endpoints/  one *_controller.py per resource (HTTP only, thin)
  app/services/          business rules + ownership checks
  app/repositories/      database queries only
  app/models/            SQLAlchemy ORM models (tables)
  app/schemas/           Pydantic request/response models
  app/core/              config, database, security (JWT), exceptions
  app/modules/           (create when needed) plug-in components: crop_rescue/, forecast/, ...
  migrations/            hand-run SQL for component tables (see migrations/README.md)
  tests/                 pytest
frontend/                Flutter app (Dart), state via `provider`, HTTP via `dio`
  lib/core/network/api_client.dart   the ONE Dio client (adds login token, refreshes it)
  lib/core/config/api_config.dart    all backend URLs
  lib/providers/         state; most still use hard-coded demo data (see FIX_PLAN F13)
  lib/screens/, lib/widgets/, lib/models/
docs/
  FIX_PLAN.md            every known issue, in priority order, with how to verify
  STATUS.md              progress, decisions, verified facts — only the coordinator session edits it
  integration/           how each component plugs into this repo
  HOW_TO_USE_CLAUDE_CODE.md   plain-language guide for the team
  FINALE_PLAN.md         the 40–50 h build plan: streams, order, budgets, cut lines
  PROMPTS.md             copy-paste prompts for every step
  PARALLEL_SESSIONS.md   how many Claude Code sessions work at once: order, file ownership, merging
```

## Commands

Backend (run from `backend/`):
```bash
pip install -r requirements.txt           # psycopg2 fails to build — see FIX_PLAN F5
python generate_jwt_keys.py               # creates secrets/jwt_*.pem (never commit them)
cp .env.example .env                      # then fill DATABASE_URL etc. Never read or print .env
uvicorn app.main:app --reload             # http://localhost:8000/docs
python -m pytest -q                       # tests
```
Frontend (run from `frontend/`):
```bash
flutter pub get
flutter analyze
flutter test
flutter run
```
Production backend: `https://farmnex.fastapicloud.dev` (FastAPI Cloud). Frontend points there via
`ApiConfig.baseUrl`.

## Hard rules (never break these)

1. **Database safety — the main Supabase DB is shared and live.**
   - Never `DROP`, `TRUNCATE`, `ALTER`, rename or delete existing tables, columns, rows or setup.
   - New features only **add** new tables (with a component prefix: `cr_`, `fc_`, `rt_`, `va_`).
   - Tests and experiments use a separate test database (`TEST_DATABASE_URL`), never the main one.
   - If a fix truly needs an existing table changed, **stop and ask Atharv**, explaining why.
2. **Every endpoint checks ownership.** Being logged in is not enough. A user may only read or change
   rows they own (or that their role allows). Another user's row → `404 Not Found` (don't reveal
   it exists). The pattern to copy is `services/farm_crop_service.py` (see backend/CLAUDE.md).
3. **Identity comes only from the login token** (`Depends(get_current_user)`), never from the request
   body or query. Fields like `payer_id`, `buyer_id`, `seller_id`, `status`, `paid_at`, `amount`
   (for payments) are set by the server, not accepted from the client.
4. **Secrets:** never read, print, or commit `.env`, `secrets/`, `*.pem`, or API keys. Don't put the
   Supabase secret key or any server key in the Flutter app.
5. **Keep `/docs` working.** The backend must start and `/docs` must load after every change —
   judges use it.
6. **Don't delete features or screens** to make something pass. Ask first.

## Components (built in separate repos, plugged in here)

| Component | Repo | How it plugs in | Guide |
|---|---|---|---|
| Crop Rescue (spoilage alerts + rescue buyers) | `farmnex_crop_rescue` | router copied into `backend/app/modules/crop_rescue/` | `docs/integration/crop-rescue.md` |
| AI forecaster (price, demand, sell options, crop choice) | `farmnex_ai_forecaster` | separate service + connector router | `docs/integration/ai-forecaster.md` |
| Route optimization (pooled loads, return trips, fares, live tracking) | `farmnex_route_optimization` | package `farmnex_routes` (pip, pinned commit) + ownership guard | `docs/integration/route-optimizer.md` |
| AI voice assistant (stretch) | `Farmnex-Voice-Assistant` | separate service (own Supabase project) calling `/api/v2/voice-tools/...` with the user's token | `docs/integration/voice-assistant.md` |

Shared rules for all of them: `docs/integration/README.md` (read its "Sync vs async" rule and
"Common failures" table before touching any component). Use `/integrate <name>`.

**Demo crop:** Tomato — the only crop every component supports (FIX_PLAN F18).

**Time limit:** the prototype must be finished within a 40–50 hour build window. Follow
`docs/FINALE_PLAN.md` for scope: prefer the simplest thing that works safely, don't add features
or abstractions beyond what the current step needs, and say so when a step will overrun its budget.

## How to work here

- Known problems and their order: `docs/FIX_PLAN.md`. Use `/fix F1` (etc.) to work one item.
- One fix item or one component per branch/PR. Small commits with clear messages.
- **Several sessions work in parallel.** Follow `docs/PARALLEL_SESSIONS.md`: start from the latest
  `main`, only touch the files your session row allows, and don't edit `docs/STATUS.md` /
  `docs/FIX_PLAN.md` (the coordinator session does) — put "Ticks:" and "Manual steps:" in the PR
  description.
- **Docs disagree?** Verified facts and decisions live in `docs/STATUS.md`; if two docs conflict,
  follow the order in `docs/PARALLEL_SESSIONS.md` §4b, keep going, and list it under "Doc conflicts:" in
  the PR (stop only if it affects files outside your session row, the database, money or security).
- Checks: `/check-fast` while working; `/check-backend` or `/check-frontend` before the PR; the full
  `/check` only for the coordinator after a wave.
- After finishing: merge the latest `main` into your branch, re-run your check, open the PR. Final
  message: at most 5 short bullets (changed / tested / manual steps / doc conflicts).
- For security-sensitive changes (auth, ownership, payments, bids), ask the `security-reviewer`
  agent to review before calling it done.
- More detail: `backend/CLAUDE.md` and `frontend/CLAUDE.md` (loaded automatically when you work
  in those folders).
