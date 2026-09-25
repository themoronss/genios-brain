# L2-2 · The interpretation fields — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **no migration · no model call**
**Against:** `speedrun008` @ `e6b4fdc2`
**Result:** 30 tests, **12,957 passed · 14 failed (all pre-existing) · 0 regressions**
**`vocabulary_fingerprint`:** `a3d5496aa0d3` — unchanged

---

## 1. ⛔ Premise correction 1 — the re-analysis used the wrong test

The plan's own correction says *"only two names appear nowhere in `genios_engine`"*. Two problems.

**It omitted `implications` from its own check.** Measured: **0 files.** Three, not two.

**And "appears nowhere in the tree" is the wrong question.** The step is about **situation**
fields:

| name | files | what those files actually are |
|---|---|---|
| `valid_until` | 8 | **all `context/authority_view.py`** — approval-delegation rules. Nothing to do with a situation |
| `reasoning_trace` | 1 | one string **literal** in `deliver/card_builder.py:733` |
| `hypotheses` | 2 | prose in a route docstring and a comment |

**So all six are missing as situation fields.** Two of them have the name in use elsewhere for an
unrelated purpose, which is worse than absent — it is the L2-1 collision waiting to happen again.

---

## 2. ⛔ Premise correction 2 — and it is what makes the step buildable today

The plan's premise paragraph:

> *"Every field that exists is an observation field. Every field missing is an interpretation
> field. Not a coincidence — the exact signature of a layer that correlates and does not reason."*

**Read against the contract, v2 is already full of interpretation, and says so itself:**

| field | the contract's own words |
|---|---|
| `visibility` | *"A situation is a **DERIVED claim**"* |
| `coverage_ready` | *"May a **NEGATIVE inference** be made in this situation's domain"* |
| `missing_facts` | *"The `GENUINELY_ABSENT` entries are **findings**, not data-quality complaints"* |
| `trends` · `anomalies` · `correlations` · `cohort_positions` | governed by V-4…V-7 **precisely because** they can be wrong: *"a trend is never certain"*, *"correlation is never cause"* |

⛔ **Layer 2 does not lack interpretation. It lacks the label saying which field is which** — and
without that label there is nowhere to hang a write-authority rule.

**That changes the step from "add six columns" to "classify twenty-eight existing ones", which
needs no migration and ships today.** And it avoids a duplication: `evidence`, `signal_ids`,
`entities` and `timeline` **are** the observed facts. Minting `observed_facts` beside them would
be the second-name defect L2-1 just spent a step undoing.

### 2.1 · The classification

`contracts/claim_state.py` — checked both directions at import:

| state | count | examples |
|---|---|---|
| **OBSERVED** — no model may write one | 8 | `evidence` · `signal_ids` · `entities` · `timeline` · `provenance_refs` |
| **INFERRED** — a model may propose | 14 | `trends` · `anomalies` · `correlations` · `confidence` · `missing_facts` · `type` · `state` |
| **ENVELOPE** — not a claim at all | 6 | `org_id` · `id` · `schema_version` · `visibility` · `metadata` |
| **HYPOTHESISED** | 0 | nothing holds one yet — that is L2-5's, with its writer |

`visibility` is ENVELOPE and still refused to a model, with the reason stated: **a model that may
set it may widen an audience.** `metadata` likewise — *"writing the bag is writing anything in
it."*

---

## 3. ⛔ THE FINDING — four of seven interpretation types carry no receipt at all

`MatchedCondition` already states the doctrine for the whole family, in its own validator:

> *"matched condition must cite the evidence it matched on — **'this fired because of these
> facts' is what makes a situation defensible**"*

Measured, and every one is constructed on a live path:

| type | receipt | built at |
|---|---|---|
| `Trend` | `evidence_points` ✅ | `context/analytic/trend.py` |
| `MatchedCondition` | `evidence` ✅ | the pattern matcher |
| **`Anomaly`** | ⛔ **none** | `context/analytic/anomaly.py:336` |
| **`MetricCorrelation`** | ⛔ **none** | `context/analytic/correlator.py:282` |
| **`CohortPosition`** | ⛔ **none** | `context/analytic/cohort.py:1478` |
| **`ImportanceAttribution`** | ⛔ **none** | `context/situation_publisher.py:121` |

**So V-9 — no interpretation without a receipt — has four subjects the day it is written.** Each
of the four gained an optional `evidence_refs`, default empty, so nothing that builds one breaks.

### 3.1 · The repo's own canonical fixture proves it

`test_l2_contracts`'s *"clean situation"* fixture now trips V-9. **That is not a defect in the
fixture** — it builds analytic objects the way `context/analytic/` does, with no receipts. Giving
the fixtures evidence to keep `failures == ()` would have hidden the finding inside the test that
reveals it. The assertions were changed to name the **rejecting** failures specifically, which is
a stronger claim than "exactly one failure exists", not a weaker one.

---

## 4. ⛔ V-10 was narrowed by measurement — the plan's version would have accused 11 types

The plan: *"An empty `unknowns` on a situation whose `coverage_ready` is false is a claim of
completeness the data does not support. Refuse it."*

Measured: **26 of 37 registered situation types declare `expected_fields`. Eleven declare none** —
`admin_period_review`, `reply_owed`, `blocked_on_unnamed`, `analytic_movement` and seven more.
**For those, an empty `missing_facts` is the correct answer**, and the unconditional rule would
have accused every one of them of hiding something that cannot exist.

So V-10 fires only where the type's domain declares something that could be absent.

---

## 5. ⛔ BOTH NEW LAWS OBSERVE RATHER THAN REJECT, AND THAT IS THE DESIGN THE CODE ASKED FOR

`LawAction`'s own docstring, written before this step:

