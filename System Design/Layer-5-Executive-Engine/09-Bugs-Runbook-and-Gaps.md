← [The Sweep and the Delivery Bridge](08-The-Sweep-and-The-Wire.md) · [Folder map](README.md)

---

# Bugs, Runbook and Gaps

---

## §6 · Bugs found and fixed

| # | Bug | How it was caught | Fix |
|---|---|---|---|
| 1 | Step classifier typed *"Review the deal history"* as an **approval gate** | ran the classifier over every shipped play | bare `review` removed; **leading verb decides** |
| 2 | *"Draft a warm outreach note"* classified as `SEND` because "outreach" appeared later | same sweep | leading-verb table beats whole-sentence scan |
| 3 | `authority_valid()` embedded Layer 4's predicate **without binding `:authority_time`** | new AST ratchet | bind supplied; `now` threaded so **one instant judges the whole sweep** |
| 4 | New tables had **no `orgs` cascade** — a commitment could outlive its tenant's deletion | `test_account_erasure.py` | five FK cascades added to `0041` |
| 5 | Unrouted commitments got a **different `execution_id`** than routed ones for the same decision | identity test | uniqueness moved to the `(org_id, decision_hash)` partial index; supersede path added |
| 6 | Stored plans had **no rehydration path** — the payload was write-only | round-trip test | `decanonicalize()` + `from_semantic_dict()` + `verify_round_trip()` at build time |
| 7 | `POST /sweep` crashed: `vars()` on a slotted dataclass | new route test | `dataclasses.asdict` |
| 8 | The dismiss route wrote SQL `now()` while everything else passes time explicitly | new route test | time is bound, **so a replay observes the instant the event recorded** |

### The six test files

| File | Tests | Proves |
|---|---|---|
| `test_executive_execution.py` | 26 | the contract: identity, the read-only boundary, autonomy, the clock |
| `test_executive_lifecycle.py` | 45 | guard, reminder, monitor, escalation, tracking, outcome labels |
| `test_executive_sweep.py` | 33 | **the orchestrator, executed** — all five endings, both nudge paths, rerouting, and that the scheduler actually drives it |
| `test_executive_store_schema.py` | 21 | every SQL column exists and every `:bind` is supplied |
| `test_executive_bridge.py` | 16 | **a reminder reaches a human** — exactly once, never stale |
| `test_executive_routes.py` | 15 | the API: org scoping, the credential boundary, dismiss → sweep → cancel |

**Two are ratchets** — they fail if the code *drifts*, not just if it breaks:

- `test_executive_store_schema.py` parses every migration for real columns and walks the **AST**
  of the store, sweep, routes and bridge to extract every SQL statement. Both of its central
  claims were verified by deliberately breaking the code and watching them fail.
- `tests/executive_fakes.py` is an in-memory database double that **raises** on any statement it
  does not model. *A silent empty result would let a test pass while skipping the very write it
  was written to check.*

> `sweep.py` and `execution_store.py` were, until this work, proven only by static analysis —
> **874 lines of orchestration and persistence with no line ever run.** Static analysis cannot
> tell you that a `COMPLETE` verdict closes the row *and* writes the outcome *and* logs the
> event. It can now.

**A note worth keeping:** an earlier full-suite run failed 70 tests, first blamed on a stale
bytecode cache. **That was wrong.** The real cause was **a second session writing to the same
repository concurrently** — twelve Layer 4 units and their tests landed mid-write. *Concurrent
sessions on one working tree is a real hazard.*

---

---

## §7 · Deployment runbook

**Layer 5 self-starts.** It is wired into the scheduler heartbeat that already runs card
expiry, retention and delivery. **No new cron, no new worker, no new service.**

### Step 1 — Apply the migration

```bash
.venv/bin/python -m genios_engine.platform.migrate
```

Applies `0041_l5_execution.sql`: five tables (`executions`, `execution_actions`,
`execution_escalations`, `execution_events`, `execution_outcomes`), their indexes, the tenant
delete-cascades, and one nullable column on `org_seats`.

