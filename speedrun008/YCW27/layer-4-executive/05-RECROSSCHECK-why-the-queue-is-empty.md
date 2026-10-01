# 05 · L4 RE-CROSSCHECK — why the queue is empty, measured to the exact line

> **Date** 2026-10-01 · **Layer** YCW27 L4 Executive (`executive/`, 27 files, 6,167 lines)
> **Every number below was measured read-only against production on 2026-10-01.**
> **Status** CROSSCHECK COMPLETE · ⛔ **the answer is not a build**

---

# PART 0 · THE HEADLINE, BEFORE ANY DETAIL

**L4 does not need building. It is built, correct, and correctly idle.**

It even does something no other layer does: `executive/unreached.py` declares every function this
layer built and does not call, each with a reason **and** a mover. Layer 2 needed nine findings to
learn that discipline; L4 shipped with it.

⛔ **What L4 needs is its input, and the input is blocked by ONE ENVIRONMENT VARIABLE plus one
spend limit.** The chain was traced link by link and every link was counted. It is not the OCR
deploy, not the migrations, not a delivery defect, and not "no domain activated".

    GENIOS_L4_LLM_DECISION_MAKER = true          ⛔ the switch is ON, for every org
    Anthropic spend limit         refusing every call since 2026-09-25 11:09 UTC
    llm_decision_maker.py:20      "Failure is DEFER, never the formula."   ← BY DESIGN

**Two ways to unblock it, both one line, and the choice is Rohit's.** Nothing in `executive/`
changes either way.

---

# PART 1 · THE CHAIN, LINK BY LINK, EACH ONE COUNTED

Every arrow below is a measurement, not an inference.

    ┌─ 1 · WHICH LAYERS ARE ACTUALLY RUNNING ──────────────────────────────────────────┐
    │  L1  event_trace          2026-09-30 10:24     ✅ RUNNING                        │
    │  L1  l1_sync_runs         2026-09-30 10:23     ✅ RUNNING                        │
    │  L1  qualified_signals    2026-09-30 10:23     ✅ RUNNING                        │
    │  L3  graph_facts          2026-09-30 10:24     ✅ RUNNING                        │
    │  L3  context_situations   2026-09-30 10:24     ✅ RUNNING                        │
    │  L2  reasoning_runs       2026-09-30 10:32     ✅ RUNNING                        │
    │  ──────────────────────────────────────────────────────────────────────────────   │
    │  L4  executions           2026-09-25 03:46     ⛔ STOPPED 5 days earlier         │
    │  L5  cards                2026-09-25 10:46     ⛔ STOPPED                        │
    └──────────────────────────────────────────────────────────────────────────────────┘

**So the pipeline runs all the way through L1, L3 and L2 and then stops.** Both candidate
explanations are refuted on the spot: the OCR deploy would have starved L1 (it did not), and
"nothing is running" is false (six stages wrote rows on 30 September).

    ┌─ 2 · WHAT L4'S OWN GATE LETS THROUGH ────────────────────────────────────────────┐
    │  `sweep._PLANNABLE_SIGNALS`, decomposed join by join on the largest org:          │
    │                                                                                  │
    │    0 · open signals                              42                              │
    │    1 · + reasoning_runs                          42                              │
    │    2 · + reasoning_run_outputs                   42                              │
    │    3 · + reasoning_candidates                    42                              │
    │    4 · + reasoning_capability_snapshots          42                              │
    │    5 · + lateral authority_play                  42                              │
    │    6 · + reasoning_reasoner_results               0   ⛔⛔ ZERO HERE              │
    └──────────────────────────────────────────────────────────────────────────────────┘

Join 6 is `reasoner_id='core.constraint' and status='completed'` on the run behind the signal.
⛔ **And it is NOT the status filter**: all 2,681 `core.constraint` rows are `completed`. It is
that **the 98 runs behind every open signal have ZERO reasoner results of any kind.**

    ┌─ 3 · THERE ARE TWO ERAS OF REASONING RUN ────────────────────────────────────────┐
    │  reasoning_runs                                12,170                            │
    │    HAS reasoner results      2,681   evaluated 2026-09-29 → 09-30   ← NEW        │
    │    ZERO reasoner results     9,489   evaluated 2026-08-17 → 09-29   ← OLD        │
    │                                                                                  │
    │  open signals pointing at OLD (zero-result) runs:   98   = 100%                  │
    │  open signals pointing at NEW runs:                  0                           │
    └──────────────────────────────────────────────────────────────────────────────────┘

