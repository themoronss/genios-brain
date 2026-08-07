# Layer 5 — The Executive Engine

**Last updated:** 7 August 2026
**Branch:** `antler-inception`
**Tests:** **195 focused Layer 5 tests**; full repository suite **1795 passed**.
**Status:** Atlas core implemented, wired to Layer 5.2 and Atlas Layer 6 learning, scheduled.
**For the CTO:** Part 5 is a runbook. Two commands: migrate, deploy. It self-starts from there.

**System Design navigation:** [Layer map](../System%20Design/Layer-5-Executive-Engine/README.md) ·
[component status](../System%20Design/Layer-5-Executive-Engine/STATUS.md) ·
[11 Executive Units](../System%20Design/Layer-5-Executive-Engine/01-Executive-Units/README.md) ·
[lifecycle](../System%20Design/Layer-5-Executive-Engine/02-Execution-Lifecycle/README.md) ·
[contracts/operations](../System%20Design/Layer-5-Executive-Engine/03-Contracts-and-Operations/README.md)

The System Design is now structured as part → unit → component module rather than the earlier
flat page list. The previous prose claims remain subject to the status ledger's code evidence.

**The one-line summary for a CTO:** GeniOS could produce an excellent recommendation and had
no idea whether anyone ever did it. Layer 5 turns a recommendation into a **commitment** —
with an owner, a deadline, a channel, an escalation ladder and a clock — and then watches it
until it is done, dead, or out of time.

Layer 4 answers **"what should happen?"**
Layer 5 answers **"how do we make it happen?"**

Those are different jobs. A conclusion is an opinion. A commitment is an opinion with a name
and a date attached.

**Start at Part 5 — it is the deployment runbook.**

> **Current-state correction, 7 August 2026.** The original build note below correctly describes
> the foundation, but the Atlas reconciliation added runtime Execution Coordination, owner-only
> live-state transitions, dependency-gated action completion, blocked escalation, resolved
> escalation recipients, and a clean queued-vs-delivered audit split. The earlier statement that
> Layer 7 did not read `execution_outcomes` is now obsolete: Atlas Layer 6 learning consumes them.
> The System Design folder is the component-level current authority.

---

## Part 1 — What already existed (and was good)

Layer 5 was not empty. Half of it — the *decision intelligence* half — was already built and
is genuinely strong:

| What | Where |
|---|---|
| **Decision Briefs** — what/why/urgency/evidence/what-if-nothing | `executive/brief.py` |
| **Verb taxonomy** — do · consider · delay · escalate · delegate · approve · reject · don't | `executive/verbs.py` |
| **Preventive mode** — "this rule trips in 14 hours", act *before* the miss | `executive/modes.py` |
| **Summary ladder** — one line / one minute / five minutes, counted never estimated | `executive/summary.py` |
| **Executive memory** — so the next decision isn't amnesiac | `executive/memory.py` |
| **Why-not receipts** — "why didn't you tell me about X?" answered from stored suppressions | `executive/explain.py` |
| **The invention validator** — rendered copy may only use facts that exist | `executive/validate.py` |
| **Law 08** — below 5 observations a play says *"new play — no data yet"*, never a number | `executive/brief.py` |

**The most important thing that was already right:** this layer never lets a model decide.
Every number it produces is arithmetic over stored truth.

### What was missing

The entire *operational* half. Not partially built — **absent**:

| Missing | Consequence |
|---|---|
| An **Execution Object** — the plan itself | A card said "follow up with Acme". Nothing recorded what the steps were, who owned them, or by when |
| **Owner resolution as Layer 5's job** | Ownership lived in `deliver/router.py`, so Layer 6 was the authority on whose problem something was |
| **Reminders** | Zero. A card sat until it expired. Nothing ever said "this is still open and it's day 9" |
| **Escalation** | Zero. Nothing ever reached a manager |
| **Monitoring** | Nothing checked whether the recommended thing actually happened |
| **Execution state** | A card had states. A *commitment* had none — no running / waiting / blocked / completed |
| **Outcome truth for learning** | Layer 7 learned only from button clicks: whether a card *looked* right, never whether acting on it *worked* |

