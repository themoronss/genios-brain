# Phase 1 — Code Done, Ready to Deploy

Code changes are complete in `genios-brain`. Nothing deployed yet — follow the
steps below when you're ready to push.

---

## What Was Built

### 1.1 — Agent Blackboard (coordination)
| File | Purpose | Lines |
|------|---------|-------|
| `app/coordination/__init__.py` | package marker | 0 |
| `app/coordination/blackboard.py` | Redis KV lock + peek + audit | 204 |
| `app/api/routes/draft.py` | `/api/generate/draft` now claims a lock per entity and returns **409 CONTACT_LOCKED** when another agent is drafting the same entity | modified |
| `app/api/routes/context.py` | `/v1/context` response now includes `other_agents_active` (current lock + last 10 events) | modified |

Behavior:
- `blackboard.claim(org_id, contact_ref, agent_id, action)` → tries Redis `SETNX` with TTL 60s.
- `blackboard.release(org_id, contact_ref, lock_id)` → only releases if lock_id matches (safe).
- `blackboard.peek(org_id, contact_ref)` → snapshot: `{ locked_by, recent: [...] }`.
- `blackboard.audit(db, ...)` → persists to `agent_activity_log` for dashboard/audit.
- Redis outage = fail-open (no lock, action proceeds; never blocks the request).

### 1.2 — Calendar Push Webhook
| File | Purpose |
|------|---------|
| `app/api/routes/webhooks_calendar.py` | new `POST /v1/webhooks/calendar` (header-based, verifies `X-Goog-Channel-Token`) |
| `app/ingestion/calendar_connector.py` | `setup_watch_channel` now accepts + echoes `channel_token` |
| `app/main.py` | registers the new router |

Already existed: Gmail Pub/Sub receiver at `POST /v1/webhooks/gmail`, Calendar watch-channel *setup* logic. Only the receiver was missing.

### 1.3 — Proactive Watch-Renewal
| File | Purpose |
|------|---------|
| `app/tasks/renew_watches.py` | renews Gmail + Calendar watches before 7-day expiry (window: 36h) |
| `app/celery_app.py` | new `task_renew_watches` + daily beat entry at 04:00 UTC |

Before: watches renewed only inline with sync tasks → silent failure if no sync scheduled.
After: daily beat guarantees renewal even for idle orgs.

### Migration 058
- `agent_activity_log` table (audit of every blackboard claim/release)
- `calendar_sync_state.channel_token` column (webhook verification)

---

## Deploy Sequence (when ready)

### Step 1 — Supabase (run migration)
```sql
-- paste migrations/058_agent_blackboard.sql into SQL editor
-- verify:
SELECT count(*) FROM agent_activity_log;                       -- should be 0
SELECT column_name FROM information_schema.columns
  WHERE table_name='calendar_sync_state' AND column_name='channel_token';
```

### Step 2 — Upstash (no action)
Reuses the existing Redis instance. New keys created by the app:
```
agent:lock:<org>:<contact>      TTL 60s
agent:recent:<org>:<contact>    TTL 24h (LIST, max 10 entries)
```
Memory cost at 10 startups: < 1 MB. No upgrade needed.

### Step 3 — GCP (Calendar webhook only)
Only needed if you want Calendar real-time push (Phase 1.2). Gmail is already wired.

Either reuse your Gmail GCP project or create a new one:
1. Enable **Google Calendar API** (already enabled if Calendar sync works today).
2. Set env var in `genios-brain` **and** `genios-celery`:
   ```
   GOOGLE_CALENDAR_WEBHOOK_URL=https://brain.thegenios.com/v1/webhooks/calendar
   ```
3. Verify domain ownership in **Search Console** for the hostname used in step 2 (Google requires this for push webhook addresses). Add the genios-brain domain.
4. On next calendar sync (or next run of `task_renew_watches`), the watch is auto-established.

No Pub/Sub topic required for Calendar — it uses direct HTTPS push (unlike Gmail).

### Step 4 — DigitalOcean App Platform
Push the updated `genios-brain` repo. The two running apps are rebuilt:
- **genios-brain** — picks up new routes, blackboard, webhook receiver.
- **genios-celery** — picks up new `task_renew_watches` + beat entry.

No new apps this phase. **No cost change.**

---

## Test Plan (run after deploy)

### T1 — Blackboard lock (duplicate-draft prevention)
```bash
# Two parallel calls, same entity — expect one 200, one 409.
curl -X POST "$BRAIN/api/generate/draft" \
  -H "Content-Type: application/json" \
  -d '{"org_id":"<id>","entity_name":"Acme","user_request":"follow up","agent_id":"a1"}' &
curl -X POST "$BRAIN/api/generate/draft" \
  -H "Content-Type: application/json" \
  -d '{"org_id":"<id>","entity_name":"Acme","user_request":"follow up","agent_id":"a2"}' &
wait
# One returns 409 { "error": "CONTACT_LOCKED", "holder": "a1|draft|<lock_id>" }
```

### T2 — Blackboard peek in /v1/context
```bash
# While T1 is still drafting, hit context for same entity:
curl -X POST "$BRAIN/v1/context" \
  -H "Authorization: Bearer <api_key>" \
  -d '{"entity":"Acme"}'
# Response should include: "other_agents_active": {"locked_by":"a1|draft|...", "recent":[...]}
```

### T3 — Agent activity audit
```sql
SELECT agent_id, action, status, started_at, ended_at
FROM agent_activity_log ORDER BY started_at DESC LIMIT 5;
-- expect rows with status in ('completed','conflicted')
```

### T4 — Calendar webhook receiver (live)
After GCP env var is set and a watch is established:
1. Create/move an event in Google Calendar.
2. Check `genios-brain` logs: `Calendar webhook: sync_triggered for org ...`
3. `SELECT status, received_at FROM webhook_events WHERE source='calendar' ORDER BY id DESC LIMIT 3;` → expect `processed`.

### T5 — Watch renewal beat
```bash
# Trigger manually once to validate (skip waiting for 04:00 UTC)
celery -A app.celery_app call app.celery_app.task_renew_watches
# Check log: "renew_watches summary: calendar={...} gmail={...}"
```

---

## Rollback

- **Blackboard misbehaves** → comment out `blackboard.claim/release` lines in `draft.py`; redeploy. Context peek is additive (safe to leave).
- **Calendar webhook failing** → unset `GOOGLE_CALENDAR_WEBHOOK_URL` in env; next renewal pass will skip. Existing calendar sync cron still works.
- **Renewal task errors** → remove the `"renew-watches-daily"` entry from `celery.conf.beat_schedule`; redeploy celery.
- **Migration 058** → additive only. No rollback needed; you can drop the table later with zero impact.

---

## Success Criteria (observe for 48 h after deploy)

| Metric | Target |
|--------|--------|
| 409 `CONTACT_LOCKED` responses on /api/generate/draft | >0 means it's working |
| `other_agents_active.locked_by` populated during concurrent drafts | yes |
| `agent_activity_log` row count / day | > context call volume × ~0.3 |
| Calendar webhook p95 latency (receive → sync_triggered) | < 5 s |
| `watch_expiry` for every row in `calendar_sync_state` | > NOW() + 36h every morning |

---

## Known Gaps (deliberately deferred to Phase 2)

- No event bus (`event_log` table) — comes in Phase 2.
- No bitemporal columns yet — Phase 2.
- No action ledger — Phase 2.
- Drive / Slack webhook receivers — later phase (Gmail + Calendar is enough to prove the pattern).
- No dashboard live-activity page — comes in Phase 5.
