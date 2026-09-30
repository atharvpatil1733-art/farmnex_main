# Copy-paste prompts for Claude Code

> **Running several sessions at once?** Use `docs/PARALLEL_SESSIONS.md` for the order and file
> rules: paste its session header first, then the prompt from here that its session table points to.

Use with `docs/FINALE_PLAN.md` (who does what, when). Rules:
- **One fresh Claude Code session per prompt** (fewer mistakes, less usage).
- **Merge the PR before the next prompt** in the same stream.
- 🧑 = something a person must do by hand; Claude Code will remind you.
- Each prompt shows its **time budget**. If it runs 50% over, stop and ask the team lead.

---

## Step 0 — first session (any stream, no changes)

```
Read CLAUDE.md, docs/FINALE_PLAN.md, docs/FIX_PLAN.md and docs/STATUS.md. In simple words, tell me the plan, what my stream does first, and anything that looks risky. Don't change anything.
```

---

## Stream A — Backend core & security

**A1. Junk files** (15 min)
```
/fix F4
```

**A2. Dependencies** (30 min) — FastAPI Cloud installs from `backend/pyproject.toml` (STATUS → Verified facts); keep `requirements.txt` matching it.
```
/fix F5
```

**A3. Load .env first + component settings list + one crop list** (1 h)
```
/fix F17
```
```
/fix F18
```

**A4. Test setup** (2 h)
```
/fix F11 — if Docker isn't available here, install PostgreSQL inside this session for the test database. Never use the Supabase database for tests. Keep the test helpers small: a test database fixture, a make-user-with-role helper, a make-token helper, and an HTTP client.
```

**A5. Roles** (30 min)
```
/fix F3
```

**A6. Unmount unused modules** (30 min) — why unmount instead of delete or "fix last": FIX_PLAN F1 "Why unmount now".
```
/fix F1 fast path — the list of 9 modules is already approved (docs/STATUS.md → Verified facts); don't ask again. Remove only those from the modules list in api/v2/router.py. Don't delete any files or tables.
```

**A7. Ownership, one module at a time** (~30–45 min each)
```
/fix F1 payment — do F2 for payments in the same change. The F1 rules table is approved (docs/STATUS.md); apply the payments row without asking.
```
Repeat with the next module name, in this order (skip any you unmounted in A6):
`bid` → `bid_event` → `order` → `order_item` → `product_listing` → `product_image` → `crop_batch` → `waste_record` → `waste_utilization_listing` → `buyer_demand_request` → `notification` → `crop_type`
Small ones can share a session: `/fix F1 notification and crop_type — ...`

**A8. Pooler check + small fixes** (1.5 h, one session each)
```
/fix F9 — ask me which port the production DATABASE_URL uses. Don't read .env.
```
```
/fix F6
```
```
/fix F7 — we use the Android app; ask me if we also deploy the Flutter web build.
```
```
/fix F10 — ask me to confirm FastAPI Cloud runs app.main:app before deleting anything.
```

**A9. Marketplace logic — plan first** (≈8 h total)
```
/fix F12 — build only the "Prototype minimum" in FIX_PLAN. First explain the flow in simple words (order → confirmed → delivered; pre-bid → winner → 20% hold → release on delivery) with the status steps and the new wallet_ledger table. Wait for my OK before writing code.
```
Then, one per session:
```
Continue F12: orders only (server totals, stock, statuses), with tests.
```
```
Continue F12: bids and pre-bid winner (decided: the farmer accepts a bid, and accepting creates the winner's PLACED order — STATUS → Verified facts → Wave 3 decisions; no double winners — test two accepts/bids at the same time; accept honours Idempotency-Key), with tests.
```
```
Continue F12: wallet_ledger + demo payment (hold 20% on win, release once on delivered), with tests. wallet_ledger is a new core model created by create_all at startup (FIX_PLAN F12) — no SQL file.
```
🧑 Nothing to run: after deploy, check in Supabase Table Editor that `wallet_ledger` exists.

**A10. Security review of everything** (2 h)
```
Act as a hackathon judge who tests security. Ask the security-reviewer agent to review every mounted endpoint and all integrated components, trying to access one user's data as another user. Explain the findings simply, then fix everything marked HIGH, one commit each.
```

---

## Stream B — Components