Grep confirmed it: `reminder`, `escalation`, `execution object`, `execution state` appeared
nowhere in the codebase before this work.

---

## Part 2 — The fork we had to settle first

The architecture document contradicts itself. Layer 5 claims an Owner Planner and a Channel
Selector; Layer 5.2 splits Delivery out as its own layer. Both cannot be true.

**You decided: Layer 5 owns who + channel too.** That is now implemented, and here is why it
is the better reading:

> Deciding whether to interrupt someone is part of the commitment, not part of the transport.
> "Slack this person right now" and "let them find it in tomorrow's digest" are two different
> promises about how much of their attention this is worth — and that judgement belongs with
> the layer that decided the work was worth doing at all.

**How it was done without breaking the topology ratchet:** the authority moved *down* into
`executive/assignment.py` and `executive/communication.py`. `deliver/router.py` is now a thin
delegation upward-in-time, downward-in-layers. Layer 6 may import Layer 5; Layer 5 may never
import Layer 6. `tests/test_layer_topology.py` still passes, and `executive/validate.py`
already documented exactly this pattern.

**Behaviour is byte-identical.** Same three ordered rules, same reason codes. Moving code and
changing it in the same step is how a refactor becomes an outage.

---

## Part 3 — What we built

Ten Atlas units plus Coordination, one output. The layer emits exactly one artifact: the
**Execution Object**.

Numbered to match your spec exactly, so this table can be read side by side with it. Every unit
in the spec is built; the unnumbered rows are the machinery the spec implies but does not name.

| Spec unit | Where | What it does |
|---|---|---|
| **1 · Decision Interpreter** | `executive/interpret.py` | Reads a Layer 4 decision as an instruction, or refuses by name |
| **2 · Execution Planning** ⭐⭐⭐ | `executive/planning.py` | Steps → typed actions, dependencies, waves, audiences, resources and deadlines |
| **2.5 · Execution Coordination** | `executive/coordination.py` | Recomputes ready/waiting/completed work and blocks out-of-order completion |
| **3 · Communication Planning** | `executive/communication.py` | Audience, channel, interrupt, tone and reason code |
| **4 · Execution Validation** ⭐⭐⭐⭐⭐ | `executive/execution_guard.py` | Re-validates authority, outcome, subject, owner and clock before every outbound moment |
| **5 · Reminder** | `executive/reminder.py` | Business relevance, due rungs, fatigue and cooldown |
| **6 · Monitoring** | `executive/monitor.py` | Progress, stalls and done-but-unproven |
| **7 · Escalation** | `executive/escalation.py` | Frozen urgency-scaled ladder with live target resolution |
| **8 · Execution Tracking** | `executive/lifecycle.py` | State machine and audit vocabulary |
| **9 · Feedback Collection** | `executive/collect.py` | Writes immutable outcome truth consumed by learning |
| **10 · Execution Object Builder** | `executive/execution.py` | Composes one immutable commitment or refuses cheaply |
| — Contract | `contracts/execution.py` | The Execution Object: frozen, content-addressed, integer-only, state machine as data |
| — Owner resolution | `executive/assignment.py` | *Who.* Moved down from `deliver/`. Pure core, injected directory |
| — Persistence | `executive/execution_store.py` | The only Layer 5 module that touches SQL |
| — Layer 5.2 handoff | `deliver/executive_bridge.py` | Carries grounded reminder/escalation events to the resolved recipient, exactly once |
| — The loop | `executive/sweep.py` | Two passes: plan commitments, then run the lifecycle. **Wired into the scheduler heartbeat** (`api/routes.py`) — no new cron |
| — Schema | `migrations/0041_l5_execution.sql` | 5 tables + the reporting line on `org_seats` |
| — Surface | `api/executive_routes.py` | `/v1/executive/commitments*`, `/sweep` |

Unit 5 is the one row that lives in `deliver/`. That is deliberate and explained in Part 7:
Layer 5 *authors* the message and decides it should be sent; Layer 6 owns the transport.

### The five decisions that matter most