Reasoner results only began being written on **2026-09-29**. Every open signal predates that.

    ┌─ 4 · SO WHY DID THE NEW ERA EMIT NO SIGNALS? ────────────────────────────────────┐
    │  the 2,681 NEW runs:                                                             │
    │    reasoning_run_outputs written          2,681   ✅                             │
    │    candidates produced                    8,044   ✅  (3 per run)                │
    │    candidates `disposition='eligible'`    7,872   ✅  not rejected               │
    │    selected_candidate_id SET                  0   ⛔                             │
    │    selected_candidate_id NULL             2,681   ⛔  all of them                │
    │    `signals` rows emitted                     0   ⛔                             │
    │                                                                                  │
    │    outcome_kind:   defer 2,669 · blocked 12 · decision ZERO                      │
    │                                                                                  │
    │  for comparison, the OLD era:                                                    │
    │    outcome_kind:   defer 8,208 · decision 1,157 · blocked 124                    │
    │    and `selected_candidate_id` is set on exactly 1,157 — only a `decision` sets it│
    └──────────────────────────────────────────────────────────────────────────────────┘

    ┌─ 5 · AND WHY IS EVERY NEW DECISION A `defer`? THE COMPONENT VALUES ──────────────┐
    │  the 8,044 NEW candidates, averaged:                                             │
    │    impact            7,351   ✅ healthy                                          │
    │    risk              1,758   ✅ healthy                                          │
    │    effort            6,610   ✅ healthy                                          │
    │    urgency           5,182   ✅ healthy                                          │
    │    success           6,658   ✅ healthy                                          │
    │    formula_utility   5,469   ✅✅ THE DETERMINISTIC SCORER WORKS PERFECTLY        │
    │    llm_utility           0   ⛔ ZERO on all 8,044 · not one exception             │
    │    ───────────────────────────────────────────────────────────────────────────    │
    │    final_utility_bp      0   ⛔ ZERO on all 8,044                                │
    │    confidence_bp         0   ⛔ ZERO on all 8,044                                │
    │                                                                                  │
    │  the OLD candidates that DID produce decisions:                                  │
    │    formula_utility   5,586  ·  llm_utility  5,258  ·  final  5,264               │
    └──────────────────────────────────────────────────────────────────────────────────┘

⛔ **The product has a healthy deterministic score of 5,469 sitting right there and composes a
final utility of 0 from it.** A 0 utility can never win a ranking, so nothing is ever selected.

---

# PART 2 · ⛔ AND IT IS NOT A DEFECT. IT IS A DECLARED DESIGN DECISION.

This would have been the **tenth** time in this programme that a state was called a defect before
the declaration that created it was read. `genios_engine/reason/llm_decision_maker.py:20-22` says
it in its own words:

> **Failure is DEFER, never the formula.** A missing key, an exhausted budget, a network error or
> an answer that fails validation after one corrected retry all DEFER with a reason code.
> **Falling back to the formula would make a test of "what does the model decide" silently measure
> the formula.**

And `:84` — `#: Uncertainty codes, written only on DEFER — a DEFER never becomes a card.`
with `LLM_UNAVAILABLE_REASON = "llm_decision_unavailable"` named explicitly.

**The reasoning is sound.** A module whose job is to measure the model's judgement must not
silently substitute the formula's, or the measurement is worthless.

## The switch, and it is on

`enabled_for(org_id)` — *"Is the LLM decision maker on for this org? Off unless the switch says
otherwise."* Measured in the live environment:

    GENIOS_L4_LLM_DECISION_MAKER                  = true     ⛔ ON
    GENIOS_L4_LLM_DECISION_MAX_CALLS_PER_ORG_DAY  = 400
    GENIOS_ANTHROPIC_MODEL                        = claude-haiku-4-5-20251001
    l4_llm_decision_maker_orgs                    = (unset)  → ON FOR EVERY ORG

## So the complete, closed diagnosis

    the switch is ON for every org
      → every decision is routed to the model
        → the Anthropic spend limit refuses the call (since 2026-09-25 11:09 UTC)
          → the module DEFERS by design, and refuses the formula by design
            → llm_utility 0 · final_utility_bp 0 · outcome_kind 'defer'
              → selected_candidate_id NULL on all 2,681 runs
                → zero `signals` rows emitted
                  → L4's gate finds nothing (join 6)
                    → 0 executions and 0 cards since 2026-09-25
                      → the 150 existing cards aged past their windows
                        → "150 of 165 expired"

