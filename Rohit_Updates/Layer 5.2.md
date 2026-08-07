# Layer 5.2 — The Delivery Engine

**Last updated:** 7 August 2026
**Branch:** `antler-inception`
**Tests:** **142 focused delivery/outbox/Executive-bridge tests**; full repository suite
**1795 passed**.
**Status:** Atlas Layer 5.2 core implemented, wired into the existing drain and Atlas Layer 6
learning, **no new worker**.
**For the CTO:** Part 5 is a runbook. Apply migrations through `0044`, deploy, then exercise one
real destination and one controlled terminal failover.

**System Design navigation:** [Layer map](../System%20Design/Layer-6-Intelligence-Distribution/README.md) ·
[component status](../System%20Design/Layer-6-Intelligence-Distribution/STATUS.md) ·
[Delivery Orchestrator](../System%20Design/Layer-6-Intelligence-Distribution/01-Delivery-Orchestrator/README.md) ·
[11 Delivery Units](../System%20Design/Layer-6-Intelligence-Distribution/02-Delivery-Units/README.md) ·
[Delivery Management](../System%20Design/Layer-6-Intelligence-Distribution/03-Delivery-Management/README.md)

The System Design now follows the Atlas's three physical parts. It explicitly marks email missing
and API-only application/mobile/extension/dashboard seams partial rather than calling all eleven
targets complete.

**The one-line summary for a CTO:** GeniOS could produce a correct, well-owned, well-worded
alert and then deliver it at 03:14. Layer 5.2 is the gate between "Layer 5 decided to speak"
and "the webhook fires" — it decides whether this message may travel, **to this person, right
now**, and when it may not, it says so in the row with a reason code.

Layer 4 answers **"what should happen?"**
Layer 5 answers **"how do we make it happen?"**
Layer 5.2 answers **"may this reach them, now?"**

That third question was not being asked. A 03:14 notification is not a delivery bug — it is how
a tenant mutes the channel in week three, and once it is muted every other layer's accuracy is
worth exactly zero.

**Start at Part 5 — it is the deployment runbook.**

> **Current-state correction, 7 August 2026.** The original build note below describes the
> admission gate introduced by migration `0042`. Atlas reconciliation now also exposes immutable
> `DeliveryObject`/`DeliveryResult` projections, leased live presence, deterministic destination
> ordering, Slack + Teams + signed webhook adapters, authenticated pull surfaces, terminal-
> failure-only failover, delivery analytics and the durable learning handoff. Migration `0044`
> adds the presence state. The System Design folder is the component-level current authority.

---

## Part 1 — What already existed (and was good)

`deliver/` was not empty. The *transport* half was already built and is genuinely solid:

| What | Where |
|---|---|
| **The outbox** — every send is a row: queued → delivered \| failed_terminal | `deliver/outbox.py` |
| **Bounded backoff** — `(5, 30, 120, 720)` minutes, then terminal. Never an infinite retry | `deliver/outbox.py` |
| **Claim safety** — `FOR UPDATE SKIP LOCKED`, so two instances never send the same message | `deliver/outbox.py` |
| **Idempotent enqueue** — unique on `(org_id, card_id, channel)`; a re-run is a no-op | `migrations/0032` |
| **Authority re-validation at send time** — a queued card proves it is *still* live before it goes | `deliver/outbox.py` |
| **The Layer 5 wire** — commitments become real messages, exactly once | `deliver/executive_bridge.py` |
| **Daily budget** — `budget_per_user_day`, "a property of the channel's politeness" | `deliver/router.py` |
| **Band cuts from pack config** — a tenant redefines "critical" in one place | `deliver/bands.py` |

**The most important thing that was already right:** delivery is *state*, not hope. Nothing is
a fire-and-forget HTTP call inside the reasoning sweep.

### What was missing

Everything between the claim and the send. Not partially built — **absent**:

| Missing | Consequence |
|---|---|
| **Any notion of the recipient's local time** | A Kolkata tenant's critical card fired at 03:00 IST. No timezone was stored anywhere per seat |
| **Quiet hours** | None. The only dial was *how many* per day, never *when* |
| **A burst limit** | `budget_per_user_day` allows 7 cards. All seven could land in the same minute |
| **An opt-out** | A person who wanted Slack pushes off had no way to say so, and no column to say it in |
| **A tenant kill switch / compliance hold** | Disabling delivery meant deleting the webhook, which also lost the config |
| **A verdict that is not "send" or "fail"** | Holding a message could only be expressed as a *failure*, which burned the retry ladder |
| **Any record of why a message did not arrive** | "Why wasn't I told?" was a log-grep against a clock that had already moved |

Grep confirmed it: `quiet_hours`, `interrupt`, `opted_out`, `defer` appeared nowhere in
`deliver/` before this work. The outbox had exactly two outcomes and neither of them meant
*not yet*.

---

## Part 2 — The fork we had to settle first

The spec calls this "Layer 5.2" and gives it its own number. The codebase has a topology file
(`LAYERS.py`) where `deliver` is already layer **6**, sitting between `executive` (5) and
`feedback` (7).

**Settled: `deliver` (6) *is* the spec's Layer 5.2.** No renumbering, no new package, no
migration of existing code. The layer already existed and already sat in the right place in the
DAG — what was missing was not a home, it was the units.

> This matters more than it sounds. Renumbering would have touched `LAYERS.py`,
> `tests/test_layer_topology.py`, and every import in `deliver/` — a large, risky diff that
> changes no behaviour. The work is filling the gap, not moving the furniture.

**The second fork: where does the gate run — enqueue or drain?**

**Settled: drain.** Enqueue happens inside the 6-hourly sweep, so a row can sit queued for
hours. Evaluating quiet hours against the *enqueue* clock would ask "is 14:00 a humane moment?"
about a message that lands at 03:00 — which is the exact bug this layer exists to fix. The
codebase had already settled this question once, for authority: never trusted from queue time,
always re-validated immediately before the send. Admission obeys the same law for the same
reason.

Enqueue's job is to **materialise** the delivery object onto the row. The gate's job is to
**judge** it against the world as it is at the instant of sending.

---

## Part 3 — What we built

The admission core remains two pure units and one composer. Around it, the Atlas reconciliation
adds the context, routing, adapter, result, analytics and recovery components required to make
Layer 5.2 a complete delivery orchestrator.

| Spec unit | Where | What it does |
|---|---|---|
| **Delivery Policy Unit** | `deliver/policy.py` | *May this travel at all?* Kill switch, hold, channel floor, opt-out. Almost always terminal |
| **Timing & Interruptibility** ⭐⭐⭐⭐⭐ | `deliver/timing.py` | *Is this the moment?* Quiet hours, burst, busy. **Never suppresses anything** |
| **Delivery Gate** | `deliver/gate.py` | Composes the units, resolves their inputs from live tenant state |
| **Delivery Context Resolver** | `deliver/presence.py`, `deliver/gate.py` | Combines preferences, recipient/channel state, burst history and an active leased presence at send time |
| **Destination Routing** | `deliver/destination.py` | Stable primary/fallback ordering from registered destinations; never trusts row order |
| **Channel Adapter Unit** | `deliver/channels/` | Slack, Teams, signed HTTPS webhook and durable pull surfaces behind one adapter contract |
| **Delivery Tracking & Result** | `deliver/results.py` | Projects the one outbox ledger into immutable public DeliveryObject and DeliveryResult contracts |
| **Retry & Failure Recovery** | `deliver/outbox.py` | Bounded transport retry and authority-reproved failover only after terminal adapter failure |
| **Delivery Analytics** | `deliver/analytics.py` | Counted status/channel metrics, attempts, deferrals, burst holds and measured p50/p95 latency |
| — Contract | `contracts/delivery.py` | `SEND` / `DEFER` / `SUPPRESS`, DeliveryObject/Result and the composition law |
| — Wiring | `deliver/outbox.py` | Enqueue stamps the delivery object; drain asks the gate before the send |
| — Schema | `migrations/0042_l6_delivery_gate.sql` | `delivery_preferences` + the delivery object on the outbox row |
| — Presence schema | `migrations/0044_l52_atlas_delivery.sql` | Tenant-scoped, expiring `delivery_presence` leases |
| — Surface | `api/delivery_routes.py` | Preferences, effective gate, held rows, context, typed results, pull inbox and analytics |

