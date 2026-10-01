# Running FarmNex with many Claude Code sessions at once

This is the step-by-step guide for building FarmNex with **several Claude Code sessions working in
parallel on the same repo**. Every session reads this file. Read it fully once before starting.

---

## 1. Is this okay? Will quality drop?

**Yes, it's okay — and quality per session stays the same — if you follow the rules in this file.**
Each session reads the same `CLAUDE.md`, guides and tests, so a session fixing payments works just as
carefully as if it were the only one.

What *can* go wrong with parallel sessions (and how this plan prevents it):

| Risk | What it looks like | Prevented by |
|---|---|---|
| Two sessions edit the same file | Merge conflicts, one session's work overwritten | §4 file ownership + foundation sessions create the shared "slots" first |
| A session builds on old code | It re-fixes something already fixed, or uses code that has changed | Every session starts from the **latest `main`** (§5 rule 2) |
| A session needs something not finished yet | It invents its own version (e.g. its own role check) | Session table (§6) lists what must be merged first — don't start early |
| Pieces don't fit together | Each part passes its own tests, the whole app fails | Integration check after every wave (§8) + fixed contracts in `docs/integration/` |
| Sessions don't know each other's decisions | Contradicting choices | Decisions live **in the repo** (`docs/STATUS.md`), never only in chat |
| **You** become the bottleneck | 5 sessions all waiting for your "OK" or review | Max 3–4 active sessions per person (§3), batch the manual steps |
| Usage limits | Sessions stop halfway | §3 — plan usage; small sessions |

**The honest limit:** Claude Code sessions can write code in parallel, but every *human* step still
needs a person: answering "OK?", reviewing and merging pull requests (PRs), running SQL in Supabase,
setting environment variables, deploying, and testing on a phone. Around 35 PRs × 10–15 minutes of
review is **6–9 hours of review work** alone. So use your teammates as **session drivers and
testers**, not only as coders — see §3.

---

## 2. How parallel sessions work (the mental model)

- Each Claude Code session gets its **own copy** of the repo and works on its **own branch**. Sessions
  never see each other's work while they run.
- Work becomes shared **only** when its PR is **merged into `main`**. A session that started earlier
  still has the old `main` until it pulls the new one.
- Sessions have **no shared memory**. What one session decided is invisible to the others unless it's
  written in the repo (code, `docs/STATUS.md`, `docs/FIX_PLAN.md`, the guides). Anything you tell a
  session in chat that others need → ask it to write it into `docs/STATUS.md`.
- Merged ≠ live. The live app changes only when the backend is **deployed** (and SQL run / env vars set
  where needed). Find out how FastAPI Cloud deploys (§10).

```
main ──●────────●──────────●──────────●──────►   (merge = everyone can build on it)
        \      /  \       /  \       /
         S01──PR   S05──PR    S09──PR             (one branch per session)
                     S06──PR    S10──PR  ...      (parallel sessions, different files)
```

---

## 3. Before you start (once)

