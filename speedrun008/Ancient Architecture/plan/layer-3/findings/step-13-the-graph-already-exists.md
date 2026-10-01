# L3-13 findings · the Intelligence Graph is already foreign keys

**2026-09-25** · +12 tests · 13,277 passed · 0 regressions · 7/7 mutations caught
**No migration. No new table. The plan asked for two and both were wrong.**

---

## 1 · What the step asked for

> **L3-13 · `intel_nodes` + `intel_edges`, landed with their first writer**
> Five node kinds (`situation · decision · delivery · outcome · interpretation`), six edge kinds,
> closed vocabularies, `on delete cascade` to `orgs`, soft-delete only.
> ⛔ **Separate tables, deliberately** — a decision in `graph_nodes` would get an `authority_rank`
> and start competing with a CRM on the same ladder.

The premise underneath it, stated in `05-TWO-HALVES-OF-THE-GRAPH.md` and repeated in L3-14:
**"no table holds both a situation and a decision."**

---

## 2 · The premise is false in three independent ways

### 2.1 `signals` holds both, and has since 0182

| column | migration | what it points at |
|---|---|---|
| `situation_id` | **0182** (L2-7) | `context_situations` |
| `reasoning_run_id` | 0029 | `reasoning_runs` |
| `reasoning_decision_hash` | **0031, FK'd** | `reasoning_run_outputs` |

⛔ The earlier scan that produced the premise read every `create table` block and found nothing.
It was blind by construction: **all three columns were added by `alter table`.**

### 2.2 The fallback argument is false too

L3-14 justified the tables a second way — *"it is a delivery table doing a graph's job — **it dies
when a signal is archived**."* Measured:

```
delete from signals        → 0 occurrences in the entire tree
update signals set status  → 12 occurrences  (open · acted · expired · resolved)
```

**Nothing deletes a signal.** Soft-delete only, which is the repo's own doctrine. Nothing purges
the reasoning spine either — the `purge_expired` family is confined to capture-side payload stores
and `health`. The join cannot die.

### 2.3 The chain does not stop at the decision

```
context_situations.situation_id
   └→ signals.situation_id                        0182
      signals.reasoning_decision_hash             0031 · FK
         └→ executions.decision_hash              0041
            └→ execution_outcomes.decision_hash   0041
```

`executions` carries `decision_hash`, `reasoning_run_id`, `candidate_id` and
`context_snapshot_id` — the same identity set `signals` carries — and `record_outcome` writes
`outcome.decision_hash` straight through.

⛔ **situation → decision → delivery → outcome. Four of the five planned node kinds, joined,
today, with no new table.**

> ⛔ **CORRECTED SAME DAY.** This said **four of the five** node kinds. It is **five of five.** The fifth — `interpretation` — is `situation_interpretations` (**migration 0183**, L2-5), keyed on `situation_id`, written by `context/interpretation_store.py`, holding the slice, the proposal, the outcome and `valid_until`. I missed it because I searched for the word *interpretation* in the reasoning tables and it lives in the CONTEXT tables. **The argument for `intel_nodes`/`intel_edges` is therefore weaker still, not stronger.** Building `intel_nodes`/`intel_edges` would have been a **second copy
of a graph the schema already enforces** — the over-scaffolding this plan has now refused twelve
times, at the cost of a migration, two tables, four closed vocabularies and a writer.

---

## 3 · What IS wrong, and it is worse than the thing that was planned

**Five functions insert into `signals`. One names `situation_id`.**

| # | writer | binds? | why |
|---|---|---|---|
| 1 | `reason/runner._emit` | ❌ | the pack lane — **the largest one** |
| 2 | `reason/publication.publish_native_signal` | ❌ | the native lane |
| 3 | `reason/composer.compose_deal_health` | ❌ | the composite lane |
| 4 | `reason/domain_shadow._emit_capability_signal` | ✅ | the compiled lane — **feature-flagged** |
| 5 | `reason/team/emit._write_card` | ❌ | a different vocabulary, must never bind |

⛔ **"A column no writer names is null forever."** 0182 landed the column in L2-7; the only writer
that fills it sits behind an activation flag. So on the live path `situation_id` is null on
essentially every row, and `deliver/card_source.classify` reads null as **`UNINTERPRETED`**.

**That is the benchmark's complaint, at its source.** Every main-path card is labelled as having
no business situation by a schema that has had the column for two migrations.

### 3.1 The fix costs nothing — which is exactly why it must not be done quietly

`reason/runner.run()` **already loads every node's situation in one query**:

```
runner.py:318   _bulk_load_situations(store, org_id)   → {anchor_node_id: {situation_id, …}}
runner.py:885   situations_by_node = _bulk_load_situations(store, org_id)
runner.py:926   ctx.situation = situations_by_node.get(nd.node_id)
```

and **all three silent main-path writers are called from inside that same function**, with the map
in scope:

