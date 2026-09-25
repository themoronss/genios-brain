# Layer 4 — the remaining steps, planned

**2026-09-25 · seven steps. Three need nothing from anybody. Four are blocked on a decision.**

Every step below states its premise. ⛔ **Layer 3 taught that eight of twenty-six steps evaporated
when their premise was measured — so each of these gets a premise check BEFORE any code**, and if
the premise is false the step is closed by measurement, not built.

---

# WAVE A · No decision needed — buildable today

## L4-01 · ⛔ `explain.py` has 0% coverage

**Premise to check first:** is it really untested, or reached through the route tests?
**Measured 2026-09-25:** traced across all 14 `test_executive*.py` files — **0 of 47 lines execute.**
`why_not` appears twice in the whole test tree, both in unrelated files.

**What it does:** answers *"Why did GeniOS not tell me about X?"* from `signal_suppression_log`
(table exists since migration 0005), which the reasoner has written a reason-coded row to since day
one. ⛔ **Six** reasons, not five — `below_gate · budget · cooldown · muted · shadow · situation`. (I wrote five and checked: the sixth is `situation`, which means the signal was suppressed because of its situation rather than its score. **A test per reason has to cover six.**)

> *"Silence without receipts is indistinguishable from a bug; this module turns the receipts into
> an answer."*

**The work:** a test per reason code, plus the empty case (no suppression rows) and the unknown-code
case. ⛔ **The unknown-code path matters most** — a reason the reasoner starts writing that
`_REASON_HUMAN` has no sentence for must degrade to something readable, not to a KeyError on a
founder's screen.

**Size:** small. One test file. No production change expected unless the unknown-code path is bare.

## L4-02 · `assignment.py` coverage — 49%, and it is the largest module

**496 lines, 244 executed.** It resolves *who holds this commitment* and it is imported by
`deliver/router.py`, `deliver/orchestrator.py`, `deliver/audience.py` — so its blind half is
reachable from delivery, not just from here.

**Premise to check first:** ⛔ **is the uncovered half dead code or untested code?** Those are
different problems with different fixes, and L4-00 already found that `resolve_approver_seat` (8
tests, 0 callers) sits inside this module. Run the trace per function before writing anything.

**Size:** medium, and it should be split by what the premise check finds.

## L4-03 · `planning.py` coverage — 58%

**275 lines, 162 executed** under `test_executive_execution.py` alone.

⛔ **This step exists because of a correction, and the correction is the lesson.** Grepping the test
tree for `plan_actions` returned **zero**, which read as "Unit 2 is untested". Tracing showed 58%.
*"No test names it" and "no test runs it" are different claims, and only one of them was measured.*
**Eleventh appearance of that family on this branch.**

**The work:** find which branches of `classify_step`, `_stages` and `_stage_deadlines` never run,
and decide per branch whether it is a missing test or an unreachable case.

---

# WAVE B · ⛔ The two real product gaps

## L4-04 · Escalation names the step it is stuck on

**The gap, in the code's own words** (`monitor.blocking_action`):

> *"What a stalled-commitment escalation should actually name. **'Your Acme follow-up is stuck on
> getting it approved'** is a message somebody can act on; **'your Acme follow-up is stalled'** is a
> message somebody can only feel bad about."*

**Measured:** `escalation.py` and all of `deliver/` contain **no reference to a blocking step**, so
every stalled escalation today is the second sentence. The function that computes the first has
**no caller and no tests** — the weaker of the two unreached states.

**Why it is blocked:** the escalation rung must **carry** the blocking step to render it, and today
a rung is `(day, action, audience, interrupt)`. Adding a field to a rung touches
`build_ladder`/`due_rungs`/`next_rung` and the stored ladder on every open commitment.

⛔ **It does NOT touch ladder TIMING**, which is the part that is policy. That separation is what
makes this safe to do without Rohit re-deciding H6.

**Order:** tests for `blocking_action` first (it has none), then the rung field, then the copy.

## L4-05 · An approval routes to an approver

**The gap:** `requires_approval` **is** read — `contracts/execution.py:233` gates autonomy on it —
but `resolve_approver_seat` has no caller, so **a commitment can announce that sign-off is needed
and can never name who signs.** Its own docstring predicted the symptom:

> *"a card that says 'this needs sign-off' and cannot say whose is less useful than one that can,
> and far better than one that quietly drops the requirement."*

**Why it is blocked:** ⛔ **on org data, not on code.** The function is deliberately strict —
`AuthorityView.resolve` has three outcomes and **only `enforced` may name anybody**:

| outcome | meaning |
|---|---|
| `enforced` | an org rule names the approver — **the only case that may route** |
| `suggested` | only OBSERVED BEHAVIOUR matched — a human must confirm first |
| `no_authority_rule` | the org holds no rule — ⛔ **this is NOT "anyone may approve"** |

**So until the org publishes authority rules, the honest answer is `None`** and the card is correct
to say only that sign-off is needed. **Eight tests already cover that distinction.**

**The work once rules exist:** call it at build time, carry the seat on the execution, render it.

---

# WAVE C · ⛔ Blocked on Rohit — two product decisions

## L4-06 · Preventive warning → card

`modes.py` calls preventive mode **the vision's USP** and quotes the product's own sentence for it.
**Measured: `deliver/` contains zero references to preventive, so no preventive finding has ever
become a card.** It exists at `GET /preventive` and must be asked for.

| | option | consequence |
|---|---|---|
| **A** | leave it pull-only | the USP is never delivered |
| **B** | one card per finding | ⛔ **spends the daily card budget on clock readings.** Every elapsed-time condition on every node produces one |
| **C** | inside the warning window **and** above an importance threshold | correct shape — **the threshold is the decision** |

⛔ **The question that sets it: how many preventive warnings should a founder see in a day?**
A number — 1, 3, 10 — turns C into a buildable step. Without it, B is the only thing that can be
built and B is wrong.

**Pre-work that needs no decision:** measure how many findings the current warning window produces
on the pilot. That number makes the threshold an informed choice rather than a guess, and it is one
read-only call to `load_preventive`.

## L4-07 · Brief → pushed or pull-only

`brief.py` calls the Decision Brief *"brief.v1, **the executive unit of output**"* — the layer's own
name for what it produces. Nothing in `sweep.py` composes one.

**The decision:** one brief each morning (push), or fetched on demand (pull)?

⛔ **Not obviously a defect.** A brief nobody asked for is a notification; the current behaviour may
be correct. What is wrong is only that **nobody has decided**, so the layer's stated output has no
producer by default rather than by choice.

---

# Order, and why

```
H1  read SweepReport.reasons after Admin goes live      ← everything else is guesswork first
 │
 ├─ L4-01  explain.py coverage          no decision, do now
 ├─ L4-02  assignment.py premise check  no decision, do now
 ├─ L4-03  planning.py branches         no decision, do now
 │
 ├─ L4-06 pre-work: count preventive findings on the pilot   ← makes C1 informed
 │
 ├─ L4-04  blocking step in escalation  needs a rung field, NOT a policy change
 ├─ L4-05  approver routing             needs org authority rules (H3/H5)
 │
 └─ L4-06 / L4-07  need Rohit's two answers
```

⛔ **Wave A is three steps that can start immediately.** Everything in B and C is waiting on data or
a decision — **and none of it is waiting on more engine.**