- [ ] **Decisions are final** — all five in `docs/STATUS.md` are answered (done ✅).
- [ ] **Who drives what.** Suggested with 6 people:
  - Atharv — *coordinator*: merges PRs, runs SQL, sets env vars, answers decisions. Drives at most 1–2 sessions.
  - Teammate 1 — drives the backend security sessions (S05, S08–S14, S33).
  - Teammate 2 — drives the component sessions (S03, S15–S17, S26).
  - Teammate 3 — drives the Flutter sessions (S02, S21–S25, S27–S28).
  - Teammate 4 — voice sessions (stretch) or second reviewer.
  - Teammate 5 — **phone tester + demo/pitch owner**: tests every merged feature on a real phone,
    prepares seed data, the pitch deck and the backup video; drives S34 and S35 with Atharv (they
    hold the demo accounts' phones).
  If you're doing it alone: run **at most 3 sessions at the same time**.
- [ ] **Usage.** Parallel sessions use your Claude plan's usage limit faster. Several sessions per hour
  can hit the limit and pause work. Spread sessions across teammates' own accounts, or choose a plan with
  more usage for the build days.
- [ ] **Deploy:** find out whether FastAPI Cloud deploys automatically when `main` changes (§10).
- [ ] **SIH rules:** check the SIH 2026 finale rules on (a) using AI coding tools and (b) code written
  before the finale, and whether the venue has reliable internet (Claude Code needs it). See §10.
- [ ] **GitHub:** everyone who drives a session has write access to the repos (or works through PRs
  you merge).

---

## 4. Shared files — who may change them

Most conflicts come from a few files that many tasks want to touch. The **foundation sessions** (S01,
S02) prepare "slots" in these files so later sessions only add to their own slot or their own file.

| Shared file | Owner | Everyone else |
|---|---|---|
| `backend/app/main.py` | S01 (then S06; S20 added the wallet timer start/stop with Atharv's OK) | Don't touch. Components plug in via their own `app/modules/<name>_host.py` |
| `backend/app/modules/wiring.py` | S01 creates it with all 4 components listed | Don't touch — it already imports your `<name>_host.py` when your flag is on |
| `backend/app/api/v2/router.py` | S08 (unmount) | Don't touch (components mount through `wiring.py`, not here) |
| `backend/pyproject.toml`, `backend/requirements.txt`, `backend/.env.example` | S01 creates a marked section per component | Add lines **only inside your own section** — dependencies go in **both** `pyproject.toml` (production uses it) and `requirements.txt`. Only exception: S17 may change `[tool.setuptools.packages.find]` in `pyproject.toml` if it has to use the `backend/farmnex_routes/` fallback |
| `backend/tests/conftest.py` | S05 | Don't touch. Put helpers in your own test file; if you truly need a shared fixture, stop and ask |
| Other `backend/tests/` files | the session whose row names them | Create **new** files only: `backend/tests/test_<module>.py` (S08–S14), `backend/tests/modules/test_<component>.py` (S15–S17; no `__init__.py`, unique file names) |
| Another module's files (e.g. S09 reading orders) | the session whose row lists that module | **Call** its existing functions (read-only use); don't edit its files. Need a new query → add it to your own repository file |
| `backend/app/api/dependencies/roles.py` | S08 | Use it, don't change it |
| `backend/app/core/*`, `backend/app/models/user.py` | nobody after S06 | Stop and ask |
| `backend/migrations/` | per component number range (`010–019` Crop Rescue, `020–029` forecaster, `030–039` routes) | Only your range |
| `frontend/pubspec.yaml` | S02 adds every planned package up front | Don't touch; ask the coordinator if you need a new package |
| `.github/workflows/*` | S05 (`backend-tests.yml`); S02 added `flutter-check.yml` | Don't touch; ask the coordinator |
| `frontend/lib/core/config/api_config.dart` | S02 creates a marked section per feature | Add URLs only in your section |
| `frontend/lib/core/network/api_client.dart`, `storage_service.dart`, `main.dart` | S02 | Don't touch |
| `backend/app/domain_model_registry.py` | S20 (one import line for `wallet_ledger`) | Don't touch |
| `frontend/lib/screens/home/home_screen.dart`, `screens/market/market_screen.dart`, `widgets/crop_card.dart`, `lib/localization/app_translations.dart`, `models/user_model.dart`, `android/.../AndroidManifest.xml` | wave 3 rules: §6 "Wave 3" (S21 / nobody / S24) | Don't touch unless that section says so |
| `frontend/lib/core/network/backend_service.dart` | nobody | New calls go in your own `lib/core/network/<feature>_api.dart` |
| `docs/DEMO.md`, `backend/scripts/seed_demo.py`, `backend/scripts/simulate_driver.py` | S34 (new files) | Don't touch. S35 only reads them; a bug in one is a fix session (§6 "Wave 5") |
| `backend/app/services/me_service.py` | S33 (the scoped-list tidy-up — Atharv, wave 5 pre-flight) | Don't touch |
| `docs/STATUS.md`, `docs/FIX_PLAN.md` | **coordinator only** (C) | Don't edit. Write "Ticks: F1 payment" etc. in your PR description instead |
| `docs/integration/*.md`, `CLAUDE.md` files | coordinator | If a guide is wrong, say so in your PR description |

Rule of thumb for every session: **if you need a file outside your row in the session table, stop and
ask the person driving you.** Don't "just fix it quickly".

---

## 4b. When two docs disagree (source of truth)

Two kinds of "conflict" exist. **Git conflicts** (two sessions change the same lines) are prevented by
§4. **Instruction conflicts** (two docs say different things, or a fact nobody verified) can't be
caught by git — they surface as a session stopping to ask. Rules that keep them rare:

1. **Each fact lives in exactly one place.** Verified facts (dependency file, deploy behaviour, crop
   codes, ids, decisions) live in `docs/STATUS.md` → "Verified facts" and "Decisions log". Other docs
   may *link* to them, not restate them.
2. **If two docs still disagree, this order wins** (highest first):
   1. `docs/STATUS.md` (Verified facts + Decisions log)
   2. `docs/PARALLEL_SESSIONS.md` (who owns which file, which session does what)
   3. `docs/integration/<component>.md` and `docs/integration/README.md`
   4. `docs/FIX_PLAN.md`, then `docs/PROMPTS.md`, then `docs/FINALE_PLAN.md`
3. **Follow the winner and keep going** — then list the disagreement under **"Doc conflicts:"** in
   the PR description so the coordinator fixes the losing doc. **Stop and ask only** if following
   the winner would touch a file your row doesn't own, change the database, spend money, or
   change security rules.
4. **Unknown fact** (nothing in the repo answers it, e.g. a setting only visible in a dashboard):
   ask once, then the answer goes into `STATUS.md` → "Verified facts" via the coordinator, so no
   later session asks again.

## 5. Rules for every session

1. **One session = one row of the session table** (§6). Nothing else.
2. **Start from the latest `main`.** Start a *new* session for each task (don't reuse an old one).
   The session's first step is to confirm it's on the newest `main` and create branch `sNN-short-name`.
3. **Check the prerequisites** in your row are merged into `main`. If not, stop and say so.
4. **Only touch the files your row allows** (§4). Need another file → stop and ask.
4b. **Docs disagree?** Follow §4b: the higher-ranked doc wins, keep going, list it under
   "Doc conflicts:" in the PR. Stop only for files/DB/money/security.
5. Show a short plan first; wait for OK (as `CLAUDE.md` says).
6. Tests + `/check-backend` or `/check-frontend` (whichever side you changed) must pass before the PR. Security-sensitive rows run the `security-reviewer`.
7. **Before opening the PR, merge the latest `main` into your branch again** and re-run the tests —
   other sessions may have merged meanwhile.
8. PR title starts with the session id: `S09: ownership checks for payments (F1+F2)`. The PR
   description lists: what changed, how it was tested, **"Ticks:"** (FIX_PLAN items done), and **"Manual
   steps:"** (SQL to run, env vars to set) — the coordinator copies these into STATUS.md.
9. Don't edit `docs/STATUS.md` or `docs/FIX_PLAN.md` (coordinator does).
10. Keep a session under ~2 hours of work. Bigger rows are split into parts (a, b, …).

### The header to paste at the start of every session

Paste this, fill in the session id, then paste the task prompt from the table:

```
You are session SNN of the FarmNex parallel build. First read docs/PARALLEL_SESSIONS.md sections 4 and 5 and your row SNN in section 6. Make sure you are on the latest main, then create branch sNN-<short-name>. Check that the prerequisites in your row are merged; if not, stop and tell me. Only change the files your row allows — if you need any other file, stop and ask me. Don't edit docs/STATUS.md or docs/FIX_PLAN.md; put "Ticks:", "Manual steps:" and "Doc conflicts:" in the PR description. If two docs disagree, follow section 4b (higher-ranked doc wins) instead of stopping, unless it affects files outside your row, the database, money or security. Before opening the PR, merge the latest main into your branch again and re-run the tests.
```

### Header for sessions in a component repo (S03, S04, S07, S30, S31)

Those repos don't contain this file, so the normal header can't be followed. Paste this instead:

```
You are session SNN of the FarmNex parallel build, working in this component repo only (not farmnex_main). Read this repo's CLAUDE.md and docs/FARMNEX_HOST.md (where it and SPEC.md disagree about the host, FARMNEX_HOST.md wins). Make sure you are on the latest main, then create branch sNN-<short-name>. Only change files inside this repo. Show me a short plan first and wait for my OK. Run this repo's own tests before the PR. PR title starts with "SNN:"; the description lists what changed, how it was tested, the final commit hash, and "Doc conflicts:" for anything in FARMNEX_HOST.md or the farmnex_main docs that looks wrong. Merge the latest main into your branch before opening the PR.
```

---

## 6. The session table (in order)

**How to read it:** a wave can start when everything in "Needs merged" is on `main`. Sessions in the
same wave with different files **can run at the same time**. "→" inside a row means *one after the
other*. Times are Claude + review time.

### Wave 0 — foundations (start immediately; S01–S04 all in parallel)

| Id | What | Prompt (after the header) | Files it owns | Needs merged | Time |
|---|---|---|---|---|---|
| **S01** | Backend foundation: F4, F5, F17, F18 + component slots | "Do FIX_PLAN F4, F5, F17 and F18. Also create `backend/app/modules/__init__.py` and `wiring.py` exactly as §7 of PARALLEL_SESSIONS.md describes, and add a marked section per component (Crop Rescue, forecaster, route optimizer, voice) to `pyproject.toml`, `requirements.txt` and `.env.example`, in the format of §7; `pyproject.toml` is what FastAPI Cloud installs. F18 is approved (add the 7 crops). One commit per item. Don't call F5 done until `pip install .` and `pip install -r requirements.txt` both work in a fresh venv." | `backend/app.zip`, `backend/0.141`, `requirements.txt`, `pyproject.toml`, `.env.example`, `app/main.py`, `app/modules/*`, `.gitignore`, and **new** test files `backend/tests/test_crops.py`, `backend/tests/test_wiring.py` (new files only; `conftest.py` is S05's) | — | 2 h |
| **S02** | Frontend foundation: F15, F16, F14 + slots | "Run `flutter analyze` and list existing errors (fix only ones that stop the build). Put that list in the PR description under \"Analyze findings:\". Then do FIX_PLAN F15, F16, F14. Add these packages to `pubspec.yaml` in one go: `flutter_secure_storage`, `geolocator`, `webview_flutter` (check current versions on pub.dev). In `api_config.dart` add empty marked sections (format in §7): listing, market, cart, payment, bidding, rescue, forecast, logistics, waste, voice; move each existing dead URL into the section of the feature that will replace it (`cropsEndpoint`/`cropBids*` → listing/bidding, `aiPricePrediction*`/`cropPricePrediction*` → forecast, `cropRescueEndpoint` → rescue, `wasteListingsEndpoint` → waste); leave `verificationUploadEndpoint` and `aiChatEndpoint` where they are." | `frontend/**` (except feature files later sessions create) **and the root `README.md`** (F16 updates its "run locally" section) | — | 2.5 h |
| **S03** | Crop Rescue Phase 5 — **in the `farmnex_crop_rescue` repo** (use the component-repo header, §5) | PROMPTS.md **B1** | that repo only | — | 1 h |
| **S04** | Voice login adapter — **in the voice repo** (stretch; **skip in three-lane mode** — voice runs last) | PROMPTS.md **V1** (first prompt) | that repo only | — | 1–2 h |
| M1 | 🧑 Deploy the forecaster to Render (free plan + keep-awake ping — decided, STATUS → Verified facts); then ask the coordinator to record its URL in STATUS | PROMPTS.md **B2** | — | — | 1 h |

### Wave 1 — tests + small fixes (after S01 is merged)

| Id | What | Prompt | Files | Needs merged | Time |
|---|---|---|---|---|---|
| **S05** | Test setup F11 | PROMPTS.md **A4** | `backend/tests/conftest.py`, `backend/tests/*` (setup only), `.github/workflows/*` | S01 | 2 h |
| **S06** | F9 → F6 → F7 → F10 | "Do FIX_PLAN F9, F6, F7, F10 in that order, one commit each. Ask me the F9 and F10 questions first." | `app/main.py`, `app/core/database.py`, `app/main_complete.py`, `app/api/v2/domain_router.py` | S01 | 1.5 h |
| **S07** | Voice pack changes (voice repo, stretch) | PROMPTS.md **V1** (second prompt) | voice repo `domain_packs/` | S04 | 1–2 h |

S05 and S06 run **at the same time** (different files).

### Wave 2 — security + component backends (after S05 is merged)

First, one short session:

| Id | What | Prompt | Files | Needs merged | Time |
|---|---|---|---|---|---|
| **S08** | F3 roles + F1 fast path (unmount the 9 modules — already approved) | "Do FIX_PLAN F3 (only `roles.py` and its own test), then the F1 fast path. The unmount list is approved in docs/STATUS.md; don't ask again." | `app/api/dependencies/roles.py`, `app/api/v2/router.py`, new file `backend/tests/test_roles.py` | S05 | 1 h |

Then **up to 4 at a time** (all need S08 merged):

| Id | What (F1 + F2 together) | Prompt | Files | Time |
|---|---|---|---|---|
| **S09** | Payments | "/fix F1 payment — do F2 for it too." | payment controller/service/repository/schema + new `tests/test_payment.py` | 45 min |
| **S10** | Bids: `bid`, `bid_event` | "/fix F1 bid and bid_event — do F2 for both." | bid + bid_event files + new `tests/test_bid.py` | 1 h |
| **S11** | Orders: `order`, `order_item` | "/fix F1 order and order_item — do F2 for both. Remove the public create routes (approved)." | order + order_item files + new `tests/test_order.py` | 1 h |
| **S12** | Listings: `product_listing`, `product_image`, `crop_batch` | "/fix F1 product_listing, product_image and crop_batch — do F2 for all three." | those files + new `tests/test_listing.py` (also renames `/crop-batchs` → `/crop-batches`) | 1.5 h |
| **S13** | Waste: `waste_record`, `waste_utilization_listing` | "/fix F1 waste_record and waste_utilization_listing — do F2 for both." | those files + new `tests/test_waste.py` | 1 h |
| **S14** | Misc: `buyer_demand_request`, `notification`, `crop_type` | "/fix F1 buyer_demand_request, notification and crop_type — do F2 for all three." | those files + new `tests/test_misc_ownership.py` | 1 h |

The F1 rules for all of these are **approved** (STATUS → Verified facts): don't stop to ask for them.
Each session "files" means its module's controller, service, repository and schema files (no models —
tables never change). Working across modules and test naming: FIX_PLAN F1.

At the same time as S09–S14 (they touch different files):

| Id | What | Prompt | Files | Needs merged | Time |
|---|---|---|---|---|---|
| **S15** | Crop Rescue into the backend | PROMPTS.md **B3** | `app/modules/crop_rescue/`, `app/modules/crop_rescue_host.py`, `migrations/010–011`, its sections in `pyproject.toml`, `requirements.txt` and `.env.example`, `tests/modules/test_crop_rescue.py` | S01, S05, S03 | 2–3 h |
| **S16** | Forecaster connector | PROMPTS.md **B4** | `app/modules/forecast/` (router **and** the small log-writing repository), `app/modules/forecast_host.py`, `migrations/020`, its sections (same three files), `tests/modules/test_forecast.py` | S01, S05, M1 | 2 h |
| **S17** | Route optimizer part 1 (+ driver sign-up, see §10 item 11) | PROMPTS.md **B5** (part 1) | `app/modules/routes_host.py`, `app/modules/logistics_host.py`, `scripts/create_staff_user.py`, `migrations/030`, its sections (same three files), `tests/modules/test_route_optimizer.py`; **only if pip-from-git fails on FastAPI Cloud:** `backend/farmnex_routes/` and the `packages.find` line in `pyproject.toml` | S01, S05 | 3 h |

S15–S17 don't need S08: they don't import `roles.py` — check roles inline as their guides show. Each of
them needs its **component repo added to the session** (S15 `farmnex_crop_rescue`, S16
`farmnex_ai_forecaster`, S17 `farmnex_route_optimization`) — add the folder when you start the session.
S15 copies the Crop Rescue code from the commit recorded in STATUS → Components **after S03 merged**
(the coordinator updates that hash; S03 changes the repo). Test recipe: `docs/integration/README.md` →
"Testing a component". S17's `request-transport` demo endpoint is **not** part 1 (it reads orders): it
comes with S26.

🧑 After S15–S17 merge: run their SQL files and set their env vars (the PR "Manual steps" list them).
Do them **in one batch** if you can.

⚠️ Pairs that are safe in parallel but **merge carefully**: S09 (payments) and S11 (orders) both read
orders — merge S11 first, then have S09 merge `main` and re-run tests (§5 rule 7).

### Wave 3 — marketplace logic + first screens

F12 is a **chain** (same files, one after another). Screens run next to it. Facts these rows rely on
(order steps, accept → order, photos, farm setup): STATUS → Verified facts → "Wave 3 decisions".

**Backend chain (S18 → S19 → S20).** "Files" = the module's controller, service, repository and schema
files (no models — tables never change), same as wave 2. Calling another module's existing
functions is fine; editing its files is not. A session may **edit the earlier session's test file**
only for a rule it deliberately changes (e.g. S18 removes S11's "no public create route" assertion).

| Id | What | Prompt | Files it owns | Needs merged | Time |
|---|---|---|---|---|---|
| **S18** | F12a orders logic | PROMPTS.md **A9** (plan prompt) → then "Continue F12: orders only…" | order + order_item files (adds `POST /orders`: buyer, listing public ids + quantities + own address — optional, default address if left out; `POST /orders/{id}/confirm`: the farmer); stock query goes in **its own** `order_repository.py` (lock the listing row, lower `available_quantity`; give it back on cancel); new `tests/test_order_flow.py`; may edit `tests/test_order.py` | S11, S12 | 2–3 h |
| **S19** | F12b bids + **farmer accepts** a bid (+ Idempotency-Key) | "Continue F12: bids and pre-bid winner — farmer accepts a bid (decided). No double winners; test two accepts at the same time; accept honours Idempotency-Key." | bid + bid_event files; new `tests/test_bid_accept.py`; may edit `tests/test_bid.py`. Accept **calls S18's order-create function** (no edit of order files) | S10, S18 | 2–3 h |
| **S20** | F12c wallet ledger + demo payment (+ unpaid `PLACED` orders expire after 30 min — decided) | PROMPTS.md A9 third prompt | new `app/models/wallet_ledger.py` + **one import line** in `app/domain_model_registry.py`; new `wallet_*` repository/service/schema files; payment controller/service/repository/schema (wallet and demo-pay routes go **inside `payment_controller.py`** — don't touch `router.py`); the accept function in `bid_service.py` (one function: add the 20% HOLD); new `tests/test_wallet.py`; may edit `tests/test_payment.py`. Expose `release_for_order(order_public_id)` for S26. The 30-minute expiry of unpaid `PLACED` orders lives in the new `wallet_*`/payment service files and **calls S18's existing cancel function** (no edit of order files; if that isn't possible, stop and ask) | S09, S19 | 2–3 h |

**Screens (Flutter).** New calls go in your own `lib/core/network/<feature>_api.dart` (rule §4). Shared
Flutter files, so parallel screens don't collide:

- `frontend/lib/screens/home/home_screen.dart`, `screens/market/market_screen.dart`, `widgets/crop_card.dart`: **S21 owns them.** S22 and S23 may add **one line each** (a call to their own new widget) and nothing else; whoever merges later merges `main` again first (§5 rule 7).
- `frontend/lib/localization/app_translations.dart`: nobody owns it — eight language maps in one file would conflict. New strings use `AutoTranslatedText` like the rest of the app. Add a key there only if you truly need `context.t(...)`, and merge `main` right before the PR (conflicts there are "keep both").
- `main.dart` is S02's: no new provider is registered in wave 3. S23 has no provider (a small widget with its own state is enough).
- No Flutter SDK on Atharv's machine and `/check-frontend` stops without one: the check is **CI** (`flutter-check.yml`, STATUS → Verified facts → CI). Open the PR, read CI, and write the exact phone taps.
- `kDemoMode` does not exist yet — don't add it. Remove demo data from the screen you connect; only S25 (waste — a cut candidate in `FINALE_PLAN.md`) may keep it, labelled "demo".

| Id | What | Prompt | Files it owns | Needs merged | Time |
|---|---|---|---|---|---|
| **S21** | Screens: listing + market (+ farm → crop → batch setup) | "/connect-screen listing — then market. New calls go in lib/core/network/listing_api.dart. A farmer needs a farm, a farm crop and a crop batch before a listing (S12 rule): add one small form for them in `lib/core/network/farm_crop_api.dart` (use the existing `BackendService.createFarm` if the farmer has no farm). No product photos — show the crop emoji." | `providers/listing_provider.dart`, `providers/market_provider.dart`, `models/crop_model.dart` (+ new model files), `screens/market/`, `screens/farmer/my_crops_screen.dart`, `widgets/crop_card.dart`, `screens/home/home_screen.dart`, `listing_api.dart`, `farm_crop_api.dart`, `api_config.dart` sections **listing** and **market** | S02, S12 | 4–5 h |
| **S22** | Screen: Crop Rescue | PROMPTS.md B6 (first) | `providers/rescue_provider.dart`, `models/rescue_listing_model.dart`, `screens/rescue/`, `core/network/crop_rescue_api.dart` (copy of the component's Dart client), `api_config.dart` section **rescue**; one line in `home_screen.dart` for the alerts poll | S02, S15 | 2–3 h |
| **S23** | Screens: forecast | PROMPTS.md B6 (second) | `widgets/dialogs/ai_forecast_dialog.dart`, `widgets/apmc_ticker.dart`, new `widgets/ceda_credit.dart` and its logo in `frontend/assets/branding/` (already declared in `pubspec.yaml` — don't touch it), `core/network/forecast_api.dart`, `api_config.dart` section **forecast**; one line each in `market_screen.dart` and `crop_card.dart` only if the dialog's call changes | S02, S16 | 2 h |
| **S24** | Screens: driver / logistics | PROMPTS.md B6 (third) | `providers/logistics_provider.dart`, `screens/logistics/`, `core/network/route_api.dart`, `api_config.dart` section **logistics**, `models/user_model.dart` + the role tile in `widgets/dialogs/auth_dialog.dart` (the app sends `LOGISTIC` and reads `DELIVERY_AGENT` as a guest — driver sign-up must send `DELIVERY_AGENT`, and log-in must map `DELIVERY_AGENT` / `LOGISTICS_MANAGER` to the logistics role), `android/app/src/main/AndroidManifest.xml` (location permissions; `INTERNET` is already there), and a reusable `screens/logistics/track_delivery_button.dart` (order id → delivery status/ETA → **Track** WebView). **S28** puts that button on the order card — S24 doesn't touch `buyer_orders_screen.dart` | S02, S17 | 4–5 h |
| **S25** | Screen: waste | "/connect-screen waste" | `providers/waste_provider.dart`, `widgets/dialogs/waste_to_wealth_dialog.dart`, `models/waste_model.dart`, `core/network/waste_api.dart`, `api_config.dart` section **waste** | S02, S13 | 2 h |

S22 and S23 need a **component repo folder added to the session** (like S15–S17): S22 `farmnex_crop_rescue`
(`integration/flutter/crop_rescue_api.dart`, at the commit in STATUS → Components), S23
`farmnex_ai_forecaster` (`integration/flutter/` kit: `forecast_api.dart`, `ceda_credit.dart`; the kit has no logo file — it was added from CEDA's site in PR 54). If a
folder isn't added, write the client from `backend/app/modules/crop_rescue/api.py` + `schemas.py` (S22)
or `docs/integration/ai-forecaster.md` (S23) — never guess a URL.

S18 → S19 → S20 one after another; S21–S25 in parallel with them (max 3–4 total at once).

### Wave 4 — connect the story

Facts these rows rely on (book truck, checkout paying, wallet buttons, what the bidding API shows):
STATUS → Verified facts → "Wave 4 decisions". Same file rules as wave 3 (new calls in your own
`lib/core/network/<feature>_api.dart`; `main.dart`, `app_translations.dart`, `backend_service.dart` as in
wave 3; Flutter is checked by CI).

| Id | What | Prompt | Files it owns | Needs merged | Time |
|---|---|---|---|---|---|
| **S26** | Route optimizer part 2 (order → load → delivered → pay) | PROMPTS.md B5 (part 2) | `app/modules/logistics_host.py` (adds `request-transport` + staff `resync`), `app/modules/routes_host.py` (listener), new `tests/modules/test_route_orders.py`. **Host files only** (Atharv): no edit of order files, so the load is booked by `request-transport`, not on confirm | S17, S18, S20 | 2 h |
| **S27** | Screen: bidding | "/connect-screen bidding" | `providers/bidding_provider.dart`, `models/bid_model.dart` (+ new model files), `screens/bidding/`, `screens/buyer/buyer_bids_screen.dart`, `widgets/dialogs/crop_pre_bidding_dialog.dart`, new `core/network/bidding_api.dart`, `api_config.dart` section **bidding** (`cropBidsWsUrl` was kept, marked dead, because the unused `websocket_service.dart` still reads it — remove both together later; stop using `websocket_service.dart`, don't delete it). Keep `CropPreBiddingDialog(crop: …)`'s constructor — S21's `market_screen.dart` and `home_screen.dart` call it. The farmer opens an event on their own listing and accepts a bid here; the won order and its payment are S28's orders screen | S19, S21 | 2–3 h |
| **S28** | Screens: cart → checkout → payment (+ the order card: status, **Track** button from S24) | "/connect-screen cart — then payment (label it Pay (demo)). Orders come from PaymentProvider today; connect the buyer orders screen too and place `track_delivery_button.dart` on the order card." | `providers/cart_provider.dart`, `providers/payment_provider.dart`, `models/payment_model.dart` (+ new order model files), `screens/buyer/cart_screen.dart`, `screens/buyer/buyer_orders_screen.dart`, `screens/payment/` (checkout + wallet), `core/payments/payment_gateway.dart` (must stop being the default), new `core/network/order_api.dart` + `payment_api.dart`, `api_config.dart` sections **cart** and **payment**. Keep `CheckoutScreen` / `CheckoutItem`'s constructors (S21's `market_screen.dart` and `crop_card.dart` call them) and `PaymentProvider`'s public members used by `profile_screen.dart` and S24's `logistics_screens.dart` (`releaseEscrow` becomes a no-op — money is released by the server). Wallet: hide Top up / Withdraw | S18, S20, S21, S24 | 3–4 h |
| **S29** | Voice tool endpoints, read-only (stretch) | PROMPTS.md **V2** | voice pre-flight sets this (voice runs last, §6b) | S15, S16, S17, S08 | 2–3 h |
| **S30** | Voice http handlers (voice repo, stretch) | PROMPTS.md **V3** | voice repo only | S29 deployed, S07 | 1 h |
| **S31** | Voice Flutter package (voice repo, stretch) | PROMPTS.md **V4** first prompt | voice repo only | S04 | 3–4 h |
| **S32** | Voice mic in the app (stretch) | PROMPTS.md **V4** second prompt | voice pre-flight sets this | S31, S02 | 1–2 h |

No farmer-orders screen is built (Atharv: only what's necessary) — in the demo the farmer confirms
and books the truck through `/docs`. S27 and S28 run in parallel (different files).

### Wave 5 — finish (one at a time)

Facts these rows rely on (demo accounts, how the demo data is made, what S33 fixes, who fixes what
S35 finds): STATUS → Verified facts → "Wave 5 decisions". Sessions still can't log in (every account
uses a real one-time code on a real phone), so **S34 and S35 never call a logged-in endpoint
themselves** — Atharv or the tester gives S34's script the tokens (see the row) and walks the demo
on a phone.

**Before S34 starts (Atharv, 🧑):** the route optimizer must be on in production (STATUS → Waiting
list, S17 steps), the `LOGISTICS_MANAGER` account created (`scripts/create_staff_user.py`), and the
`wallet_ledger` RLS line run. S34 can write the files without them, but its script can't be tried.

| Id | What | Prompt | Files it owns | Needs merged | Time |
|---|---|---|---|---|---|
| **S33** | Whole-app security review + fixes (HIGH, and MEDIUM when small) | PROMPTS.md **A10** | Reads everything that is merged (backend and the Flutter app's secrets/tokens; **not** voice — it isn't built yet, and its own PRs get the normal `security-reviewer` review). **Edits:** only the files of a finding, one commit per finding with the finding in the message; the module's own test file or a new `backend/tests/test_security_review.py`; `backend/app/services/me_service.py` (the scoped-list tidy-up). **Never:** `backend/app/models/*` existing columns, `migrations/` (a fix that needs a table change → stop and ask), `conftest.py`, `.github/workflows/*`, docs | S26, S27, S28 (all merged) | 2 h |
| **S34** | Demo data + `docs/DEMO.md` | PROMPTS.md **B7** + the DEMO.md prompt in "Final hours" | new `docs/DEMO.md`, `backend/scripts/seed_demo.py`, `backend/scripts/simulate_driver.py` (nothing else; the scripts call only our public API with tokens from environment variables — never the database, never a secret in a file) | S33 | 2 h |
| **S35** | Final dry run (report only) | "Final hours" second prompt in PROMPTS.md | none — it edits **no file**; it reports, most demo-critical first | S34 | 1 h |

**S35 runs as the coordinator** (the full `/check` is allowed for it). Without a `.env` the local
server start in `/check` can't run: it says so and relies on CI (Backend tests, Flutter check) plus
the public production checks (`/health`, `/db`, `/docs`, `/openapi.json`, the forecaster's `/health`,
one tracking page). The logged-in walk-through is the tester's, on a phone, from `docs/DEMO.md`.

**After S35 — fixes:** Atharv starts **one small session per bug** (named `S35-fix1`, `S35-fix2`, …),
most demo-critical first. Such a session may edit the files that bug needs, but only after Atharv
says OK in chat (the "ask the person driving you" rule); one bug per PR. After H42 of the build
(FINALE_PLAN) nothing new, only these fixes.

### The coordinator session (C) — run after every 2–4 merges

```
You are the coordinator session. Read docs/PARALLEL_SESSIONS.md. Look at the PRs merged since the last update (git log on main). Update docs/STATUS.md (counts, component table, log) and tick docs/FIX_PLAN.md using each PR's "Ticks:" line; collect every "Manual steps:" line that isn't done yet into a "Waiting for Atharv" list at the top of STATUS.md. Run the backend tests and /check on main. Then tell me which session ids from section 6 are now ready to start (all their "Needs merged" are on main). Also fix the docs listed under any PR's "Doc conflicts:" (the higher-ranked doc in §4b wins) and move any newly confirmed fact into STATUS.md → "Verified facts". Open a PR titled "C: status update".
```

### Docs pre-flight (C) — run before starting each wave

```
You are the coordinator session doing a docs pre-flight for wave N of docs/PARALLEL_SESSIONS.md. For every session in that wave: read its row, the prompt it points to, and every doc that prompt and the /fix, /integrate or /connect-screen commands point to. List (a) any two places that say different things, (b) any fact the session will need that no doc answers, (c) any file it would need that its row doesn't allow. Fix (a) and (c) in the docs following §4b (one fact, one place). For (b), ask me the question, then record the answer in STATUS.md → "Verified facts". Open a PR titled "C: pre-flight wave N". Change only docs.
```

---

## 6b. Three-lane mode (one person running 3 sessions — recommended)

If one person drives everything, run **exactly 3 sessions at a time**, one per lane. When a session
finishes and its PR is merged, start that lane's next session. Same session ids, prompts and file
rules as above — this only fixes the order per lane. Some rows are grouped into one session (commits
stay separate) to cut start-up, review and merge overhead; keep each session under ~2 hours.

| Lane | Model / effort | Sessions, in order (→ = wait for the previous one to merge) |
|---|---|---|
| **A — backend & security** (critical path) | strongest model, high effort for S08–S20 and S33; a lighter model is fine for S01/S05 | S01 → S05 → S08 → **S11+S09** (orders, then payments; one session) → S10 → S18 → S19 → S20 → S33 |
| **B — components & catalogue** | medium model/effort; strongest for S17 (guard) | S03 (Crop Rescue repo) → S06 (after S01) → S12 (after S08) → S15 → S16 → S17 → **S13+S14** (one session) → S26 |
| **C — Flutter** | medium model/effort | S02 → S21 (after S12) → S22 (after S15) → S23 (after S16) → S24 (after S17) → S25 → S27 (after S19) → S28 (after S20) → S34 (after S33) → S35 (run as coordinator) |
| **Coordinator** | lightest model, low effort; short (~15 min) | pre-flight before each lane moves to a new wave; status update after every 2–4 merges (§6 prompts). Not one of the 3 lanes. |
| **Voice (last)** | — | Only after S26, S28 and S33 are merged **and** there's time left: S04 → S07 → S29 → S30 → S31 → S32. Otherwise skip; the demo video can mention it as next. |

If a lane is waiting on another lane (e.g. C waits for S12), don't start something out of order —
use the gap to review/merge PRs, run SQL, set env vars, or phone-test.

**Keeping sessions cheap:** start each task with the session header + the short prompt (don't ask it
to "understand the whole repo"); use `/check-fast` while working and the one-side check before the
PR; if a session gets long, use `/compact` (check with `/context`), or finish and start a fresh one.

## 7. What S01 builds so component sessions never collide

**Marked sections** (one format everywhere, so sessions can find and extend their own):
S01 (backend) and S02 (`api_config.dart`) create them empty; a later session edits only between its
own two marker lines.

```
# >>> crop-rescue >>>        (backend: pyproject.toml, requirements.txt, .env.example — use "#")
# <<< crop-rescue <<<
// >>> listing >>>           (frontend: api_config.dart — use "//")
// <<< listing <<<
```
Backend section names: `crop-rescue`, `forecast`, `routes`, `voice`. Frontend section names: `listing`,
`market`, `cart`, `payment`, `bidding`, `rescue`, `forecast`, `logistics`, `waste`, `voice`. In
`pyproject.toml` the markers sit as comments inside the `dependencies` list. In `.env.example` each
backend section already holds its `ENABLE_*` flag (default `false`) and the variables its guide names.

`backend/app/modules/wiring.py` knows all four components up front; each component session only
creates **its own** `<name>_host.py`.

```python
# backend/app/modules/wiring.py  (created by S01 — later sessions don't edit it)
COMPONENTS = [
    # (flag env var,            host module under app.modules)
    ("ENABLE_CROP_RESCUE",      "crop_rescue_host"),
    ("ENABLE_FORECAST",         "forecast_host"),
    ("ENABLE_ROUTE_OPTIMIZER",  "routes_host"),
    ("ENABLE_VOICE_TOOLS",      "voice_tools_host"),
]
# mount_components(app): for each flag that is "true", import app.modules.<host> *inside the
# function* and call its mount(app). If the import or mount fails (missing module, bad config),
# log ONE clear error and continue — the backend must still start.
# start_components() / stop_components(): call start()/stop() on mounted hosts that have them.
```
Each `<name>_host.py` exposes `mount(app)` and optionally `start()` / `stop()`. `app/main.py` calls
`mount_components(app)` once and `start_components()` / `stop_components()` in its lifespan.
S01 also adds `app/modules/crops.py` with the crop-name map (F18): `crop_types.name` (capitalised,
e.g. `Tomato`) → Crop Rescue `crop_code` (lowercase: tomato, spinach, okra, brinjal, cauliflower,
grapes, capsicum, cucumber), forecaster crop (`Onion`, `Tomato`, `Potato`), voice crop id (lowercase);
`None` where a component doesn't support the crop.

---

## 8. Keeping the pieces working together

- **Before every wave** run the **docs pre-flight** (§6) — it catches the questions a session would
  otherwise stop and ask, before any session starts.
- **After every wave** (and at FINALE_PLAN checkpoints H12/H24/H38) run the coordinator session:
  full tests on `main` + `/check`. A wave isn't "done" until `main` is green.
- **Tag a known-good version** after each green wave, so you can roll back on stage:
  ask the coordinator "create git tag `good-wave-N` on main and push it".
- **Phone test after each wave** (tester): install the app built from `main` against the deployed
  backend, run the part of the demo story that exists so far, note problems as new sessions.
- **Deploy after each wave**, not only at the end (and run pending SQL / env vars first).

---

## 9. When things go wrong

| Situation | What to do |
|---|---|
| PR shows a merge conflict | In that session: "Merge the latest main into this branch, resolve the conflicts keeping both sides' intent, re-run tests, push." If both sides changed the same logic, it will ask you which to keep. |
| A session wants to edit a file it doesn't own | Say no, or pause it and check who owns the file. Usually the right fix is a small separate session. |
| A prerequisite isn't merged yet | Don't start the session. Start a different ready one instead (ask the coordinator). |
| Two sessions made the same helper | Keep the one merged first; the later session removes its copy after merging `main`. |
| Tests pass in the session but `main` breaks after merge | Coordinator: "Find which merge broke main and open a fix PR." Fix before merging anything else. |
| A session is going in circles / over its time budget by 50% | Stop it. Start a fresh session with a smaller task and the error text. |
| Usage limit reached | Switch to a teammate's account for the next session; don't restart the same long session. |
| Live app broken after a deploy | Re-deploy the last `good-wave-N` tag; turn off the broken component's flag on FastAPI Cloud. |

---

## 10. Things you may not know yet

1. **Sessions only know what's in the repo.** A decision you gave in one chat is invisible to every
   other session unless it's written in `docs/STATUS.md` or a guide.
2. **"Merged" doesn't mean "live" — unless GitHub is connected.** With FastAPI Cloud's GitHub
   integration, **every push to the default branch (`main`) deploys automatically**, and there are no
   preview deployments for PRs. So: merge only green PRs, and set any new env vars on FastAPI Cloud
   **before** merging the PR that needs them. Check in the FastAPI Cloud dashboard whether GitHub is
   connected; if not, deploy by hand (`fastapi deploy`) after each wave.
   Production installs dependencies from `backend/pyproject.toml` (not `requirements.txt`).
3. **Cloud sessions can't reach your Supabase or `.env`** (and must not). They test on a temporary
   database. The first real test of SQL, env vars and components is after you deploy.
4. **SQL files don't run themselves.** A component merged without its SQL run fails with
   `relation … does not exist`. Keep the coordinator's "Waiting for Atharv" list short.
5. **Order matters more than speed.** Starting a session before its prerequisites are merged is the
   #1 way to create rework.
6. **SIH finale rules.** Check the official SIH 2026 finale rules for AI tools and pre-built code, and
   confirm venue internet. If AI tools or internet are limited there, finish as much as possible
   *before* the finale and keep a fully offline demo backup (recorded video + local run).
7. **Review is real work.** Plan 10–15 minutes per PR. Let a second person review too, and always read
   the `security-reviewer` output on auth / money / bid PRs.
8. **Keep secrets out of chats.** Never paste database passwords or API keys into a session; set them
   on FastAPI Cloud / Render yourself.
9. **Don't edit files on GitHub's website while sessions are running** on those files — it causes
   conflicts the sessions don't expect.
10. **Squash and merge.** Use GitHub's "Squash and merge" button so each session is one clean commit on
    `main` (easy to find and undo).
11. **Drivers and managers can't sign up today.** Public registration allows only FARMER, BUYER and
    VENDOR (`public_registration_roles` in `app/core/config.py`). The logistics demo needs a
    DELIVERY_AGENT (driver) and a LOGISTICS_MANAGER. S17 handles it: allow DELIVERY_AGENT in public
    sign-up through the env setting (fine for the prototype), and create the manager/admin accounts
    with a small one-off script that Atharv runs — never make ADMIN or MANAGER self-sign-up roles.

---

## 11. One-page cheat sheet

```
Before each wave:        C pre-flight (docs only) → merge it → start the wave
Wave 0 (now, parallel):  S01 backend foundation | S02 frontend foundation | S03 Crop Rescue Ph5 | M1 deploy forecaster   (S04 voice auth: skip, voice runs last)
Wave 1 (after S01):      S05 tests  ‖  S06 small fixes  ‖  S07 voice pack
Wave 2 (after S05):      S08 roles+unmount → then ‖ S09 pay ‖ S10 bids ‖ S11 orders ‖ S12 listings ‖ S13 waste ‖ S14 misc
                         and ‖ S15 Crop Rescue ‖ S16 forecaster ‖ S17 routes pt1     (max 3–4 per person at once)
                         🧑 run SQL + env vars for S15–S17
Wave 3:                  S18 → S19 → S20 (F12 chain)  ‖  S21 listing/market ‖ S22 rescue ‖ S23 forecast ‖ S24 logistics ‖ S25 waste
Wave 4:                  S26 routes pt2 ‖ S27 bidding ‖ S28 checkout   (+ voice S29–S32 if on budget)
Wave 5 (one at a time):  S33 security review → S34 demo data → S35 dry run → FREEZE
Voice (S04, S07, S29–S32): only after S26, S28, S33 — the lowest priority, an add-on
One person?              use §6b three-lane mode instead of whole waves
Coordinator C:           after every 2–4 merges
```
