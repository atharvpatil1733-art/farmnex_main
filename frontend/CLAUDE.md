# Frontend rules (Flutter)

Read the root `CLAUDE.md` first. This file adds Flutter-specific detail.

## Stack facts (checked 2026-09-29)

- Flutter / Dart, state with `provider` (`ChangeNotifier`s in `lib/providers/`), HTTP with `dio`.
- **One HTTP client:** `ApiClient().dio` in `lib/core/network/api_client.dart`. It sets the base URL,
  adds `Authorization: Bearer <access token>`, and refreshes the token on 401. Every backend call —
  including component clients (Crop Rescue, forecaster, routes, voice) — must go through this Dio so
  login and refresh work everywhere. Don't create new `Dio()` or raw `http` clients for our backend.
- All URLs live in `lib/core/config/api_config.dart`. Backend base: `https://farmnex-a.fastapicloud.dev`.
  Our API is under `/api/v2/...`.
- `lib/core/network/backend_service.dart` has typed calls for auth, users, addresses, farms.
  Don't add to it: new calls go in your own `lib/core/network/<feature>_api.dart` (parallel sessions
  would otherwise collide in this one file) — never inside widgets.
- Tokens are stored by `lib/core/storage/storage_service.dart` (`flutter_secure_storage`, kept in memory; F14 done — language, onboarding and user details stay in `shared_preferences`).
- Languages: `lib/localization/` (`app_translations.dart`, `l10n_extension.dart`). Farmers use
  Marathi/Hindi — every new user-facing string goes through the translation system.

## Current state — important

Only **login/registration, the user profile and the farm-file upload** (upload center) talk to the
real backend. `backend_service.dart` already has methods for addresses and farms, but no screen uses
them yet. These providers
still use hard-coded demo data: `bidding`, `market`, `cart`, `payment`, `rescue`, `logistics`,
`listing`, `waste`, `admin`, `verification`, `crop_media`. `core/payments/payment_gateway.dart`
fakes success. `api_config.dart` contains old URLs that don't exist on the backend
(`/api/crops`, `/api/ai/*`, `/api/rescue/request`, `/api/waste/listings`, `/ws/bidding/*`).
The plan to connect them is FIX_PLAN F13 — use `/connect-screen <provider>`.

## When connecting a screen to the backend

1. Check the endpoint really exists: open the backend's `/docs` or read the controller. Never invent
   a URL. Add it to **your feature's section** of `api_config.dart`.
2. Add typed methods in your own `lib/core/network/<feature>_api.dart` using `ApiClient().dio`.
3. Model classes: plain Dart with `fromJson`, JSON keys exactly as the backend (snake_case). Use
   `public_id` strings as ids.
4. Provider: keep the same public getters so screens don't break; replace demo data with loading /
   error / empty states. Keep demo data only behind an explicit `kDemoMode` flag if the demo needs it.
5. Errors: show a short translated message (no raw exception text) and a retry.
6. Don't send identity fields (`buyer_id`, `farmer_id`, ...) — the backend takes them from the token.

## Checks before done

`flutter analyze` has no new issues, `flutter test` passes, and the screen was tried against the
backend (or you say clearly that you could not run it and what Atharv should tap to test).

## Don'ts

- No server secrets in the app (Supabase secret key, forecaster API key, etc.).
- No real company or person names in demo data (use made-up names).
- Don't delete screens or features to make analysis pass.
