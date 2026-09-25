# L3-0 · Name the Decision Object

**Needs Harsh:** none · **Model calls:** none · **Migration:** none

> **NOT STARTED**

⛔ **A graph of decisions cannot be built while "the decision" is five nouns.** L2-1 measured what
two names for one thing cost: **fifteen compiler annotations naming the wrong situation stage**.
This is that step, one layer up — and it is cheaper, because the schema already decided.

---

## 1. Premise — the schema voted in migration 0031

```sql
foreign key (org_id, reasoning_run_id, reasoning_decision_hash)
  references reasoning_run_outputs (org_id, run_id, decision_hash)
```

**`signals` already points at `reasoning_run_outputs` with a database-enforced foreign key.**
Nothing points at the other four. On the live engine path `reasoning_run_outputs` has **one
writer** (`reason/store.py:1552`) and `decisions` has **one** (`api/intelligence_routes.py:112`,
the query API's cache).

**So this step does not choose. It writes down a choice the schema made two hundred migrations
ago, and demotes the rest to what they already are.**

## 2. The five, and what each actually is

| today | what it is | after |
|---|---|---|
| `reasoning_run_outputs` | the engine's only decision writer, FK'd from `signals` | ⛔ **the Decision Object** |
| `DecisionCandidate` | the in-memory candidate the reasoner ranks | **a candidate** — a stage, not the object |
| `l4_reasoning_bundles` | the narrative, keyed on `decision_hash` | **the decision's trace** |
| `decisions` | written only by the query API | **a read cache** — and labelled as one |
| `execution_outcomes` | what happened afterwards | **an outcome**, already its own noun |

## 3. Units

| | |
|---|---|
| **0-U1** | `contracts/decision.py` — `DecisionRef` (`org_id`, `run_id`, `decision_hash`), the one addressable identity. `DECISION_OUTCOME_KINDS` mirroring the table's six-value check, with a **totality guard in both directions** |
| **0-U2** | `DECISION_SHAPES` — a table naming all five, each with its role and its writer. Import-time check that every module writing any of them is named |
| **0-U3** | Docstring + comment pass on the five, each stating which it is and pointing at `contracts/decision.py` |
| **0-U4** | `decisions` table's comment says **read cache**, and a test asserts no engine module writes it |
| **0-U5** | `scripts/decision_shapes.py` — read-only, prints the five, their writers and their row roles. No DB needed for the static half |

## 4. Done criteria

- [ ] `DecisionRef` exists and is the only type the later steps address a decision by
- [ ] `DECISION_OUTCOME_KINDS` matches the migration's `check` constraint, guarded **both ways**
- [ ] `DECISION_SHAPES` names all five with role and writer; a test fails if a sixth appears
- [ ] a test asserts **no module outside `api/` writes `decisions`**
- [ ] `scripts/decision_shapes.py` runs with no database
- [ ] technique 3: neutralise the totality guard → the probe goes red
- [ ] full suite: 0 regressions

## 5. What this step does NOT do

* **No migration.** Nothing moves; nothing is renamed in the database.
* **No behaviour change.** A founder sees nothing. This is the vocabulary the next seven steps use.
* **It does not delete `decisions`.** The query API reads it. It gets labelled, not removed.
