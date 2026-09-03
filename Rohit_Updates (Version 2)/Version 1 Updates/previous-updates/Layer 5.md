# Layer 5 — The Executive Engine

**Last updated:** 6 August 2026
**Branch:** `harsh/mvp`
**Tests:** 799 passing (Layer 5 added 88 of them)
**Status:** feature-complete and green in tests — **NOT yet running against a real database**

**The one-line summary for a CTO:** GeniOS could produce an excellent recommendation and had
no idea whether anyone ever did it. Layer 5 turns a recommendation into a **commitment** —
with an owner, a deadline, a channel, an escalation ladder and a clock — and then watches it
until it is done, dead, or out of time.

Layer 4 answers **"what should happen?"**
Layer 5 answers **"how do we make it happen?"**

Those are different jobs. A conclusion is an opinion. A commitment is an opinion with a name
and a date attached.

**Start at Part 5 if you want the action list.**

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

Eleven units, one output. The layer emits exactly one artifact: the **Execution Object**.

| Unit | Where | What it does |
|---|---|---|
| **Contract** | `contracts/execution.py` | The Execution Object: frozen, content-addressed, integer-only, with the state machine as data |
| **1 · Decision Interpreter** | `executive/interpret.py` | Reads a Layer 4 decision as an *instruction*, or names precisely why it is not one |
| **2 · Execution Planning** | `executive/planning.py` | Steps → actions with kinds, dependency waves, owners, resources, per-step deadlines |
| **3 · Communication Planning** | `executive/communication.py` | Audience, channel, interrupt, tone — and a reason code for each |
| **· Owner Resolution** | `executive/assignment.py` | *Who.* Moved down from `deliver/`. Pure core, injected directory |
| **4 · Execution Object Builder** | `executive/execution.py` | Composes the units into one commitment, or refuses with a named code |
| **· Execution Validation** ⭐ | `executive/execution_guard.py` | **Your improvement.** Re-validates against live state before *every* outbound moment |
| **5 · Reminder** | `executive/reminder.py` | Business relevance, not a calendar |
| **· Escalation** | `executive/escalation.py` | The ladder, scaled by urgency, capped by the decision's expiry |
| **7 · Monitoring** | `executive/monitor.py` | Progress, stalls, and the gap between "ticked" and "proven" |
| **9 · Execution Tracking** | `executive/lifecycle.py` | The state machine and its audit vocabulary |
| **10 · Feedback Collection** | `executive/collect.py` | The outcome record Layer 7 will learn from |
| **· Persistence** | `executive/execution_store.py` | The only module that touches SQL |
| **· The loop** | `executive/sweep.py` | Two passes: plan commitments, then run the lifecycle |
| **· Schema** | `migrations/0041_l5_execution.sql` | 5 tables + the reporting line on `org_seats` |
| **· Surface** | `api/executive_routes.py` | `/v1/executive/commitments*`, `/sweep` |

### The four decisions that matter most

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
state immediately before it happens. The guard has six verdicts, not a boolean, because "do not
send" covers four genuinely different situations:

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

### What Layer 7 gets that it never had

Layer 7 currently learns from card clicks — whether a recommendation *looked* right on arrival.
`execution_outcomes` measures whether acting on it *worked*, and labels the ending by who or
what ended it:

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

**Two new ratchets** were added so these classes of bug cannot come back:

- `tests/test_executive_store_schema.py` parses every migration for real columns and walks the
  **AST** of the store, sweep and routes to extract every SQL statement — then proves every
  inserted, updated and selected column exists, that the insert binds one value per column, and
  that **every `:bind` parameter is supplied.** Both were verified by deliberately breaking the
  code and watching them fail.
- The layer topology test still passes with the ownership move.

---

## Part 5 — The action list

**1. Run migration 0041 against a real Postgres. Nothing here has ever executed.**
Same caveat as Layer 2, same reason: CI has no database. Every unit is pure and tested; the
SQL is statically proven to reference real columns and bind real parameters, but static proof is
not execution.

