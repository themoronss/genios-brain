# PENDING · Layer 4 (Executive) — analysed, basics fixed, the rest waiting on decisions

**Branch `speedrun008` · 2026-09-25 · `13,313 passed · 0 regressions`**

> ## ⛔ THE HEADLINE, BECAUSE IT IS THE OPPOSITE OF LAYER 3
>
> **Layer 4's execution half is fully wired and runs on every heartbeat tick.** This is not a layer
> waiting to be switched on. `api/routes.py:1150` calls `sweep.run_executive` for every org, before
> distribution, and it plans commitments then validates, transitions, reminds, escalates and closes
> them. Five tables, delegation wiring, fourteen test files, `record_outcome` feeding Layer 7.
>
> **What is NOT delivered is the other half** — briefs, summaries, memory, preventive warnings and
> why-not receipts exist only as `GET` endpoints. Nothing pushes them. ⛔ **Including the product's
> own stated USP.**

---

# PART 1 · WHAT LAYER 4 IS

`genios_engine/executive/` — 25 files, 5,731 lines. Its own statement:

> *"Layer 4 answers **what should happen**. This layer answers **how we make it happen** — and
> those are different jobs. A conclusion is an opinion; **a commitment is an opinion with an owner,
> a deadline, a channel, a ladder and a clock attached.** Until this layer existed, GeniOS produced
> excellent recommendations and then stopped: it had no idea whether anything was ever done."*

⛔ **Numbering trap, same family as Layer 3's.** In the PRODUCT vocabulary this is **Layer 4**. In
the code's own `LAYERS.py` the package is **5**. `executive`/`deliver`/`feedback` are 5/6/7 in code
and 4/5/6 in product. The whole tail is off by one.

## Three laws that hold across every module here

1. **No model decides anything.** An LLM may improve the wording of a reminder. It may never decide
   whether to remind, who to escalate to, what the steps are, or how urgent something is.
2. **Nothing fires without re-validation.** Every outbound moment — first delivery, each reminder,
   each escalation rung — is re-checked against live state immediately before it happens.
   *"A nudge about something that already happened costs more trust than ten missed ones."*
3. **The plan is immutable; only the row moves.** Execution objects are frozen and
   content-addressed over `(org, decision, plan)`.

---

# PART 2 · HOW IT RUNS

```
api/routes.py:1150   run_executive(engine, org, eval_time=now)      every org, every tick
                     ├─ plan_commitments()   authoritative decisions → executions
                     └─ run_lifecycle()      validate → transition → remind → escalate → close
                                             → record_outcome()  →  Layer 7
```

Its comment: *"Runs **BEFORE distribution** on purpose: a reminder decided in this tick should
leave in the same tick rather than waiting a whole interval."*

## ⛔ The input gate — why Layer 4 may be doing nothing today

`plan_commitments` reads `AUTHORITATIVE_SIGNAL_PREDICATE`, which requires **all** of:

```
an audited reasoning run  ·  active pack authority  ·  matching authority revision
matching config version   ·  run completed after the pack's last update
signal still open         ·  authority not expired
```

⛔ **If Layer 3 produces no authoritative decisions, Layer 4 has nothing to plan.** It runs, finds
nothing, and reports `examined=0`. **So activating Admin is a prerequisite for Layer 4 doing
anything at all.**

`SweepReport.reasons` counts refusals **by reason** rather than lumping them:

> *"A sweep that plans nothing because every decision was `no_action` is healthy; one that plans
> nothing because every build hit `window_closed` is a misconfigured pack, and a single 'skipped'
> counter cannot tell those apart."*

⛔ **That counter is the first number to read after Admin goes live.**

---

# PART 3 · WHAT WAS FIXED NOW (needed nothing from anybody)

## `genios_engine/executive/unreached.py` — the declaration this layer had none of

Every other layer can say which of its silences are deliberate — `reason/uncited_lanes`,
`reason/situation_binding`, `context/lane_health.DORMANT_LANES`,
`patterns/routing.UNROUTED_PATTERN_TYPES`. **`executive/` had nothing of the kind**, so a function
with no caller was indistinguishable from an oversight.