### The seven decisions that matter most

**1. DEFER is a first-class verdict, and it spends nothing.**
This is the single most important line in the layer. The outbox already had a retry ladder for
*failures*, and that ladder is bounded — a channel that never works must eventually stop being
tried. Deferral is the opposite kind of event: **nothing is broken, the recipient is asleep.**

If a hold consumed an `attempts` slot, a message queued at 22:00 would burn all four attempts
against quiet hours and be `failed_terminal` by breakfast — the exact message the recipient
most wanted. So `_defer` moves `next_attempt_at`, bumps a **separate** `defer_count`, and
touches nothing else. A test loops ten deferrals and asserts the row never goes terminal, and
another asserts the SET clause literally does not contain the word `attempts`.

**2. Gating keys on channel *physics*, not sender *intent*.**
Layer 5's `CommunicationPlan.interrupt` means "this deserves attention". It does **not** mean
"this will make a phone buzz": a high-band card is pushed to Slack with `interrupt=False` and
still lights a lock screen at midnight.

`DeliveryCandidate.intrusive` is a property of the *channel class* — chat is intrusive, digest
is not, in-app is not, email is not. That is what closes the gap. A digest is never gated on
the clock, because nobody was ever going to be woken by a digest.

**3. Break-glass inherits Layer 5's confidence floor for free.**
The escape hatch is `band ≥ override_band AND interrupt`, and the second half is doing more
work than it looks. `executive/communication.py` only sets `interrupt` when the reasoner's
confidence clears its floor — a critical-*scoring* conclusion it is 40% sure of comes through
with `interrupt=False`. So a low-confidence crisis **cannot** wake anybody, and the timing unit
gets that property without knowing what a confidence interval is.

One dial, upstairs. And because there is no band above `critical`, raising `override_band` to
`critical` is how a tenant says "never wake me".

**4. Constraints compose; they do not race.**
A meeting, quiet hours and a burst limit are three independent facts, and a delivery has to
satisfy all three. Rather than an if/elif ladder whose *order* silently decides the answer,
each check produces its own decision and `DeliveryDecision.combine` folds them:

> **First SUPPRESS wins. Among DEFERs, the latest window binds. Otherwise the first SEND.**

Intersection, not a vote. Adding a fourth unit later is adding a line to a list — and it can
only ever make the system **quieter**, never louder, which is the correct direction for a
mechanism that spends human attention.

The tie-breaks are deterministic on purpose: two units that both suppress must always name the
same reason, or the same delivery blocked twice gets explained two different ways depending on
dictionary ordering. That is the kind of nondeterminism that turns an incident review into an
argument.

**5. `suppressed` is a third status, not a flavour of `cancelled`.**
`cancelled` already meant one specific thing: the subject stopped being live before the send —
a closed commitment, a revoked decision. A person who turned this channel off is a *different
fact with a different fix*. Three outcomes, three statuses, because an operator seeing
`suppressed` should look at preferences, not at Slack's status page.

**6. Bad configuration degrades in the engine and is refused at the door.**
Two responses to the same predicate, and the asymmetry is deliberate:

- **`build_context` degrades.** A tenant who types `Amercia/New_York` must never stop *another*
  tenant's mail draining. Every unusable value falls back to the **protective** default — a
  broken timezone becomes UTC quiet hours, not *no* quiet hours — and the reason travels into
  the audit row so the setting is visibly wrong rather than silently ignored.
- **`PUT /delivery/preferences` refuses.** It writes, re-resolves inside the same transaction,
  and rolls back if the result would degrade.

The engine cannot afford to fail; the form field cannot afford to lie. The consequence is the
one that matters: **a setting that survives a PUT is a setting that will actually take effect.**

