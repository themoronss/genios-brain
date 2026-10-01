# L2 · does it actually WORK? — measured against production, read-only

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Method:** one `set transaction read only` connection to production. No writes. No model calls.
`GENIOS_ALLOW_PROD_WRITE` was never set — that variable is named for writes because it was written
for writes.

> Rohit asked for more than green tests: *"saari cheezein perfectly kaam karni chahiye … kya mistakes
> ho rahi hain, kya problem statement mein aa rahi hai?"* So this page measures behaviour, not
> structure. The suite was at **14,397 passed** while everything below was true.

---

## What production actually holds

| | |
|---|---|
| orgs | **3** |
| signals | **165** (99 open) |
| cards | **165** |
| **reasoning runs** | **12,170** |
| **expertise packages** | **1,150** |
| `learned_brain_entries` | ⛔ **0** |
| `temporary_memories` | ⛔ **0** |

⛔ **So both planes have genuinely run.** Plane R has executed 12,170 runs; Plane D has compiled 1,150
packages. This is not a cold system. And **`ALARM A3` is confirmed from the database**: the two tables
the Organisation, Behaviour and Adaptive brains live in are **empty**.

⛔ **And `ALARM A5` was WRONG, in my favour and against me.** I wrote that the live lane *"schedules
none of `core.impact`, `core.cost`, `core.opportunity`."* Measured: **all three have completed
thousands of times.** `core.cost` 1,973. `core.impact` 1,973. `core.opportunity` 1,088. **Twenty units
have completed in production** — the roster is running far more widely than any document said.

---

## ⛔ THE FINDING · two units complete on every run and compute nothing

```
unit                 completed   silent   share
core.impact               1973     1973    100%   ⛔ SAYS NOTHING, EVER
core.opportunity          1088     1032     94%   ⛔
```

*Silent* = emitted **no finding, no check, and no non-zero metric.** `core.impact`'s entire output on
all 1,973 runs is `{"impact_signal_count": 0}` — a count of how many of its three dimensions reported,
which is **zero**, every time.

⛔ **Its status is `completed`.** So every probe that asks *"does this unit speak?"* — including my own
`l2_unit_silence.py` — reports it as speaking. It succeeds, and it computes nothing.

⛔ **And the unit is RIGHT to be quiet.** Its own docstring:

> *"**Silence is not zero.** A dimension with no evidence contributes no observation *and publishes no
> metric*. Emitting `revenue_exposure_bp = 0` because Layer 2 never supplied a deal value would be a
> fabricated fact … An absent metric lets the reader supply their own default; a fabricated zero
> silently lies."*

**That design is correct.** The defect is that **nothing downstream can tell its honest silence from a
measurement.**

---

## ⛔ What the silence cost, measured end to end

`tradeoff_unit.AXIS_SOURCES` declares `benefit_source → core.impact → impact_bp`.
`core.impact` never publishes `impact_bp`. Therefore:

```
core.tradeoff   1,165 of 1,165 completed
  tradeoff.speed_vs_certainty    1,163 firings
  tradeoff.risk_vs_reward          597 firings
  tradeoff.cost_vs_benefit         ⛔ 0 firings in 1,200 rows

  axis_count:       1 on 63%   ·   2 on 37%   ·   3 on 0%
  contested_count:  0 on 84%
```

It declares **six** sources and compares **at most two axes, usually one.**

### ⛔ And a green test proves the axis works

`tests/reason/test_tradeoff_cost_axis.py::test_the_cost_versus_benefit_axis_produces_an_observation`
**passes.** It supplies the prior metric itself. Production does not.

> **A green test proving an axis works, over 1,200 production rows where it has never spoken once.**

### ⛔ And a previous fix was applied to the wrong side

`CostVersusBenefitPlugin`'s docstring says:

> *"The default cost source is `core.cost`, which is where `effort_bp` has always been published. It
> used to be `core.effort`, a unit that does not exist — so this axis, alone among the three, could
> never speak, and its silence was indistinguishable from an honest one."*

**Somebody found the bug, fixed the COST side, wrote that it was fixed — and the axis is still
silent**, because the **BENEFIT** side was broken for an unrelated reason. Verified: `core.cost`
publishes `effort_bp` on 300 of 300 sampled rows. The cost side works. Nobody checked whether the
axis then spoke.

---

## ⛔ The chain behind it — four links, every one behaving correctly

