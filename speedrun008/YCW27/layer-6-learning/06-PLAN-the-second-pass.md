# L6 · PLAN — the second pass over `feedback/`

**Date:** 2026-10-02 · **Owner:** me · **Milestone:** `M14.C2` (M14.C1 was the attribution pass)
**Reads from:** [`05-RECROSSCHECK-the-loop-that-runs-and-is-never-questioned.md`](05-RECROSSCHECK-the-loop-that-runs-and-is-never-questioned.md)
**Nothing is built until this file is confirmed.**

---

## 0 · The one-sentence shape

> The learning loop **runs**; nothing it writes is ever **questioned**. Four presence receipts are
> all satisfied by a single successful tick, and the four append-only ledgers that would answer the
> correctness questions have **no reader**.

So this pass is not a wiring pass — `feedback/` is wired. It is a **reading** pass: give the layer
its first correctness guards, each one taking its evidence from a ledger that is already being
written and already indexed.

```
   U01 ─┐
        ├─ U03 ── U04 ── U05 ── U06        the critical path, 5 deep
   U02 ─┘
   U07  U08  U09  U10                      independent, any order
```

---

## 1 · Every unit, with its measure-first gate

⛔ **Each unit states what must be MEASURED before it is written.** Four retractions in this
programme came from skipping that line, and two of them were receipts that could never have failed.

### ⛔ `U01` · establish the baseline — what are the 27 skips?

| | |
|---|---|
| **what** | `tests/feedback` runs **60 passed, 27 skipped**, and no document in this folder mentions them. Name every skip and its reason |
| **why first** | ⛔ *Establish the baseline, or the harness is theatre.* `STEP-14` reported a mutation as caught because the harness never re-ran clean. Adding tests to a layer whose existing skips are unexamined repeats that |
| **artifact** | a measured table in `03-FINDINGS.md` — no code |
| **verify** | `.venv/bin/pytest tests/feedback -q -rs` |
| **measure first** | nothing — this IS the measurement |
| **depends on** | — |

⛔ **A skip is not a pass.** If any of the 27 is a DB skip hiding a real gap, it changes what the
later units assert — and if they are all DB skips, that is a finding for Harsh, not for me.

### `U02` · guards per package becomes a measured number

| | |
|---|---|
| **what** | `platform/receipt_coverage.py` — per receipt **claim**, the package it guards and whether it is a `correctness` or `presence` check. Both directions: a new receipt with no entry fails the build, an entry naming a claim that no longer exists fails too |
| **why** | ⛔ the `STEP-10` error. The count lived in prose in eleven documents and was derived once by hand from a label filter. *A claim worth asserting is worth storing as data* |
| **artifact** | `genios_engine/platform/receipt_coverage.py` + `tests/platform/test_a_receipt_label_is_not_a_package.py` |
| **verify** | `.venv/bin/pytest tests/platform/test_a_receipt_label_is_not_a_package.py -q` |
| **measure first** | ⛔ that the **outer** `from` can be resolved for all 35 receipts. The first attempt read `l2_convergence` as table `l` — `[a-z_]+` cannot match a digit — and `jsonb_each` is a function, not a table. **Two of 35 break a naive resolver**, so the table is DECLARED per claim, not parsed |
| **depends on** | — |
| ⛔ **explicitly NOT in scope** | **changing a single `Receipt.layer` value.** `receipts(layer)` filters on that string; a relabel changes which receipts a layer-scoped operator run executes. That is Rohit's call, recorded in `08-CORRECTION` §8 |

### ⛔ `U03` · the first correctness receipt — an illegal learning transition

| | |
|---|---|
| **what** | a receipt over `learning_transitions (from_state, to_state)` against `contracts/learning.ALLOWED_LEARNING_TRANSITIONS`. `expect(0) is True` — **any** illegal transition is a failure |
| **why** | it is the layer's **first** correctness guard, and it gives `learning_transitions` its **first reader** |
| **artifact** | `genios_engine/platform/receipts.py` + `tests/platform/test_the_learning_loop_is_asked_whether_it_was_right.py` |
| **verify** | `.venv/bin/pytest tests/platform/test_the_learning_loop_is_asked_whether_it_was_right.py -q` |
| ⛔ **measure first** | **can it fail?** `brain_pipeline.py:218` says *"the publisher itself only ever appends there after `persist`"* — if `publisher.log_transition` is the only writer and it validates, the receipt is **structurally 0 forever** and must be REJECTED exactly as `STEP-10` rejected candidates `A` and `D`. ⛔ **But there is a SECOND writer**: `api/learning_routes.py:141` inserts into `learning_transitions` directly, and whether that path validates is the whole question. **Measure the second writer before writing the receipt** |
| **depends on** | `U01` |