**1. Identity is the decision plus the plan — never the routing.**
`execution_id` hashes `(org, decision_hash, plan_hash)` and deliberately *excludes* who it was
assigned to. Reassigning a commitment must not create a second one for the escalation ladder to
chase separately. Running the sweep twice must produce one row. A partial unique index on
`(org_id, decision_hash) where closed_at is null` enforces it in the database too.

**2. Nothing fires without re-validation.**
This is the improvement you asked for, and it is the single most important thing in the layer:

> The classic failure of any reminder engine is that it reminds you about something that
> already happened. The plan was correct when it was made; the world moved; nobody told the
> scheduler. You get nudged to chase a customer who replied yesterday — and from that moment
> every future nudge is presumed wrong until proven otherwise.

So every outbound moment — first delivery, each reminder, each escalation rung — re-checks live
state immediately before it happens. The guard returns one of six verdicts rather than a boolean,
because five of them are refusals and they mean genuinely different things — collapsing them
would make the difference invisible in exactly the reports where it matters:

| Verdict | Means |
|---|---|
| `COMPLETE` | The world already did it |
| `CANCEL` | It should never happen now (authority revoked, deal closed, human said no) |
| `EXPIRE` | The window closed with nothing observed |
| `REROUTE` | Valid work, wrong person — the rep left |
| `SUPPRESS` | Not now (blocked, cooldown) — the commitment stays open |
| `PROCEED` | Proven still live and unmet |

One subtlety worth knowing about: **an observed event only counts if it happened *after* the
commitment was created.** The event that *causes* a recommendation is usually the same kind as
the event that would *prove* it resolved — an inbound reply both signals a stalled deal and
proves the follow-up landed. Counting history would mark every commitment complete on day zero,
which is the most convincing possible way to look like it is working while doing nothing.

**3. A read-only play can never change the outside world.**
Pack steps are classified by a fixed lexicon, never by a model — approval boundaries cannot be
probabilistic. When a read-only play says *"Send the renewal notice"*, it is not asking GeniOS
to send anything; it is asking GeniOS to get a send *ready for a person to approve*. The
planner records the declared kind in metadata, plans the action GeniOS is actually committing
to, and attaches the approval gate. The audit trail shows both what the pack said and what the
system did about it. The contract itself refuses a read-only action with an external effect.

**4. Reminders are about business relevance, not the calendar.**
Nothing counts days for its own sake. The deadline warning fires at a *proportion of the
window* (75% burned), not at a fixed "48 hours before" — a two-day commitment and a
fortnight-long one are not both urgent two days out. Fatigue is a hard stop, not a taper: after
four reminders the unit stops asking and hands over to escalation, because a fifth identical
nudge does not produce action, it produces a filter rule.

**5. The wire respects Layer 5's judgement, and adds nothing to it.**
Layer 5 cannot import Layer 6, so it cannot send anything itself. What it can do is write its
decision down — and it does: the reminder event carries the routing plan on the parent commitment
and the *grounded fact corpus* in its own `detail`. `deliver/executive_bridge.py` reads that and
turns it into a message.

The division comes out exactly right:

> Layer 5 decides **whether to speak, to whom, through which channel, and what may be said.**
> Layer 6 decides **how it looks and gets it there, with retries.**

Three properties make it safe to send. A commitment Layer 5 planned for the digest is **not**
pushed — respecting that is the whole reason Layer 5 was given the channel decision. The bridge
has no access to the graph and cannot look anything up, so "invents nothing" is *structural*
rather than a matter of discipline. And the message is re-validated at send: a reminder can sit
through a retry backoff while the customer replies, so a commitment that closed in that window is
cancelled rather than delivered.

Exactly-once falls out of the synthetic key `exec:<execution_id>:<event_id>` against the existing
`(org, card, channel)` unique index — the same trick the daily digest already uses. No new
bookkeeping table, and a crashed sweep that re-enqueues cannot double-send.

### Escalation, in practice

