# L6 · ATLAS CHECK — Layer 7 Learning, claim by claim

**Date:** 2026-10-02 · **Source:** `Rohit_Updates/Secret War Updates/07-Layer-7-Learning-Atlas-6/`
(six documents, 624 lines) · **Checked against:** the working tree, not `harsh/mvp@b739bd5`

> ⛔ **This document should have come FIRST and it did not.** My
> [`06-PLAN-the-second-pass.md`](06-PLAN-the-second-pass.md) put the Atlas check at `U08`, near the
> end, and derived its units from the **ledgers** instead. The programme's Step 0 rule is the
> opposite: *verify every badge claim by claim before building, because the build order rests on the
> badges.* Running that check first **retracted three of my own units and found two live defects I
> had not seen.**

---

## 0 · The numbering, settled by the Atlas itself

The Atlas document's own first line:

> *"Numbering: this is current code **Layer 7** (`feedback/`) and **Atlas Layer 6**. 'Layer 6' in
> Atlas quotations below does not mean the current `deliver/` package."*

⛔ **So the receipt labels were never drifted** — `L6` = `deliver/` and `L7` = `feedback/` is the
engine vocabulary that `genios_engine/LAYERS.py` codifies, and `944b4f76` *("close 97 of 106
audited gaps across all **seven** layers")* used it consistently. What introduced the collision is
`22d598b1` *("align all **six** product layers — L1 to L6")*, which added receipts under the
**Atlas** numbering into the same field — and ⛔ **I then added three more**, following `lane`'s
label instead of the file's dominant vocabulary. See
[`../layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`](../layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md),
whose §3 is sharpened by this: **two vocabularies in one field, mixed inside a single commit.**

---

## 1 · The Atlas's eleven architecture gaps, verified

| # | Atlas gap | Verdict | Evidence |
|---|---|---|---|
| 1 | *canonical verdict input is missing* — feedback, preference and temporary-memory units explicitly empty | ⚠️ **PARTLY CLOSED** | `unit_feedback_learning` is **built** and reads `card_feedback_verdicts`, with its own note that returning `[]` would have discarded *"the FIRST verdict a human ever gives"*. ⛔ `unit_preference_learning` and `unit_temporary_memory` still `return []` — *"Empty until the inbox lands"* |
| ⛔ **1 · NARROWED 2026-10-02 by `S5`** | — | ⚠️ **PARTLY — and the residue is a `kind`, not a table** | ⛔ `learning_event_inbox` (0046) **exists, is written in production** by `reason/moments/store.record_feedback` (via `api/moment_routes.py:746`), **is loaded into every weekly batch**, and ⛔ **no unit consumes it** — `run_learning` counts the drop as `inbox_unconsumed`. Every row carries `payload.kind == "moment_feedback"`. **A table is a migration; a `kind` is a SURFACE**, and there is none. Everything downstream of `unit_temporary_memory` is built. ⛔ **The surface is Rohit's, and it is the Atlas's own P1.** → [`STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md`](STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md) |
| 2 | *direct personalization evolution is missing* — the Behavior/Adaptive cohort builder returns no proposals | ⛔⛔ **LIVE — and now less visible than the Atlas found it** | `units.py:394-405` the two units **look wired**; they delegate to `_cohort_candidate`, whose entire body is `units.py:390-391` → `return []`. **I was one step from recording this as closed from the call site alone** |
| ⛔⛔ **2 · CLOSED 2026-10-02 by `S4`, BY REFUTATION** | — | ✅ **CLOSED** | `packs/brains/__init__.py`: *"This package is the **supply side**."* `behavior_distill.distill` (776 lines) → `BEHAVIOR` and `adaptive_lease.lease_proposals` (301 lines) → `RUNTIME`, both appended to the same weekly run by `brain_pipeline.brain_pipeline_proposals`, each inside a savepoint. ⛔ **The stub (`365cf7a6`, 2026-08-08) predates the implementation (`ed1b10c3`, 2026-09-07) by a month.** ⛔ And the row above is itself a wrong conclusion: *"one step from recording this CLOSED"* — **it IS closed.** → [`STEP-S4-DONE-a-silent-unit-names-its-producer.md`](STEP-S4-DONE-a-silent-unit-names-its-producer.md) |
| 3 | *outcome truth is fragmented* | ⚠️ **partly** | see `#8`; a full reconciliation measurement is not yet done |
| ⛔⛔ **3 · MEASURED 2026-10-02 by `S10`** | — | ⚠️ **PARTLY CLOSED — 2 of 3 clauses, and the third is not this layer's** | ✅ *"same external event counted once"* is **forbidden by the database**: `migrations/0041:248` `unique (org_id, execution_id)`, named `execution_outcomes_once` and commented in Layer 7's own words — *"a second row would double-count it in every precision calculation Layer 7 runs."* ✅ *"unknown stays neutral"* — `label_class`/`counts_against_the_play`, one table, `graded = succeeded + failed`. ⛔ *"correction retracts derived proposal"* — **no durable proposal is derived from a correction**: every unit reading `card_feedback_verdicts` targets `METRICS`. Blocked behind `#1`. ⛔⛔ **AND THE REAL FINDING: `unit_recommendation_learning` pins `evidence.distinct_days=1` against a default floor of 2, and `validate_learning` runs BEFORE `preflight`/`govern` and short-circuits — so §2's declared authority violation is UNREACHABLE, and the obvious repair opens it.** → [`STEP-S10-DONE-the-three-unmeasured-gaps.md`](STEP-S10-DONE-the-three-unmeasured-gaps.md) |
| 4 | *population-aware confidence is incomplete* — one-person companies need higher repetition | ⚠️ **PARTLY CLOSED** | `min_distinct_entities` now exists on `LearningPolicy`, is stored (`0045`) and **is loaded** (`orchestrator.load_or_seed_policy`). The *caps* the Atlas asks for are not there |
| 5 | *permitted-use enforcement is unproven* | ❓ **not measured** | `VisibilityScope` and `visibility.principals` are enforced in `governance.preflight`; cross-layer propagation into rendering is unmeasured |
| ⛔ **5 · MEASURED 2026-10-02 by `S10`** | — | ⚠️ **PARTLY CLOSED — the enforcement is PROVEN, the residue is UNREACHED** | ✅ The DECISION path enforces it: `runtime_brains._visibility_allows_package` is wired into a live exclusion and requires scope narrowness **and** `set(package.principals) <= set(entry.principals)` — the whole audience. `contracts/learned_state._visible` is fail-closed including an UNKNOWN scope. ⛔ `api/brain_routes` renders the VALUE of both sinks with no principal check behind an org-only dependency that admits a `member` seat — **safe only because all three durable producers declare `Visibility(scope=ORGANIZATION)`**; the one PRIVATE `LearningObject` targets `METRICS`. Declared as a PAIR, guarded both ways, plus receipt **41** for the approval path that rehydrates visibility from the database. ⛔⛔ And the bijection `VisibilityScope` ↔ `contracts/visibility.SCOPES` was **unguarded** — `runtime_brains` records the last failure of that shape as *"A SILENT TOTAL LOSS."* **The route's seat principal is Rohit's.** |
| 6 | *company reset is partial* | ❓ **not measured** | `feedback/reset.py` exists (`apply_organization_reset`, 3 external callers) |
| ⛔ **6 · MEASURED 2026-10-02 by `S10`** | — | ⚠️ **PARTLY CLOSED — and the reset propagates FURTHER than the Atlas credits** | ✅ Runtime leases expired, durable rows untouched — both measured off the statement. ✅ ⛔ **`deliver/outbox.py:1050-1068` reads the latest reset at SEND time and cancels any card built before it**, same connection and locks as the authority re-proof, fail-closed-to-send. ⛔ Two of the three callers are **seat lifecycle, not pivots** — and both justify it in writing (*"a memory formed under a wrong 'us' set was formed about the wrong world"*), so that candidate **retired before it was written down**. ⛔⛔ The finding was MINE: `feedback_health`'s declaration said `latest_reset_at` was *"a surface that was never built"* — **the reader exists one layer DOWN and may not import upward**, so the query is reimplemented there and the duplication is FORCED. ⛔ *"fails promotion"* is unimplemented and now guarded. **Rohit's.** |
| 7 | *outcome causality remains weak* — needs exposure, action, external result, window, counterfactual | ✅ **CLOSED** | `migrations/0072_counterfactual_ledger.sql` joins **signal → card → card_events → verdict → delivery → execution → outcome → llm_costs**, one row per recommendation, and carries a production receipt |
| 8 | *product truth diverges from stored truth* — the stats endpoint says zero outcomes | ✅ **CLOSED**, ⛔ with a stale reason left behind | `intelligence_routes.py:771-773` counts `execution_outcomes` for real, and `acted` carries a fix comment: the old predicate matched `kind in (…)` while every writer puts those values in `cause` — *"it would have read as 'the learning loop still is not working' long after it was."* ⛔ **But the same handler still returns `value_state: "unavailable_no_counterfactual_ledger"` and comments that the ledger *"does not exist"* — `0072` creates it and `#7` is closed** |
| 9 | *human approval is not publication* — approval records `promoted` without calling `publish_brain` | ✅ **CLOSED** | `api/learning_routes.py` — *"APPROVAL MUST PUBLISH. Renaming the row to `promoted` and stopping there left the object approved-but-unpublished… A reviewer who approves has every reason to believe the system now knows something — and it did not."* `_publish_approved(...)` runs **in the same transaction**, plus the `authority_rules` projection |
| 10 | *loaded policy is weaker than stored policy* — the active query drops `blocked_targets` and `blocked_subject_prefixes` | ⚠️ **PARTLY CLOSED — and the residue is a fail-OPEN** | The `SELECT` now loads both, with a comment that omitting them meant *"a tenant's 'never learn about these targets' list was loaded as empty on every run."* ⛔ **But `_as_tuple` returns `()` for `None` AND for any non-list value**, while its own docstring says it is *"refusing to silently invent an empty one"* and that treating a NULL as *"nothing is blocked"* is *"the failure mode this whole field guards against."* **The docstring describes behaviour the function does not have** |
| ⛔ **10 · CLOSED 2026-10-02 by `S3`** | — | ✅ **CLOSED** | the absence is now representable (`LearningPolicy.prohibitions_state`), refused at **two** gates (`preflight` for all three producers, `run_learning` **before the weekly claim**), and `_as_tuple` is gone. 40 tests · 8/8 mutations → [`STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md`](STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md) |
| 11 | *Adaptive short-horizon semantics are unrepresentable* | ⚠️⛔ **PARTLY CLOSED — and the residue is ONE producer** | ⛔ the Atlas's own **option B is already built**: `packs/brains/adaptive_lease.py` routes timing verdicts through the **RUNTIME** target to `temporary_memories` with a 7-day TTL clamped to `max_runtime_ttl_seconds`, enforced three ways. The residue is `unit_recommendation_learning` → durable `ADAPTIVE`. §2 |

```
  11 Atlas architecture gaps  —  ⛔⛔ AS OF `S10`, NONE IS UNMEASURED
   5 CLOSED            #2 (⛔ by REFUTATION, S4) · #7 · #8 · #9 · #10 (S3)
   3 PARTLY CLOSED     ⛔ #1 NARROWED by S5 — the inbox EXISTS and is FED; the missing thing is a
                          `kind`, i.e. a SURFACE. Rohit's, and the Atlas's own P1
                       #4 population caps · #11 the durable ADAPTIVE residue — ⛔ Rohit's
   0 ⛔ LIVE            — ⛔ none. No Atlas Layer 7 gap is fully live any more
   0 not yet measured  ⛔⛔ #3 · #5 · #6 MEASURED BY `S10`, and all three land PARTLY CLOSED
```

⛔ **`S10` closed no gap, and that is the result rather than a shortfall.** Each of the three has
exactly one clause left, and every one of them is a decision rather than a defect: the correction
SURFACE (`#3`, behind `#1`), the route's seat principal (`#5`), and whether a pivot should block
promotion (`#6`). ⛔ **The programme's remaining Layer 7 work is six PARTLY rows whose residues are
all Rohit's** — which is a different state from "three things nobody has looked at".

⛔ **Three of eleven were already fixed, and one of those (#9) is the exact finding I had reached
independently from the other side** — `api/learning_routes.py:141` as the *second writer* of
`learning_transitions`. It is the second writer **because the approval path was repaired**. *Two
findings that meet from opposite directions are one finding.*

---

## 2 · ⛔⛔ The sharpest live defect — and my first version of it was overstated

> ⛔ **CORRECTED INSIDE THIS PASS.** I first wrote that Adaptive TTL is *"unrepresentable, LIVE,
> reachable and auto-promoting"* — the Atlas's own framing. Then I read a file whose **name** is
> the counter-evidence: `packs/brains/adaptive_lease.py`. **A lease has an expiry by definition**,
> and that module implements the Atlas's option B in full. **Fifth time this discipline has caught
> me, and the correction makes the finding narrower and much harder to argue with.**

### ⛔ What is already right, and it is excellent

`packs/brains/adaptive_lease.py` routes a `bad_timing` card verdict through the **`RUNTIME`**
target, which `govern()` sends to `TEMPORARY` and `publish_runtime` writes to
`temporary_memories` — the one store whose `expires_at` is `NOT NULL`:

```
LEASE_TTL_SECONDS = 7 * 24 * 3600        clamped by lease_ttl_seconds(policy) to the tenant ceiling
enforced three ways                      the NOT NULL column · governance.preflight · expire_leases
and reported                             scripts/brain_content_report.py prints leases that expired
                                         and were NOT cleared, because "the sweep stopped running"
                                         and "nothing has expired yet" look identical in the table
```

And the module's header states the governing principle:

> *"**A lease that never expires is a permanent memory wearing a temporary label**, so the expiry is
> not decoration — it is the entire difference between this brain and the Organization brain."*

⛔ **It also records that the Adaptive brain is a UNION of two stores**: *"it is written to
`temporary_memories` and the compiler read only `learned_brain_entries`. See
`PostgresRuntimeBrains.snapshot`, which now reads both."*

### ⛔⛔ The residue: the bounded half is bounded, and the durable half has one producer

| Unit | `proposed_value` | Target |
|---|---|---|
| `unit_feedback_learning` | rates and counts | `METRICS` |
| `unit_outcome_analysis` | `success_rate_bp`, counts, attention | `METRICS` |
| `unit_actor_outcome_analysis` | rates and counts | `METRICS` |
| `unit_performance_optimization` | rates and counts | `METRICS` |
| ⛔ **`unit_recommendation_learning`** | **`success_rate_bp`, `attention_per_outcome_bp`, `efficacy_bp`** | ⛔⛔ **`ADAPTIVE`** |
| `unit_behavior_evolution` / `unit_adaptive_evolution` | — | ⛔ **CORRECTED by `S4`:** both propose nothing via `_cohort_candidate` → `[]`, **and their work is built and wired one package down** (`packs/brains/behavior_distill`, `packs/brains/adaptive_lease`). Declared in `target_policy.DELEGATED`, guarded by five links → [`STEP-S4-DONE-a-silent-unit-names-its-producer.md`](STEP-S4-DONE-a-silent-unit-names-its-producer.md) |

```
units.py:452    unit_recommendation_learning → LearningObject(target=ADAPTIVE,
                                                 visibility=_org_visibility())   ⛔ NOT a stub
governance:53   preflight → "Behavior/Adaptive without a resolved subject are org-derived — ALLOWED"
                  ⛔ and ZERO expiry checks for ADAPTIVE, against THREE for RUNTIME
governance:112  govern   → GovernanceDecision(PROMOTED, "auto_promote")   ⛔ no human review
publisher:210   publish  → target in _BRAIN_TARGETS → publish_brain, state = PUBLISHED
publisher:95    publish_brain → insert into learned_brain_entries … active = true
                  ⛔ no expiry column in the insert at all
contracts:226   expires_at → raises unless target is RUNTIME
```

> ⛔ **Four sibling units that produce rates and counts target `METRICS`. The fifth, whose output is
> also rates and counts, targets the one durable brain that has no expiry contract — and it
> auto-promotes with no human in the loop.**

### ⛔⛔ And it breaks an Atlas authority boundary outright

The Atlas's own boundary for Recommendation Learning is **"No self-training from recommendation
score."** And `packs/compiler/runtime_brains.py:497` reads
`where org_id=:o and active and brain in ('organization','behavior','adaptive')` **into the
compiled expertise package**.

> ⛔ **So the recommendation efficacy score is published into a brain that the pack compiler reads
> back into the package the recommender reasons from. That is self-training from the recommendation
> score, by the Atlas's own definition, and it is the boundary the Atlas names for this exact
> unit.**

And `api/brain_routes.py:106` tells the user the adaptive brain *"Moves this current signal forward
in the executive brief **while it applies**."* ⛔ **The product promises the user an expiry that
the durable half cannot express.**

### The three ways out, and which are mine

| | Option | Whose |
|---|---|---|
| a | add mandatory expiry/decay to `ADAPTIVE` proposals **and** brain selection | ⛔ a contract change — **Rohit's** |
| b | prohibit durable `ADAPTIVE` publication; route short-horizon signal through expiring Runtime | ⛔ **already built for timing** (`adaptive_lease`). Extending it is a design change — **Rohit's** |
| c | ⛔ **retarget `unit_recommendation_learning` to `METRICS`** — matching its four siblings, its own output shape, and the Atlas's "no self-training" boundary | **the smallest and most consistent**, but it changes what the Adaptive brain contains → **Rohit's** |

⛔ **What is MINE, and needs no decision:** make the violation **impossible to ship silently**. A
guard that pins which units may target which brain, so a new unit cannot route a measurement into a
durable brain without a human noticing. **Additive, no behaviour change, and it holds the finding as
data rather than as a paragraph.**

⛔ **The production blast radius is NOT knowable from this checkout.** The code-level readers are
the pack compiler, `contracts/learned_state.py` and the UI. Whether any `learned_brain_entries` row
with `brain='adaptive'` exists needs one read-only query —
`select brain, count(*) from learned_brain_entries group by brain` — inside
`set transaction read only`. ⛔ `packs/brains/org_discovery.py:5` **comments** that the table
*"has been empty since migration 0045 shipped"*, and **a comment is not a measurement.**

---

## 3 · ⛔ What this retracts from my own plan

| | |
|---|---|
| ⛔ `U03` *an illegal learning transition* | **RETRACTED as the spine.** It was derived from a ledger, not from a named gap, and its gate question (*does the second writer validate?*) is answered by Atlas `#9`: the second writer **is** the repaired approval path |
| ⛔⛔ **`U03` — UN-RETRACTED 2026-10-02 by `S6`** | **The retraction above was WRONG.** It conflated two questions: the second writer (`api/learning_routes.py`) is indeed the repaired approval path and both its edges are legal — but the **first** writer, `publisher.publish`, was emitting `governed → published`, which `ALLOWED_LEARNING_TRANSITIONS` forbids, on **every brain publish**. I never looked at it. ⛔ **A retraction needs its own measurement, not a neighbouring one** — fifth retraction in this programme and the first of a retraction. Fixed, guarded and receipted → [`STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md`](STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md) |
| ⛔ `U04` *a publish outside its governing policy revision* | **RETRACTED as written.** The real policy defect is `#10`'s residue — `_as_tuple` defaulting to permissive empty tuples — which the Atlas states as a required repair with acceptance evidence |
| ⛔ `U05` *the refusal ledger* | **KEPT, demoted.** Still true (`learning_input_rejections` has no reader) but it is a monitoring gap, not one of the Atlas's eleven |
| ✅ `U01` the 27 skips | stands, measured, **Harsh's** (`H7`) |
| ✅ `U02` guards per package as data | stands, and §0 sharpens why |
| ✅ `U06`–`U10` | stand, all after the Atlas work |

> ⛔ **Three invented units.** I built a plan from the evidence I had measured instead of from the
> specification that already existed, and two live defects — one of them a permanent brain row from
> a short-horizon signal with no human in the loop — were not in it. **A plan derived from the code
> alone cannot find a gap the code is silent about.**

---

## 4 · The revised order

→ [`08-PLAN-v2-from-the-atlas.md`](08-PLAN-v2-from-the-atlas.md)
