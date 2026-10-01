# Layer 4 — the remaining steps, step by step

**2026-09-25 · seven steps. Three need nothing from anybody. Four are blocked on a decision or on data.**

> ⛔ **Every step below starts with a premise check.** Layer 3 taught that eight of twenty-six steps
> evaporated when their premise was measured — and **L4-04 below already shrank by an order of
> magnitude** when its premise was checked. If a premise turns out false, the step is closed by
> measurement, not built.

**Work order:** Wave A can start today. Wave B needs data. Wave C needs two answers from Rohit.

---

# WAVE A · Buildable today — no decision, no data

## L4-01 · `explain.py` has 0% coverage

**Premise — CHECKED ✅ 2026-09-25.** Traced across all 14 `test_executive*.py` files: **0 of 47
lines execute.** `why_not` appears twice in the entire test tree, both in unrelated files.

**What the module is:** answers *"Why did GeniOS not tell me about X?"* from
`signal_suppression_log` (table exists since migration **0005**), which the reasoner has written a
reason-coded row to since day one.

> *"Silence without receipts is indistinguishable from a bug; this module turns the receipts into
> an answer."*

### ⛔ Good news found while measuring: the dangerous path is already safe

```python
"reason": _REASON_HUMAN.get(r.reason_code, r.reason_code)
```

An unknown reason code **falls back to the raw code** — it does not raise. So there is no KeyError
waiting on a founder's screen. **This step is tests only; no production change is expected.**

### The exact tests to write

| # | case | why |
|---|---|---|
| 1 | each of the **six** codes maps to its sentence | `below_gate · budget · cooldown · muted · shadow · situation` |
| 2 | ⛔ an **unknown** code returns the raw code, not a crash | the reasoner may start writing a seventh |
| 3 | `days` clamps to **1..90** | `max(1, min(int(days), 90))` |
| 4 | `limit` clamps to **1..200** | `max(1, min(int(limit), 200))` |
| 5 | `entity_id` filter narrows to one subject | |
| 6 | `rule_id` filter narrows to one rule | |
| 7 | both filters together | they compose into one `where` |
| 8 | empty result returns `{"suppressions": []}` | not None, not an error |
| 9 | `detail` that is not a dict becomes `{}` | `r.detail if isinstance(r.detail, dict) else {}` |
| 10 | entity names resolve from `graph_nodes`, and a missing node gives `entity: None` | |
| 11 | ordering is **newest first** | `order by eval_time desc` |

**Size:** one test file, ~11 tests. **No migration. No production change.**

---

## L4-02 · `assignment.py` — 49% covered, and it is the largest module

**496 lines, 244 executed.** Imported by `deliver/router.py`, `deliver/orchestrator.py` and
`deliver/audience.py` — **so its blind half is reachable from delivery, not only from here.**

### ⛔ Premise to check FIRST — and it is not "write more tests"

**Is the uncovered half dead code or untested code?** Different problems, different fixes. L4-00
already found `resolve_approver_seat` (8 tests, **0 callers**) living inside this module, so at
least part of the uncovered half is **unreached**, not untested.

**How to check:** trace per function, not per module —

```python
# same tracer as 00-STATUS.md's coverage table, but record which FUNCTION each line belongs to
```

Then split the result three ways:

| bucket | action |
|---|---|
| **reached, untested** | write the test |
| **unreached, and should be** | that is a wiring bug — a separate step |
| **unreached, correctly** | ⛔ declare it in `executive/unreached.UNREACHED` with a reason and a mover |

### ⛔ One thing already known, and it is load-bearing

`resolve_owner`'s Rule 3 comment, measured against production:

> *"Every input above is **structurally absent in production**: `deal.owner`/`relationship.owner`
> have **no `write_fact` producer anywhere**, `commitment.actor` is never written as a fact, and
> `graph_nodes.attributes` is **never populated at all**."*

**So Rules 1 and 2 never fire in production; everything lands on Rule 3 — the org admin.** Any
coverage work here must not "fix" that by inventing a producer; the correct fix is upstream, and
for a single-founder tenant Rule 3 is the right answer anyway.

