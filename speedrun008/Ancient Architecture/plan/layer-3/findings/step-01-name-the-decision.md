# L3-01 · Name the Decision Object — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ The premise was wrong, and the correction is the finding

The plan said:

> *"'The Decision Object' is five shapes in the schema… one must become it before a graph of
> decisions can exist."*

**It is not five shapes. It is one object and five projections of it.**

`contracts/reasoning.py:1316` holds `ReasoningDecision` — a frozen, slotted dataclass carrying
`outcome`, `capability_id/version`, `context_snapshot_id`, the full `candidates` tuple with
dispositions, `selected_candidate_id`, `confidence_bp`, `uncertainty`, `do_nothing_consequence`,
`expires_at`, `outcome_window_days`, `citations` (**quoted, not paraphrased**) and
`constraints_applied` — hashed by `to_semantic_dict` into `decision_hash`.

**It was already the Decision Object. Nothing had to become it.**

### 1.1 · What the five actually are

| | role |
|---|---|
| `ReasoningDecision` | ⛔ **THE object** — in memory, frozen, hashed |
| `reasoning_run_outputs` | its persisted row · the engine's only decision writer · migration 0031 FKs `signals` to it |
| `l4_reasoning_bundles` | its trace |
| **`signals` decision columns** | ⛔ **the shredded projection the card reads** |
| `decisions` | the query API's cache, written by `api/intelligence_routes.py:112` and nothing else |

### 1.2 · ⛔ The sixth projection I had not counted is the one that matters most

`reason/runner.py:1187`:

```python
# The DecisionObject's own content, captured HERE — the last point it exists in memory.
_decision = reasoned.execution.decision
```

It is then **flattened into columns on `signals`** — `do_nothing_consequence`, `uncertainty`,
`outcome_window_days`, `rejected_candidates`, `candidate_steps`, `citations` — and
`deliver/pipeline.py:76` reads the pieces back off that row.

**So the card's recommendation comes from a delivery table, not from the decision.** And the
comment says why that was deliberate: before it, *"the card layer rebuilt its recommendation from
the reason_code STRING through an API if/elif chain: a parallel generator sharing nothing with this
decision but a label."* **The flattening is the fix for a worse bug, not a defect.**

---

## 2. ⛔ What was genuinely missing

### 2.1 · `ReasoningDecision` had no docstring at all

*"The DecisionObject"* appears in **six comments** across `reason/` and `deliver/`. The class those
six comments mean carried **zero** lines of documentation.

**The concept was named everywhere except on the type that is it** — which is exactly how *"which
one is the real one?"* became a question worth a planning step.

### 2.2 · The outcome vocabulary was not held to the database

```python
DecisionOutcome  = decision · no_action · defer · insufficient_context · blocked · failed
check constraint = decision · no_action · defer · insufficient_context · blocked · failed
```

**They agree. Nothing held them together.** An enum member the constraint rejects is a write that
fails at 3am on a real decision; a constraint value the enum lacks is a row nothing can read back
into the contract. Guarded now in **both** directions.

⛔ **And the five non-`decision` outcomes are the point.** `no_action`, `defer`,
`insufficient_context`, `blocked` and `failed` are decisions the product must be able to state. A
projection carrying only `decision` loses five sixths of the vocabulary, and the test pins that so
a later "simplification" to a boolean is a build failure.

---

## 3. My own test bug, caught by its own probe

`test_the_projection_table_is_reachable...` went red on correct code: it walked `ast.Assign` only,
and `DECISION_PROJECTIONS: tuple[...] = (...)` is an **`AnnAssign`**. A guard that only sees untyped
constants would have quietly stopped covering every annotated constant in the file.

**Same family as L3-00's blunt grep, one day apart: the assertion was about a shape of the syntax
rather than the thing being asserted.**

---

## 4. Result

```
FULL SUITE   13,143 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-01: 13,135 passed · 14 failed
```

**+8 tests · 0 regressions · no migration · no model call.**

**Technique 3 — four mutations, all red:** an enum member the DB rejects; the docstring stripped; a
table name placed first in the projections; a receipt field dropped.

## 5. What this step does NOT do

* **It does not move the decision out of `signals`.** That flattening is a deliberate fix. Whether
  the Intelligence Graph should point at `reasoning_run_outputs` instead is **L3-14's** question.
* **It does not delete `decisions`.** The query API reads it; it is labelled, not removed.
* ⛔ **It removes a blocker the plan claimed existed.** Wave 6 assumed the Decision Object had to be
  chosen first. It does not — `decision_hash` is already the identity an `intel_nodes` row would
  point at.