**7. Preferences resolve field-by-field, never row-by-row.**
Rows are keyed `(org_id, seat_id, channel)` with `'*'` as the wildcard, at four specificities:

```
(org, seat, 'slack')  →  this person, this channel     "no Slack pushes, keep email"
(org, seat, '*'    )  →  this person, everywhere       their timezone, their quiet hours
(org, '*',  'slack')  →  everyone, this channel        "Slack is escalations only"
(org, '*',  '*'    )  →  the tenant default            set by an admin
```

Each *column* independently walks from most specific to least and takes the first non-null
opinion. Picking a winning **row** would mean a person who sets only their timezone thereby
discards their tenant's quiet hours. A seat beats an org-wide channel rule, because the seat is
a statement about a human and the channel is a statement about a pipe.

`'*'` is a sentinel rather than NULL because **NULLs never compare equal inside a primary key**,
which would let two org-wide default rows coexist and make resolution depend on physical row
order.

### What is deliberately absent, and why

**No second daily cap.** `budget_per_user_day` already exists in `deliver/router.py`. A second
daily dial here would be a second answer to one question — and the failure mode is not that a
message gets blocked twice, it is that a support engineer finds one limit, changes it, and
nothing happens. Timing caps only the **burst**, which the daily budget genuinely does not
cover: seven cards are a reasonable day and an unreasonable minute.

**No "are they already handling it?" check.** Layer 5 owns that and already does it
(`executive_bridge.executive_delivery_is_live`). Two copies of an authority rule is how a
revoked recommendation gets delivered.

**No content inspection.** The gate sees a candidate, never a payload. A rule that reads the
message is a rule that will eventually be asked to make exceptions for important-sounding ones —
and at that point "should I interrupt?" has quietly become a second reasoning engine sitting
below the real one.

### The thirteen reason codes

Every blocked delivery names itself. "Why wasn't I told?" is asked far more often, and far more
angrily, than "why *was* I told?" — so the answer is in the row, not in a log.

| Unit | Reason code | Verdict |
|---|---|---|
| `policy` | `org_delivery_disabled` | suppress |
| `policy` | `org_delivery_held` | **defer** (the only one policy issues) |
| `policy` | `channel_inactive` | suppress |
| `policy` | `below_channel_min_band` | suppress |
| `policy` | `recipient_inactive` | suppress |
| `policy` | `recipient_opted_out` | suppress |
| `policy` | `permitted` | send |
| `timing` | `quiet_hours` | defer |
| `timing` | `recipient_busy` | defer |
| `timing` | `burst_limit` | defer |
| `timing` | `channel_not_intrusive` | send |
| `timing` | `override_band_<band>` | send — **the break-glass** |
| `timing` | `within_attention_window` | send |
| `timing` | `quiet_window_unsatisfiable` | send (defensive; unreachable via the contract) |

---

## Part 4 — Bugs found and fixed while building

**1. A card pushed to chat had no interrupt flag, and no dial to get one.**
The card path never builds a `CommunicationPlan`, so it had nothing to say whether a card could
break through quiet hours. Fixed by extracting `may_interrupt(band, confidence_bp, cfg)` out of
`executive/communication.py` and calling it from the card enqueue — **with the tenant's own
config snapshot**, pulled from the `authority_cfg` join that was already in the query.

It reads the snapshot the card was *authorised under*, not the current pack config. A tenant who
tightens `interrupt_band` while a card is queued must not have that card re-judged by a rule its
band was never cut by. Both ends of the comparison talk about the same configuration.

**2. `'*'` is a scope, never a route.**
The preferences validator built a probe candidate with `channel='*'` and the contract correctly
refused it — a delivery that names no channel is not a delivery. Fixed by expanding a wildcard
rule to the concrete adapters it governs and validating against each, so a setting that is
harmless for the digest and broken for chat is caught at save time rather than at 03:00.