**Size:** medium, and it should be **split by what the premise check finds** rather than planned as
one unit now.

---

## L4-03 · `planning.py` — 58% covered

**275 lines, 162 executed** under `test_executive_execution.py` alone.

### ⛔ This step exists because of a correction, and the correction IS the lesson

Grepping the test tree for `plan_actions` returned **zero**, which read as *"Unit 2, 354 lines, no
tests"*. Tracing execution showed **58%**.

> *"No test names it"* and *"no test runs it"* are different claims, and only one of them was
> measured. **Eleventh appearance of the blunt-grep family on this branch.**

### What to do

Find which branches never run, then decide **per branch** whether it is a missing test or an
unreachable case. The three functions worth tracing individually:

| function | what it decides |
|---|---|
| `classify_step` | a step's `ActionKind` from its text — the token matching is the branchy part |
| `_stages` | how the kinds group into ordered stages |
| `_stage_deadlines` | how the window is divided across those stages |

**Size:** small-to-medium. No production change expected unless a branch turns out unreachable.

---

# WAVE B · The two real product gaps

## L4-04 · ⛔ Escalation names the step it is stuck on

### The gap, in the code's own words (`monitor.blocking_action`)

> *"What a stalled-commitment escalation should actually name. **'Your Acme follow-up is stuck on
> getting it approved'** is a message somebody can act on; **'your Acme follow-up is stalled'** is a
> message somebody can only feel bad about."*

### ⛔ PREMISE CORRECTED 2026-09-25 — this step is far smaller than first planned

**What this file said before:** *"blocked — the escalation rung must carry the blocking step, and a
rung is `(day, action, audience, interrupt)`, so adding a field touches `build_ladder`/`due_rungs`/
`next_rung` and the stored ladder on every open commitment."*

**Measured, that is wrong. No rung field is needed and no migration is needed.** Two facts:

1. **`execution_escalations.target_seat` is already resolved at FIRE time, not plan time** — the
   column's own comment says so. So per-fire values do not belong in the stored rung.
2. **`record_reminder` already carries a `facts` payload** — `reminder.reminder_facts`, described as
   *"the grounded fact corpus a reminder may be worded from… Layer 6's invention validator will
   refuse any rendered sentence containing a number, name or date that is not in this dict, so this
   function is quite literally **the vocabulary of what a reminder is allowed to say**."*

### ⛔ And the defect is visible inside that dict

```python
"next_action": execution.first_action.label,      # ← the FIRST action
```

**On a partly-completed commitment the first action is the wrong step.** `blocking_action(execution,
report)` computes the right one — *"the single step everything else is waiting on"* — and nothing
calls it.

### The work, in order

| # | what | note |
|---|---|---|
| 1 | **Tests for `blocking_action` first** | ⛔ it has **none** — unreached *and* unexercised |
| 2 | Add its label to `reminder_facts`, e.g. `blocked_on` | **one key**. Without it the invention validator would refuse the sentence |
| 3 | Decide whether `next_action` stays or becomes the blocking one | ⛔ **keep both.** `next_action` is right on a fresh commitment; `blocked_on` is right on a stalled one |
| 4 | `deliver/executive_bridge.format_reminder` renders it | it already reads the payload |
| 5 | Remove the entry from `executive/unreached.UNREACHED` | the guard will fail until you do — that is the reminder |

**Size: small.** No migration, no rung change, no policy change. ⛔ **It does not touch ladder
TIMING**, which is the part that is policy — so it needs no decision from Rohit.

---

## L4-05 · An approval routes to an approver

### The gap

`requires_approval` **is** read — `contracts/execution.py:233` gates autonomy on it — but
`resolve_approver_seat` has **no caller**, so a commitment can announce sign-off is needed and can
never name who signs.

> *"a card that says 'this needs sign-off' and cannot say whose is less useful than one that can,
> and far better than one that quietly drops the requirement."*

