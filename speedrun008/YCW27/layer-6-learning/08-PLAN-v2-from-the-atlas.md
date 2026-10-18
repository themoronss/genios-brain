# L6 · PLAN v2 — derived from the Atlas, not from the ledgers

**Date:** 2026-10-02 · **Owner:** me · **Milestone:** `M14.C2`
**Supersedes the spine of** [`06-PLAN-the-second-pass.md`](06-PLAN-the-second-pass.md) — that file
is kept because it is the record, and three of its units are retracted in writing.
**Derived from** [`07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md`](07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md).

---

## 0 · Why there is a v2

⛔ **v1 was built from the evidence I had measured instead of from the specification that already
existed.** Running the Atlas check first retracted three of its units and found two defects v1 did
not contain — one of them a durable brain row written from a short-horizon score, auto-promoted,
with no human in the loop, breaking an authority boundary the Atlas names for that exact unit.

> ⛔ **A plan derived from the code alone cannot find a gap the code is silent about.**

```
  11 Atlas architecture gaps
   5 CLOSED            #2 (by refutation, S4) · #7 · #8 · #9 · #10 (S3)
   3 PARTLY CLOSED     ⛔ #1 NARROWED by S5 — the inbox exists and is FED; the `kind` is missing
                       #4 population caps · #11 the ADAPTIVE residue
   0 ⛔ LIVE            ⛔ #2 CLOSED by S4 (2026-10-02) — by REFUTATION, not by building
   3 not measured      #3 outcome reconciliation · #5 permitted-use · #6 company reset
```

---

## 1 · The order, and the one unit that needs no decision

```
  S1 ─ the guard            ✅ DONE 2026-10-02 · 27 tests · 4/4 mutations caught
  S2 ─ the stale value_state  ✅ DONE 2026-10-02 · 18 tests · 6/6 mutations caught
                              ⛔ planned as a comment fix; became the sharpest PRODUCT finding
                              ⛔ the North Star ledger has never had a writer
  S3 ─ the policy fail-open   ✅ DONE 2026-10-02 · 40 tests · 8/8 mutations caught
                              ⛔ Atlas gap #10 CLOSED · F23 (a fail-OPEN on an authority list)
                              ⛔ F24 — the fail-closed and its READER shipped as one unit
  S4 ─ _cohort_candidate      ✅ DONE 2026-10-02 · 23 tests · 8/8 mutations caught
                              ⛔ Atlas gap #2 CLOSED **BY REFUTATION** — the components are built
                              ⛔ one package down; the stub outlived its replacement by a month
  S5 ─ the two stub units     ✅ DONE 2026-10-02 · 27 tests · 8/8 mutations caught
                              ⛔ "Empty until the inbox lands" was STALE — the inbox landed, is
                              ⛔ written in production, loaded into every batch, consumed by NOTHING
                              ⛔ + the layer's FIRST correctness receipt
  S6 ─ the unread ledgers     ✅ DONE 2026-10-02 · 46 tests · 9/9 mutations caught
                              ⛔ NOT monitoring — two of the four were recording a LIVE defect:
                              ⛔ three discarded refusal reasons, and governed → published, which
                              ⛔ the contract forbids, on EVERY brain publish. U03 un-retracted
  S7 ─ guards per package     ✅ DONE 2026-10-02 · 20 + 55 tests · 9/9 + 8/8 mutations
                              ⛔ the ratio was already in org_rule_discovery_runs.counters; the gap
                              ⛔ was the OTHER writer — a quarantined seam read as an empty one
                              ⛔ + the delivery seam was degraded on EVERY run (a getattr typo)
                              ⛔⛔ + the derived count points at context/, not deliver/
  S8 ─ the Atlas scorecard     ✅ DONE 2026-10-02 · L1-to-L5 → L1-to-L6 · 45 → 56 claims
                              ⛔ 4 EXPIRED · 4 PARTLY · 3 still true — and FOUR cells hid a
                              ⛔ defect the Atlas did not name. "L1-to-L7" above was my own
                              ⛔ instance of the collision: this scorecard numbers deliver/ as L5
  S9 ─ the paperwork           ✅ DONE 2026-10-02 · +10 tests · 2/2 mutations caught
                              ⛔⛔ F17 RETRACTED — MOVES WITH is in 9 of 13 modules, a CONVENTION.
                              ⛔ The gate stopped me tightening a guard onto 29 correct entries
                              ⛔ The 104 guards: the RULE (tests/README.md), not 78 rewrites
  S10 ─ Atlas #3 #5 #6        ✅ DONE 2026-10-02 · the LAST · 69 tests · 27/27 mutations caught
                              ⛔⛔ 0 of 11 Atlas gaps now UNMEASURED — and none of the three
                              ⛔ became CLOSED: each has one clause left, all three Rohit's
                              ⛔⛔ #3's real finding: recommendation_learning's ADAPTIVE path is
                              ⛔ unreachable by ARITHMETIC, and the obvious repair opens it
                              ⛔ #5 the enforcement is PROVEN; the rendered surface is unreached
                              ⛔ #6 the reset propagates further than the Atlas credits; the
                              ⛔ latest_reset_at declaration was MINE and wrong
                              ⛔ FOUR of my own guards needed repair, found by mutation
```