⛔ **The spend limit did not merely switch off LLM features. It stopped the card pipeline, in a
way that reads from the outside as a delivery defect.** That is the finding, and it reframes the
spend limit from a 🟠 inconvenience to a 🔴 total block on everything downstream of L2.

> ⛔ **A deliberate refusal to degrade is still a stop.** The design is right that a measurement
> must not be faked. What nothing declared is that the measurement mode is the PRODUCTION mode —
> so a budget ceiling became a full product outage with no alarm that said so.

---

# PART 2b · ⛔ THERE ARE **TWO** BLOCKS, NOT ONE — and STEP-02 was right too

PART 2 found what stops work **entering** L4. It does not supersede `STEP-02-DONE-organisation-
readiness.md`, which found something different and is **still live**. Both were measured today.

## BLOCK 1 · the input · ⛔ NEW · stops commitments being created at all

The switch, the spend limit and the declared DEFER (PART 2). **0 new commitments since
2026-09-25.**

## BLOCK 2 · the ladder · STEP-02's finding, confirmed with a number

`executive/readiness.py` was built in STEP-02 to answer *"why can this tenant not be routed to"*.
Run today, through its own `platform/org_readiness_sql.COUNT_SQL`:

    org                           seats   reporting_line   channels
    org_66bca8...                     1            ⛔ 0           1
    org_2f1bc0...                     1            ⛔ 0           1
    org_e97e86...                     1            ⛔ 0           1

**Seats and channels exist, so a commitment can find an owner and a channel — which is exactly why
186 executions were written.** The reporting line is zero, and `manager_of` has two sources and
both are empty:

    org_seats.manager_seat_id          0 of 3 seats     (the standing line)
    seat_responsibilities              0 rows           (the dated line)

⛔ **And here is what that cost, counted:**

    execution_escalations, 466 rows, by rung:
      day 1 · notify   · owner      175 rows   127 fired   127 with a target   ✅
      day 2 · remind   · owner        1 row      1 fired     1 with a target   ✅
      day 3 · remind   · owner      165 rows    75 fired    75 with a target   ✅
      day 5 · escalate · manager      1 row      1 fired     1 with a target   ✅
      day 7 · escalate · manager    124 rows     0 fired     0 with a target   ⛔⛔

**124 day-7 manager escalations were scheduled and not one ever fired, because there is no
reporting line for `manager_of` to climb.** The ladder works to day 3 and stops.

> ⛔ **Two blocks at two places.** One stops work entering the layer; the other caps the ladder
> inside it. Fixing either alone leaves the other. Neither is a defect in `executive/`.

## And a precision note on the reporting line's name