```
runner.py:1310   _emit(store, org_id, rule, node_id, …)              key: node_id
runner.py:1347   publish_native_signal(…, publication=publication)   key: publication.subject_node_id
runner.py:1365   compose_deal_health(store, org_id, …)               key: p["deal_id"] (needs the map)
```

**Zero extra queries. Zero migrations. One column per insert, one parameter per signature.**
This is `not_carried` in its purest form — *a value computed correctly and then not carried.*

---

## 4 · ⛔ Why it is NOT wired, and why that is Rohit's call

### 4.1 Co-location is not provenance

A pack rule fires on **graph nodes**. It never reads the situation. Writing that situation's id
onto the signal asserts *"this card came from that situation"* about a decision made without it —
the same class of untruth as `graph_edges.valid_from` carrying event time under a knowledge-time
predicate (L3-04).

### 4.2 `classify` is binary, so there is no honest middle value

```python
def classify(*, situation_id):
    return CardSource.SITUATION if str(situation_id or "").strip() else CardSource.UNINTERPRETED
```

There is **no value meaning "a situation sits on this subject but the rule did not use it."**
Any non-empty id reads as provenance.

### 4.3 It would corrupt the measurement that decides the cutover

`card_source.COMPARISON_KEYS` grades the new path against the old on `cards_from_situation` vs
`cards_uninterpreted`. Binding co-located situations **moves rows from the second to the first
without changing a single decision** — the old path would appear to have become the new one.

### 4.4 The repo already measured it and already stopped

`reason/uncited_lanes.UNCITED_LANES["general"]`, measured **2026-09-16** on the pilot:

> *"9 of 11 OPEN general-pack signals sit on a subject that ALSO holds an active L2 situation, so
> the understanding exists and the card is simply not bound to it. Binding the pack lane to the
> situation its subject already has is **an architecture decision, not a repair, and it is the
> user's to make. Nothing here changes until it is made.**"*

**82% of the pilot's open general-pack signals.** The situation exists. The signal exists. They are
not bound, deliberately.

---

## 5 · What was built instead

`genios_engine/reason/situation_binding.py` — the gap made **impossible to lose**.

- `SIGNAL_WRITERS` — a closed tuple of all five writers, each with `binds` and a reason that
  names its mover. Checked in **both directions** against the tree.
- `signal_insert_columns(source)` — reads each writer's real column list **out of the AST**.
- `binding_drift(...)` — declared `binds` vs the real column list, so the declaration cannot go
  stale silently. **The day the decision is made, the build tells whoever wires it to update the
  reason beside it.**
- `bound_fraction()` → **(1, 5)**, pinned.

### 5.1 ⛔ The parser is structural, and that is the whole point

Python concatenates adjacent string literals **at parse time**, so a statement wrapped across nine
source lines arrives as **one `ast.Constant`** — and comments never enter the tree at all.

Nine assertions in this project have gone green (or red) on a word that lived only in a comment:
L1-14, L1-18, L2-6, L3-00, L3-02b, **L3-04 twice**, L3-05, L3-10. A structural read cannot make
either mistake.

### 5.2 ⛔ The guard found a defect in itself on its first run

**A docstring is an `ast.Constant` like any other.** `situation_binding`'s own explanation of what
it parses registered as a **fifth writer of `signals`**, and the totality check went red on a
correct tree.

The fix is the statement's **shape**, not a prose heuristic:

```python
tail = text.split("insert into signals", 1)[1]
return tail.lstrip().startswith("(") and "values" in tail.lower()
```

Prose *describes* an insert; an insert *has a column list and then supplies them*. Pinned by
`test_prose_that_names_the_statement_is_not_a_writer`.

---

## 6 · Technique 3 — 7/7

Every mutation asserted **the edit applied** before judging the probe (L3-05's lesson: *a mutation
that does not apply is indistinguishable from a test that does not work*).

| # | mutation | result |
|---|---|---|
| 1 | `domain_shadow` stops binding | ✅ RED |
| 2 | `runner` starts binding (co-location as provenance) | ✅ RED |
| 3 | the declaration lies about `runner` | ✅ RED |
| 4 | a writer loses its declaration | ✅ RED |
| 5 | the parser stops requiring the statement's shape | ✅ RED |
| 6 | the column reader falls through into `VALUES` | ✅ RED |
| 7 | a hard `delete from signals` appears | ✅ RED |

---

## 7 · Premise corrections from this step

| # | the plan said | measured |
|---|---|---|
| 12 | no table holds both a situation and a decision | **`signals` holds both** — 0182 + 0031, added by `alter table`, invisible to a `create table` scan |
| 13 | the join dies when a signal is archived | **nothing deletes a signal** — 0 hard deletes, 12 status updates |
| 14 | five node kinds need two new tables | ⛔ **ALL FIVE are already foreign keys.** situation → decision → delivery → outcome, plus `interpretation` = `situation_interpretations` (0183) |