> ⛔ **The block above was cleaned on 2026-10-02 and it had rotted the way the `19-PENDING` table
> did.** Eight steps of incremental edits each replaced their own line and appended the next, and
> the v1 lines for `S3` and `S9` were never removed — so the order block listed `S3` as *"fail-
> CLOSED; the docstring already promises it"* three steps after it was DONE, and `S9` twice. ⛔ One
> line also carried a doubled `← next`. *A list edited one line at a time accumulates the lines
> nobody edited* — and this is the second document in the pass to need rebuilding rather than
> patching (see `F33`).

---

## 2 · ⛔ `S1` · a unit may not route a measurement into a durable brain

| | |
|---|---|
| **the finding** | four sibling units emit rates and counts to `METRICS`; `unit_recommendation_learning` emits `success_rate_bp`, `attention_per_outcome_bp`, `efficacy_bp` to **`ADAPTIVE`** — the one durable brain target with no expiry contract — and `govern()` auto-promotes it with no human |
| **why it is not cosmetic** | `packs/compiler/runtime_brains.py:497` reads `brain in ('organization','behavior','adaptive')` **into the compiled expertise package.** The Atlas's authority boundary for this unit is **"No self-training from recommendation score."** The score is published into a brain the recommender then reasons from |
| ⛔ **what I will NOT do** | **retarget the unit, add a TTL to `ADAPTIVE`, or forbid its publication.** All three change what the Adaptive brain contains, which changes compiled packages. Those are Rohit's, written up in the Atlas check §2 |
| **what I WILL do** | a declaration + guard: **which unit may target which brain, and why** — so a new unit cannot route a measurement into a durable brain without failing the build. ⛔ **Additive, reversible, and it holds the finding as data rather than as a paragraph** |
| **artifact** | `genios_engine/feedback/target_policy.py` + `tests/feedback/test_a_unit_may_not_write_a_durable_brain_from_a_measurement.py` |
| **verify** | `.venv/bin/pytest tests/feedback/test_a_unit_may_not_write_a_durable_brain_from_a_measurement.py -q` then the **full suite** |
| ⛔ **measure first** | the ten units' `(unit, target)` pairs read from the **AST**, not from a grep — `grep target=LearningTarget` already found nine of ten and missed the one routed through `_cohort_candidate`'s keyword argument. **A grep for a keyword argument misses the call that passes it through** |
| **depends on** | — |

⛔ **The guard asserts the SET of `(unit, target)` pairs, not a count** — *a membership list shrinks
every time the work succeeds; an invariant does not*, and this programme broke three tests on
correct code learning that.

## 3 · ✅ `S2` · the value the product withholds for a ledger that exists — **DONE**

> ⛔ **The measure-first gate paid for itself twice.** Gate 1 (*does anything branch on the
> literal?*) said no — the rename was safe. Gate 2 (*what would actually carry money?*) moved the
> unit from a comment fix to **F21**: `macv_ledger`, *"the North Star … the number the customer can
> verify"*, appears five times repo-wide and **the only code that touches it deletes it.**
> → [`STEP-S2-DONE-the-north-star-has-no-writer.md`](STEP-S2-DONE-the-north-star-has-no-writer.md)

| | |
|---|---|
| **what** | `api/intelligence_routes.py` returns `value_recovered_inr: None` and `value_state: "unavailable_no_counterfactual_ledger"`, and comments that the ledger *"(L7-12) … does not exist"* |
| **what is true** | `migrations/0072_counterfactual_ledger.sql` **creates it**, it joins signal → card → events → verdict → delivery → execution → outcome → spend, and it carries a production receipt asserting the join reaches end to end. Atlas gap **#7 is CLOSED** |
| ⛔ **what I will NOT do** | **invent a value.** The view carries `outcome_label`, `seconds_to_close`, `llm_calls`, `input_tokens`, `output_tokens` — ⛔ **no monetary column.** `value_recovered_inr: None` is the right answer; only the **reason** is false. *The fix for a wrong reason is the reason, not the answer* |
| **artifact** | the comment and the `value_state` string |
| **verify** | targeted test on the handler, then the full suite |
| ⛔ **measure first** | whether any caller branches on the literal `"unavailable_no_counterfactual_ledger"`. ⛔ **A string a client matches on is an API contract**, and renaming it is a breaking change dressed as a comment fix |
| **depends on** | — |