**2. Put the sweep on a schedule.**
`executive.sweep.run_executive(engine, org_id)` runs both passes. Both are idempotent and both
use guarded writes, so two workers are safe. Suggested cadence: every 15 minutes. There is a
`POST /v1/executive/sweep` for a manual run.

**3. Populate `org_seats.manager_seat_id`.**
Nullable and optional — without it, "escalate to the manager" falls back to the org's admins,
which works but is blunt. With it, day 7 reaches the right person.

**4. Wire the card ↔ commitment link.**
`executions.card_id` exists and is unused. Layer 6's `deliver/pipeline.py` should stamp it when
it builds a card for a commitment, so the UI can show "this card is day 4 of a 14-day
commitment, escalates to your manager in 3 days."

**5. Decide the reminder transport.**
Today a reminder is recorded (`execution_events`, `reminder_count`, `last_reminded_at`) and the
escalation rung fires — but the *message* still needs Layer 6's outbox to carry it. The
communication plan tells it exactly where to send and whether to interrupt; the enqueue call is
one function away.

**6. Have Layer 7 read `execution_outcomes`.**
The table is written and indexed for the cohort read (`org, capability, play, closed_at`).
`feedback/calibrate.py` currently learns from clicks alone. This is the richer signal, and it is
sitting there.

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

**4. No reopening a completed commitment.**
Terminal states go only to `archived`. If the world changes again, that is a *new* decision
producing a *new* commitment. Reopening would silently rewrite the outcome Layer 7 already
learned from. The one exception is `expired → running`: a human who picks lapsed work back up
has demonstrably not finished with it, and refusing them would just make them create a duplicate
by hand.

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
| A Delivery Unit inside Layer 5 | Layer 5 marks the commitment delivered; Layer 6's outbox carries the message | Two layers owning the send means two places to look when a message doesn't arrive |
| Reminder Unit decides based on "business relevance" | Implemented as *proportion of window burned* + the promised ladder + untouched detection | "Business relevance" needs a definition a machine can compute deterministically, or it becomes a model call |

---

## Summary

| Capability | Status |
|---|---|
| Execution Object — frozen, content-addressed, replayable | ✅ Built, round-trip proven |
| Decision Interpreter — refuses non-instructions by name | ✅ Built |
| Execution planning — kinds, waves, owners, deadlines | ✅ Built, deterministic, no model |
| Owner resolution owned by Layer 5 | ✅ Moved down, behaviour identical, ratchet green |
| Channel + interrupt owned by Layer 5 | ✅ Built, reason-coded |
| **Execution Validation (stale suppression)** | ✅ Built — runs before *every* outbound moment |
| Reminders on business relevance | ✅ Built, fatigue-capped |
| Escalation ladder, urgency-scaled, expiry-capped | ✅ Built, frozen at plan time |
| Monitoring — progress, stalls, done-but-unproven | ✅ Built |
| State machine + full audit trail | ✅ Built, one transition table shared by code and tests |
| Outcome records for Layer 7 | ✅ Written and indexed — ⚠️ not yet read |
| Tenant-tunable via pack data (LVL2/LVL3 merge, pins, guardrails) | ✅ `sales` pack v1.8.0 |
| **Ever executed against Postgres** | ❌ **Not once. Do this first.** |
| Reminder message actually delivered | ⚠️ Recorded and escalated; the send needs one outbox call |
| Card ↔ commitment link | ⚠️ Column exists, unused |

**Layer 5 is feature-complete.** Nothing is half-built. What remains is proving it against a
real database and connecting two wires to Layer 6.

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

**Where to spend a junior engineer's first week:**
Part 5, items 1 and 2 — migration against a real database, then the sweep on a scheduler. That
converts the entire layer from "written and proven" to "running", and everything else on the
list is a wire, not a build.
