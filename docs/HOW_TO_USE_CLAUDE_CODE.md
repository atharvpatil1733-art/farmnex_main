# How to use Claude Code on FarmNex (for the team)

This repo is set up so Claude Code already knows the project, its rules, the list of problems to fix,
and how the four components plug in. You just give short commands.

## What's in the setup

| File | What it's for |
|---|---|
| `CLAUDE.md` | Project rules Claude reads every time (DB safety, security, how to explain things) |
| `backend/CLAUDE.md`, `frontend/CLAUDE.md` | Extra rules when working in each folder |
| `docs/FIX_PLAN.md` | Every known problem, in order, with how to check it's fixed |
| `docs/STATUS.md` | Progress, decisions and verified facts — only the coordinator session updates it |
| `docs/integration/*.md` | How Crop Rescue, AI forecaster, route optimizer and voice assistant plug in, and what can go wrong |
| `docs/FINALE_PLAN.md` | The 40–50 h plan: streams, hours, checkpoints, cut lines |
| `docs/PROMPTS.md` | Copy-paste prompts for every step |
| `docs/PARALLEL_SESSIONS.md` | Running many sessions at once: session order, which can run together, file ownership, merging |
| `backend/migrations/` | SQL for new component tables — **you** run these in Supabase |
| `.claude/commands/` | The shortcuts below |
| `.claude/agents/security-reviewer.md` | A second Claude that checks security changes |
| `.claude/settings.json` | Stops Claude from reading `.env`/keys, force-pushing, or `rm -rf` |

## The shortcuts

| Type this | What happens |
|---|---|
| `/fix F1 payment` | Fixes one item from the fix plan (here: ownership checks for payments), tests it, ticks it off |
| `/integrate crop-rescue` | Plugs a component in, step by step, after showing you the plan |
| `/connect-screen listing` | Switches one app screen from fake data to the real backend |
| `/check-fast` | Quick check of just what this task changed (use while working) |
| `/check-backend` / `/check-frontend` | Checks one side of the app (use before a pull request) |
| `/check` | Full check of everything (coordinator, after each wave or before a demo) |

Component names for `/integrate`: `crop-rescue`, `ai-forecaster`, `route-optimizer`, `voice-assistant`.

## Order of work

Don't follow a list from memory — use these two files:
- **`docs/FINALE_PLAN.md`** — the 40–50 hour plan: three streams (backend security, components,
  app screens), who waits for whom, checkpoints, and what to cut if you're behind.
- **`docs/PROMPTS.md`** — the exact prompt for every step, in order, with a time budget each.

The short version: **cleanup and test setup first** (F4 → F5 → F17 → F11), **then security**
(F3 → F1 + F2), then components and screens in parallel. Tests come before the security fixes
because they're how we prove a fix works.

## How the backend gets onto the internet (FastAPI Cloud) — plain version

- **FastAPI Cloud** is the company that runs your backend for you at
  `https://farmnex-a.fastapicloud.dev`. Its **dashboard** is the website where you manage it (log in at
  fastapicloud.com with the account that first deployed FarmNex).
- **GitHub** holds your code. Merging a pull request changes the code on GitHub — **it does not
  change the live backend by itself.** Something has to copy the new code to FastAPI Cloud. That
  copy is called a **deploy**. There are two ways:
  1. **By hand:** someone runs `fastapi deploy` from the `backend/` folder on their computer (after
     `fastapi login`). Whoever set FarmNex up probably did this.
  2. **Automatically ("connecting GitHub"):** you link the GitHub repo to the FastAPI Cloud app once.
     After that, every merge to `main` is deployed automatically.

**Do you need to connect GitHub?** No, it's optional. Pick one and tell the team:
- **Connect (recommended for a non-technical team):** nobody has to remember to deploy, and the live
  app always matches `main`. Rule: merge only PRs whose checks passed, and set new environment
  variables *before* merging the PR that needs them. How: dashboard → your app → **Settings** →
  **Source Repository** → **Connect** → sign in to GitHub → allow the FastAPI Cloud app → pick
  `farmnex_main` → **Connect**. Then Settings → **Application Directory** → type `backend` → **Update**
  (the backend lives in that folder).
- **Don't connect:** the live app only changes when someone runs `fastapi deploy`. More control, but
  you must deploy after each wave (§8 of `PARALLEL_SESSIONS.md`).

Either way, **environment variables** (secret settings like database URLs) are set in the same
dashboard, under the app's settings — never in the code.

## Things only you can do

- Run SQL files from `backend/migrations/` in the Supabase SQL editor.
- Set environment variables on FastAPI Cloud (Claude will list exactly which).
- Deploy separate services (the forecaster, the voice assistant).
- Test on a real phone.

## Tips

- One fix or one component per session/branch keeps things easy to review. At the end, ask Claude
  to push the branch and open a pull request, then merge it before the next step.
- If Claude's explanation is too technical, say "explain simpler" — `CLAUDE.md` tells it to.
- If something looks wrong, ask Claude to run the `security-reviewer` agent on the current changes.
