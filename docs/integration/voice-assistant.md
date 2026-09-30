# AI voice assistant → main app

**Source repo:** `atharvpatil1733-art/Farmnex-Voice-Assistant` (commit: see `docs/STATUS.md` → Components,
2026-09-29 — milestone M4 done). Backend `backend/` (FastAPI, `voice_core` package, `uv`), domain
pack `domain_packs/farm_marketplace/`, DB migration `supabase/migrations/0001_voice_core.sql`.
**What it does:** push-to-talk in Hindi / Marathi / English over a WebSocket (`/v1/voice`), speech
→ text → LLM with tools → spoken answer (~2.4 s to first audio). Writes (create listing, accept bid,
…) need a spoken or button "yes", enforced in code, executed once (idempotency key).
**Status: stretch goal.** Read-only version (section "Minimum demo") ≈ **10–12 h**: voice repo
changes 3–4 h + FarmNex voice-tool endpoints 2–3 h + Flutter mic 5–6 h. Write tools add **3–4 h**
and need F12.

Follow the shared rules in `README.md` in this folder. This file lists what's specific.

---

## What's ready vs. what's missing

| Part | State at `483599b` |
|---|---|
| Speech in/out (Groq Whisper STT, edge-tts; Sarvam optional), segmenter, hi/mr/en number & date reading | ✅ done, measured |
| Agent loop, prompt, language switching, confirmation gate, idempotency, audit rows | ✅ done, 355 tests, safety review passed |
| WebSocket protocol (`docs/PROTOCOL.md`) + REST `/v1/chat`, `/v1/confirm` | ✅ done |
| HTTP tool handler (calls a host API, forwards the user's token) | ✅ done (default timeout 4 s) |
| **Login** | ❌ only a dev fake (`dev-token`); the server **refuses to start outside `APP_ENV=dev`** |
| **Tools** | ❌ all 8 use fixture files (`handler: {type: mock}`) — fake data |
| **Flutter client (M5)** | ❌ not built; the planned demo app uses Supabase login, which FarmNex doesn't use |
| Pack naming | ⚠️ `app_name: "BhumiBij"` — should be FarmNex |
| Crop list | ⚠️ `onion, tomato, soybean, pomegranate` — only **tomato** is supported by every FarmNex component |

---

## Changes in the voice repo

These are listed for the voice repo in its `docs/FARMNEX_HOST.md` too.

1. **FarmNex login adapter (1 h).** A generic `AuthVerifier` adapter for RS256 JWTs (no domain words,
   so it can live in `voice_core/adapters/jwt_rs256/`), selected by config
   (`AUTH_PROVIDER=jwt_rs256`, `JWT_PUBLIC_KEY_PEM` or `JWT_PUBLIC_KEY_PATH`, `JWT_ISSUER=farmnex-api`,
   `JWT_AUDIENCE=farmnex-mobile`). It must:
   - verify signature, `exp`, `iss`, `aud` with the FarmNex **public** key only (never the private key);
   - **require `type == "access"`** — FarmNex signs refresh (30-day) and registration tokens with the
     same key; without this check a stolen refresh token would open a voice session;
   - return `Principal(user_ref=payload["sub"])` (the user's `public_id`);
   - allow `APP_ENV=prod` to start once this adapter is configured.
2. **Pack: FarmNex facts (30 min).** `app_name: "FarmNex"`; crop enum → the crops FarmNex can serve
   (see "Crops" below); knowledge docs updated to the real rules (20% advance on a won pre-bid,
   paid after delivery; Crop Rescue = spoilage alerts + nearby buyers). Marathi knowledge files are
   missing (`knowledge/mr/`) — add at least `crop-rescue` and `pre-bidding` for the demo.
3. **Pack: tools → `http` handlers (1–2 h).** Point each tool at the FarmNex "voice tool" endpoints
   below with `handler: {type: http, path: …}`; keep tool names and parameters. `HOST_API_BASE_URL=https://farmnex-a.fastapicloud.dev`,
   `HOST_API_AUTH_MODE=forward_user_jwt`. Give the forecast tool `timeout_s: 12`.
4. **Replace `request_crop_rescue(listing_ref, days_left)`** (and update the eval cases that use it). It doesn't match the real Crop Rescue
   component, which works on *lots* (crop, kg, harvest time, location, storage) and raises alerts
   itself. For the prototype use two read tools instead: `get_rescue_alerts` and
   `get_rescue_matches(lot_ref)`, plus (optional, write) `mark_rescue_lot_sold(lot_ref)`.
5. **Database: its own Supabase project (recommended).** The migration creates a `voice` schema and
   the `vector` + `pgcrypto` **extensions**. Our rule for the main DB is "only add prefixed tables,
   no extensions", so run `0001_voice_core.sql` in a **separate free Supabase project** (Supabase
   allows two free projects). Zero risk to the marketplace data. If Atharv prefers one project, he
   must approve the extension + schema explicitly and record it in `docs/STATUS.md`.
6. **Deploy (1–2 h).** A host that supports long WebSockets: run
   `uvicorn app.main:app --ws-max-size 65536`. Render's free plan sleeps (~1 min wake + ~6 s DB
   connect) → warm it before judging, or use a paid instance. Venue fallback: run it on a laptop and
   expose it with a tunnel (e.g. `cloudflared`) — test this once before the finale.