**3. A burst read cached across a pass would have let a flood through.**
Ten intrusive messages coming due in one drain against a limit of three: a memoised count reads
"0 delivered this hour" ten times and every one of them goes out — the exact flood the limiter
exists to prevent. Fixed with `note_delivered`, which folds this pass's own sends into the
window so the fourth message is held by the three that preceded it seconds earlier.

**4. A successful send kept a stale hold reason.**
A row deferred overnight still carried `gate_reason='quiet_hours'` after it finally delivered —
and worse, a message that *woke somebody* could not say why. Fixed: the success path writes the
admitting verdict too. `override_band_critical` in the row is the whole answer to "who
authorised this at 2am?", which is a question that does get asked.

**5. A gate that cannot read must not decide by accident.**
An exception in the resolver would have taken the whole drain down, or — worse in a naive
fix — sent the message anyway. Fixed per row: a gate failure takes the existing bounded retry
ladder. The message survives, nothing goes out un-judged, a gate that stays broken ends
`failed_terminal` with the reason in the row, and one tenant's bad state cannot stop the pass
draining for everybody else.

**6. The resolver held a snapshot across an outbound POST.**
The gate connection sat `idle in transaction` while Slack answered, holding a snapshot and
blocking vacuum. Fixed with a rollback between rows — these are read-only queries, so it costs
nothing and additionally means each resolve sees deliveries this pass just committed.

### Atlas reconciliation defects closed after the admission core

| # | Gap or failure mode | Current correction |
|---|---|---|
| 7 | The Atlas promised DeliveryObject and DeliveryResult, but callers saw private outbox rows | Immutable typed projections now expose a stable public lifecycle without creating a second ledger |
| 8 | A crashed client could leave somebody permanently busy | Presence is a mandatory-expiry lease; effective busy time is capped by its expiry |
| 9 | Destination selection depended on whichever channel row arrived first | Explicit integer priority with stable channel-name tie-break |
| 10 | Failover could have bypassed quiet hours, opt-out or revoked authority | Only `failed_terminal` opens failover, and authority is re-proved before enqueueing the next destination |
| 11 | Calling a mobile/dashboard row “delivered” could be mistaken for device push | These adapters are explicitly pull surfaces; success means durable availability in the authenticated inbox |
| 12 | A broad delivery failure rate could mislabel queued/suppressed work as transport failure | Analytics excludes open work and counts transport reliability only over delivered + failed-terminal rows |

### The current focused test families

| File | What it proves |
|---|---|
| `tests/test_delivery_gate.py` | Contract invariants, policy/timing composition, DST, resolver and drain wiring |
| `tests/test_delivery_routes.py` | Effective gate, transactional preference refusal, held surface and tenant boundary |
| `tests/test_delivery_atlas.py` | Typed objects/results, leased presence/resolver, deterministic routes, adapter validation, analytics, migration and failover law |
| `tests/test_delivery.py` | Card/digest routing and format behaviour |
| `tests/test_l6_outbox.py` | Claim safety, authority revalidation, bounded retry and one-ledger lifecycle |
| `tests/test_executive_bridge.py` | Frozen Layer 5 communication handoff, resolved recipients and stale suppression |

Three schema-conformance locks are worth calling out because they catch the *silent* failure:
every preference column the gate reads, every column the router writes, and every column the
held view selects must exist in a migration. Rename one and `preferences.get(...)` returns
`None` everywhere, the gate falls back to defaults, and a tenant who set quiet hours watches
nothing change **with no error anywhere**. The read list is derived from the source, so it
cannot drift out of date.

---

## Part 5 — Deployment runbook

**Layer 5.2 self-starts.** It sits inside the drain that already runs on the scheduler
heartbeat. No new cron, no new worker, no new service, no new environment variable. Apply the
migration, deploy the branch, and it begins gating.

---

### Step 1 — Apply the migration

```bash
.venv/bin/python -m genios_engine.platform.migrate
```

Applies both Layer 5.2 migrations in sequence:

`0042_l6_delivery_gate.sql`:

- `delivery_preferences` — the rules table, with the `'*'` sentinel and its org cascade FK
- seven columns on `delivery_outbox` — `recipient`, `band`, `channel_class`, `interrupt`,
  `defer_count`, `gate_unit`, `gate_reason`
