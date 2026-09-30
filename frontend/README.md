# FarmNex — Flutter app

The mobile/web app for FarmNex: farmers, buyers, logistics partners and admins.
It talks to the FastAPI backend in `../backend` (production: `https://farmnex-a.fastapicloud.dev`).

## Run it

```bash
cd frontend
flutter pub get
flutter analyze
flutter test
flutter run                 # or: flutter run -d chrome
```

Needs Flutter with Dart `^3.13` (see `pubspec.yaml`). The backend address is set in one place,
`lib/core/config/api_config.dart` (`ApiConfig.baseUrl`). To use a local backend, start it
(see the root `README.md`) and change `baseUrl` to `http://localhost:8000` — don't commit that change.

## What is real and what is demo

- **Real (talks to the backend):** OTP register/login, token refresh, logout, profile and farm-file
  upload. Login tokens are kept in secure storage (`flutter_secure_storage`); language and onboarding
  flags stay in `shared_preferences`.
- **Demo data:** most providers in `lib/providers/` still use hard-coded sample data (all names are
  fictional). Each is switched to the real API in its own task (`../docs/FIX_PLAN.md`, F13).
- **Payments** use a mock gateway (`lib/core/payments/`): no real money moves. The server must compute
  amounts and verify payments; never put payment secrets in this app.

## How the code is organised

```
lib/
  core/config/api_config.dart        every backend URL (one marked section per feature)
  core/network/api_client.dart       the ONE Dio client: adds the login token, refreshes it on 401
  core/storage/storage_service.dart  secure token storage + simple preferences
  core/navigation/role_tabs.dart     which tabs each role sees (access control)
  core/payments/                     payment gateway interface + mock
  core/voice/                        voice assistant (speech + intent parser)
  core/translation/                  translation helper (Google ML Kit on phones)
  localization/                      app strings; use context.t('key')
  models/  providers/  screens/  widgets/
```

Data flow: `Screen → Provider → ApiClient (Dio) → FastAPI → database`.

## Roles

| Role | Tabs |
|---|---|
| Farmer | Home / My Crops / Pre-Bid / Crop Rescue / Profile |
| Buyer | Mandi / Crop Rescue / Cart / Orders / Profile |
| Logistics | Loads / Trips / Earnings / Profile |
| Admin | Console / KYC / Users / Money / Profile |
| Guest | Home / Mandi / Crop Rescue / Pre-Bid / Login |

A role's screens are never built for another role. The server is the authority on role.

## Languages

English, Hindi, Marathi, Telugu, Tamil, Kannada, Bengali, Gujarati. The app opens on language
selection. Some older screens still contain hard-coded English. Find them with:

```bash
grep -rn "Text('[A-Z]" lib/screens lib/widgets --include=*.dart
```

## Voice

Speech input uses `speech_to_text` and `flutter_tts`. Recognition for Indian languages depends on
language packs installed on the phone, so not every language works on every device. On Chrome the
microphone needs browser permission and localhost/HTTPS.

## Test on small screens

Tamil and Telugu labels are the longest; check a 5-inch phone in those languages for overflow.