**B1. Crop Rescue: finish its Phase 5 — in the `farmnex_crop_rescue` repo** (1 h). Start the session with the **component-repo header** from `PARALLEL_SESSIONS.md` §5 (that repo doesn't contain the main app's docs). Still needed: as of 2026-09-29 that repo has no `integration/` folder or `INTEGRATION.md` yet.
```
/build-phase 5 — first read docs/FARMNEX_HOST.md in this repo and follow it where it differs from SPEC.md (farmer id = users.public_id, own CR_DATABASE_URL, never pass the host's async engine).
```

**B2. Forecaster: put it online** (1 h) 🧑 Follow Step 1 of `integration/INTEGRATION.md` in the `farmnex_ai_forecaster` repo (Render). Check `https://<your-render-url>/health` shows `"status":"ok"`.

**B3. Crop Rescue into the main app** (2–3 h)
```
/integrate crop-rescue — the source is the farmnex_crop_rescue repo at the commit recorded in docs/STATUS.md → Components (updated after S03 merged; add that repo folder to this session).
```
🧑 Run `010_cr_crop_rescue.sql` and `011_cr_demo_seed.sql` in Supabase. Set on FastAPI Cloud: `ENABLE_CROP_RESCUE=true`, `CR_DATABASE_URL` (session pooler, psycopg form), `CR_ENABLE_SIMULATE=true`.

**B4. Forecaster into the main app** (2 h)
```
/integrate ai-forecaster — the forecaster is deployed at the URL in docs/STATUS.md → Verified facts → Forecaster URL (if it still says `<not set>`, stop: M1 isn't done). Our login is FarmNex's own JWT, not Supabase Auth; follow the "Important" table in the guide.
```
🧑 Run `020_fc_forecast_logs.sql`. Set `ENABLE_FORECAST=true`, `FORECASTER_URL`, `FORECASTER_API_KEY` on FastAPI Cloud.

**B5. Route optimizer backend** (5–6 h, two sessions)
```
/integrate route-optimizer — part 1: install farmnex_routes pinned to the commit in the guide, SQL file, wiring with the ROUTES_DATABASE_URL checks, the allow-list + ownership guard, and the vehicle host endpoints. Tests for the guard. Stop before Slip 2/3.
```
🧑 Run `030_rt_route_tables.sql`. Set `ENABLE_ROUTE_OPTIMIZER=true`, `ROUTES_DATABASE_URL`, `ROUTES_AUTO_CREATE_TABLES=false`, `ROUTES_PUBLIC_BASE_URL=https://farmnex-a.fastapicloud.dev`, `PUBLIC_REGISTRATION_ROLES=["FARMER","BUYER","VENDOR","DELIVERY_AGENT"]`. Run `scripts/create_staff_user.py` once for the LOGISTICS_MANAGER account.

After Stream A finishes A9 (orders):
```
/integrate route-optimizer — part 2: Slip 2 (CONFIRMED order → load, with the coordinate and weight checks) and Slip 3 (listener → order DELIVERED → wallet release once), following the guide. Tests.
```

**B6. Component screens** (one session each)
```
/connect-screen rescue — use the Crop Rescue Dart client from the component repo (integration/flutter/crop_rescue_api.dart; add that repo folder to the session) on ApiClient().dio, paths under /api/v2/rescue. Take the crop list from GET /rescue/crops.
```
```
Connect the AI forecast dialog and the APMC ticker to /api/v2/forecast (docs/integration/ai-forecaster.md step 7). Use a 100-second timeout only for forecast calls and show "waking up the forecaster…" while waiting. Show the CEDA credit (kit's ceda_credit.dart and logo from the farmnex_ai_forecaster repo folder; logo into frontend/assets/branding/).
```
```
/connect-screen logistics — driver flow from docs/integration/route-optimizer.md "Flutter": vehicle, go online, trip, stop buttons, GPS ping only while the trip screen is open, and a reusable Track button widget (S28 places it on the order card) that opens tracking_url in a WebView. `geolocator` and `webview_flutter` are already in pubspec.yaml; add the Android location permissions. Fix the driver role: the app must send DELIVERY_AGENT and read it back (STATUS → Verified facts).
```

**B7. Demo seed** (1 h)
```
Prepare demo data for the route optimizer against production: one driver vehicle near Pune and three pending loads from two farmers to the same buyer, using our host endpoints (not the component's blocked routes). Write the steps into docs/DEMO.md.
```