- two partial indexes — the burst-window read and the operator's "what is held?" view

`0044_l52_atlas_delivery.sql`:

- `delivery_presence` — one bounded lease per `(org_id, seat_id)`
- a database check that `expires_at > observed_at`
- tenant deletion cascade and an active-lease lookup index

**Verify:**

```sql
select filename from schema_migrations
 where filename in ('0042_l6_delivery_gate.sql', '0044_l52_atlas_delivery.sql')
 order by filename;  -- 2 rows
\d delivery_preferences
\d delivery_presence
\d delivery_outbox
```

**Note:** the column adds carry non-volatile defaults, so PostgreSQL 11+ does them without a
table rewrite. The cascade constraint is `not valid`, matching the 0033/0041 convention — it
binds every future write without taking a full-table lock on deploy.

**If it fails:** migrations are immutable and checksummed. Ship a new migration; never edit an
already-applied file in place.

---

### Step 2 — Deploy the branch

No new settings. Layer 5.2 uses what is already there:

| Setting | Why | Already set? |
|---|---|---|
| `GENIOS_DATABASE_URL` | everything | yes |
| `GENIOS_SCHEDULER_ENABLED` | drives the drain the gate sits in | yes |

**Behaviour on day one, before anybody configures anything:** the defaults are protective on
timing and permissive on policy, and that asymmetry is deliberate. An unconfigured tenant gets
quiet hours **on** (21:00–08:00 UTC), a burst cap of 3/hour, and critical break-glass — but
delivery itself stays enabled. Silence by default would be indistinguishable from the product
being broken.

> **Expect a visible change in the first night's numbers.** High-band cards that used to go out
> at 02:00 will now be held until 08:00 local. That is the feature. `drain()` reports it:
> `deferred` and `suppressed` are new keys in the returned totals.

---

### Step 3 — Confirm it is running

The fastest check is the surface, because it runs the *real* gate rather than describing it:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$API/api/org/$ORG/delivery/effective?at=2026-08-08T02:00:00%2B00:00" | jq
```

Expect `"in_quiet_hours": true`, `verdicts.high.verdict == "defer"` with
`reason_code == "quiet_hours"` and a `not_before` at 08:00 local, and
`verdicts.critical_interrupt.verdict == "send"` with `reason_code == "override_band_critical"`.

Then confirm the drain is producing the new outcomes:

```sql
select status, gate_unit, gate_reason, count(*)
from delivery_outbox
where created_at > now() - interval '1 day'
group by 1,2,3 order by 4 desc;
```

---

### Step 4 — Read the reason codes before assuming anything is wrong

`suppressed` rows are **not** errors. The table in Part 3 is the decoder. In particular:

| If you see | It means | Do |
|---|---|---|
| lots of `quiet_hours` | working as designed, first night | nothing |
| `channel_inactive` | the webhook was removed or deactivated | re-register in Settings → Channels |
| `below_channel_min_band` | someone set a channel floor above the card's band | intended, or lower `min_band` |
| `recipient_opted_out` | that person turned this channel off | intended |
| `org_delivery_disabled` | tenant kill switch is on | intended, or clear it |
| `delivery gate unavailable` in `last_error` | the gate could not read — usually the migration did not run | Step 1 |

The operator view is one call:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$API/api/org/$ORG/delivery/held" | jq
```

It returns each held message with `held_by` (which unit), `reason_code`, `retryable`, and
`next_attempt_at`. It reads the **row**, not a log, because by the time anybody asks the clock
has moved on and the log has rotated.

---

### Step 5 — The tenant-side settings that change behaviour

All four specificities go through one endpoint. `PUT` writes; omitted fields are left alone;
an explicit `null` clears an override so it inherits again.

