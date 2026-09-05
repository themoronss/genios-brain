# L1.2 — Knowledge Connectors (the ingestion control plane)

**Group responsibility:** authentication, permission, sync cadence — and nothing else.

**Group law:** *No intelligence lives here. LLM: 0%.* A connector that interprets its
own payload is an architectural bug.

**Package:** `genios_engine/capture/connectors/`, `capture/acquire/`, `capture/connections/`
**Input:** a tenant connection
**Output:** `RawObject` batches

---

## Component map

| # | Component | Units | Wave | Status |
|---|---|---|---|---|
| L1.2.1 | Connector Manager | 3 | — | ✅ exists |
| L1.2.2 | Authentication | 3 | — | ✅ exists |
| L1.2.3 | **Permission Manager** | 3 | — | ✅ **strong — do not touch** |
| L1.2.4 | Incremental Sync | 3 | W9 | ⚠️ **broken promise** |
| L1.2.5 | Webhook Listener | 3 | W9 | ⚠️ **parity gap** |
| L1.2.6 | Polling Scheduler | 3 | W9 | ⚠️ partial |

Three components are good and must be preserved as they are. Three carry defects that
Layer 1 v2 depends on fixing.

---

# ✅ L1.2.3 · Permission Manager — PRESERVE

This is the strongest component in the current Layer 1 and it must survive the refactor
untouched.

**What it does right:** it stamps source-derived visibility at the normalize seam and
the gate **parks** `visibility_unknown` rather than publishing under a guessed
audience. Globe Rule 10 says *the audience of a derived insight can never be wider than
the audience of the evidence it came from*, and L1 is the only layer that still knows
the recipient list — by L2 the email is a fact and the list is gone.

**Instruction to the coding agent:** do not refactor `capture/visibility_rules.py` or
the S0.6 provenance check in `capture/gate/gate.py` while doing anything else in this
plan. If a change appears necessary, it is a separate PR with its own review.

**Regression test to add:** an event whose audience no derivation rule can name must
park, never publish. Assert this explicitly so a future refactor cannot quietly weaken it.

---

# ⚠️ L1.2.4 · Incremental Sync

### L1.2.4-U1 · Configurable backfill window — **THE FIX**

**WHAT** — Make the first-connect history window a per-connection setting.

**WHY** — Today it is a hardcoded constant:
- `capture/connectors/composio.py:79` — `_BACKFILL_WINDOW = "newer_than:60d"`
- `capture/connectors/calendar.py:16` — `_BACKFILL_DAYS = 60`

and `acquire/sync_runner.py:270-299` documents `backfill_drain` as draining **"FULL
history"** while routing through `initial_snapshot`, which reuses the same 60-day query.
**The documented promise and the code disagree.**

Consequences, concretely: you cannot know who your highest-LTV customers are (their
acquisition threads predate the window), you cannot mine what historically worked (no
prior outcomes), you cannot see a deal cycle longer than 60 days, and there is no
year-over-year comparison possible for any tenant, ever.

**HOW**
```
connection_settings.backfill_days   int, default 540 (18 months)
                                    per connection, set at connect time, admin-editable

initial_snapshot(window_days=conn.backfill_days)
backfill_drain()  -> actually drains conn.backfill_days, in pages, as a durable job
```

**Cost control — the window is safe because of the extraction cache.** A deep backfill
extracts each document once, ever (L1.4.9). The one-time cost is bounded and
predictable; there is no recurring charge for history. Additionally:
- deep-tail pages are rate-shaped, not fired in a burst
- the existing daily-USD circuit breaker still applies
- the tier router (ALG-05) sends most old mail to T1

**FAILURE MODES**
- 18 months of mail overwhelms first sync -> the drain is a durable background job with
  visible progress; onboarding does not block on it.
- Tenant has a 10-year mailbox -> `backfill_days` is a setting; start at 540 and let an
  admin raise it deliberately.

**ACCEPTANCE**
```
pytest tests/capture/connectors/test_backfill_window.py -q
# a connection with backfill_days=540 produces a query covering 540 days
# backfill_drain() with backfill_days=540 does NOT emit a 60d query
# the default for a new connection is 540, not 60
```

