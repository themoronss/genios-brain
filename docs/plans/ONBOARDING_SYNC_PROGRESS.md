> **Created:** 2026-08-14 · **Status:** Active
> **Purpose:** Make the real-user onboarding sync (Gmail + Calendar, 2 months, no count cap) complete reliably and show honest, human-readable, refresh-proof progress on the frontend.

# Onboarding Sync + Progress

Grounded in a 3-agent code audit (2026-08-14) of the connect→sync→L1→L2→L3 chain. This plan fixes what the audit found, keyed to the user's requirements: (1) one **Sync** click pulls **2 months of everything** for a tool with no further action, (2) the frontend always shows **what is happening right now** (phase + counts), never blank/stuck-at-0, survives refresh, and **never leaks L1/L2/L3 jargon**, (3) it must not error even at ~2000 emails / 30–45 min.

## Audit verdict (what's actually true today)

- **Connect ≠ sync.** OAuth completing does nothing; a separate trigger is required. Decision: after connect, UI shows **"Connected — click Sync to start"**; the existing **Sync** button does the full job.
- **Caps violate "everything".** Gmail first-connect hard-capped ~600 (`_BACKFILL_MAX_ROUNDS=24×25`), Calendar 150 (`_SOURCE_EVENT_CAP`). Window (60d/120d) is fine.
- **`sync-all` doesn't backfill** (only 3 newest pages). Only first-time `/integrations/{tool}/sync` backfills — and it runs L1 **synchronously in-request** → DO gateway 502 after ~60–100s.
- **No progress model.** Only an in-memory running/idle boolean (lost on restart) + absolute counts. No percent, no total, no phase. The "processing" banner vanishes after the first record (`processed>0`). A `"syncing"` vs backend `"running"` string mismatch disables the pulse indicator.
- **L2 drain is solid** (per-email isolation, resumes after restart, ~17–33 min for 2000). **L3 reasoning is the bottleneck** (10–30+ min, can emit 0 signals due to mid-pass graph drift — see PERFORMANCE_HARDENING.md).
- **No timeouts** on Anthropic or Composio calls. Broken `/context/process` (passes unsupported `limit=` → TypeError).

## Decisions (user-confirmed 2026-08-14)

1. **Everything in the 2-month window**, count-cap removed, with a **safety ceiling ~5000 emails** + log (guards a pathological 20k inbox).
2. **No auto-start.** Keep the **Sync** button. After connect, notify "Tool connected — press Sync to start." One Sync click then completes the whole tool (backfill → process → graph → intelligence) with no further action.

## Plan

### Part 1 — One Sync click pulls 2 months, in the background, no cap
- Raise `_BACKFILL_MAX_ROUNDS` so ceiling ≈ 5000 msgs (200×25); raise `_SOURCE_EVENT_CAP` gcal to a window-bounded high ceiling (e.g. 2000). Keep the ceiling + explicit log.
- Make the **Sync** action run the **full backfill** in the background for every connected tool (not the 3-page `sync-all`). No synchronous L1 in the request → no gateway kill.
- L3 runs **once at the end** of the whole backfill+L2 (not every 6 rounds) to avoid graph-drift 0-signal.

### Part 2 — DB-backed progress model (refresh + restart proof)
- Migration: `onboarding_progress(org_id pk, phases jsonb, current_phase, overall_percent, state, started_at, updated_at)`.
- Progress helper `platform/progress.py`: `start(org, sources)`, `set_phase(org, key, state, done, total, detail)`, `finish(org)`, `read(org)`.
- Phases (user-facing labels, **no jargon**): `connecting` "Connecting your accounts" · `emails` "Syncing your emails" · `calendar` "Syncing your calendar" · `processing` "Understanding your conversations" · `graph` "Building your relationship graph" · `intelligence` "Finding intelligence" · `ready` "Ready".
- The sync background chain writes progress at each step (backfill loop → live email/event counts; L2 → processed/total; L3 → running→done).
- Endpoint `GET /api/org/{org}/onboarding-progress` → `{state, current_phase, overall_percent, phases:[{key,label,state,done,total,detail}]}`.

### Part 3 — Frontend progress UI
- A progress panel (integrations + post-connect) that **polls every ~4s**, shows the phase list with running/done ticks + live counts + a "this can take 20–45 min, you can close and come back" note. Re-hydrates from the endpoint on mount (refresh-proof).
- Fix: connect success → "Connected — press Sync to start." Fix banner-disappears-after-first-record (drive off `state`, not `processed>0`). Fix `"syncing"`/`"running"` mismatch.

### Part 4 — Robustness (2000 emails, 30–45 min, no error)
- Add request timeouts to the Anthropic client and Composio executes.
- Fix `/context/process` (`limit` → `max_total`).
- Keep per-email isolation/park (already good); L3-once (Part 1).

## Verify
- Prod e2e on a real/throwaway org: connect state → Sync → poll `onboarding-progress` through phases → confirm >600 emails ingested (cap gone) → L2 drains all → graph + intelligence phases complete → refresh mid-run shows live progress (not blank). No 502, no unparked errors.

## Alignment
- In-process BackgroundTasks only (no Celery/Upstash — quota). Never leak v1/v2 or L1/L2/L3 to users. Progress is derived/DB-backed so a restart resumes truthfully.