The shipped ladder is 1 / 3 / 7 / 14 days: notify → remind → escalate to manager → critical to
leadership. It is **frozen into the execution object at build time**, not recomputed when it
fires — otherwise retuning the pack on a Tuesday would silently rewrite the history of every
commitment made on Monday.

Urgency compresses it. A critical commitment runs the same ladder at half the delay
(1 / 2 / 4 / 7). The shape is preserved; only the tempo changes. That is the difference between
an escalation *policy* and a timer.

And it stops at the decision's expiry. A rung that would fire after Layer 4 stopped standing
behind the conclusion is dropped at build time, so the execution object is *provably* incapable
of escalating on lapsed authority.

### What Atlas Layer 6 learning gets that it never had

The original learner used card clicks — whether a recommendation *looked* right on arrival.
`execution_outcomes` measures whether acting on it *worked*, and Atlas Layer 6 now consumes this
cohort for Outcome Analysis, Recommendation Learning and Knowledge Evolution:

| Label | Means |
|---|---|
| `succeeded` | The world produced the declared evidence. **The only positive label** |
| `completed_unproven` | Every step ticked, nothing observed |
| `expired_untouched` / `expired_in_progress` | Ran out of time, with or without progress |
| `cancelled_by_human` / `by_world` / `by_system` | Dismissed / deal closed / incident |

`completed_unproven` is kept separate on purpose. **A play people are happy to finish and that
never produces its outcome is the most expensive failure mode a recommendation system has**,
and merging it into "succeeded" would hide it permanently. Each row also carries
`reminders_sent` and `escalations_fired` — the *cost* in human attention. A play that succeeds
once per four reminders and one escalation is not obviously better than one that fails quietly.

---

## Part 4 — Bugs found and fixed while building

Loop engineering, not afterthoughts. Each was caught by writing the test before trusting the code.

| # | Bug | How it was caught | Fix |
|---|---|---|---|
| 1 | Step classifier typed *"Review the deal history"* as an approval gate | Ran the classifier over every shipped play | Bare `review` removed from approval phrases; the sentence's **leading verb** decides |
| 2 | *"Draft a warm outreach note"* classified as `SEND` because "outreach" appeared later | Same sweep | Leading-verb table beats whole-sentence keyword scan |
| 3 | `authority_valid()` embedded Layer 4's predicate without binding `:authority_time` | New AST ratchet | Bind supplied; `now` threaded through so one instant judges the whole sweep |
| 4 | New tables had no `orgs` cascade — a commitment could outlive its tenant's deletion | `test_account_erasure.py` | Five FK cascades added to migration 0041 |
| 5 | Unrouted commitments got a different `execution_id` than routed ones for the same decision | Identity test | Uniqueness moved to `(org_id, decision_hash)` partial index; supersede path added |
| 6 | Stored plans had no rehydration path — payload was write-only | Round-trip test | `decanonicalize()` + `from_semantic_dict()` + `verify_round_trip()` at build time |
| 7 | `POST /sweep` crashed: `vars()` on a slotted dataclass | New route test | `dataclasses.asdict` |
| 8 | The dismiss route wrote SQL `now()` while everything else passes time explicitly | New route test | Time is bound, so a replay observes the instant the event recorded |
| 9 | The Execution Object described dependencies but runtime could complete blocked actions | Atlas coordination tests | Added a deterministic Coordination Snapshot and dependency-gated completion |
| 10 | A blocked commitment had no legal live-state mutation | Route/state-machine tests | Added authenticated `running ↔ waiting/blocked` transitions with audit events |
| 11 | Blocked work could wait forever without reaching an escalation rung | Lifecycle scenarios | Blocked state now remains monitorable and escalatable instead of silently stalling |
| 12 | Cooldown/fatigue could hide a reminder rung that was already due | Boundary-clock tests | Due-ladder/business-relevance checks run before fatigue/cooldown suppression |
| 13 | Escalation used a stale recipient after the reporting line changed | Bridge tests | Resolve the current manager/leadership target immediately before handoff |
| 14 | An expired commitment could be reopened as ordinary running work | State-transition ratchet | Expired work remains terminal; renewed work requires a new decision/commitment |
| 15 | A queued reminder could be reported as delivered before transport success | Outbox/bridge tests | Execution event records queued handoff; transport truth remains in DeliveryResult |
| 16 | Concurrent escalation sweeps could enqueue the same rung twice | Race/idempotence scenarios | Guarded rung claim plus stable delivery key makes the handoff exactly once |
| 17 | Ticking an action on a newly created commitment skipped the running transition | Route tests | The first valid completion moves the commitment through the legal running state |