## 4 · ✅ `S3` · a malformed policy block list must block the run — **DONE**

> ⛔ **The plan called this "contained". It was, and the containment was the hard part.** Five
> units bottom-up: the contract (make the absence representable) → the loader (report WHICH case) →
> `preflight` (the gate all three producers share) → `run_learning` (⛔ **before** the weekly claim,
> because a fail-closed after it converts a policy problem into a lost week) → ⛔ **the sweep's
> reader**, without which the refusal would have been a silent stop.
> → [`STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md`](STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md)

| | |
|---|---|
| **what** | `orchestrator._as_tuple` returns `()` for `None` **and for any non-list value**, while its docstring says it is *"refusing to silently invent an empty one"* and that treating a NULL as *"nothing is blocked"* is *"the failure mode this whole field guards against"* |
| **the Atlas's required repair** | *"unknown/malformed policy fields **block the run** rather than defaulting to permissive empty tuples"*, with acceptance evidence: *"round-trip fixtures prove both block lists survive seed/load/restart and preflight rejects the exact target/prefix under the loaded revision"* |
| ⛔ **the honest reading** | `_as_tuple` **cannot** implement its own docstring: it receives only the value, so it cannot tell *"the tenant authored a revision and the column is NULL"* from *"this is the seeded default."* **The docstring promises a behaviour the signature makes impossible** — the fix belongs at the caller, which knows the revision |
| ⛔ **severity** | the comment in the `SELECT` says it is *"latent rather than live only because nothing can write them yet; the moment a policy-write surface exists it becomes a silent authority hole."* ⛔ **A comment is not a measurement** — confirm no writer exists before filing it as latent |
| **artifact** | `genios_engine/feedback/orchestrator.py` + a round-trip test |
| **verify** | `.venv/bin/pytest tests/feedback -q` then the full suite |
| **depends on** | `S1` |

## 5 · ✅ `S4` · `_cohort_candidate` returns `[]` — ⛔ **and the gap was a wrong conclusion**

> ⛔⛔ **The gate said "build, or DECLARE" and the answer was neither at first: MEASURE WHERE THE WORK IS.** `packs/brains/` is the supply side; `brain_pipeline_proposals` appends both components into the same weekly run. The stub predates the real implementation by a month. **Atlas gap #2 is CLOSED by refutation.** → [`STEP-S4-DONE-a-silent-unit-names-its-producer.md`](STEP-S4-DONE-a-silent-unit-names-its-producer.md)

| | |
|---|---|
| **what** | `units.py:390-391` — the entire body is `return []  # derived candidates require a stable parent cohort; wired as cohorts accumulate`. `unit_behavior_evolution` and `unit_adaptive_evolution` both delegate to it, so **direct personalization evolution emits nothing** |
| ⛔ **why it is worse than the Atlas found it** | the Atlas saw two units returning `[]`. The stub has since moved into a **shared helper**, so both call sites now *look wired*. ⛔ **I was one step from recording this as CLOSED from the call site alone** |
| ⛔ **measure first** | what `feedback/store.load_batch` actually puts in a `LearningBatch`, and whether a stable parent cohort is derivable from it **today**. ⛔ **If it is not, the honest outcome is a DECLARED SILENCE with a mover, not a build** — exactly how L5 filed twelve un-cut-over functions |
| **artifact** | `units.py` **or** `feedback_health.py` — the measurement decides which |
| **verify** | `.venv/bin/pytest tests/feedback -q` then the full suite |
| **depends on** | `S3` |

## 6 · ✅ `S5` · the two units that are still `[]` on purpose — **DONE**

> ⛔⛔ **The plan said "a declared silence, not a build" and both halves turned out to be wrong in
> the same direction.** *"Empty until the inbox lands"* was **stale**: `learning_event_inbox`
> (0046) exists, is written in production by `reason/moments/store.record_feedback` (via
> `api/moment_routes.py:746`), is loaded into **every** weekly batch, and **no unit consumes it**.
> ⛔ **The gap is a `kind`, not a table** — a table is a migration, a `kind` is a SURFACE. And it
> was not only a declaration: `inbox_unconsumed` got a reader, the layer's **first correctness
> receipt.** → [`STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md`](STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md)