**+12 tests · 8/8 mutations caught · 0 regressions.**

### ⛔ Six public functions are called by nothing. Two are real product gaps.

| function | verdict |
|---|---|
| ⛔ **`monitor.blocking_action`** | **REAL GAP.** Its docstring: *"'Your Acme follow-up is **stuck on getting it approved**' is a message somebody can act on; 'your Acme follow-up is **stalled**' is a message somebody can only feel bad about."* Measured: escalation and `deliver/` contain no blocking-step reference, so **every stalled escalation today is the second sentence.** ⛔ And it has **no tests either** |
| ⛔ **`assignment.resolve_approver_seat`** | **REAL GAP.** The `requires_approval` flag IS read (`contracts/execution.py:233` gates autonomy on it) but **nothing resolves who must sign.** Its own docstring predicted the symptom: *"a card that says 'this needs sign-off' and cannot say whose is less useful than one that can."* 8 tests, 0 live callers |
| `coordination.can_complete` | **Correctly dead.** The live route calls `dependencies_met` instead and handles already-ticked differently — routing an idempotent re-submit through `can_complete` would turn a double-click into a 409 |
| `coordination.coordination_snapshot` | No reader. It is the shape a *"what can I do next"* view would read, and that view has not been asked for |
| `execution.build_from_decision` | **An alternative entry shape, not a bypassed gate.** It starts from a decision OBJECT; the sweep starts from a SQL ROW. Both run the identical tail |
| `lifecycle.is_terminal` | Trivial predicate over `TERMINAL_STATES`. Kept so the closed set does not acquire a second inline spelling. **No tests** |

### ⛔ Five surfaces are PULL-ONLY — built, routed, never pushed

| surface | route | why it matters |
|---|---|---|
| ⛔ **`modes.load_preventive`** | `GET /preventive` | **THE USP.** `modes.py` calls it *"the vision's USP"* and quotes the product's own sentence. Measured: `deliver/` has **zero** references to preventive, so **no preventive finding has ever become a card** |
| **`brief.load_briefs`** | `GET /briefs` | `brief.py` calls the Decision Brief *"the executive unit of output"*. Nothing composes one on a tick |
| `summary.build_summary` | `GET /summary` | closest to pushed — `deliver/outbox.py:315` imports it |
| `memory` | `GET /memory` | working context, never carried forward automatically |
| `explain.why_not` | `GET /why-not` | ⛔ **correctly pull** — a receipt for a silence is asked for, never volunteered |

### ⛔ Two defects the guard found in my own first measurement

1. **Aliased imports.** `deliver/actions.py` imports `link_card as _link_execution_card` and calls
   the alias — my first scan reported a function on the live card path as **dead**. The scanner now
   resolves every renamed import back to its original name. **That is the exact false verdict this
   guard exists to prevent, and it made it itself.**
2. **O(functions × files).** The first version re-parsed ~600 modules for each of ~80 candidates —
   about 48,000 AST parses, minutes per run. *A correctness guard too slow to run is one people
   start skipping.* Now one pass: **2 seconds.**

### A declared UNKNOWN, not a finding

Module docstrings number the units 1, 2, 2.5, 3, 4, 5, 7, 9, 10. `assignment`, `escalation` and
`execution_guard` carry no number. **6 and 8 are absent** — but three unnumbered files and two gaps
do not divide cleanly.

⛔ **No conclusion drawn, deliberately.** The L5 spec is not in this repo, and L3-17 is the standing
lesson: `prior_decision 0` was a grep, and the capability it declared missing had been running on
every sweep for months. **An absent number is not an absent unit.**

---

# PART 4 · WHAT IS STILL NEEDED — from Rohit

## A · ORG DATA — rows, not code