### The current focused test families

| File | Proves |
|---|---|
| `tests/test_executive_execution.py` | contract identity, read-only boundary, autonomy and clocks |
| `tests/test_executive_coordination.py` | parallel dependency waves, joins and corrupt-order detection |
| `tests/test_executive_lifecycle.py` | guard, reminder, monitor, escalation, tracking and outcome labels |
| `tests/test_executive_sweep.py` | the orchestrator executed through all endings and nudge paths |
| `tests/test_executive_store_schema.py` | every SQL column exists and every bind is supplied |
| `tests/test_executive_bridge.py` | resolved recipients, exactly-once handoff and stale suppression |
| `tests/test_executive_routes.py` | org scoping, credentials, coordination and live-state mutations |

Two of them are **ratchets** — they fail if the code drifts, not just if it breaks:

- `test_executive_store_schema.py` parses every migration for real columns and walks the **AST**
  of the store, sweep, routes and bridge to extract every SQL statement. Both of its central
  claims were verified by deliberately breaking the code and watching them fail.
- `tests/executive_fakes.py` is an in-memory database double that **raises** on any statement it
  does not model. A silent empty result would let a test pass while skipping the very write it
  was written to check.

`sweep.py` and `execution_store.py` were, until this work, proven only by static analysis — 874
lines of orchestration and persistence with no line ever run. Static analysis cannot tell you
that a `COMPLETE` verdict closes the row *and* writes the outcome *and* logs the event. It can
now.

**A note on the numbers, and on a wrong diagnosis.** Earlier drafts of this file reported 799 and
then 850 passing, and one full-suite run failed 70 tests. I first blamed a stale bytecode cache.
**That was wrong.** The real cause: a second session was writing to this repository at the same
time — twelve Layer 4 reasoner units and their tests landed in `genios_engine/reason/reasoners/`
and `tests/` between 23:03 and 23:23, interleaved with this work. A half-written module imported
mid-write is what failed those 70 tests, and the growing file count is what moved the totals.

Both workstreams are green together and no file was touched by both. But flagging it plainly:
**concurrent sessions on one working tree is a real hazard**. The final reconciled snapshot is
1795 repository tests, and Layer 5's focused collection is 195 independently runnable tests:

```
.venv/bin/pytest --collect-only -q tests/test_executive*.py
```

---

## Part 5 — Deployment runbook

**Layer 5 self-starts.** It is wired into the scheduler heartbeat that already runs card expiry,
retention and delivery (`api/routes.py :: run_maintenance_sweep`). There is no new cron, no new
worker, no new service. Deploy the branch, run the migration, and it begins.

What follows is what to do, in order, and how to know each step worked.

---

### Step 1 — Apply the migration

```bash
.venv/bin/python -m genios_engine.platform.migrate
```

Applies `0041_l5_execution.sql`: five tables (`executions`, `execution_actions`,
`execution_escalations`, `execution_events`, `execution_outcomes`), their indexes, the tenant
delete-cascades, and one nullable column on `org_seats`.

**Verify:**

```sql
select count(*) from schema_migrations where filename = '0041_l5_execution.sql';   -- 1
\d executions
```

**If it fails:** migrations are immutable and checksummed. If `0041` was already applied and then
edited, the runner refuses by design — ship `0042`, never edit in place.

---

### Step 2 — Deploy the branch

No new environment variables. Layer 5 uses what is already set:

| Setting | Why Layer 5 needs it | Already set? |
|---|---|---|
| `GENIOS_DATABASE_URL` | everything | yes |
| `GENIOS_SCHEDULER_ENABLED` (default `true`) | drives the sweep | yes |
| `GENIOS_SYNC_INTERVAL_HOURS` (default `6`) | how often commitments advance | yes — **see the note below** |