`03-FINDINGS.md` F1 and the Atlas both write *"`seat_responsibilities.reports_to`"*, which reads
as a column. ⛔ **There is no such column** — the table's columns are `org_id, seat_id, scope_kind,
scope_key, accountability, source, evidence_ref, valid_from, valid_until, created_at`, and
`assignment.REPORTS_TO = "reports_to"` is a **value of `accountability`**, not a column name.
`reports_to` appears in **no migration**, correctly.

**The code is right**; `readiness.py:66` states both paths exactly — *"set
`org_seats.manager_seat_id` for the standing line, or file a dated `reports_to` responsibility"*.
Only the prose in two documents is imprecise, and this is the correction.

---

# PART 3 · WHAT THE ATLAS SAYS ABOUT L4, CLAIM BY CLAIM

The Atlas's L4 section is unusually accurate. Each claim verified:

| | Atlas claim | Verdict |
|---|---|---|
| 1 | `executive/` 26 files, 5,990 lines | ⚠️ **27 files, 6,167 lines** — the Atlas is from 29 Sep; `readiness.py` landed after. Not an error, a date |
| 2 | "Units 6 and 8 have no file and three files carry no number" | ✅ **EXACT.** Numbered: 1, 2, 2.5, 3, 4, 5, 7, 9, 10. Unnumbered "Unit": `assignment`, `escalation`, `execution_guard`. 6 and 8 absent |
| 3 | "the spec that numbered them is not in the repo — an open question, not a gap" | ✅ and ⛔ **the code says it better.** `unreached.UNIT_NUMBERING_UNRESOLVED` already records it as *"A declared UNKNOWN, not a finding"* with *"An absent number is not an absent unit"* |
| 4 | execution.v1 runs on every heartbeat tick, before distribution | ✅ — but at **`api/routes.py:1195`**, not the `:1150` `unreached.py` cites. See **F-6** |
| 5 | Ladder: day 1 notify · 3 remind · 7 escalate · 14 critical · max_rungs 6 | ✅ built · **466 escalation rows** in production |
| 6 | Five tables, migration 0041, delegation wiring 0157 | ✅ `executions` 186 · `_actions` 794 · `_escalations` 466 · `_events` 1,021 · `_outcomes` 186 |
| 7 | "Why the queue is empty: no domain activated; organisation data missing" | ⛔ **SUPERSEDED.** L4 produced 186 executions and 165 cards, so it was never blocked on activation. The real cause is PART 2 |
| 8 | `seat_responsibilities.reports_to`, never `org_seats.manager_seat_id` | ✅ and already built — `STEP-01-DONE-reporting-line.md` |
| 9 | DecisionObject is `target`; brief.v1 exists | ✅ and `unreached.PULL_ONLY` says why: *nothing in `sweep.py` composes a brief* |
| 10 | Two open product decisions: preventive → card? brief pushed? | ✅ **both already declared in `unreached.PULL_ONLY`**, with the cost of each spelled out |
| 11 | L4 owns who/where (`assignment.py`, `communication.py`) | ✅ `deliver/router.py:9-12` records the move; all four `deliver/` modules import it |

**The Atlas got L4 right.** Its one superseded claim (#7) was true when written and is no longer
the binding constraint.

---

# PART 4 · THE FOUR REAL L4 GAPS — already declared, never built

These come from `executive/unreached.py`, which measured them before the Atlas did. **These, and
only these, are L4 build work.**

| | Gap | What it costs today | Tests |
|---|---|---|---|
| **G1** | ⛔ `monitor.blocking_action` — unreached **and untested** | Every stalled-commitment escalation says *"your Acme follow-up is stalled"* instead of *"stuck on getting it approved"*. Its own docstring: *"a message somebody can act on"* vs *"a message somebody can only feel bad about"*. `escalation.py` and `deliver/` contain **no reference to a blocking step** | ⛔ **none** |
| **G2** | ⛔ `assignment.resolve_approver_seat` — unreached | `requires_approval` **is read** (`contracts/execution.py:233` gates autonomy on it) and **nothing ever resolves WHO must sign.** A commitment can announce that approval is needed and never name the approver | ✅ 8 |
| **G3** | `brief.v1` is never composed on a tick | `brief.py` calls it *"the executive unit of output"*. Nothing in `sweep.py` produces one — a client must GET /briefs. **The layer's unit of output is never produced** | — |
| **G4** | ⛔ preventive mode is never pushed | `modes.py` names it *"the vision's USP"*. `deliver/` contains **no reference to preventive anything** — **no preventive finding has ever become a card** | — |

## Why G1 and G2 are the right two to build, and G3/G4 are not

**G1 and G2 are mechanical.** Each has one named reader, a defined output, and no product
decision inside it. G2 is additionally the safer of the two: eight tests already pin the
three-outcome distinction (`enforced` may name somebody, `suggested` needs human confirmation,
`no_authority_rule` is **not** "anyone may approve"), so the hard thinking is done.

**G3 and G4 are product decisions wearing engineering clothes**, and `unreached.py` says why:

> ⛔ *Turning [preventive] into a push is NOT a small change: every elapsed-time rule condition on
> every node produces a clock reading, so a naive 'one card per finding' would spend the daily card
> budget on warnings. **It needs a threshold, and the threshold is a product decision about how
> many warnings a founder should see a day.***

Building either without that number first would be building a guess. **They stay Rohit's.**

---

# PART 5 · TWO MORE FINDINGS FROM THE SWEEP

| | Finding | Severity |
|---|---|---|
| **F-4** | ⛔ `source_events.occurred_at` max = **2056-04-20** — a date **30 years in the future** in a production column. Every freshness axis, every window and every "most recent" read over that table is wrong for that row. It is one row shaped like a parser escape | 🟠 L1 · own unit |
| **F-5** | `ranking_weights_version` is present on **1,973 of 2,681** new outputs. The missing 708 are exactly the `legacy.rule` + `legacy.score_gate` count (708). So the legacy lane writes no ranking weights version — two scoring lanes, one of which does not say which weights it used | 🟡 L2 · own unit |
| **F-6** | ⛔ `executive/unreached.py`'s own docstring cites **`api/routes.py:1150`** for the `run_executive` call. It is at **1195**. The claim is true and the address is stale — which is exactly the shape this programme has a rule against: *a comment that cites a record reads as a record somebody can go and read*. ⛔ **And `tests/test_spec_deferrals_resolve.py` did not catch it**, because it resolves document paths, not `file.py:line` citations in prose | 🟡 own unit, and it generalises |

---

# PART 6 · HOW IT MUST BE BUILT — the shape, before the steps

Four rules this layer's own code already enforces, and which every unit below must respect:

1. **`validate → transition → observe → decide → speak`, always in that order.** `sweep.py`'s
   docstring: *"Never 'remind, then check'. The single most damaging thing a system like this can
   do is nudge somebody about work the world already finished, and the only structural defence is
   to make the guard unskippable."* A new field on a rung does not get to skip the guard.
2. **The plan is immutable; only the row moves.** Execution objects are frozen and
   content-addressed over organisation, decision and plan — so *"why did this escalate on day 7?"*
   is answerable months later. **G1 adds a field to the rung, never a mutation to the plan.**
3. **No model decides anything in L4.** A model may improve a reminder's wording; never whether to
   remind, whom to escalate to, the steps, or the urgency.
4. ⛔ **Both directions, or it is half a guard.** `tests/test_the_executive_says_what_it_does_not_call`
   already checks `unreached.UNREACHED` in both directions — an entry naming a function that is
   now called is as much a lie as a function unreached and undeclared. **So building G1 or G2
   means DELETING its entry in the same commit, and the test is what proves it.**

---

# PART 7 · THE PLAN — six units, in dependency order

## ⛔ U0 · THE DECISION THAT UNBLOCKS EVERYTHING — Rohit's, not a build

**Nothing below produces a single card until this is answered.** L4 can be perfect and still show
nobody anything while every decision defers.

| | Option | What it costs | What it means |
|---|---|---|---|
| **A** | **Raise the Anthropic spend limit** | money | the switch stays on; the product resumes exactly as designed; LLM decisions resume being measured |
| **B** | **`GENIOS_L4_LLM_DECISION_MAKER = false`** | the LLM-decision measurement stops | the formula decides. `formula_utility` averages **5,469** on live candidates, so cards resume immediately on deterministic scoring |
| **C** | **Build a third path** — `llm_decision_unavailable` falls back to the formula, `llm_declined` still defers | one unit of work, and a doctrine change | the module's stated reason covers a model that **answered badly**; it arguably does not cover a model that was **never reachable**. This is the only option that makes the product survive a budget ceiling without a human noticing |

**My recommendation: B now, C as a unit, A when the budget allows.** B restores the product today
with a scorer that is already healthy and already tested. C is what stops this recurring — but C
changes a declared doctrine, so it needs saying out loud rather than slipping in.

⛔ **Whichever is chosen, it belongs in `02-DECISIONS.md` as decision #5 with its reason**, because
a switch that silently converts a budget ceiling into a product outage is the thing this
programme exists to make legible.

## U1 · a receipt that says "the queue is empty because every decision deferred" — **UNBLOCKED**

The honest first build, and it is small. **Today nothing anywhere says this.** The operator-visible
symptom is "no cards", and six layers look healthy.

- a 32nd claim in `platform/receipts.py`: *"no reasoning era selects zero candidates"* — red when a
  window of runs produces outputs with 100% `selected_candidate_id is null`
- ⛔ it must be a **conjunction**, not a count: `defer` is healthy in isolation (the old era
  deferred 8,208 times and still produced 1,157 decisions). **A 100% defer rate over a window is
  the defect; a high defer rate is not.** That distinction is what audit D taught
- `SweepReport.reasons` already counts refusals by reason — this is the same discipline one layer up

**Verify:** the receipt is RED today against production, and would have been red since 29 September.
A receipt that is green on a broken product is the thing it exists to prevent.

## U2 · G2 · `resolve_approver_seat` reaches a live path — **UNBLOCKED**

The safest of the four gaps: pure resolution, eight tests already written, no product decision.

- `sweep.plan_commitments` resolves the approver beside the owner when
  `context.requires_approval` is set
- ⛔ **`None` stays `None`.** `no_authority_rule` is **not** "anyone may approve"; `suggested` needs
  a human to confirm. Only `enforced` may name anybody. The card then says *"sign-off needed"* and
  names nobody, which is what it says today and is correct
- delete the `assignment.resolve_approver_seat` entry from `unreached.UNREACHED` **in the same
  commit** — the both-directions test fails otherwise, and that is the point

**Verify:** `pytest tests/executive/ -q` plus the both-directions guard; then a commitment carrying
`requires_approval` with an `enforced` authority rule names its approver, and one with
`no_authority_rule` still names nobody.

## U3 · G1 · the escalation names the step it is waiting on — **UNBLOCKED**

- `monitor.blocking_action` gains tests first — it is the **only** entry in `UNREACHED` with none,
  and building on an untested function is how an untested function becomes a wrong one
- the `remind` and `escalate` rungs carry the blocking step; `escalation.py` copy names it
- ⛔ **timing does not move.** This is a change to escalation *copy*, not to the ladder's policy.
  `unreached.py` says exactly that, and it is the line that keeps this unit small

**Verify:** a stalled commitment whose second action is unticked escalates with that action named;
one with no identifiable blocker escalates with today's wording, not an invented one.

## U4 · F-4 · the future-dated row — **UNBLOCKED, L1**

`source_events.occurred_at` = 2056-04-20. Measure the blast radius first (how many reads order by
that column), then decide between a bound at ingest and a correction. ⛔ **One row is a finding;
the absence of a bound is the defect.**

## U5 · F-5 · the legacy lane's ranking weights — **UNBLOCKED, L2**

708 outputs carry no `ranking_weights_version`. Either the legacy lane records its weights or it
declares that it has none. A scoring lane that cannot say which weights it used is not replayable.

## U6 · G3 + G4 · brief push and preventive push — ⛔ **BLOCKED on a product number**

Not buildable until somebody says **how many warnings a founder should see a day** and **whether a
brief arrives or is fetched**. Both are already declared in `unreached.PULL_ONLY` with their costs.
**I will not build a threshold by guessing it.**

---

# PART 8 · WHAT IS AND IS NOT TRUE

    TRUE   · L4 is built, 27 files, 6,167 lines, and runs on every heartbeat tick
    TRUE   · it produced 186 executions, 794 actions, 466 escalations, 186 outcomes
    TRUE   · it declares its own unreached functions with a reason AND a mover — uniquely
    TRUE   · its gate closes at join 6 because the runs behind every open signal have no
             reasoner results at all
    TRUE   · every new candidate scores formula_utility ~5,469 and final_utility_bp 0
    TRUE   · that is `llm_decision_maker`'s DECLARED behaviour, not a defect
    TRUE   · GENIOS_L4_LLM_DECISION_MAKER = true, for every org
    FALSE  · "the queue is empty because no domain is activated" — it produced 165 cards
    FALSE  · "the 150 expired is a delivery defect" — L5 never received anything to deliver
    FALSE  · "the OCR deploy starved it" — L1 wrote rows on 30 September
    OPEN   · ⛔ U0: raise the limit, flip the switch, or build the third path. **Rohit's.**
    OPEN   · how many preventive warnings a day · whether a brief is pushed

**Nothing in `executive/` is wrong. The layer is waiting, correctly, for a decision one layer up.**

---

# PART 9 · THE FIVE CLAIMS IN THIS DOCUMENT THAT WERE CHECKED BY HAND

Because PART 2 is the tenth near-miss, every load-bearing citation here was opened and read:

| | Claim | Checked |
|---|---|---|
| 1 | `contracts/execution.py:233` gates autonomy on `requires_approval` | ✅ `return not self.requires_approval and not self.external_effect` |
| 2 | `deliver/outbox.py:315` imports `build_summary` | ✅ exact line |
| 3 | `escalation.py` and `deliver/` contain **no** reference to a blocking step | ✅ **zero hits** — G1 confirmed |
| 4 | `deliver/` contains **no** reference to preventive anything | ✅ **zero hits** — G4 confirmed |
| 5 | `api/routes.py:1150` calls `run_executive` | ⛔ **stale — it is 1195.** Became F-6 |

One in five was wrong. That is the ratio this programme keeps measuring, and it is why the
citations get opened.
