← [Channels, Digest and Agent Delivery](07-Channels-Digest-and-Agents.md) · [Folder map](README.md)

---

# Bugs, Runbook and Gaps

---

## §6 · Bugs found and fixed

| # | Bug | Fix |
|---|---|---|
| 1 | **A card pushed to chat had no interrupt flag, and no dial to get one.** The card path never builds a `CommunicationPlan` | extracted `may_interrupt(band, confidence_bp, cfg)` from `executive/communication.py` and called it at card enqueue — **with the tenant's own config snapshot**, from the `authority_cfg` join already in the query. It reads the snapshot the card was *authorised under*, not the current pack config: *a tenant who tightens `interrupt_band` while a card is queued must not have that card re-judged by a rule its band was never cut by* |
| 2 | **`'*'` is a scope, never a route.** The preferences validator built a probe candidate with `channel='*'` and the contract correctly refused it | expand a wildcard rule to the concrete adapters it governs and validate against each — *so a setting harmless for the digest and broken for chat is caught at save time rather than at 03:00* |
| 3 | **A burst read cached across a pass would have let a flood through.** Ten messages against a limit of three: a memoised count reads "0 delivered this hour" ten times and **every one goes out** | `note_delivered` folds this pass's own sends into the window, so the fourth message is held by the three that preceded it seconds earlier |
| 4 | **A successful send kept a stale hold reason.** A row deferred overnight still carried `gate_reason='quiet_hours'` after it delivered — and worse, **a message that *woke somebody* could not say why** | the success path writes the **admitting** verdict too. `override_band_critical` in the row is the whole answer to *"who authorised this at 2am?"* |
| 5 | **A gate that cannot read must not decide by accident.** An exception in the resolver would have taken the whole drain down — or, in a naive fix, **sent the message anyway** | per row: a gate failure takes the existing bounded retry ladder. The message survives, nothing goes out un-judged, a gate that stays broken ends `failed_terminal` **with the reason in the row**, and one tenant's bad state cannot stop the pass draining for everybody else |
| 6 | **The resolver held a snapshot across an outbound POST** — `idle in transaction` while Slack answered, blocking vacuum | rollback between rows. These are read-only queries, so it costs nothing — **and each resolve now sees deliveries this pass just committed** |

### The test files

| File | Size | Proves |
|---|---|---|
| `test_delivery_gate.py` | 952 lines · 70 tests | the contract's invariants, both units end to end (incl. **DST**), the resolver, and the drain wiring against a recording fake engine |
| `test_delivery_routes.py` | 412 lines · 23 tests | `/effective` answers with the **real** gate, a refused write leaves nothing behind, the owner boundary holds |
| `test_l6_outbox.py` | pre-existing | still green — retry ladder untouched |
| `test_executive_bridge.py` | pre-existing | extended to carry the delivery object |

**Three schema-conformance locks** catch the *silent* failure:

> Every preference column the gate reads, every column the router writes, and every column the
> held view selects must exist in a migration. **Rename one and `preferences.get(...)` returns
> `None` everywhere, the gate falls back to defaults, and a tenant who set quiet hours watches
> nothing change — with no error anywhere.** The read list is derived from the source, so it
> cannot drift out of date.

---

---

## §7 · Deployment runbook

**Layer 6's admission half self-starts.** It sits inside the drain that already runs on the
scheduler heartbeat. No new cron, worker, service or environment variable.

### Step 1 — Apply the migration

```bash
.venv/bin/python -m genios_engine.platform.migrate
```

`0042_l6_delivery_gate.sql` adds:

- `delivery_preferences` — the rules table, with the `'*'` sentinel and its org cascade FK
- **seven columns** on `delivery_outbox` — `recipient`, `band`, `channel_class`, `interrupt`,
  `defer_count`, `gate_unit`, `gate_reason`
- **two partial indexes** — the burst-window read and the operator's *"what is held?"* view

> The column adds carry **non-volatile defaults**, so PostgreSQL 11+ does them without a table
> rewrite. The cascade constraint is `not valid`, matching the 0033/0041 convention — *it binds
> every future write without taking a full-table lock on deploy.*

### Step 2 — Deploy

**Behaviour on day one, before anybody configures anything** — and the asymmetry is deliberate:

| Dimension | Default | Rationale |
|---|---|---|
| timing | **protective** — quiet hours **on** (21:00–08:00 UTC), burst cap 3/hour, critical break-glass | a 03:14 push is unrecoverable |
| policy | **permissive** — delivery stays enabled | **silence by default would be indistinguishable from the product being broken** |

> **Expect a visible change in the first night's numbers.** High-band cards that used to go out
> at 02:00 will now be held until 08:00 local. **That is the feature.** `drain()` reports it:
> `deferred` and `suppressed` are new keys in the returned totals.