> **Consider lowering the interval.** At the default 6 hours, a commitment is examined four times
> a day. That is fine for planning but coarse for reminders: a "day 1" rung can fire up to six
> hours late. `GENIOS_SYNC_INTERVAL_HOURS=1` costs one extra cheap pass per hour and makes the
> ladder land when it says it will. The sweep is idempotent, so a shorter interval is safe.

**Multi-instance:** if you run more than one instance, the existing guidance still applies — set
`GENIOS_SCHEDULER_ENABLED=false` on all but one, or drive the sweep externally. Layer 5 is safe
either way (every write is guarded and the unique index absorbs duplicates); it is a cost
question, not a correctness one.

---

### Step 3 — Confirm it is running

The heartbeat now reports Layer 5. On the first tick after deploy, the log line is:

```
scheduled maintenance sweep: {... 'executive': {'orgs': N, 'commitments_created': X,
                                                'commitments_examined': Y} ...}
```

To force a pass for one tenant instead of waiting:

```bash
curl -XPOST -H "Authorization: Bearer $OWNER_TOKEN" https://<host>/v1/executive/sweep
```

**Expect:** `planned.created > 0` on the first run, `0` on the second. That zero *is* the
idempotence guarantee — it means re-running cannot duplicate a commitment.

Then look at what it committed to:

```bash
curl -H "Authorization: Bearer $OWNER_TOKEN" https://<host>/v1/executive/commitments
```

Each row should carry an owner, a deadline and a band.

---

### Step 4 — Read the refusal counters before assuming anything is wrong

`planned.reasons` is a histogram, not a log. Nothing created is usually correct, and the counter
says which:

| Reason | Means | Do |
|---|---|---|
| `outcome_no_action` | Layer 4 looked and concluded nothing should happen | nothing — this is health |
| `built` | a commitment was created | nothing |
| `no_steps` | a play declares no step text | fix the pack; GeniOS will not invent steps |
| `window_closed` | `window_days` leaves no time to act | widen the play's window |
| `decision_expired` | the decision lapsed before the sweep saw it | shorten the sweep interval |
| `unreadable_expiry` | a stored decision has no parseable expiry | escalate — this is a data defect |

---

### Step 5 — Two tenant-side settings that change behaviour

Both optional. Layer 5 works without them; it works *better* with them.

**5a. `org_seats.manager_seat_id`** — the reporting line.

```sql
update org_seats set manager_seat_id = '<manager_seat_id>'
 where org_id = '<org>' and seat_id = '<report_seat_id>';
```

Without it, "escalate to the manager" on day 7 falls back to the org's admins. That works, but it
is blunt: everyone's escalation lands on the same person.

**5b. A Slack channel** — so reminders actually leave the building.

Already supported by the existing endpoint; nothing new:

```bash
curl -XPUT -H "Authorization: Bearer $OWNER_TOKEN" \
  -d '{"webhook_url":"https://hooks.slack.com/services/..."}' \
  https://<host>/api/org/<org>/channels/slack

curl -XPOST -H "Authorization: Bearer $OWNER_TOKEN" \
  https://<host>/api/org/<org>/channels/slack/test      # sends a real message now
```

**Without a channel, nothing is lost.** Commitments are still planned, tracked, escalated and
reported; they simply wait on the card surface instead of being pushed. The communication plan
records `no_channel_registered` so the reason is visible, not mysterious.

---

### Step 6 — What to watch in week one

```sql
-- Is it committing to anything?
select state, count(*) from executions where closed_at is null group by state;

-- Are reminders leaving?
select status, count(*) from delivery_outbox
 where card_id like 'exec:%' group by status;

-- THE number: does acting on these plays actually work?
select label, count(*) from execution_outcomes
 where closed_at > now() - interval '7 days' group by label order by 2 desc;
```

The last query is the one that matters. `succeeded` means the world produced the evidence the play
declared. `completed_unproven` means people did the steps and nothing happened — **a play that
lands consistently in that bucket is busywork that feels productive**, and no click metric will
ever tell you.