```bash
# Tenant default: Kolkata hours, quiet 22:00–08:00
curl -X PUT -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  "$API/api/org/$ORG/delivery/preferences" \
  -d '{"tz_name":"Asia/Kolkata","quiet_start_hour":22,"quiet_end_hour":8}'

# One person turns Slack pushes off
curl -X PUT ... -d '{"seat_id":"seat_42","channel":"slack","opted_out":true}'

# "Slack is escalations only"
curl -X PUT ... -d '{"channel":"slack","min_band":"critical"}'

# Compliance hold with a known end (a stop and a pause are mutually exclusive — 422 if both)
curl -X PUT ... -d '{"hold_until":"2026-08-12T09:00:00+00:00"}'

# "Never wake me" — there is no band above critical
curl -X PUT ... -d '{"override_band":"critical"}'
```

A `422` here is the router refusing to write something that would degrade. The message names
the field.

---

### Step 6 — What to watch in week one

1. **The `deferred` counter should be non-zero and then drain.** Rows held overnight should
   deliver in the morning batch. If `defer_count` climbs past ~3 on the same row, a window is
   not opening — check `tz_name` and the quiet bounds.
2. **`suppressed` should be small and explainable.** A spike in `channel_inactive` means a
   webhook died.
3. **`burst_limit` appearing at all** means seven-a-day is landing in bursts, which is worth
   knowing regardless.
4. **`override_band_critical` on a delivered row** is a message that woke somebody. Those should
   be rare and each one should look justified.

---

### Step 7 — Rollback

Layer 5.2 adds delivery columns plus the preference and presence tables; it changes no existing
business decision, but the drain now proves admission before sending and may recover an exhausted
transport through the next registered destination.

To neutralise it without redeploying, set the tenant default to no quiet hours:

```bash
curl -X PUT ... -d '{"quiet_enabled":false}'
```

That returns behaviour to exactly what it was — policy defaults are permissive, so with quiet
hours off the gate admits everything it used to. The tables can be left in place; they are inert
if nothing writes to them.

---

### The one thing that is genuinely unproven

**The new SQL has not been exercised against a live PostgreSQL deployment in this handoff.** Every
unit, the composer and the drain wiring execute against in-memory doubles, while schema ratchets
check the statements against migration-declared tables and columns.

What *has* been done to close the gap as far as it can be closed without a database:

- **Schema-conformance tests** assert that every column read or written exists in a
  migration, derived from source rather than restated.
- **`'suppressed'` was proven to break no consumer** — `outbox.py` is the only reader of
  `delivery_outbox.status` in the whole repo.

That proves syntax and naming. It does not prove "this column exists on your deployed table".
**Step 1 and Step 3 are what close it, and they are why this runbook starts there.**

---

### Still open, deliberately

**Presence has a trusted manual publisher, not an automatic one.** Owner-authenticated product
surfaces can publish and clear a 30–3600 second lease through `/delivery/context`; expired state is
ignored. Automatic calendar/browser/mobile projection still needs a trusted seat identity and a
publisher lifecycle. Calendar plans alone are deliberately not fabricated into live presence.

**External adapters are Slack, Teams and signed webhook.** App, dashboard, API, application,
extension and mobile are durable pull surfaces; mobile does **not** mean APNs/FCM. Native email and
device push remain open until provider, identity, unsubscribe/token, receipt and outage semantics
are chosen. Production also needs network-level egress controls for customer webhooks.

**No admin role check.** Writes take `require_owner`, which is the strongest boundary this
codebase has. `org_seats.role` exists; a shared admin dependency belongs in `platform/auth.py`
when one is written, not invented inside a settings router.

---

## Part 6 — What this layer will not do, on purpose

**1. It never decides that somebody should not be told something.**
That judgement was made upstairs by a layer with the context to make it. The timing unit only
ever moves the *moment*, and where it cannot find a humane one it says so with a reason code
rather than quietly dropping the message. `evaluate_timing` returning `SUPPRESS` is impossible,
and a test sweeps every reachable combination of profile, state, band, interrupt flag and hour
across eight days to prove it.

**2. It never reads the message.**
The candidate carries no headline, no facts, no payload. A timing unit that could read the body
would eventually be asked to make an exception for an important-sounding one.

