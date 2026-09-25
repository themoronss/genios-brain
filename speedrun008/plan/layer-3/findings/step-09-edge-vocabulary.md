# L3-09 · The typed relation vocabulary — findings

**Run:** 2026-09-25 · premise checked before any code · ⛔ **no migration — the plan was wrong again**

---

## 1. ⛔ Seventh premise wrong — the seven "missing" relations all have mechanisms

The plan said *"5 of 12 typed relations exist; the seven missing ones carry the product's meaning."*
**Every one of the seven is implemented — in a different layer.**

| "missing" relation | where it actually lives |
|---|---|
| `same_entity_as` | `graph_aliases` ＋ merge proposals — **identity**, 14 files |
| `responds_to` | `in_reply_to` ＋ `reconstruct_thread` — **thread structure** |
| `satisfies_condition` | `correlate_timeline(DormantCondition, ConditionWorld)` |
| `fulfills` | the commitment state machine, 12 files |
| `assigned_to` | `owner_basis`, 10 files |
| `requested_from` | `awaited_from` |
| `scheduled_for` | meeting nodes ＋ `attended`, 40 files |

⛔ **Adding seven parallel edge types would have created two answers to every one of those
questions** — the over-scaffolding pattern this layer has now refused seven times.

---

## 2. ⛔ What was actually wrong: the vocabulary was not a vocabulary

```sql
edge_type text not null        -- no check constraint
```

**And no `EDGE_TYPES` constant existed anywhere in the engine.** Six types are written. Anything
else was accepted **silently** — including a typo of one of the six.

⛔ **`work_at` is one character from `works_at`.** Before this, it wrote a relation every reader
walks straight past: **a fact in the graph that can never be found, with no error anywhere.**

### 2.1 · And the specs' hazard could not be violated because there was nothing to violate

> §2: *"`related_to` **must not silently become** `blocks`."*
> CC-35 / DP-06: *"co-occurrence cannot produce `causes` or `blocks`."*

**There was no rule.** Any module could have written either.

---

## 3. Built — a closed set and three named refusals

| | |
|---|---|
| `EDGE_TYPES` | six, each stating **its direction and what it does NOT mean** |
| `FORBIDDEN_EDGE_TYPES` | ⛔ `causes` · `blocks` · `related_to`, each with its own reason |
| `write_edge` | **raises** on an unknown or forbidden type |
| totality | both ways — declared ⟷ written, at build time |

### 3.1 · ⛔ It raises rather than skipping, and that is the same argument twice

An edge type is written by a **programmer**, not supplied by data, so an unknown one is a **bug in
the caller**. A silent skip would let it ship. That is `corroborate`'s argument at its own seam —
*"a warn would let it ship"* — applied here.

### 3.2 · Why the three refusals, and why each carries a reason

*"Not allowed"* teaches nobody. **The reason is what stops the next person adding it back with a
better argument, because the argument is already written down.**

* **`causes`** — a causal claim. An edge cannot carry the evidence that would make it one. If
  something really does cause something else, that is a **conclusion**, and conclusions belong
  where their slice and their law live.
* **`blocks`** — a dependency **verdict**. `requires` is a claim a requirement definition can
  support; `blocks` is one only a reasoner can. ⛔ **The refusal names the alternative**, so the
  caller has somewhere to go.
* **`related_to`** — the untyped edge. The specs' warning is that it *"must not silently become
  blocks"*, and the way that happens is somebody writes it **because the real type was unclear**,
  and a later reader needs it to mean something.

### 3.3 · Each type states what it does NOT mean

`attended` is presence, **not engagement**. `corresponded_with` is that mail was exchanged, **not
that a relationship is strong**. ⛔ **Those distinctions are exactly how an edge becomes a
conclusion**, so the vocabulary states them rather than leaving them to a reader's assumption.

### 3.4 · No migration, and the plan said there would be one

A check constraint would make adding a relation a **schema change**, and would fail on any historic
row nobody has audited. This repo's idiom for a closed set is a Python constant with a totality
guard in both directions — `LAYERS`, `PRECEDENCE`, `ANCHOR_FAMILIES`, `SYNC_HEALTHS`.

---

## 4. Result

```
FULL SUITE   13,237 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-09: 13,224 passed · 14 failed
```

**+13 tests · 0 regressions · no migration · no model call.**

⛔ **No live call can raise:** `test_every_written_type_is_declared` walks the whole engine and
proves every `edge_type=` in the codebase is one of the six.

**Technique 3 — five mutations, all red:** unknown types pass through; the forbidden set is
bypassed; a refusal loses its reason; a declared type nothing writes; a module writes an undeclared
type.

## 5. What this step does NOT do

* ⛔ **It does not add seven relation types.** They exist elsewhere; parallel edges would be two
  answers to one question.
* **It does not add a check constraint.** Recorded in a test, so if one ever lands the guard becomes
  belt-and-braces rather than the only thing standing between a typo and an invisible edge.
* ⛔ **It does not audit existing rows.** A pre-existing typo'd edge is still in the table and still
  invisible. **Nothing can be written that way again**, which is the fix — finding the old ones is a
  query somebody should run, not a code change.