> *"a law that later downgrades or parks is a **one-line change here plus a branch in
> `validate_situation`**, rather than a condition somebody has to notice"*

Arming V-9 or V-10 to reject would refuse live situations — **and nobody has counted how many.**
L1's step 10 set the precedent by gating itself on a measurement. So `LAW_ACTIONS` gives both
`OBSERVE`, `validate_situation` branches on the **action** rather than on whether any failure
exists, and **arming either is a one-line change to the table.**

**An OBSERVE law is not a soft law. It is a law waiting for its number.** → Harsh item 24.

---

## 6. Two guards caught this build, and both were right

### 6.1 · ⛔ The import ratchet — I broke a layer rule and wrote a comment claiming I had not

V-10's first draft read `context.domain_spec` from inside `contracts/situation.py` behind a
deferred import, with a comment saying the deferral *"keeps the contract package's import rule
intact."*

```
AssertionError: situation.py imports genios_engine.context
```

**A contract may import platform and stdlib only.** Fixed by handing the answer in — the exact
shape `build_business_situation(refusal=...)` already uses: *"computed by the caller because this
builder holds no connection, and passed in."* `context/expected_facts.py` does the lookup, and
`situation_publisher` passes it.

**`None` means the caller did not compute it and V-10 is not evaluated — not that nothing is
expected.** Different facts, and a test drives the production call site to prove the argument is
actually named there, because a law nobody supplies the input for is a law that never fires.

### 6.2 · ⛔ The H0 gate — a non-rejecting action must bring its machinery

`test_the_layer_two_gate_has_no_park_and_no_downgrade_to_drift_into` failed, and its own docstring
says why:

> *"L1's decision carries a `parked` record and a `confidence_downgrade_bp`; L2's carries neither,
> **so a later edit cannot quietly turn a reject into a park without adding the machinery
> first**."*

**It was pointing at a real hole: two laws written to end an invisible refusal had nowhere to be
seen.** An ADMIT carried the failures and nothing read them.

**The machinery, built:** `observed_reasons()` writes `observed:<law>:<subject>` into
`situation_admission_decisions.reasons` — the durable ledger L2-0 already identified — and L2-0's
report gained a `BY LAW` table **built from the `L2Law` enum**, so an eleventh law appears at zero
the day it is added. The guard now asserts that machinery directly instead of forbidding the
action, and **a new non-rejecting action with no path to the ledger still fails it.**

```
BY LAW  (V-9 and V-10 OBSERVE: the situation published, and this is what
         the gate noticed about it. The rest reject.)
  V-1 … V-8                              0
  V-9                                    0
  V-10                                   0
```

---

## 7. Two caller-error traps, both the same class as L2-0's

| | |
|---|---|
| `domains_declaring("support_case")` → `()` | it takes an **anchor** type, not a situation type. A silent empty that reads exactly like *"this type expects nothing"* |
| `Anomaly(severity_bp=…, window_days=…)` | invented field names; the real ones are `mad_bp`, `deviation_bp`, `z_like_bp`, `periods_used` |

The first is the same shape as L2-0's `situation_admission_reason` trap — **a lookup that answers
plausibly when called wrong**. Named in `expected_facts.py` so the next reader does not repeat it.

---

## 8. Cost check

| | |
|---|---|
| model calls | **none** |
| migration | **none** — the classification needs no column |
| `vocabulary_fingerprint` | `a3d5496aa0d3`, measured before and after |
| runtime behaviour | **no situation that published yesterday stops publishing.** Both new laws OBSERVE |
| new columns | four optional `evidence_refs`, default `()` — nothing that constructs one breaks |

---

## 9. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | `ClaimState` exists, closed, guarded | ✅ four members — three claims plus `envelope` — with totality both ways over all 28 v2 fields |
| 2 | all six fields on v2, integer basis points | ⛔ **DEFERRED to L2-5, with its writer.** §10 |
| 3 | four validators | ⚠️ **two built and wired** — V-9 (a receipt) and V-10 (completeness vs coverage). The other two — *"an inference must point at an observation"*, *"a hypothesis needs confidence"* — need the fields, and go with them |
| 4 | migration 0182 + the store names every column | ⛔ **DEFERRED with #2** |
| 5 | full suite green, fingerprint unchanged | ✅ 12,957 passed · 14 pre-existing · `a3d5496aa0d3` |

**Three closed, two deferred with a reason, one half-built with its other half named.**

---

## 10. ⛔ Why the fields are deferred, and the plan says it first

The step's own §5:

> *"It does not fill the fields. Nothing writes them until L2-5. **A field with no writer is the
> `started_at` mistake**, so L2-2 and L2-5 ship together or L2-2 ships knowingly empty — and the
> STATUS row must say which."*

The build order is `0 → 1 → 2 → 3 → 4 → 6 → 7 → 5 → 8`. **L2-5 is five steps away.** Shipping four
columns and a migration now means Harsh applies 0182 for fields that are null for five steps.

**And L2-0's entire finding was eight things built and never switched on.** This would make nine.

**So: the doctrine ships now, the storage ships with its writer.** The classification, the write
authority and the two laws are what L2-5 needs to exist *before* it — *"a rule added after its
writer is a rule the writer was built around"* — and none of them needs a column.

---

## 11. What this step does NOT do

* **It does not add `observed_facts`.** `evidence` + `signal_ids` + `entities` + `timeline` are
  the observed facts and are now labelled as such. A fifth name for them is the L2-1 defect.
* **It does not arm V-9 or V-10.** One line in `LAW_ACTIONS`, after the count. **Harsh item 24.**
* **It does not make any producer cite its evidence.** The four gained a place to put a receipt;
  filling it is each producer's own unit, and V-9 now names who has not.
* **It does not weaken a law.** The eight originals still reject, asserted one at a time.