```sql
select count(*) from schema_migrations where filename = '0041_l5_execution.sql';   -- 1
\d executions
```

> **If it fails:** migrations are immutable and checksummed. If `0041` was applied and then
> edited, the runner refuses **by design** — ship `0042`, never edit in place.

### Step 2 — Deploy the branch

**No new environment variables.**

| Setting | Why Layer 5 needs it |
|---|---|
| `GENIOS_DATABASE_URL` | everything |
| `GENIOS_SCHEDULER_ENABLED` (default `true`) | drives the sweep |
| `GENIOS_SYNC_INTERVAL_HOURS` (default `6`) | how often commitments advance |

> **Consider lowering the interval.** At 6 hours a commitment is examined four times a day —
> fine for planning, coarse for reminders: **a "day 1" rung can fire up to six hours late.**
> `GENIOS_SYNC_INTERVAL_HOURS=1` costs one extra cheap pass per hour. The sweep is idempotent,
> so a shorter interval is safe.

### Step 3 — Confirm it is running

```
scheduled maintenance sweep: {... 'executive': {'orgs': N, 'commitments_created': X,
                                                'commitments_examined': Y} ...}
```

```bash
curl -XPOST -H "Authorization: Bearer $OWNER_TOKEN" https://<host>/v1/executive/sweep
curl        -H "Authorization: Bearer $OWNER_TOKEN" https://<host>/v1/executive/commitments
```

> **Expect `planned.created > 0` on the first run, `0` on the second. That zero *is* the
> idempotence guarantee** — it means re-running cannot duplicate a commitment.

### Step 4 — Read the refusal counters before assuming anything is wrong

See the table in §3.7. **`outcome_no_action` is health, not a fault.**

### Step 5 — Two tenant-side settings

**5a · `org_seats.manager_seat_id`** — the reporting line. Without it, day-7 escalation falls
back to the org's admins: *that works, but it is blunt — everyone's escalation lands on the same
person.*

**5b · A Slack channel** — so reminders leave the building.

> **Without a channel, nothing is lost.** Commitments are still planned, tracked, escalated and
> reported; they wait on the card surface instead of being pushed. The communication plan
> records `no_channel_registered` so *the reason is visible, not mysterious.*

### Step 6 — What to watch in week one

```sql
select state, count(*) from executions where closed_at is null group by state;

select status, count(*) from delivery_outbox where card_id like 'exec:%' group by status;

-- THE number
select label, count(*) from execution_outcomes
 where closed_at > now() - interval '7 days' group by label order by 2 desc;
```

Two counters worth an alert:

- **`delivery_outbox` rows with `card_id like 'exec:%'` and `status='cancelled'`** — each one is
  a reminder correctly suppressed because the world resolved it first. **A zero here over a busy
  week is suspicious:** it suggests the guard is not finding observations, not that the world
  never moves.
- **`executions where routing_rule = 'rule3_unrouted'`** — commitments nobody owns. Tracked and
  visible by design, but a growing count means CRM ownership is missing for real accounts.

### Step 7 — Rollback

Layer 5 adds tables and reads existing ones. To stop it for one tenant, disable the pack — the
sweep only visits orgs with an active `tenant_packs` row. To stop it globally,
`GENIOS_SCHEDULER_ENABLED=false`. The tables can be left in place; they are inert.

---

---

## §10 · Gaps

### The one thing that is genuinely unproven

> **No SQL in this layer has ever run against Postgres.** CI has no database. Every unit and
> the whole orchestrator execute against an in-memory double, and every statement is
> *statically* proven to name real columns and bind real parameters — **but neither proves the
> two meet.** Steps 1 and 3 of the runbook are what close that.

### Still open, deliberately

**Layer 7 does not yet read `execution_outcomes`.** The table is written and indexed for the
cohort read (`org, capability, play, closed_at`); `feedback/calibrate.py` still learns from card
clicks alone. *Not built here on purpose — Layer 7 is its own brick, and this is the first item
of it.*

---