---

## Stream C — Flutter core

**C1. Quick fixes** (2 h total, one session each)
```
/fix F15
```
```
/fix F16
```
```
/fix F14
```

**C2. Screens** (after the backend part is fixed — see FINALE_PLAN dependencies)
```
/connect-screen listing
```
```
/connect-screen market
```
```
/connect-screen bidding
```
```
/connect-screen cart
```
```
/connect-screen payment — use the demo payment from F12; label it "Pay (demo)".
```
```
/connect-screen waste
```

**C3. Demo accounts** (1 h)
```
List the demo accounts we need (FINALE_PLAN "Demo safety kit") and how to create each one through the app or the API. Don't create them in the database directly.
```

---

## Voice (stretch — read-only first; see docs/integration/voice-assistant.md)

**V1. In the `Farmnex-Voice-Assistant` repo** (2–3 h, one session each):
```
Read docs/FARMNEX_HOST.md and do change 1 only: a generic RS256 JWT AuthVerifier adapter (FarmNex public key, issuer farmnex-api, audience farmnex-mobile, and it must reject tokens whose "type" claim isn't "access"). Tests with a locally generated key pair. Show me the plan first.
```
```
Read docs/FARMNEX_HOST.md and do changes 2 and 4: rename the pack to FarmNex, update the crop list and knowledge docs to the real FarmNex rules, add Marathi crop-rescue and pre-bidding docs, and replace request_crop_rescue with get_rescue_alerts and get_rescue_matches (still mock handlers with new fixtures). Run the golden evals and report the numbers.
```
🧑 Create a **second, free Supabase project** for the voice assistant and run `supabase/migrations/0001_voice_core.sql` there. Deploy the voice backend (FARMNEX_HOST.md change 6) and put the FarmNex **public** key in its settings.

**V2. In `farmnex_main`** (after Crop Rescue + forecaster are integrated; 2–3 h):
```
/integrate voice-assistant — part 1: the read-only voice tool endpoints (demand, rescue-alerts, rescue-matches, pickup) in backend/app/modules/voice_tools_host.py (flag ENABLE_VOICE_TOOLS), returning exactly the voice pack's fixture shapes, reusing our services so ownership applies. Tests: another farmer's data is never returned.
```

**V3. Back in the voice repo** (1 h):
```
Switch get_demand_forecast, get_rescue_alerts, get_rescue_matches and get_pickup_status to http handlers pointing at https://farmnex-a.fastapicloud.dev/api/v2/voice-tools/... with forward_user_jwt (forecast timeout_s 12). Keep contracts unchanged. Run the evals in live mode against a test farmer account.
```

**V4. Flutter mic** (5–6 h). First in the voice repo:
```
Implement M5 with the flutter-voice-client skill, but without the Supabase-login demo app: FarmNex is the host app (docs/FARMNEX_HOST.md). The voice_assistant package takes a tokenProvider callback, handles auth.refresh and close codes 4400/4401/4403, and has no FarmNex words inside. Check package choices on pub.dev first.
```
Then in `farmnex_main`:
```
/integrate voice-assistant — part 2: add the voice_assistant Flutter package as a git dependency pinned to a commit, tokenProvider from our StorageService, mic button in ai_assistant_dialog, client actions, mic permission and consent notice. Keep the old on-device voice as offline fallback.
```

**V5. Only if F12 is done and it's before H36:** write tools (`create_prebid_listing`, `accept_bid`) with `Idempotency-Key` handling on our side.

---

## Final hours (everyone)

```
Write docs/DEMO.md: a 5-minute demo script for the story in FINALE_PLAN (listing → pre-bid → Crop Rescue alert + forecast → confirmed order → pooled route → tracking → payment released), with demo accounts and exact taps. Check each endpoint it uses responds on production.
```
```
Run /check and a full demo dry-run checklist against production. List anything broken, most demo-critical first. Don't fix yet.
```

---

## Anytime

```
Explain that again more simply, like I'm new to coding.
```
```
Here's the error: <paste>. Find the cause, explain it simply, and fix it. Don't change unrelated code.
```
```
Read docs/STATUS.md, docs/FIX_PLAN.md and docs/FINALE_PLAN.md. What's done, what's left in my stream, and are we on budget?
```
```
/check
```