Two counters worth an alert:

- `delivery_outbox` rows with `card_id like 'exec:%'` and `status='cancelled'` — each one is a
  reminder correctly suppressed because the world resolved it first. A **zero** here over a busy
  week is suspicious: it suggests the guard is not finding observations, not that the world never
  moves.
- `executions` where `routing_rule = 'rule3_unrouted'` — commitments nobody owns. They are tracked
  and visible by design, but a growing count means CRM ownership is missing for real accounts.

---

### Step 7 — Rollback

Layer 5 adds tables and reads existing ones; it changes no existing behaviour except that
`deliver/router.py` now delegates ownership to `executive/assignment.py` (same rules, same reason
codes, byte-identical results).

To stop Layer 5 without redeploying, disable the pack for the tenant — the sweep only visits orgs
with an active `tenant_packs` row. To stop it globally, `GENIOS_SCHEDULER_ENABLED=false`, which
also stops the existing passes. The tables can be left in place; they are inert if nothing writes
to them.

---

### The one thing that is genuinely unproven

**No SQL in this layer has ever run against Postgres.** CI has no database. Every unit and the
whole orchestrator execute against an in-memory double, and every statement is statically proven
to name real columns and bind real parameters — but neither proves the two meet. Step 1 and
Step 3 are what close that, and they are the reason this runbook starts there.

---

### Still open, deliberately

**Outcome learning is connected.** `feedback/store.py::load_batch` reads the indexed
`(org, capability, play, closed_at)` cohort. `completed_unproven` remains a visible neutral class,
while succeeded and failed cohorts feed deterministic effectiveness calculations.

**Still open:** concrete per-action multi-owner seat/agent allocation, digest batching for
digest-planned commitment reminders, Redis acceleration and live-PostgreSQL proof.

---

## Part 6 — What this layer will not do, on purpose

**1. No model decides anything.**
An LLM may improve the *wording* of a reminder. It may never decide whether to remind, who to
escalate to, what the steps are, or how urgent something is. Approval boundaries cannot be
probabilistic — if a model classified "Send the renewal notice" as an internal draft on Monday
and an outbound send on Tuesday, the same play would sometimes require approval and sometimes
not.

**2. No autonomy by default.**
Autonomy is granted **per action**, never per plan. A plan claims it only if every single action
is free of external effects and approval gates. No shipped pack qualifies today, and that is the
intended answer.

**3. No load balancing on ownership.**
No round-robin, no "assign to whoever is least busy". Those would make the same commitment land
on different people on different days, and an owner who cannot predict what reaches them stops
trusting the queue.

**4. No reopening a terminal commitment.**
Terminal states go only to `archived`. If the world changes again, that is a *new* decision
producing a *new* commitment. Reopening would silently rewrite the outcome Layer 7 already
learned from. `expired → running` was removed during Atlas reconciliation for exactly this reason;
renewed work must come from fresh authority and a new commitment.

**5. No silent drops.**
An unroutable commitment is still created, still tracked, still reported on. It lands in the
admin queue as `rule3_unrouted`. Dropping it is how a system quietly stops mentioning the
accounts nobody owns — which are exactly the accounts most likely to be lost.

---

## Part 7 — Where we disagreed with the architecture spec

| Spec says | We did | Why |
|---|---|---|
| Layer 5 owns Owner Planner + Channel Selector; Layer 5.2 splits Delivery out | Layer 5 **authors** the communication plan; Layer 6 **executes** it | The spec contradicts itself. Interruption is part of the commitment; adapters, retries and copy are transport |
| "Layer 5 returns exactly one thing: an Execution Object" | Kept exactly — but the object is **immutable**, and state lives in a row that points at it | An object that mutates cannot answer "why did this escalate on day 7?" after the pack is retuned |
| A Delivery Unit inside Layer 5 | Built as `deliver/executive_bridge.py` — Layer 5 authors the message and decides it should be sent; Layer 6 carries it, with retries | Layer 5 cannot import Layer 6 without breaking the topology ratchet. So Layer 5 writes its decision down and Layer 6 reads it: the dependency points downward and the send has one owner, not two |
| Reminder Unit decides based on "business relevance" | Implemented as *proportion of window burned* + the promised ladder + untouched detection | "Business relevance" needs a definition a machine can compute deterministically, or it becomes a model call |