> ⛔ *A receipt that cannot fail is not a gate.* If the measurement says the publisher makes an
> illegal transition impossible and the API route validates too, the honest outcome of `U03` is a
> **rejection with its reason recorded** — and that is a complete unit, not a failed one.

### `U04` · the second correctness receipt — a publish outside its governing policy revision

| | |
|---|---|
| **what** | a receipt over `learning_object_evaluations (run_id, policy_revision, result_state, sink_reason)`, joined to `learning_policies`' active revision |
| **why** | gives `learning_object_evaluations` its first reader **and its `_by_run` index its first query** — one of two indexes maintained on every insert for readers that were never built |
| **artifact** | `platform/receipts.py` + the same test module |
| **verify** | same |
| ⛔ **measure first** | whether `policy_revision` on an evaluation row **can** differ from the tenant's active revision. If the orchestrator always stamps the revision it just loaded, this is 0 forever. ⛔ And whether `sink_reason = 'metric_identity_conflict'` is a **failure** or a **correctly-refused duplicate** — the migration lists it beside `no_material_change`, which is plainly not a failure. **A receipt that calls a correct refusal a defect is worse than no receipt** |
| **depends on** | `U03` |

### `U05` · the refusal ledger — a reader, or a declared silence

| | |
|---|---|
| **what** | `learning_input_rejections` gets either a receipt or an entry in a declaration table |
| **why** | ⛔ `record_refusal`'s own docstring: *"A refusal that lives only in a return value is indistinguishable from a candidate the model never produced."* The record was promoted out of a return value into a ledger **with no reader**, so the defect it names still holds one level down |
| **artifact** | `platform/receipts.py` **or** the declaration table from `U06` |
| **verify** | the matching test module |
| ⛔ **measure first** | **is a refusal-rate receipt able to fail?** It needs a denominator — admissions — and `learning_input_rejections` alone does not carry one. If the ratio cannot be computed from the ledgers that exist, the honest outcome is a **declared silence with a mover**, not a receipt built on a join that is not there. ⛔ Also measure: the spend limit has refused every model call since **2026-09-25**, so `DISCOVERY_SEAM` refusals may be the only rows in the table, and a receipt that fires on a known model outage is an alarm for something nobody can fix |
| **depends on** | `U04` |

### ⛔ `U06` · `UNREAD_LEDGERS` — a package declares the tables it writes that nothing reads

| | |
|---|---|
| **what** | `STEP-17`'s shape, generalised from **functions** to **ledgers**: `{table: (why, mover)}` per package, both directions, and **ONE parametrised guard over every package** |
| **why** | ⛔ *A record nobody reads is presence without effect — the reader is half the unit* is doctrine in this programme and has no guard. `feedback/` has four; **the other ten packages have never been measured** |
| **artifact** | `platform/reachability.py` gains the ledger walk; each package's existing `*_health.py` gains the table |
| **verify** | `.venv/bin/pytest tests/platform/test_every_package_says_which_ledgers_nobody_reads.py -q` |
| ⛔ **measure first** | the **engine-wide** count, exactly as `STEP-17` priced 147 → 109 before writing an entry. ⛔ And the reader detection must not repeat **this pass's own method error**: `context/authority_view.py:55` holds `AUTHORITY_TABLE = "authority_rules"` and builds its query from the constant, so a `from X`/`join X` scan reported three readers as one. **A name-constant is a read.** |
| **depends on** | `U03`, `U04`, `U05` — ⛔ **deliberately last**: each of those gives a ledger a reader, so building the declaration first would mean editing it three times, and *a list you must remember to extend is a list that will be wrong* |

### `U07` · the mover convention, and a guard that cannot see a deviation

| | |
|---|---|
| **what** | `feedback_health.py` uses `MOVES WITH`; the convention elsewhere is `MOVES WHEN`. `test_every_entry_carries_a_reason_and_a_mover` only requires *"at least two parts"*, so it passes |
| ⛔ **measure first** | the **distribution across all ten declaration modules**. If `MOVES WITH` appears in several, it is a convention and the guard is right to accept both; if it appears once, it is a deviation |
| ⛔ **the rule** | **Do not weaken the guard to make an entry pass, and do not tighten it to make one fail.** The generic mover check has already failed on two CORRECT tables once, because it demanded two long strings and a `PULL_ONLY` route is eleven characters |
| **artifact** | `feedback/feedback_health.py` **or** the shared guard — the measurement decides which |
| **verify** | `.venv/bin/pytest tests/platform/test_every_package_says_what_it_does_not_call.py -q` |
| **depends on** | — |

