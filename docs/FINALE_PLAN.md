# FarmNex finale plan (40–50 h build window)

**Goal:** a working, safe demo of one complete story — not every feature half-done.

> A farmer lists produce → buyers pre-bid → the winner pays a 20% advance → a lot nears spoilage →
> Crop Rescue alerts the farmer and suggests buyers, with the AI price forecast → the order is
> confirmed → a pooled truck route is planned → the buyer tracks the truck → on delivery the farmer
> is paid.

**Use Tomato for the whole story** — it's the only crop every component supports (FIX_PLAN F18).

Voice assistant = **stretch** (read-only 10–12 h, write tools +3–4 h — see its guide). Everything
else serves the story above.

Total work is roughly **75–90 person-hours** (including buffer). That fits 40–50 hours only by
working in **three parallel streams** with 5–6 people. Anything you can finish **before** the finale
(the first block below) makes the finale much safer.

---

## Before the finale (if you have days left) — do these first

These are small, independent, and remove the biggest risks:
1. Stream A: F4, F5, F11, F3 and the F1 + F2 fast path (see `FIX_PLAN.md`).
2. Stream B: Crop Rescue Phase 5 in its own repo; deploy the forecaster to Render.
3. Everyone: run the app once against the deployed backend on a real phone; list what breaks.

---

## Streams

| Stream | People | Owns | Budget |
|---|---|---|---|
| **A — Backend core & security** | 2 | F4 F5 F11 F3 F1 F2 F9 F6 F7 F10 F17, F12 minimum, final security review | ~24 h |
| **B — Components** | 2 | Crop Rescue, forecaster, route optimizer (backend + their Flutter screens) | ~26 h |
| **C — Flutter core** | 1–2 | listing/market, cart/checkout, bidding, waste, F14 F15 F16, demo accounts + seed data | ~17 h |
| Voice (stretch) | 0–1 | voice repo changes (login adapter, pack, deploy) + read-only voice tools + Flutter mic | 10–12 h (read-only) |

Dependencies between streams (the arrows are the only times you wait for each other):
- C's **listing/market** needs A's F1 for `product_listing` (+ `product_image`).
- C's **checkout/bidding** needs A's F12 orders/bids.
- B's **route optimizer Slip 2/3** (order → load → delivered → pay) needs A's F12.
- B's components need A's **F17** (`load_dotenv` + env list) — 15 minutes, do it first.

---

## Hour-by-hour (48 h window; stretch the blocks if you have 50 h, shrink buffer if 40 h)

| Hours | Stream A | Stream B | Stream C |
|---|---|---|---|
| 0–4 | F4, F5, F17, F18, start F11 | Crop Rescue Phase 5 (its repo); deploy forecaster | F15, F16, F14; plan screens |
| 4–12 | F11 done, F3, F1+F2: payment, bid, bid_event, order, order_item, product_listing, product_image | `/integrate crop-rescue`, `/integrate ai-forecaster` (backend) | demo accounts; start listing/market as soon as product_listing is fixed |
| **12** | **Checkpoint 1** | | |
| 12–20 | F1+F2 remaining modules, F9, F6, F7, F10 | route optimizer backend: install, SQL, vehicles host endpoints, guard, tracking | rescue screen + forecast screen (pair with B) |
| 20–24 | start F12: orders | route optimizer tests | listing/market done |
| **24** | **Checkpoint 2** | | |
| 24–32 | F12: bids + pre-bid close, wallet ledger, demo pay | logistics Flutter: vehicle, online, trip, stop buttons, GPS ping, Track WebView | bidding screen |
| 32–38 | Slip 2/3 wiring with B (CONFIRMED → load, DELIVERED → release) | Slip 2/3 with A; demo seed (`seed_demo.py`) | cart + checkout (after F12 orders); waste screen |
| **38** | **Checkpoint 3** | | |
| 38–42 | security review (`security-reviewer` on everything), fix HIGHs | bug fixes | bug fixes, polish |
| 42–46 | **Feature freeze.** Full demo run ×2 on real phones against production; fix only demo-breaking bugs | | |
| 46–48 | Rehearse the pitch; record a backup demo video; warm up the forecaster | | |

Rest in rotation — a tired team makes the bugs that cost hours.

---

## Checkpoints and cut lines

At each checkpoint the team lead asks every stream: *on budget, or behind by how much?*

| If behind at… | Cut (in this order) | What the demo shows instead |
|---|---|---|
| Checkpoint 1 (H12) | Voice write tools (keep read-only voice if its person is on budget) | Read-only voice, or mention it as "next" |
| Checkpoint 2 (H24) | Voice entirely, if its login adapter + one tool aren't working yet | Demo the voice service alone from a laptop, or mention as "next" |
| Checkpoint 2 (H24) | Waste-to-wealth screen; admin screens; F8 | Keep demo data for those screens, labelled "demo" |
| Checkpoint 3 (H38) | Backhaul UI, real-phone GPS | `backend/scripts/simulate_driver.py` (S34) moves the truck on the map |
| Checkpoint 3 (H38) | Pre-bid auto-close | Manager "close bidding now" button |
| H42 | **Nothing new.** Only fixes. | — |

**Never cut:** P0 security (F1–F3) for anything the demo touches, and the "not your data → 404"
behaviour. Judges who test security will try it.

---

## Demo safety kit (prepare by H40)

- **Feature flags** (`ENABLE_CROP_RESCUE`, `ENABLE_FORECAST`, `ENABLE_ROUTE_OPTIMIZER`): if one breaks on
  stage, switch it off on FastAPI Cloud and the rest still works.
- **Demo accounts:** farmer ×2 (near Pune), buyer ×2, driver ×1, manager ×1 — written on one card.
- **Seed data:** listings (crop emoji — there are no product photos), one bid event open, Crop Rescue demo buyers
  (`011_cr_demo_seed.sql`), route loads near the driver's base (made by `backend/scripts/seed_demo.py`, S34).
- **Warm-up 5 minutes before:** open forecaster `/health`, backend `/docs`, one tracking page (and, only
  if the voice assistant was built, its `/healthz` — ask it one question).
- **Unused endpoints unmounted** (F1 fast path) so `/docs` shows only what works.
- **Bad venue internet:** `ROUTING_PROVIDER=haversine` (estimated distances), phone hotspot as backup.
- **Crop Rescue:** `CR_ENABLE_SIMULATE=true` for the demo (fast-forward spoilage), `false` after.
- **Backup video** of the full story, recorded at H46.

---

## Rules during the build

- Running several Claude Code sessions at once: follow **`docs/PARALLEL_SESSIONS.md`** (session
  order S01–S35, which run together, who owns which file, the coordinator session).

- One step = one branch = one PR. Merge only after its `/check-backend` or `/check-frontend` passes.
- Deploy to FastAPI Cloud at least every ~4 hours, not only at the end — deploy problems found at H45
  are the worst kind.
- Claude Code: one fresh session per step, using `docs/PROMPTS.md`. If a step runs over its budget
  by 50%, stop and decide with the team lead: simplify, or cut.
- Nobody runs SQL on the main Supabase except the person assigned (Atharv), from
  `backend/migrations/`; the coordinator session records it in `docs/STATUS.md`.