---

## Summary

| Capability | Status |
|---|---|
| Execution Object — frozen, content-addressed, replayable | ✅ Round-trip proven |
| Decision Interpreter — refuses non-instructions by name | ✅ |
| Execution planning — kinds, waves, owners, deadlines | ✅ Deterministic, no model |
| Owner resolution owned by Layer 5 | ✅ Moved down, behaviour identical, ratchet green |
| Channel + interrupt owned by Layer 5 | ✅ Reason-coded |
| **Execution Validation (stale suppression)** | ✅ Runs before *every* outbound moment |
| Reminders on business relevance | ✅ Fatigue-capped |
| Escalation ladder, urgency-scaled, expiry-capped | ✅ Frozen at plan time |
| Monitoring — progress, stalls, done-but-unproven | ✅ |
| State machine + full audit trail | ✅ One transition table shared by code and tests |
| Outcome records for Atlas Layer 6 | ✅ Written, indexed and consumed |
| Tenant-tunable via pack data (LVL2/LVL3 merge, pins, guardrails) | ✅ `sales` pack v1.8.0 |
| Orchestrator (`sweep.py`) executed end to end | ✅ 33 scenarios against an in-memory double |
| Persistence (`execution_store.py`) executed | ✅ Idempotence, guarded races, supersede |
| **A reminder actually reaches a human** | ✅ `deliver/executive_bridge.py` — 16 scenarios |
| Card ↔ commitment link | ✅ Self-healing sweep, write-once |
| Commitment API (`/v1/executive/commitments*`) | ✅ 15 scenarios incl. org scoping + credentials |
| Runs automatically — no new cron, worker or service | ✅ In the scheduler heartbeat, before distribution |
| **Ever executed against Postgres** | ❌ **Not once. Step 1 + Step 3 of the runbook close this.** |

**Layer 5's Atlas core is connected and scheduled.** Every unit, Coordination, the orchestrator,
persistence, Layer 5.2 handoff, learning outcome seam and API surface are covered locally. The
remaining work is explicit rather than hidden: concrete per-action multi-owner allocation, digest
batching, Redis acceleration and real-database deployment proof.

---

## Appendix — the 60-second version for a CTO

**What Layer 5 does now that it didn't before:**
A recommendation becomes a commitment with a name, a date and a ladder. If nobody acts, it
reminds. If reminding doesn't work, it escalates. If the world resolves it, it notices and
closes itself. If the deal dies, it cancels quietly instead of nagging.

**What it will not do, on purpose:**
Let a model decide anything, act autonomously, or reopen a closed outcome.

**The one number to watch after go-live:**
The ratio of `succeeded` to `completed_unproven` in `execution_outcomes`. It is the only
measure of whether a play *works* rather than whether people are willing to do it. If
`completed_unproven` dominates, the play is busywork that feels productive.

**The biggest risk:**
Not that it crashes. That it reminds somebody about something they already did. That is why the
Execution Validation Unit exists, why it runs before every single outbound moment rather than
once at creation, and why an observed event only counts if it happened *after* the commitment
was made. Trust is lost far faster than it is earned, and one wrong nudge poisons every correct
one that follows.

**The first hour after go-live:**
Run the migration, hit `POST /v1/executive/sweep` once for a real tenant, then
`GET /v1/executive/commitments`. If commitments appear with owners and deadlines, the layer is
alive. Run the sweep a second time: `planned.created` should be `0`. That is idempotence, and it
is the property that makes it safe to put on a timer.

**What is genuinely left:**
Run migration `0041` and the cross-layer migrations through `0045` against live PostgreSQL, then
exercise a real tenant. Product refinements remain for concrete per-action multi-owner assignment,
digest batching and Redis acceleration; none of them changes the current deterministic authority
or safety boundary.