### Step 3 — Confirm it is running

The fastest check is the surface, **because it runs the *real* gate rather than describing it**:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$API/api/org/$ORG/delivery/effective?at=2026-08-08T02:00:00%2B00:00" | jq
```

Expect `"in_quiet_hours": true`, `verdicts.high.verdict == "defer"` with
`reason_code == "quiet_hours"` and a `not_before` at 08:00 local, and
`verdicts.critical_interrupt.verdict == "send"` with `reason_code == "override_band_critical"`.

```sql
select status, gate_unit, gate_reason, count(*)
from delivery_outbox where created_at > now() - interval '1 day'
group by 1,2,3 order by 4 desc;
```

### Step 4 — Read the reason codes before assuming anything is wrong

**`suppressed` rows are not errors.**

| If you see | It means | Do |
|---|---|---|
| lots of `quiet_hours` | working as designed, first night | nothing |
| `channel_inactive` | the webhook was removed or deactivated | re-register in Settings → Channels |
| `below_channel_min_band` | someone set a channel floor above the card's band | intended, or lower `min_band` |
| `recipient_opted_out` | that person turned this channel off | intended |
| `org_delivery_disabled` | tenant kill switch is on | intended, or clear it |
| `delivery gate unavailable` in `last_error` | the gate could not read — **usually the migration did not run** | Step 1 |

`GET /api/org/{org}/delivery/held` returns each held message with `held_by`, `reason_code`,
`retryable` and `next_attempt_at`. **It reads the row, not a log.**

### Step 5 — Tenant settings

All four specificities go through one endpoint. `PUT` writes; omitted fields are left alone; an
explicit `null` clears an override so it inherits again. A `422` is the router **refusing to
write something that would degrade**, and the message names the field.

```bash
# tenant default
-d '{"tz_name":"Asia/Kolkata","quiet_start_hour":22,"quiet_end_hour":8}'
# one person turns Slack pushes off
-d '{"seat_id":"seat_42","channel":"slack","opted_out":true}'
# "Slack is escalations only"
-d '{"channel":"slack","min_band":"critical"}'
# compliance hold (a stop and a pause are mutually exclusive — 422 if both)
-d '{"hold_until":"2026-08-12T09:00:00+00:00"}'
# "never wake me" — there is no band above critical
-d '{"override_band":"critical"}'
```

### Step 6 — What to watch in week one

1. **The `deferred` counter should be non-zero and then drain.** If `defer_count` climbs past
   ~3 on the same row, **a window is not opening** — check `tz_name` and the quiet bounds.
2. **`suppressed` should be small and explainable.** A spike in `channel_inactive` means a
   webhook died.
3. **`burst_limit` appearing at all** means seven-a-day is landing in bursts.
4. **`override_band_critical` on a delivered row is a message that woke somebody.** Those should
   be rare and each one should look justified.

### Step 7 — Rollback

```bash
curl -X PUT ... -d '{"quiet_enabled":false}'
```

Policy defaults are permissive, so with quiet hours off **the gate admits everything it used
to.** The tables can be left in place; they are inert.

---

---

## §10 · Gaps

### The one thing genuinely unproven

> **No SQL in this layer has ever run against Postgres.** This machine has no database, no
> docker and no `psql`; CI has no service containers.

What *has* been done to close the gap as far as it can be closed:

- **All 47 statements this layer issues parse as real Postgres** — the migration's 19, every
  literal query in the four modules, and both statements built by string interpolation at
  runtime, **in every shape they can take** (the burst query's two recipient forms, the upsert
  at 1, 2 and 11 columns). Zero failures.
- **Three schema-conformance tests** assert every column read or written exists in a migration,
  **derived from source rather than restated**.
- **`'suppressed'` was proven to break no consumer** — `outbox.py` is the only reader of
  `delivery_outbox.status` in the whole repo.

*That proves syntax and naming. It does not prove "this column exists on your deployed table."*

### Still open, deliberately

| Gap | Detail |
|---|---|
| **`AttentionState.busy_until` has no producer** | GeniOS ingests calendars, but nothing yet projects *"in a meeting until"* per seat, and **a fabricated busy signal would be worse than none.** The branch, the field and its tests all exist so the projection plugs in without reopening a single decision below it. Today it is always `None` → "not busy" |
| **One channel adapter** | `channel_class_for` reads Layer 5's `CHAT_CHANNELS`, so registering a second chat adapter makes it interruptive in **both** layers at once. Email would arrive as `ChannelClass.EMAIL`, deliberately **not** intrusive |
| **No admin role check** | Writes take `require_owner`, the strongest boundary this codebase has. `org_seats.role` exists; *a shared admin dependency belongs in `platform/auth.py` when one is written, not invented inside a settings router* |

---