### ⛔ Blocked on org data, not on code — and the function is right to be strict

`AuthorityView.resolve` has **three** outcomes, and only one may name anybody:

| outcome | meaning | may route? |
|---|---|---|
| `enforced` | an org rule names the approver | ✅ **only this one** |
| `suggested` | only OBSERVED BEHAVIOUR matched | ❌ a human must confirm first |
| `no_authority_rule` | the org holds no rule | ❌ ⛔ **this is NOT "anyone may approve"** |

**So until the org publishes authority rules, `None` is the honest answer** and the card is correct
to say only that sign-off is needed. **Eight tests already cover that distinction.**

### The work once rules exist

1. call it at build time, beside `resolve_owner`
2. carry the seat on the execution object
3. render it — *"this needs sign-off from X"*
4. remove the entry from `UNREACHED`

**Size: small. Blocked on:** the org publishing authority rules (Harsh's **H5**).

---

# WAVE C · ⛔ Blocked on Rohit — two product decisions

## L4-06 · Preventive warning → card

`modes.py` calls preventive mode **the vision's USP** and quotes the product's own sentence for it.
**Measured: `deliver/` contains zero references to preventive**, so no preventive finding has ever
become a card. It exists at `GET /preventive` and must be asked for.

| | option | consequence |
|---|---|---|
| **A** | leave it pull-only | the USP is never delivered |
| **B** | one card per finding | ⛔ **spends the daily card budget on clock readings.** Every elapsed-time condition on every node produces one |
| **C** | inside the warning window **and** above an importance threshold | correct shape — **the threshold is the decision** |

### ⛔ Pre-work that needs NO decision, and should happen first

**Count how many findings the current warning window actually produces on the pilot.** One
read-only call:

```python
from genios_engine.executive.modes import load_preventive
load_preventive(graph, org_id, registry=registry, limit=500)
```

**That number turns the threshold from a guess into a choice.** If it returns 4, option B is fine
and there is no decision to make. If it returns 400, only C is possible.

**The question that sets the threshold:** how many preventive warnings should a founder see in a
day — 1, 3, 10?

---

## L4-07 · Brief → pushed or pull-only

`brief.py` calls the Decision Brief *"brief.v1, **the executive unit of output**"* — the layer's own
name for what it produces. Nothing in `sweep.py` composes one.

⛔ **Not obviously a defect.** A brief nobody asked for is a notification, and the current behaviour
may be correct. What is wrong is only that **nobody has decided**, so the layer's stated output has
no producer by default rather than by choice.

**The decision:** one brief each morning (push), or fetched on demand (pull)?

---

# L4-08 · Units 6 and 8 — a declared UNKNOWN, not a step

Module docstrings number the units 1, 2, 2.5, 3, 4, 5, 7, 9, 10. `assignment`, `escalation` and
`execution_guard` carry no number. **6 and 8 are absent — but three unnumbered files and two gaps do
not divide.**

⛔ **No conclusion drawn, deliberately.** The L5 spec is not in this repository, and **L3-17 is the
standing lesson**: `prior_decision 0` was a grep, and the capability it declared missing had been
running on every sweep for months. **An absent number is not an absent unit.**

**MOVES WHEN** somebody supplies the L5 spec.

---

# The order, and why

```
H1   read SweepReport.reasons after Admin goes live        ← everything else is guesswork first
 │
 ├── L4-01  explain.py tests              small · today
 ├── L4-03  planning.py branches          small · today
 ├── L4-02  assignment.py premise check   medium · today, then split
 ├── L4-04  blocking step in reminders    ⛔ SMALL — one key + tests · today
 │
 ├── L4-06 pre-work: COUNT the preventive findings on the pilot   ← makes C1 informed
 │
 ├── L4-05  approver routing              blocked on H5 (org authority rules)
 └── L4-06 / L4-07                        blocked on Rohit's two answers
```

⛔ **Four steps can start today, not three** — L4-04 moved into that group when its premise was
checked. **None of the rest is waiting on more engine.**