7. **LLM free-tier limits.** Status notes say the free chain allows about **1 turn per minute per Groq
   model**. For judging: a paid key, or a longer `LLM_FALLBACK_CHAIN`, and pause between questions.
   Run the latency check (`voice_core.evals.latency`) once on the demo network.
8. **M5 Flutter package without the Supabase-login demo app** — FarmNex is the host (see "Flutter" below).

---

## Changes in farmnex_main

### Voice tool endpoints (3–4 h for reads)

The voice tools expect specific response shapes (see the pack's `fixtures/*.json`). The HTTP
handler can only pick a sub-object (`pick:`), not reshape data. So add a small router in
`backend/app/modules/voice_tools_host.py` (flag `ENABLE_VOICE_TOOLS`), mounted at `/api/v2/voice-tools` with
`Depends(get_current_user)`, whose endpoints **reuse our services** (so F1 ownership applies) and
return exactly the fixture shape. One endpoint per tool:

| Voice tool | Kind | FarmNex endpoint → source | Needs first |
|---|---|---|---|
| `get_demand_forecast(crop)` | read | `GET /voice-tools/demand?crop=` → forecaster `/forecast/demand` for the user's farm district; map `HIGH/NORMAL/LOW` → `rising/stable/falling` | forecaster integrated |
| `get_rescue_alerts` (new) | read | `GET /voice-tools/rescue-alerts` → Crop Rescue alerts for this farmer | Crop Rescue integrated |
| `get_rescue_matches(lot_ref)` (new) | read | `GET /voice-tools/rescue-matches/{lot_ref}` → Crop Rescue matches | Crop Rescue integrated |
| `get_pickup_status(order_ref)` | read | `GET /voice-tools/pickup?order_ref=` → route optimizer `delivery_for_order` | route optimizer integrated |
| `get_my_listings(status)` | read | `GET /voice-tools/listings` → own listings | F1 product_listing |
| `get_order_status(order_ref)` | read | `GET /voice-tools/orders/latest` or by id → order + ledger status | F12 orders + ledger |
| `get_bids_for_listing(listing_ref)` | read | `GET /voice-tools/listings/{ref}/bids` | F12 bids |
| `create_prebid_listing(...)` | write | `POST /voice-tools/prebid-listings` → listing + bid event | F12; honour `Idempotency-Key` |
| `accept_bid(listing_ref, bid_ref)` | write | `POST /voice-tools/listings/{ref}/bids/{bid}/accept` | F12; honour `Idempotency-Key` |
| `mark_rescue_lot_sold(lot_ref)` (optional) | write | Crop Rescue mark-sold | Crop Rescue integrated |

Rules for these endpoints:
- `'latest'` refs are resolved **server-side** for the logged-in user; unknown or not-yours → 404.
- Writes accept the `Idempotency-Key` header and return the same result for a repeated key (how it is stored: STATUS → Verified
  facts → "Bid accept rules" and "Pre-flight defaults" (2) — accept is idempotent per bid, and the key is also the `wallet_ledger` key from S20).
- Keep answers short and plain (numbers in kg / ₹ per kg, dates ISO) — the voice reads them aloud.
- No voice-specific rules in our services: these endpoints only reshape data.

### Flutter (5–6 h)

Use the voice repo's own plan (its milestone M5, `docs/PORTING.md` section C): it builds a reusable
Flutter package `voice_assistant` (controller, mic button, ordered playback, captions, confirm card,
client actions) with **no** FarmNex words inside. Change only one thing in that milestone: **skip the
Supabase-login demo app** — FarmNex is the host app.

In the voice repo (≈3–4 h): build the `voice_assistant` package per its M5, with a `tokenProvider`
callback instead of Supabase login; handle `auth.refresh`, close codes 4400/4401/4403.

In farmnex_main (≈1–2 h):
- Add the package as a git dependency in `frontend/pubspec.yaml`, **pinned to a commit**.
- `tokenProvider` = our access token from `StorageService` (refresh through `ApiClient` first when
  it's close to expiry).
- Put its mic button / sheet into `lib/widgets/dialogs/ai_assistant_dialog.dart`; register the
  pack's `client_actions` (`navigate` → our routes, `open_photo_picker`, `refresh` → reload the
  provider named in the action).
- Microphone permission (Android manifest) and the consent notice.
- Voice service URL in `api_config.dart`.
- Keep the existing on-device `lib/core/voice/voice_service.dart` / `intent_parser.dart` as the
  offline fallback.

---

## Crops (applies to every component)

| Crop | Main `crop_types` | Crop Rescue | Forecaster | Voice pack |
|---|---|---|---|---|
| Tomato | ✅ | ✅ | ✅ | ✅ |
| Onion | ✅ | — | ✅ | ✅ |
| Potato | ✅ | — | ✅ | — |
| Spinach, okra, brinjal, cauliflower, grapes, capsicum, cucumber | — | ✅ | — | — |
| Soybean, pomegranate | — | — | — | ✅ |

**Demo crop: Tomato** (the only one every part understands). Voice enum → `tomato, onion, potato` plus
the Crop Rescue crops; the voice tool endpoints answer "not available for this crop yet" instead of
failing when a component doesn't support one. See FIX_PLAN F18 for the main app.

---

## Minimum demo (≈10–12 h)

Only the read tools that don't depend on F12: `get_demand_forecast`, `get_rescue_alerts`,
`get_rescue_matches`, `get_pickup_status`. Login adapter + those endpoints + Flutter push-to-talk.
No write tools. Don't start write tools in the last 12 hours before judging.
Even smaller (≈4 h, no Flutter work): demo from a laptop with the voice repo's CLI/REST client using a
real FarmNex farmer token — shows the brain and the Marathi speech, but not in the app.

## What can go wrong (and how you'll notice)

| Symptom | Cause | Fix |
|---|---|---|
| Voice server exits at startup: "no real AuthVerifier adapter exists yet" | `APP_ENV` not `dev` and no JWT adapter | Change 1 |
| WebSocket closes with **4401** after ~15 min | FarmNex access token expired | App sends `auth.refresh` after its normal token refresh |
| Every tool answer "I couldn't check that" | `HOST_API_BASE_URL` wrong/http, or the tool still `mock` | https URL; `handler: {type: http}` |
| Tool returns another farmer's data | F1 not done for that resource | Never enable a tool before its F1/F12 dependency |
| Forecast tool times out | Forecaster cold start vs 4 s handler timeout | `timeout_s: 12` + warm the forecaster before the demo |
| Answers stop after a few questions | Free LLM tier limit | Paid key / longer fallback chain / pause between questions |
| Voice replies but no sound on phone | Audio encoding/sample rate not handled by the player | Match `audio.segment` encoding from PROTOCOL.md in the player |
| "Speaking" frozen on stage | Voice host asleep | Warm up 5 minutes before; tunnel fallback |
| WebSocket closes with **4403** | User hasn't accepted the voice consent | Show the consent notice once and send consent as PROTOCOL.md says |

## Done when

- A farmer logged into FarmNex taps the mic, asks in Marathi "टोमॅटोला मागणी कशी आहे?" and hears the
  forecaster's answer.
- "माझ्या क्रॉप रेस्क्यू अलर्ट सांगा" reads their own alerts; another farmer's are never read.
- (Full path) "Accept the highest bid" → spoken confirmation → "हो" → accepted once; a second "हो"
  doesn't repeat it.