| | what | table | what breaks without it |
|---|---|---|---|
| **A1** | who the people are | `org_seats` (0008) | no owner resolves; a commitment has no holder |
| **A2** | ⛔ **the reporting line** | `seat_responsibilities.reports_to` (0131) — **not** `org_seats.manager_seat_id` | ⛔ the **day-7 "escalate to manager"** rung has nobody to climb to. The ladder stops at 3 rungs |
| **A3** | which channels are registered | `org_channels` (0032) | default is `in_app` only — nothing reaches Slack |
| **A4** | who answers for what scope | `seat_responsibilities` (0131) | empty reads as *"the tenant"* — **every card to everybody** |

⛔ **A2 has two mechanisms and the code says which is right:**

> *"`org_seats.manager_seat_id` is a **single mutable column**: covering the North for June means
> overwriting it on 1 June and remembering to overwrite it back on 1 July. **Nobody remembers**, so
> July's escalations still climb to the acting manager — and the June state was **DESTROYED** by the
> July write. A `reports_to` responsibility **carries its own window** and simply stops applying."*

## B · POLICY — shipped defaults, confirm or change

### B1 · The escalation ladder as shipped

| day | action | audience | interrupt |
|---|---|---|---|
| 1 | notify | owner | no |
| 3 | remind | owner | ⛔ yes |
| 7 | escalate | **manager** | no |
| 14 | critical | **executive** | ⛔ yes |

*"Days are **offsets from creation**, not from the deadline, because the useful intervention is
early — an escalation that starts when the window is already gone is a post-mortem."*
*"A ladder longer than 6 rungs is **somebody automating harassment** rather than escalation."*

⛔ **Open question:** in a company of two, what do "manager" and "executive" mean? The manager rung
may not exist, in which case the ladder should be three rungs, not four.

⛔ **Good property:** a misconfigured ladder **raises `EscalationConfigError`** rather than silently
falling back — *"an org believes it changed its escalation policy and it did not, and they would
only discover otherwise on the day the policy mattered."*

### B2 · Band multipliers · B3 · Reminder cadence · B4 · Urgency

```
critical 5,000 bp   high 7,500 bp   standard 10,000 bp        (ladder tempo by band)

min_interval_hours 20     "never twice inside a working day"
max_reminders       4     "two more than most people need, one fewer than it takes to get muted"
untouched_hours    24     deadline_warning_bp 7,500      recheck_hours 6

urgency: critical 85 · high 70
```

## C · PRODUCT DECISIONS — the two that block engineering

### ⛔ C1 · Should a preventive warning become a card?

| | option | consequence |
|---|---|---|
| **A** | leave it pull-only | the USP is never delivered |
| **B** | one card per finding | ⛔ **spends the daily card budget on clock readings** — every elapsed-time condition on every node produces one |
| **C** | cards only inside the warning window **and** above an importance threshold | correct shape; **the threshold is the decision** |

**The question that sets the threshold: how many preventive warnings should a founder see a day?**

### ⛔ C2 · Should a brief be pushed?

One brief each morning, or fetched on demand?

---

# PART 5 · THE ORDER

```
1. Activate Admin (Layer 3's P3)          — Layer 4 has nothing to plan until this
2. Read SweepReport.reasons               — says exactly where the gate stops things
3. Fill A1–A4 org data
4. Confirm B1–B4 policy
5. Answer C1 and C2
6. Then: wire preventive → cards, brief → sweep, blocking_action → escalation copy,
   resolve_approver_seat → approval routing
```

⛔ **Steps 6's four items are the whole remaining engineering, and every one of them is blocked on
a decision above it — not on code.**

---

# PART 6 · VERIFY IT YOURSELF

```bash
# the declared silences, both directions, 2 seconds
.venv/bin/python -m pytest tests/test_the_executive_says_what_it_does_not_call.py -q

# what the layer declares it does not call
.venv/bin/python -c "
from genios_engine.executive.unreached import UNREACHED, PULL_ONLY
for k,(w,m) in UNREACHED.items(): print('UNREACHED', k)
for k,(r,w) in PULL_ONLY.items(): print('PULL-ONLY', k, r)"
```