**3. It never reassigns.**
A deactivated seat is a suppression, not a reroute. Choosing a different person at delivery time
would invent an owner the commitment never had — and Layer 5's unrouted path already exists for
work with nobody to send it to. The commitment stays live, keeps escalating, and stays visible
on the card surface. Only this push stops.

**4. It never fails open on ambiguity.**
Every fallback resolves toward silence: an unrecognised channel class is assumed **intrusive**
and gated; an unreadable band becomes `standard`, which cannot break glass; a row carrying both
a stop and a pause resolves to the stop; a card with no recorded confidence cannot interrupt.
The one deliberate exception is a structurally impossible quiet window, where sending slightly
rudely beats never sending at all — and the contract refuses that config at construction, so it
is unreachable.

**5. It never lets a hold become a loss.**
Deferral is unbounded by design, because every deferral has a real end: a quiet window opens, a
burst clears, a hold lifts. Staleness stays owned by the authority re-validation, which runs the
moment the window opens and cancels an expired card there. A second age check here would be a
second, weaker copy of a predicate that already exists.

---

## Part 7 — Where we disagreed with the architecture spec

| Spec says | We did | Why |
|---|---|---|
| Layer 5.2 is a distinct layer | It **is** `deliver` (layer 6), which already sat between executive and feedback | Renumbering touches the topology file, its ratchet test and every import, and changes no behaviour. The layer had a home; it was missing units |
| A "Delivery Object" | Materialised as **columns on the outbox row**, not a new table | The outbox already *is* the delivery ledger. A second table would be a second write per send and a second thing to keep true |
| A notification-history table for rate limiting | Answered from `delivery_outbox` itself, with a partial index | Once the row carries `recipient` and `channel_class`, "how many intrusive messages this hour?" is a range scan over rows the system already writes |
| Interrupt decided at delivery | Interrupt is **decided by Layer 5** and only *honoured* here | Layer 5 gates it on a confidence floor. Re-deriving it below would put a second, weaker copy of a confidence rule under the real one |
| Quiet hours as a delivery-time filter | Quiet hours produce a **DEFER with a clock**, never a drop | A filter loses the message. The whole layer turns on deferral being distinct from both failure and refusal |

---

## Summary

| Capability | Status |
|---|---|
| SEND / DEFER / SUPPRESS as a closed, typed contract | ✅ Both halves of the DEFER invariant enforced at construction |
| Quiet hours, in the recipient's own timezone | ✅ DST-correct — proven against spring-forward, fall-back and +05:30 |
| Timing unit can never suppress | ✅ Exhaustively swept |
| Break-glass, inheriting Layer 5's confidence floor | ✅ Low-confidence critical cannot wake anyone |
| Burst limit (per hour), distinct from the daily budget | ✅ Counts this pass's own sends |
| Per-org / per-channel / per-seat policy | ✅ Field-by-field resolution, four specificities |
| Deferral never spends a retry | ✅ Locked at the SQL level by test |
| `suppressed` distinct from `cancelled` and `failed_terminal` | ✅ Three outcomes, three fixes |
| Every blocked delivery explains itself in the row | ✅ 13 reason codes + `/delivery/held` |
| Bad config degrades in the engine, is refused at the door | ✅ Same predicate, opposite responses |
| Tenant control surface | ✅ Preferences, `/effective`, held rows, leased context, results, pull inbox and analytics |
| Schema conformance locked by test | ✅ Reads, writes and the held view |
| Typed DeliveryObject and DeliveryResult | ✅ Immutable projection over the one outbox ledger |
| Leased live context | ✅ Owner-published, TTL-bounded and ignored after expiry |
| Destination routing and terminal-failure failover | ✅ Stable priority; never routes around policy, timing or authority |
| Slack, Teams and signed webhook | ✅ Validated adapters behind bounded retry |
| Pull surfaces and inbox | ✅ Durable availability, explicitly not device push |
| Delivery analytics and Atlas Layer 6 handoff | ✅ Counted from the same durable ledger |
| **Run against a real Postgres** | ❌ **Step 1 + Step 3 of the runbook** |