**REVERSE PROMPT**
```
TASK: Make the L1 backfill window configurable per connection.

THE BUG: composio.py:79 has _BACKFILL_WINDOW = "newer_than:60d" and calendar.py:16 has
_BACKFILL_DAYS = 60. Both are hardcoded. Worse, sync_runner.py:270-299 documents
backfill_drain as draining "FULL history" but dispatches to initial_snapshot which
reuses the same 60-day query. The docstring is a promise the code does not keep.

CHANGES:
1. Add `backfill_days int not null default 540` to the connections table (new migration).
2. Thread it: connection -> connector factory -> initial_snapshot(window_days=...).
3. Gmail: build the query from window_days, not from a module constant.
4. Calendar: timeMin = now - window_days.
5. backfill_drain(): actually drain window_days, paged, as a durable background job with
   progress reporting. Do not silently reuse initial_snapshot's window.
6. Update the sync_runner docstring so it describes what the code does.
7. Expose backfill_days in the admin console as an editable per-connection setting.

DO NOT:
- Do not remove the daily LLM spend circuit breaker.
- Do not fire the deep tail as one burst; keep the existing page budget and rate shaping.
- Do not change the default for EXISTING connections in the migration. New default 540;
  existing rows keep 60 until an admin raises them. Backfilling history for a live tenant
  is a deliberate action, not a migration side effect.

TEST tests/capture/connectors/test_backfill_window.py — the three assertions in doc 02
L1.2.4-U1 ACCEPTANCE, plus: an existing connection row is untouched by the migration.
```

### L1.2.4-U2 · Cursor integrity — ✅ exists, keep
### L1.2.4-U3 · Rate-limit awareness — ✅ exists, keep

---

# ⚠️ L1.2.5 · Webhook Listener

### L1.2.5-U1 · Ingest parity — **THE FIX**

**WHAT** — Webhook-pushed events must pass through the same pipeline as polled events.

**WHY** — `api/routes.py:1549-1551` calls `capture_event` with only
`repo/trace_repo/payload_store/document_job_store` — **no relevance classifier, no
prepared_store, no parked_store, no mailbox_owner.** So the real-time path skips the
junk gate, lands without prepared clean text, and any park outcome is recorded nowhere.

The always-on mode the customer experiences is therefore the **least-guarded** ingestion
lane. And in v2 this gets worse, not better: without `prepared_content` there is no
clean text for S2 to extract from and no offset map for evidence spans to align against.

**HOW** — pass the same wiring the sweep uses, or better: route webhook payloads into
the same queue the sync runner drains, so there is exactly one ingest path.

**Preferred: one path.** Two ingest paths will drift again.

**ACCEPTANCE**
```
pytest tests/capture/test_webhook_parity.py -q
# the same message delivered by webhook and by poll produces IDENTICAL
# source_events, prepared_content and gate trace rows
```

### L1.2.5-U2 · Signature verification — ✅ exists (`verify_webhook_hmac`), keep
### L1.2.5-U3 · Redelivery tolerance — ✅ exists via dedup, keep

---

# ⚠️ L1.2.6 · Polling Scheduler

### L1.2.6-U1 · Per-source cadence

**GAP** — one global `sync_interval_hours = 6.0` for every source
(`platform/config.py:88`). Gmail and a quarterly-updated Notion page poll at the same rate.

**FIX**
```
source_cadence = {
    "gmail":    0.25,   # 15 min — webhook primary, poll is the safety net
    "gcal":     1.0,
    "hubspot":  2.0,
    "notion":   12.0,
    "gdrive":   6.0,
    "database": 1.0,
}
```
Per-connection override permitted.

### L1.2.6-U2 · Jitter

**GAP** — no jitter. Every connection for every tenant fires on the same boundary,
producing a thundering herd against both the provider and our own workers.

**FIX** — `+/- 10%` deterministic jitter seeded by `connection_id`, so it is stable
across restarts and reproducible in tests.

### L1.2.6-U3 · Catch-up windows

**GAP** — after downtime, the scheduler resumes at the current interval and the gap is
covered only by cursor semantics.

**FIX** — if `now - last_success > 3 * cadence`, run a catch-up sync with an extended
page budget and mark the run `catch_up=true` so it is visible in the admin console.

**ACCEPTANCE**
```
pytest tests/capture/acquire/test_scheduler.py -q
# gmail cadence != notion cadence
# jitter is deterministic for a given connection_id
# a 24h gap triggers a catch-up run with catch_up=true
```

---

## Group acceptance gate

```
pytest tests/capture/connectors tests/capture/acquire -q     # all pass, 0 skips
```

Plus, on a pilot tenant:

| Metric | Gate |
|---|---|
| webhook-ingested events with `prepared_content` | 100% |
| webhook vs poll trace-row parity on the same message | identical |
| connections with `backfill_days == 60` after admin opt-in | 0 |
| distinct poll cadences in use | >= 3 |