```
core.relationship    NEVER completes · 708 insufficient_context · 221 skipped
        │              needs deal.status; nothing supplies it
        ▼
core.impact          AccountImportancePlugin falls back to core.relationship.coverage_bp → absent
                     RevenueExposurePlugin needs deal.value → absent
                     ⇒ impact_signal_count: 0 on every run, impact_bp correctly OMITTED
        │
        ▼
core.tradeoff        CostVersusBenefitPlugin reads core.impact.impact_bp → absent → returns ()
        │
        ▼
axis_count: 1        the honest signal, published on every run …
        │
        ▼
      ⛔ …and read by NOBODY. Grepped: zero consumers outside tradeoff_unit.py
```

⛔ **Every link is correct in isolation.** `core.relationship` is right to refuse without
`deal.status`. `core.impact` is right not to fabricate a zero. `core.tradeoff` is right to stay
silent on an unmeasurable axis. **And the composition loses the information entirely**, which is
`not_carried` and the six-times defect at the same seam.

---

## Two more findings from the same pass

⛔ **`core.policy` has never completed** — 165 rows, all `skipped: no_declared_input_available`. It
needs `deal.approval_status`, `contact.do_not_contact` or `contact.consent_status`, and nothing
supplies any of them. **This is the unit `WAVE Y1`'s Organisation-Brain lever is supposed to work
through.** The lever is wired, the brain is empty, *and* the unit has never run.

⛔ **`core.signal_composition` never appears in the table at all** — not as a completion, not as a
skip. Registered, scheduled by nothing.

---

## What was built in response

**`scripts/l2_unit_said_nothing.py`** — read-only, no model, and it would have caught all of this.
**14 tests** in `tests/reason/test_a_unit_that_says_nothing_is_not_working.py`.

⛔ **It asks the right question, and the first version asked the wrong one.** Counting empty
`findings` reports `core.constraint` (2,681 completions, 0 findings) and `legacy.score_gate` (708, 0)
as broken. **Both are fine** — their `output_kind` is `candidate_checks` and they emit CHECKS. A unit
is silent only when it emitted no finding, **no check**, and no non-zero metric.

> *A crude slice that happens to fail looks exactly like a real finding.*

It also **separates the two defects**, because mixing them lets one hide the other:
`core.relationship` has **no input** (929 rows, never completed); `core.impact` **has input and
produces nothing from it** (1,973 completions, all empty). Opposite investigations.

The known-silent set is **pinned** — `{core.impact: 100, core.opportunity: 94}` — so a *new* silent
unit exits non-zero rather than being discovered six weeks later.

---

## ⛔ What I did NOT change, and why

| | |
|---|---|
| ⛔ **`core.tradeoff` does not yet publish WHICH axis it lost** | that is the right fix, and it adds a metric or a reason code to the output of **every** run — which rehashes every `output_hash` in `reasoning_reasoner_results`. **That is the exact trap I hit in L5 with the lane-in-hash**, and it needs a version decision, not a quiet edit |
| `core.impact`'s silence | **correct behaviour.** Fabricating a zero is the thing its docstring forbids |
| `core.relationship`'s refusal | **correct.** Nothing supplies `deal.status`; the fix is upstream data, not this unit |
| the empty brains | `ALARM A3`. Populating them is Rohit's |

---

## ⛔ ALARMS — new, from behaviour rather than structure

| | | Whose |
|---|---|---|
| 🔴 **B1** | **`core.impact` completes 1,973 times and computes nothing.** Three units downstream read its absence as "no signal here" rather than "this unit had nothing to read" | needs the `core.tradeoff` receipt (a version decision) — **Rohit** |
| 🔴 **B2** | **`tradeoff.cost_vs_benefit` has fired 0 times in production**, while a unit test proves it works | same |
| 🔴 **B3** | **`core.relationship` has never completed** — 929 rows. `deal.status` has no writer. It is a declared source of `core.risk` AND `core.impact` | upstream data — **Harsh** |
| 🟠 **B4** | **`core.policy` has never completed** — and it is the unit the Organisation-Brain lever works through | **Rohit / Harsh** |
| 🟠 **B5** | **`core.signal_composition` never appears at all** — registered, scheduled by nothing | **Rohit** |
| 🟡 **B6** | **`axis_count` is published on every run and read by nobody** | the receipt again |
| ✅ | **`ALARM A5` was wrong** — all three units DO run in production. Corrected here | — |