### `U08` · the Atlas scorecard reaches L6

| | |
|---|---|
| **what** | `08-ATLAS-SCORECARD-L1-to-L5.md` → `L1-to-L6`, claim by claim, every badge verified against the code |
| **why** | the programme's Step 0 rule: **1 of the first 3 badges spot-checked was wrong**, and the build order rests on the badges. L5 produced 45 claims and **5 superseded badges plus 1 omission** |
| **artifact** | the renamed scorecard |
| **verify** | each row cites a file and line |
| **depends on** | — |

### `U09` · the status lines in this folder

| | |
|---|---|
| **what** | `00-START-HERE.md` says **`COMPLETE`**; `01-CROSSCHECK`'s addendum says *"87 tests"*; the file says *"53 tests"*; the directory runs **60 passed, 27 skipped** |
| ⛔ **why it is not cosmetic** | `01-CROSSCHECK`'s own addendum warns that *"a reader scanning for status reads that line as current, and this programme has now paid for that mistake three separate times."* **This folder then did it again, in the file a reader opens first** |
| ⛔ **the rule** | L5's `STEP-11` was planned as *"a document correction, not code"* and the full suite caught a `tests/executive/` failure the targeted runs never touched. **Run the full suite anyway** |
| **verify** | `.venv/bin/pytest -q` |
| **depends on** | `U01` (the real count comes from it) |

### `U10` · a stale comment in `scripts/`

| | |
|---|---|
| **what** | `wipe_org_data.py:40` says the old exclusion *"omits MATERIALIZED views — `counterfactual_ledger` (0072) slipped through."* `0072` creates a **plain** view and states why it is not materialised |
| **severity** | low — the fix the comment justifies (select base tables positively) is correct regardless. Only the **reason** is wrong |
| ⛔ **why it is a unit at all** | *Noticed something adjacent? New unit, not a silent fix.* And *a stale comment reads as a measurement* — sixth instance |
| **verify** | `.venv/bin/pytest tests/ -q -k wipe` then the full suite |
| **depends on** | — |

---

## 2 · ⛔ What is NOT in this plan, and who owns it

| | Owner | Why not mine |
|---|---|---|
| the eleven **Wrong** reasons — all eleven shown, or four groups? | **Rohit** | a product judgment about a founder's experience. The vocabulary is right; what is *displayed* is a one-line surface change |
| relabelling the receipts | **Rohit** | `receipts(layer)` filters on the label; a relabel changes operator behaviour |
| whether each unread ledger is **deliberate** or **a reader never built** | **Rohit** | three of four read as the latter, and ⛔ **declaring one deliberate without asking would invent a reason** — the exact defect `contract_health.py` was corrected for on 2026-10-02 |
| the 27 skips, if they turn out to need a database | **Harsh** | joins `H6`: `pytest tests/test_delivery_spine.py -q` where a DB exists |
| the spend limit vs `GENIOS_L4_LLM_DECISION_MAKER` | **Rohit** | `DECISION #5`. ⛔ It is also what makes `U05`'s receipt an alarm nobody can act on |

---

## 3 · Doctrine this plan is built on

| Rule | Where it was paid for |
|---|---|
| ⛔ **a receipt that cannot fail is not a gate** | `STEP-10` rejected two of five candidates for it; `U03` and `U04` are gated on it |
| ⛔ **establish the baseline, or the harness is theatre** | `STEP-14`'s mutation harness reported a survivor as caught; `U01` exists only for this |
| ⛔ **a record nobody reads is presence without effect — the reader is half the unit** | `U03`–`U06` are all this rule |
| ⛔ **a list you must remember to extend is a list that will be wrong** | why `U06` is last |
| ⛔ **a name-constant is a read** | found inside this pass, when `authority_rules` read as 1 reader and has 3 |
| **a guessed reason is decoration and a guessed severity is worse** | why three ledger decisions are Rohit's |
| **do not weaken a verify to make it pass** | `U07`, in both directions |

---

## 4 · Stop here

This file is the plan. ⛔ **Nothing is built until it is confirmed** — this is the cheapest moment
to change the shape, and the last one before code exists.