`unit_preference_learning` and `unit_temporary_memory` both `return []` with *"Empty until the inbox
lands."* ⛔ **A declared silence, not a build** — the structured preference inbox is a surface that
does not exist, and *a function that names the reader it does not have is a surface that was never
built.* Entry per unit in `feedback_health.py`, with a mover.
**depends on** `S4`.

## 7 · `S6`–`S10` · unchanged from v1, and all AFTER the Atlas work

| | |
|---|---|
| ⛔ ✅ **`S6`** | **DONE** — ⛔ **"demoted to monitoring" was wrong.** Asking each ledger *"what question would you answer?"* found **two live defects**: the no-silent-drop contract broken in nine lines, and `governed → published` — an edge `ALLOWED_LEARNING_TRANSITIONS` forbids — written on **every brain publish**, unvalidated, into the one ledger nothing reads. ⛔ **`U03` is un-retracted**: *a retraction needs its own measurement, not a neighbouring one.* → [`STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md](STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md) |
| ~~`S6` (as planned)~~ | ⛔ **demoted from v1's spine to monitoring.** `learning_input_rejections` still has no reader and `record_refusal`'s docstring still states the defect. ⛔ **`S5` gave a FIFTH unread thing a reader** (`learning_runs.counts`), so the pattern and the method are both established |
| ⛔ ✅ **`S7`** | **DONE.** ⛔ The ratio was already in `org_rule_discovery_runs.counters`; the gap was the ledger's **other** writer — `store._read_optional_seam` quarantines a failed read and returned `()`, so a lost seam read as an empty one (`L7-29`). ⛔ **And the delivery seam was reported degraded on EVERY run** because `getattr(batch, "deliveries", ())` names a field that does not exist. ⛔⛔ **The derived count points at `context/`** — 50,877 lines, two guards, 5.4× worse than the figure that triggered `STEP-10`. → [`STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md](STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md) |
| ~~`S7` (as planned)~~ | guards per package becomes data (v1's `U02`). ⛔ Sharpened: the collision is **two vocabularies in one field, mixed inside a single commit** — `944b4f76` *"seven layers"* vs `22d598b1` *"six product layers"*, and I added three more under the wrong one |
| ⛔ ✅ **`S8`** | **DONE** — `08-ATLAS-SCORECARD-L1-to-L5` → **`-L1-to-L6`**, 45 → **56** claims. ⛔ **The `L1-to-L7` in this row was my own instance of the collision**: this scorecard numbers `deliver/` as L5, so the learning layer is **L6** here, while the source matrix labels the same rows `L7 Learning`. 4 EXPIRED · 4 PARTLY · 3 still true, and ⛔ **four cells hid a defect the Atlas did not name** |
| ⛔ ✅ **`S9`** | **DONE.** ⛔⛔ **`F17` is retracted as my own false finding** — `MOVES WITH` appears **29 times across nine of thirteen** declaration modules against 115 `MOVES WHEN`: a convention, not a deviation, and the gate *"measure the distribution before touching either side"* stopped me tightening a guard onto 29 correct entries. A third form DID exist and is now impossible. ⛔ **The 104 guards got the RULE, not 78 rewrites** — a resolver meant to find each guard's target file resolved **1 of 104**, so the at-risk subset is not statically knowable; `tests/README.md` carries the rule. `F16` and `F18` closed. → [`STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md](STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md) |
| ~~`S9` (as planned)~~ | the status lines · the `MOVES WITH` guard hole · `scripts/wipe_org_data.py:40` · ⛔ **WIDENED by `F22`: 104 source-text phrase-absence guards share the shape that failed in `S2`.** Every one is structurally vulnerable — a comment documenting the forbidden thing fires the guard on correct code. ⛔ *"104 broken guards" would be an overstatement*: which are actually at risk needs 104 readings. The mitigation is `S2`'s — **assert attribution, not presence** |
| `S10` | ⛔ Atlas **#3** (outcome reconciliation), **#5** (permitted-use propagation), **#6** (company reset) — **three gaps nobody in this programme has measured.** They are named here so they are not quietly dropped |

---

## 8 · ⛔ What v1 got wrong, in writing

| v1 unit | Fate |
|---|---|
| `U03` an illegal learning transition | ⛔ **RETRACTED.** Derived from a ledger, not a named gap — and its gate question is answered by Atlas `#9`: the second writer of `learning_transitions` **is** the repaired approval path |
| `U04` a publish outside its policy revision | ⛔ **RETRACTED as written.** The real policy defect is `#10`'s residue, now `S3` |
| `U05` the refusal ledger | **KEPT, demoted** to `S6` |
| `U01` the 27 skips | ✅ measured, Harsh's (`H7`) |
| `U02`, `U06`–`U10` | ✅ kept as `S7`–`S9` |

---

## 9 · Rohit's, and why each one is his

| | Why it is not mine |
|---|---|
| ⛔ the Adaptive durable path — TTL, prohibit, or retarget to `METRICS` | all three change what the Adaptive brain contains, and the pack compiler reads it into the compiled package |
| ⛔ one read-only query | `select brain, count(*) from learned_brain_entries group by brain` inside `set transaction read only` — it is the only way to know the **production** blast radius of the above |
| the eleven *"Wrong"* reasons | a product judgment about a founder's experience |
| relabelling the receipts | `receipts(layer)` filters on the label |
| whether each unread ledger is deliberate | ⛔ declaring one deliberate without asking would invent a reason |

## 10 · Doctrine this analysis produced

| Rule | What it cost |
|---|---|
| ⛔ **a plan derived from the code alone cannot find a gap the code is silent about** | three invented units |
| ⛔ **a call site that looks wired is not a wired call site** | `_cohort_candidate` — one step from a false CLOSED |
| ⛔ **a call site that looks DEAD is not a dead feature** | ⛔ the mirror, and it cost TWO readings: the Atlas's and mine |
| ⛔ **a grep hands over a sentence without its subject** | *"NOTHING wires this adapter today"* was true about the LLM labeler |
| ⛔ **a guard that stops at a package boundary catches nothing across it** | `S1` guarded eleven units and not the two producers |
| ⛔ **an invalid mutation is not a surviving mutation** | `S4`'s `M2` was dead code, not a stub |
| ⛔ **a claim about CODE must be checked against the AST, not the text** | ⛔ `S5` — the third instance of this class in one session, and an attribution window would have been the WRONG tool |
| ⛔ **a docstring that explains a gap contains the words of the gap** | — |
| ⛔ **the gap is a `kind`, not a table** | a table is a migration; a `kind` is a surface |
| ⛔ **a gate that is always red is a gate nobody reads** | `receipts.py`'s own rule — so guard the visibility, not the known drop |
| ⛔ **a retraction needs its own measurement, not a neighbouring one** | ⛔ `S6` — `U03` was retracted on a fact about a DIFFERENT writer. Fifth retraction, first of a retraction |
| ⛔ **a counted refusal is not a named refusal** | the Atlas's no-silent-drop contract, broken in nine lines |
| ⛔ **derive the legal set from the contract** | a copied pair list drifts in the permissive direction |
| ⛔ **never weaken a verify to make it pass** | now enforced by three tests, not remembered — mutation `M6` |
| ⛔ **a guard at the writer protects the future and says nothing about the past** | hence the receipt beside the fix |
| ⛔ **a flag that is always set is a flag nobody reads** | ⛔ `S7` — the delivery seam was degraded on every run, forever |
| ⛔ **a `getattr` with a default converts a wrong attribute name into a plausible value** | on a dataclass it would have raised immediately |
| ⛔ **a test double that cannot fail the way production fails is a test that proves nothing** | `S7`'s `M4` survived because the double was kinder than PostgreSQL |
| ⛔ **a stale `__pycache__` makes a restored file read as the mutant** | ⛔ bias toward FALSE KILLS; all seven harnesses re-verified with caching off |
| ⛔ **a declared silence that fails the build when it stops being true is the only kind worth writing** | `S6`'s test failed on cue when `S7` gave its ledger a reader |
| ⛔ **measure the distribution before calling one instance a deviation** | ⛔ `S9` — `F17` was my own false finding, refuted by its own gate |
| ⛔ **a resolver that answers for 1 of 104 answers nothing** | check a resolver's COVERAGE, not only its output |
| ⛔ **a hardcoded count in a document is wrong the next day** | date it, or point at the command |
| ⛔ **a real fix with an invented reason is the harder stale comment to notice** | the code around it is correct |
| **the rule, not the rewrite** | 78 mechanical conversions with no measured defect is speculative work |
| ⛔ **a grep for a keyword argument misses the call that passes it through** | nine of ten units found; the tenth routed its target through a helper |
| ⛔ **a file's NAME can be the counter-evidence** | `adaptive_lease.py` narrowed gap #11 from *unrepresentable* to *one producer* |
| ⛔ **the fix for a wrong reason is the reason, not the answer** | `value_recovered_inr: None` is correct; its `value_state` is not |
| ⛔ **a string a client matches on is an API contract** | why `S2` measures before renaming |
| **a docstring can promise a behaviour the signature makes impossible** | `_as_tuple` |
