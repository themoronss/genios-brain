# L6 · findings — what measuring `feedback/` actually turned up

**Date:** 2026-09-30. Everything here was measured before any code was written.

---

## ⛔ F1 · The milestone's own promise was already kept, in three places

M14 ships *"a wrong card debits the layer that failed, **and a timing complaint never lowers a
correct rule's precision**."*

```
calibrate.TAXONOMY["wrong:bad_timing"]  ->  {"label": "timing", "precision": "none"}
feedback/units.py:135                   ->  judged = acted + wrong   # bad_timing does not grade
calibrate._PRECISION_SQL                ->  in ('not_relevant','wrong_facts')
```

with `packs/brains/adaptive_lease.py` documenting the same rule from the consuming side.

⛔ **And `_PRECISION_SQL` goes further than the milestone asked.** It also restricts the denominator
to `card_level in ('prescriptive','predictive')`, with the best statement of the principle anywhere
in the repo: *"counting that as a precision failure made answering the system's own question evidence
the system was wrong."* A NULL level is excluded rather than assumed, because *"defaulting it to
'instruction' is how the old behaviour comes back."*

It was work to **not break**. **Correction #10.**

---

## ⛔ F2 · Nothing in `feedback/` names a layer

`grep -rn "layer" genios_engine/feedback/` → seven hits, **every one prose in a comment** about the
import topology. No reason→layer map, no layer counter, no layer column. The milestone's *first*
clause was entirely unbuilt.

`TAXONOMY` is its ancestor: it routes a reason to a **consequence** and a **label**. It never says
which layer to go and look at.

---

## ⛔ F3 · Three reasons, and five readers of the three

| Where | What it holds |
|---|---|
| `deliver/card_builder.py:849` | what the card **offers** |
| `deliver/actions.py:31` | what the API **accepts** |
| `feedback/calibrate.py` | what calibration **maps** |
| `feedback/units.py:124` | what the counter **branches on** |
| `context/correlation_history.py:148` | what a retry decision **reads** |

Widening one without the others reproduces `FEATURE_CARDS_FROM_SITUATIONS` exactly — *"the reader was
looking for a word the writer rejected"* — which cost this codebase a lane no tenant could enable.

---

## ⛔ F4 · The widening would have broken F1, in both directions at once

**Over-counting.** `units.py` tested one literal. Five of the eleven reasons say the card was RIGHT;
**four of those five would have landed in the `else` and debited the rule's accuracy.** The defect
this milestone exists to end, created for four new reasons by the step meant to fix it for one.

**Under-counting, and harder to notice.** `_PRECISION_SQL` held two reasons. Six now count against a
rule. Four real quality failures — `misread_source`, `wrong_subject`, `bad_link`, `bad_reasoning` —
could have been recorded by a founder and **counted by nothing.** Nothing breaks, and precision
merely looks better than it is.

---

## ⛔ F5 · `contracts/learning.py` exists, and is not this

310 lines of `LearningObject` v2 — content-addressed, round-trip verified, with its own hard rules.
`M14.C1.U01` names it as its artifact. **Adding a member to an enum it validates against would change
identities already minted.** The new vocabulary went beside it, not into it.

---

## ⛔ F6 · The topology gate caught my own violation

`contracts/learning_attribution.py` imported `genios_engine.LAYERS` so the layer names could be
checked at import time. `test_contracts_import_nothing_above_platform` failed the build: *"contracts/
is the boundary vocabulary — it may depend on platform/stdlib only."*

**The gate was right.** `contracts/` is what every layer imports, so a dependency added there is added
everywhere — and `LAYERS.py` exists to be read by the topology *test*, not by shipped code (nothing
else in `genios_engine/` imports it). Same lesson as `capture → context` in L1 Step 10.

---

## ⛔ F7 · Two of my own tests were blunt greps, in one file

One asserted `"denominator" not in src` and failed on **its own docstring**, which uses the phrase
*"the precision denominator"* to explain the rule. The other matched `OFFSET_BOUND` in a module
docstring, where it appears to say that learning is bounded **and an attribution is not.** Both
rewritten as AST walks.

---

## ✅ F8 · What was already right

| | |
|---|---|
| Wilson intervals | a rule with 8 judgments does not get the same confidence as one with 800 |
| the mute floor | `MUTE_PRECISION = 0.25` with `MUTE_MIN_JUDGMENTS = 12` — a cold rule cannot be muted on noise |
| the offset bound | `OFFSET_STEP = 5`, `OFFSET_BOUND = 15` — learning cannot run away |
| the abstention exclusion | a `review` card answered by a human is not a precision failure |
| the import direction | `feedback/consumer.py` records a real correction: a consumption contract only the producing layer could import was *"a decoy seam"* |
| `(action, reason)` carried whole | *"`bad_timing` invites a later retry, `not_relevant` does not"* |

---

## What changed because of these findings

| Finding | Effect |
|---|---|
| F1 | `U03` narrowed; two **guard** functions now hold the property, with tests |
| F2 | `contracts/learning_attribution.py` — eleven reasons, one layer each |
| F3 | all five readers widened in one step; a test asserts the card and the API agree |
| F4 | `units.py` asks the map; `_PRECISION_SQL`'s list is generated from it. Both directions tested |
| F5 | a new file beside `learning.py`; `tree.yaml`'s artifact updated with the reason |
| F6 | layer names are plain strings; two tests assert them against `LAYERS.py` |
| F7 | both tests rewritten as AST walks |
| F8 | nothing rebuilt |


---
---

# ⛔ THE SECOND PASS · 2026-10-02 · F9 — F20

`F1`–`F8` are M14's findings and **none of them is retracted**. These are from the re-crosscheck
over the whole layer: [`05-RECROSSCHECK-the-loop-that-runs-and-is-never-questioned.md`](05-RECROSSCHECK-the-loop-that-runs-and-is-never-questioned.md).

```
feedback/    14 files · 3,111 lines      (12 · 2,737 at F1–F8)
receipts     4, every one labelled L7    778 lines per guard — the BEST ratio of any layer
tests        60 passed · ⛔ 27 skipped
```

## ✅ F9 · The loop runs, is scheduled, and is reached — the opposite of L5

| | Where |
|---|---|
| the learning sweep | `api/routes.py:1274-1278` — `run_learning_sweep(_graph.engine, now=now)`, **inside the heartbeat** |
| calibration | `api/routes.py:1247-1264` — per org × per active pack, same heartbeat |
| org-rule discovery | `api/upload_routes.py:489`, `api/knowledge_routes.py:94` — `background_tasks.add_task` on upload |

*"Weekly per tenant, enforced by a PostgreSQL tenant/week claim (not process memory), so it is safe
to call every heartbeat: a completed week is a no-op."* **Eleven public functions are called or
referenced from outside the package.** There is no cutover gap in `feedback/` and no dead control
plane. ⛔ **This finding is why the rest of the pass went looking elsewhere.**

## ⛔⛔ F10 · Four guards, and not one asks whether the result is right

A receipt is either **presence** (`expect(0)` False — zero is the failure) or **correctness**
(`expect(0)` True — any row is the failure). Measured over all 35:

| Package | Receipts | correctness | presence |
|---|---|---|---|
| `deliver/` | 8 | **5** | 3 |
| ⛔ **`feedback/`** | **4** | ⛔ **0** | **4** |
| ⛔ **CORRECTED 2026-10-02 by `S5`** | — | — | — |
| `feedback/` | **5** | ⛔ **1** | 4 |

```
[L7] the learning engine has executed             → "has it run?"
[L7] calibration has executed                     → "has it run?"
[L7] the counterfactual ledger joins end to end   → "does the join reach?"
[L7] a human verdict has reached the loop         → "has anything arrived?"
```

> ⛔ **All four are satisfied by a single successful tick.** Nothing asks whether a published brain
> value was governed, whether a proposal took a legal transition, whether a rule was muted on
> enough evidence, or whether an expired lease actually expired.

> ⛔ **CORRECTED 2026-10-02 by `S5`:** the layer now has **one** correctness receipt — *"no
> completed learning run hides whether it dropped inbox rows"* — and it reads
> `learning_runs.counts`, which was written every week and read by nothing. The other four
> sentences above still stand: nothing yet asks about a legal transition, a governed publish, a
> mute's evidence or an expired lease.

⛔ **And `3,111 / 4 = 778` lines per guard is the best ratio in the product.** Guards per line was
never going to find this: *it counts guards; it does not read them.* **This is the finding that
retires guards-per-line as a diagnostic** — the metric that motivated `STEP-10` and whose number
`08-CORRECTION` had to fix.

## ⛔⛔ F11 · The four ledgers nobody reads are the four that would answer the correctness questions

`feedback/` writes **19 tables**. Four are read by nothing — not the engine, not `scripts/`, not an
API route, not a receipt:

| Ledger | Written at | The question it already holds the answer to |
|---|---|---|
| `learning_transitions` (`0045`) | `publisher.py:34` ⛔ **and `api/learning_routes.py:141`** | did any object take an **illegal** transition? `contracts/learning.ALLOWED_LEARNING_TRANSITIONS` already exists |
| `learning_object_evaluations` (`0046`) | `orchestrator.py:197` | did a run publish **without a material change**? `sink_reason` is `published_to_dynamic_target \| no_material_change \| metric_identity_conflict` |
| `learning_input_rejections` (`0046`) | `store.py:193`, `org_rule_ingest.py:181` | is the loop **refusing everything it is fed**? |
| `learning_metrics` (`0045`) | `publisher.py:151` | *"measurement artifacts (not a brain)"* |

> ⛔ **The data needed to guard the learning loop is already being written, in indexed append-only
> ledgers, and nothing asks it a question.**

> ⛔ **CORRECTED 2026-10-02 by `S6`: four became two, and asking the question found two live
> defects.** `learning_object_evaluations` now has the no-silent-drop receipt (and its `_by_run`
> index its first query); `learning_transitions` now has the illegal-edge receipt. ⛔ **Both were
> recording a defect nobody read** — three discarded refusal reasons, and a `governed → published`
> edge the contract forbids. `learning_input_rejections` and `learning_metrics` are still unread and
> now **declared** rather than merely observed. ⛔ **UPDATED AGAIN by `S7`: two became ONE.** The
> isolation ledger got its reader, and `S6`'s declared-silence test **failed on cue** — so the
> tally moved deliberately instead of being discovered weeks later. Only `learning_metrics`
> remains. → [`STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md`](STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md) *A record nobody reads is presence without effect — the
> reader is half the unit*, at the scale of a layer rather than a function.

## ⛔ F12 · Two indexes maintained for queries nobody wrote

```sql
create index if not exists learning_object_evaluations_replay
    on learning_object_evaluations (org_id, learning_id, evaluated_at);
create index if not exists learning_object_evaluations_by_run
    on learning_object_evaluations (org_id, run_id);
```

**An index is a statement that a query exists.** `_replay` names a replay path and `0046` promises
*"object replay never mutates the proposal"* — **there is no replay query** in the engine, in
`scripts/`, or in a route. Both indexes are paid for on every insert.

## ⛔ F13 · The sharpest instance states the defect in its own docstring

`feedback/org_rule_ingest.py:174`, `record_refusal`:

> *"A refusal that lives only in a return value is indistinguishable from a candidate the model
> never produced."*

The reasoning is right, and it is why the refusal was promoted out of a return value into
`learning_input_rejections`. ⛔ **That ledger has no reader**, so the refusal is now
indistinguishable from a candidate the model never produced **one layer further down**. The fix
moved the record and never built the reader.

## ⛔ F14 · One model-call site, model-off since 2026-09-25 — and only half its failures are visible

`org_rule_ingest.run_org_discovery` is the **only** model call in `feedback/`; `attribution.py:35`
says the rest is *"PURE. No I/O, no clock, no model."*

| Outcome | Recorded in | Read by |
|---|---|---|
| the model raised | `org_rule_discovery_runs`, `outcome='extractor_failed'` | ✅ `org_rule_ingest.py:235` |
| a candidate was **gated out** | ⛔ `learning_input_rejections` | ⛔ **nothing** |

⛔ **A model outage is visible; a refusal is not.** The cost gate *before* the model call is good
design — *"Paying for a T2 extraction to read a wiki page is how a per-document unit becomes a
per-document bill"* — and its own accounting is the half with no reader.

## ⛔ F15 · All 27 skips are the same thing, and they are the two files that matter most

```
14  tests/feedback/test_org_brain_filled_through_the_routes.py                 ENTIRELY skipped
13  tests/feedback/test_behavior_and_adaptive_brains_filled_through_the_paths.py  ENTIRELY skipped
--
27  every one: "GENIOS_TEST_DATABASE_URL not set — J4's org row / brain rows need real Postgres"
```

⛔ **The two files that prove the brains are actually FILLED — "through the routes", "through the
paths" — are the two that do not run in this checkout.** The 60 that pass are the deterministic
ones. **A skip is not a pass**, and no document in this folder had mentioned them. → joins Harsh's
`H6`.

## ⛔ F16 · `00-START-HERE.md` said `COMPLETE`, and three documents disagree about the test count

| Source | Count |
|---|---|
| `00-START-HERE.md` | *"53 tests"* |
| `01-CROSSCHECK.md`'s 2026-10-01 addendum | *"3 steps, all DONE, 87 tests"* |
| ⛔ the directory, measured | **60 passed, 27 skipped** |

⛔ **And `01-CROSSCHECK`'s own addendum warns about exactly this**: *"a reader scanning for status
reads that line as current, and this programme has now paid for that mistake three separate
times."* **This folder then did it again, in the file a reader opens first** — fourth instance, and
the first inside a file that documents the pattern.

## ⛔ F17 · A mover-convention deviation the guard cannot see

`feedback_health.py` uses **`MOVES WITH`** for `every_legacy_reason_still_grades_the_way_it_did`;
the convention elsewhere is `MOVES WHEN`. `test_every_entry_carries_a_reason_and_a_mover` requires
only *"at least two parts"*, so it passes. ⛔ **A guard hole, not a defect** — and the distribution
across all ten declaration modules has not been measured, so which one is wrong is not yet known.
*Do not weaken a verify to make it pass; do not tighten one to make it fail.*

> ⛔⛔ **F17 IS RETRACTED 2026-10-02 BY `S9` — IT WAS MY OWN FALSE FINDING.** Measured:
> **`MOVES WITH` appears 29 times across NINE of the thirteen declaration modules**, against 115
> `MOVES WHEN`. ⛔ **It is a CONVENTION, not a deviation**, and it says what `MOVES WHEN` cannot —
> *"this entry moves when its PAIR moves"*, two guards over one map from opposite sides. **The
> existing guard is right to accept both**, and the sentence directly above — *do not tighten one to
> make it fail* — is the sentence this finding would have made me break.
>
> ⛔ The gate *"measure the distribution BEFORE touching either side"* stopped me tightening a guard
> onto **29 correct entries**. ⛔ A THIRD form did exist (one `MOVES ON` in `context_health.py`),
> now normalised, and a new guard rejects a third form **without demanding a mover** — three tables
> correctly have none. → [`STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md`](STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md)

## ⛔ F18 · A stale comment in `scripts/`

`wipe_org_data.py:40` — *"The old exclusion read information_schema.views, which omits MATERIALIZED
views — `counterfactual_ledger` (0072) slipped through."* ⛔ `0072` creates a **plain** view and
says why: *"A VIEW, not a table: every source is already append-only/versioned, so materialising a
copy would be a second thing to keep honest."* The comment's **reason** is wrong; the fix it
justifies (select base tables positively) is correct regardless. **Sixth instance of *a stale
comment reads as a measurement*.**

## ⛔ F19 · Two near-misses of my own, both caught before anything was written down

| | |
|---|---|
| **`counterfactual_ledger` has no writer** | TRUE, and the conclusion would have been FALSE — it is a **VIEW**. ⛔ Second time in two layers a *"nothing writes/calls it"* measurement was correct and the inference wrong; the first was `realtime.purge_expired`, reached by duck-typed dispatch |
| ⛔ **the reader scan undercounts** | `context/authority_view.py:55` holds `AUTHORITY_TABLE = "authority_rules"` and builds the query from the constant, so a `from X`/`join X` scan read **3 readers as 1**. Every *"read by nothing"* claim in `F11` was re-verified by a direct grep for the bare table name. **A name-constant is a read** — new doctrine |

⛔ And one regex fault: `[a-z_]+` cannot match a digit, so the first table resolver read
`l2_convergence` as table **`l`**. *Fourth time in this programme a name-shaped regex produced a
confident wrong answer.*

## ⛔ F20 · This pass forced a correction on L5

Asking *"which receipts guard `feedback/`?"* exposed that `Receipt.layer` is a hand-written digit,
not a package — the exact reading `genios_engine/LAYERS.py` forbids in its own docstring. `STEP-10`
claimed `deliver/` had **2** receipts and **1** working; it had **5** and **4**.
→ [`../layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`](../layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md),
and the eleven documents it touched.

⛔ **`feedback/` is guarded by the four receipts labelled `L7`.**

---

## ⛔⛔ F21 · The North Star ledger has never had a writer — and only the delete list knows it

Found while measuring **why** `/v1/insights/stats` withholds `value_recovered_inr` (`S2`). The
endpoint blamed the counterfactual ledger *"which does not exist"*; it exists (`0072`, with a
receipt) and was never the one that would carry money.

`migrations/0012_l6_feedback.sql:35` — *"F8 MACV ledger — **the North Star**. caught→acted→resolved;
distinct-deal SUM + non-deal COUNT (anti-inflation double-count rule). **The number the customer can
verify**."* Columns: `period`, `deal_id`, `amount`, `resolved_signal_id`.

⛔ **Five occurrences repo-wide, and not one is a read or a write:**

```
migrations/0012_l6_feedback.sql       creates it, names it the North Star
migrations/0033_org_data_cascade.sql  the org cascade FK
api/account_routes.py:670             ⛔ the DELETION list
tests/test_reasoning_retention.py:27  ⛔ the retention test's table list
docs/LAYER_MAP.md:15                  ⛔ claimed feedback/ WRITES it — it does not
```

> ⛔⛔ **Nothing inserts a row and nothing selects one. The only code that touches the product's
> headline value ledger deletes it.** *A record nobody reads is presence without effect* turned
> inside out — a ledger that exists only in the delete list, both of whose code references say
> "remember to wipe this".

⛔ **`None` is still the right answer.** Reading the empty ledger to report `0` would be exactly the
defect the handler's own first sentence exists to prevent. `S2` changed the **reason**, not the
value, and bound the new reason to the measurement:
`tests/api/test_the_value_is_withheld_for_the_right_reason.py` fails the moment a writer appears.

⛔ **Rohit's:** what counts as recovered value, which deals attribute, and the *"anti-inflation
double-count rule"* the migration names are product decisions. The migration's
`distinct-deal SUM + non-deal COUNT` is a specification nobody implemented.
→ [`STEP-S2-DONE-the-north-star-has-no-writer.md`](STEP-S2-DONE-the-north-star-has-no-writer.md)

## ⛔ F22 · A guard must check attribution, not presence — the 18th instance, with the rule in its own docstring

`S2`'s first guard asserted the old false sentence was **absent** from the handler. ⛔ It failed on
the correct fix, because the corrected comment **quotes** that sentence in order to say it is false
— and the docstring directly above the assertion read *"a grep for a known-false phrase matches the
record of its own correction."*

⛔ **The eighteenth instance in this programme, and the first where I wrote the rule into the
docstring of the test that then violated it.** The repair generalises: the phrase may appear, and
every occurrence must sit within four lines of a marker identifying it as the old wording. A relapse
adds an **unmarked** occurrence and fails — proven by mutation `M5`.

*A log is append-only and corrections are new lines, so a guard that forbids the words cannot tell a
correction from a relapse.*

### ⛔ The measured scope of the consequence — and what it is NOT

```
584   assert "..." not in <anything>           across tests/
104   assert "..." not in src|code|source|text|blob|content|body     ⛔ SOURCE-TEXT guards
```

⛔ **104 guards share the shape that just failed.** But *"104 broken guards"* would be an
overstatement and this programme has paid for those: most assert a **construct** is absent —
`"insert into" not in source` proving a module is read-only, `"find_or_create_node" not in source`
proving a path never creates — and a correction comment is unlikely to quote those.

> ⛔ **Every one of the 104 is STRUCTURALLY vulnerable** — the moment anybody documents the
> forbidden thing in a comment, including to explain *why* it is forbidden, the guard fires on
> correct code. ⛔ **Which of them is ACTUALLY at risk cannot be known without reading all 104**,
> and that reading is `S9`'s, not `S2`'s.

The general mitigation is the one `S2` now uses: ⛔ **assert attribution, not presence** — allow the
phrase, require a marker within a few lines identifying it as the old wording.

---

## ⛔⛔ F23 · A fail-OPEN on an authority list — the database kept two facts apart and the load collapsed them

`learning_policies.blocked_targets` / `.blocked_subject_prefixes` are nullable `jsonb` (`0045`) and
the seed writes `cast('[]' as jsonb)` with the comment *"an empty prohibition list is a decision
('nothing is blocked'), NULL is an absence. **Keeping them distinct is what lets the guard below
tell a deliberate empty policy from one that failed to load**."*

⛔⛔ **There was no guard below.** `_as_tuple` returned `()` for `None`, a dict, a bare string and a
list of integers alike — so a tenant whose *"never learn about these targets"* list failed to read
was indistinguishable from one who blocks nothing, and `preflight` returned **`admitted`** for the
exact target they meant to forbid.

⛔ **And the helper could not keep the promise in its own docstring** — it received only the value,
never the revision. *A docstring can promise a behaviour the signature makes impossible.*

Atlas Layer 7 gap **#10**'s required repair, verbatim: *"unknown/malformed policy fields **block the
run** rather than defaulting to permissive empty tuples."*
→ [`STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md`](STEP-S3-DONE-a-policy-that-did-not-load-may-not-learn.md)

## ⛔⛔ F24 · The learning sweep counted its skips and never said why

`run_learning_sweep` returned `{orgs, passes, skipped}`. ⛔ **A tenant who turned learning off, a
tenant whose week was already claimed, and a tenant whose transaction raised were the same number**
— and the `except` recorded nothing at all.

So `F23`'s fail-closed would have been **invisible**: a silent stop, which is worse than the
fail-open it replaces, because at least a fail-open is loud in its consequences. ⛔ **The fail-closed
and its reader had to ship in one unit.** *The reader is half the unit*, and this is the same shape
as L5's *a dead row cannot tell "we chose not to send" from "we lost it"*.

Closed with `skipped_by_reason` — additive, so the heartbeat's existing keys are untouched — and the
`except` now records the exception **type**, because `{"error": True}` hid a `NameError` in the
executive sweep for 15 days.

## ✅ F25 · A false finding refuted before it was written — `knowledge_requires_review`

`load_or_seed_policy` **selects** `knowledge_requires_review` and then passes a literal `True`. I
began writing that up as *"a selected column that configures nothing — a setting that lies."*

⛔ `migrations/0045_l6_learning.sql:37` holds
`constraint learning_policies_knowledge_review_locked check (knowledge_requires_review)`, and the
table comment says *"**CHECK-locked true** — it can never be disabled."* **It is an invariant
enforced in three places** (the database CHECK, the contract's `raise`, the loader's literal) and
the selected column is **redundant, not misleading**.

⛔ **Sixth time verifying a suspicion before writing it prevented a false finding.** *A redundant
read is not a lie; a lie is a read whose value could differ and does not matter.*

---

## ⛔⛔ F26 · The Atlas's only LIVE gap was a wrong conclusion — and this programme repeated it

Atlas Layer 7 gap **#2**: *"Direct personalization evolution is missing. Behavior and Adaptive
cohort builder returns no proposals."* Both units do return nothing, through a shared
`_cohort_candidate` whose entire body is `return []`.

⛔ **Both components are built, wired, isolated and scheduled** — one package down:

```
packs/brains/behavior_distill.py   776 lines  distill()         → LearningTarget.BEHAVIOR
packs/brains/adaptive_lease.py     301 lines  lease_proposals() → LearningTarget.RUNTIME, 7-day TTL
```

`packs/brains/__init__.py` says so in its first paragraph — *"**This package is the supply side**…
The drivers live on the Layer 6 side"* — and `feedback/brain_pipeline.brain_pipeline_proposals`
appends both into the **same weekly run**, each inside a `begin_nested()` savepoint, from the line
directly after `run_all_units`.

⛔ **The stub predates the implementation by a month:** `365cf7a6` (2026-08-08, *"the ten analysis
units"*) vs `ed1b10c3` (2026-09-07, *"Layer 3 v2 … the four brains"*). The placeholder was never
removed or declared, so `ALL_ANALYSIS_UNITS` still shows a silent unit where a built component
belongs.

> ⛔⛔ **Two readers reached the same wrong verdict from the same evidence** — the Atlas, and this
> programme, which filed #2 as *"LIVE — and now less visible than the Atlas found it"*. ⛔ **And
> that note was itself a wrong conclusion**: it said *"I was one step from recording this as CLOSED
> from the call site alone"* — **it IS closed.** The call site was the wrong evidence in both
> directions.

⛔ **One grep made it worse.** `behavior_distill.py:551` contains *"NOTHING wires this adapter
today"* — about the optional **LLM labeler**, not about `distill`. A grep hands over a sentence
without its subject.

**A call site that looks wired is not a wired call site — and a call site that looks DEAD is not a
dead feature.** → [`STEP-S4-DONE-a-silent-unit-names-its-producer.md`](STEP-S4-DONE-a-silent-unit-names-its-producer.md)

## ⛔ F27 · `S1`'s guard stopped at the package boundary, and the two real producers were outside it

`durable_from_a_measurement()` reads `UNIT_TARGETS`, which is **`units.py`'s registry**. But
`brain_pipeline_proposals` appends proposals from two producers in **another package** straight into
the same run.

> ⛔ So *"which producer may write which brain"* was guarded for **eleven units** and **unguarded
> for the two that actually produce.** *A guard that stops at a package boundary catches nothing
> across it* — the mirror of `STEP-17`'s *one guard over eleven packages catches the twelfth.*

Closed by `DELEGATED`'s target column and `broken_delegations()`' **link 5**, which walks the
producer's **whole module**: both producers build their `LearningObject` in a private helper the
entry function calls, so a function-scoped walk finds no target and reports every delegation broken.
⛔ **The same mistake as grepping for a keyword argument, one level up.**

## ⛔ F28 · An invalid mutation is not a surviving mutation

`S4`'s `M2` — *"the producer is stubbed to its own signature"* — **SURVIVED on its first run**, and
the fault was the mutation. I appended the stub `def distill(...)` **before** the real one, and at
module level Python's **last** definition wins (as does the resolver's dict comprehension). It was
dead code, not a stub, and **the guard was right to pass.**

> ⛔ The distinction only exists because the harness reported the survival instead of rounding it
> up. This is `STEP-14`'s lesson holding in the opposite direction: **that** run reported a
> survivor as caught; **this** one refused to report a non-mutation as a kill.

## ✅ F29 · A widening I stopped myself from making — same sink, different input

`unit_temporary_memory` returns `[]`, and `adaptive_lease` writes exactly its sink: an expiring
runtime directive in `temporary_memories`. I began adding it to `DELEGATED`.

⛔ **The inputs differ.** That unit wants an **explicit human directive** — *"Explicit directive →
a Runtime lease with a mandatory expiry"* — from a structured inbox that does not exist;
`adaptive_lease` **infers** a lease from `card_feedback_verdicts`. **Same sink, different input**,
so one does not do the other's job, and recording it as a delegation would have been **a lie about
which capability exists.** It stays a declared stub and its entry now says why.

⛔ **Atlas gap #1's residue is real**: the preference and temporary-memory inboxes do not exist.

---

## ⛔⛔ F30 · The inbox landed. The `kind` did not — and the rows are dropped on the floor

Both stub units carried the docstring *"Empty until the inbox lands"*, and
`orchestrator.run_learning` justified its unconsumed counter with *"Empty at both ends today, so it
costs nothing — **but the day something starts writing to that table**, rows would be read and
dropped on the floor with no counter moving anywhere."*

⛔⛔ **That day had already come.** Measured 2026-10-02:

```
migrations/0046_l6_learning_hardening.sql   learning_event_inbox — idempotent, with a lease
reason/moments/store.record_feedback        ⛔ INSERTS a row per moment-feedback action
api/moment_routes.py:746                    ⛔ reached in PRODUCTION
feedback/store.py                           loaded into EVERY weekly batch as `batch.inbox`
feedback/units.py                           ⛔ NO unit reads it (asserted on the AST)
orchestrator.run_learning                   counts the drop as `inbox_unconsumed` → learning_runs.counts
```

⛔ **The gap is a `kind`, not a table, and that decides who can close it.** Every row written today
carries `payload.kind == "moment_feedback"` — a card action, not an explicit first-person
instruction with a subject, a scope and exceptions. **A table is a migration; a `kind` is a SURFACE
where a founder states a preference, and there is none.**

⛔ **Everything downstream of `unit_temporary_memory` already exists** — `LearningTarget.RUNTIME`,
`govern()` → `TEMPORARY`, `publish_runtime` → `temporary_memories` with `expires_at NOT NULL`,
`preflight`'s three expiry checks, `expire_leases`, and the inbox's own `lease_until` column.
**The missing input is the whole of the gap**, which is why `S5` is a declaration and not a build.

⛔ **And not a model.** The Atlas, quoted in the declaration: *"Adding a model directly to empty
units would produce eloquent ungrounded preferences. **First wire typed evidence**."* Its own
improvements table makes the **inboxes** P1 — not the extraction. → [`STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md`](STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md)

## ⛔ F31 · The layer's first correctness receipt, and it reads a column nobody read

`F10` measured `feedback/` at four receipts, **all four presence checks**. ⛔ `inbox_unconsumed` was
written into `learning_runs.counts` every week and **read by nothing** — `F11`'s pattern, one level
in.

```
receipts            35 → 36
feedback/ receipts  4 → 5      ⛔ CORRECTNESS: 0 → 1
```

⛔ **The claim guards the VISIBILITY, not the drop.** `inbox_unconsumed > 0` is the known state of a
declared gap, so a receipt on it would be red forever — and `platform/receipts.py` already carries
the rule: *"a gate that is always red is a gate nobody reads. The claim is the one that is true
today and false when it gets worse."* So the receipt asks whether the count is **recorded at all**:
delete the counter, or complete a run without it, and it goes red.

## ⛔⛔ F32 · A claim about CODE must be checked against the AST — the third instance in one session

`S5`'s guard read `assert "batch.inbox" not in units` and ⛔ **failed on correct code**, because the
corrected docstring I had just written **explains** that the inbox is *"loaded into every weekly
batch as `batch.inbox`"*. **A docstring that explains a gap contains the words of the gap.**

| | The three |
|---|---|
| `S2` | asserted a false phrase was absent; the correction **quoted** it → *check attribution, not presence* |
| `S2` again | the rule was in the **docstring of the test that broke on it** |
| ⛔ `S5` | asserted a **code** string was absent from a file whose **documentation** names it |

> ⛔ **The sharper form: for a claim about code, check the AST — not the text, and not even
> attribution.** An attribution window would have passed here and would have been the **wrong
> tool**: the question is not *"who said this"* but *"does any unit read this attribute"*.

The guard now walks the AST for `*.inbox` **and** `getattr(batch, "inbox", …)`, because the
orchestrator reaches it the second way. ⛔ **This widens `S9`'s scope again**: the 104 source-text
guards include some that assert a CODE fact, and those need the AST, not an attribution window.

---

## ⛔ F33 · An edit that cannot fail cannot be trusted — in the script doing the correcting

`19-PENDING-who-owns-what.md`'s MINE table stayed on plan v1's `U01`–`U10` through `S2`, `S3` and
`S4`, listing ⛔ **`U03`/`U04`/`U05` as *"planned"* when the Atlas check had retracted them.**

⛔ **The cause was my own tooling.** Those three edits used a plain `str.replace()` with **no
assertion that the anchor matched**, so each silently did nothing while the narrative blocks beside
them — which *were* asserted — landed correctly. **A document can go stale between two correct
paragraphs.**

> ⛔ **An edit that cannot fail cannot be trusted** — the same defect class this whole programme is
> about, committed by the script correcting it. Every anchored edit in this session's scripts now
> asserts its match count; **the three that did not are the three that were lost.**

---

## ⛔⛔ F34 · The no-silent-drop contract, broken in nine lines

```python
ok, _ = validate_learning(obj, policy)       # ⛔ the reason is DISCARDED
if not ok: held += 1; continue                #    counted, never named
if not preflight(obj, policy, now=now).ok:    # ⛔ PreflightResult.reason_code DISCARDED
    refused += 1; continue
decision = govern(obj, policy)
if decision.rejected: refused += 1; continue  # ⛔ GovernanceDecision.reason_code DISCARDED
```

**All three callees compute and return a reason; all three call sites throw it away**, and
`_record_evaluation` ran only on the paths that survived — so `learning_object_evaluations`
recorded only the successes.

The Atlas: *"Every rejected or deferred candidate must retain run_id, tenant, unit, evidence IDs,
**reason code**, failed gate, policy version, timestamp, and recovery status… **A weekly sweep that
returns zero objects without this accounting is operationally indistinguishable from broken
wiring.**"*

⛔ **And `migrations/0046` names the held case itself**: *"append-only: every actual per-run decision
(new or **HELD** object)"*. ⛔ **No migration was needed** — the ledger already carries every field
the Atlas asks for, and `learning_id` has no foreign key, so a proposal that never reached
`persist` can still be recorded. *Checked before writing.* → [`STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md`](STEP-S6-DONE-no-silent-drop-and-an-illegal-edge.md)

## ⛔⛔ F35 · An illegal lifecycle edge, live, on the most important path in the layer

```
every brain publish wrote:   governed → published
ALLOWED_LEARNING_TRANSITIONS[GOVERNED] = (temporary, human_review, promoted, rejected)
learning_can_transition(GOVERNED, PUBLISHED) = False                       ⛔ ILLEGAL
```

`publisher.publish()` fixes `from_state = GOVERNED`, reassigns `target_state = PUBLISHED` after a
brain publish, and logs once. ⛔ The map's own docstring states **two hops** — *"| Promoted→Published
| Rejected}"* — and the publisher skipped `PROMOTED`: the state that distinguishes *"promoted,
publisher not yet done"* from *"published"*, which is exactly the ambiguity the Atlas's **`L7-30`**
is about.

> ⛔ **`ALLOWED_LEARNING_TRANSITIONS` existed from the start and nothing checked it on this path** —
> because `learning_transitions`, written by five call sites, is read by none.

Fixed at the source (the hop is logged, and `log_transition` now **refuses** an illegal edge after
all six call sites were enumerated), plus a receipt whose legal set is **derived from the contract**.
⛔ **A guard at the writer protects the future and says nothing about the past**, so the receipt has
no date gate: a pre-existing illegal row is **named, not hidden**.

## ⛔⛔ F36 · My retraction of `U03` was wrong — a retraction needs its own measurement

[`07-ATLAS-CHECK`](07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md) §3 retracted `U03`
*"an illegal learning transition"* because *"its gate question (does the second writer validate?) is
answered by Atlas #9: the second writer **is** the repaired approval path."*

⛔ **That conflated two questions.** The second writer (`api/learning_routes.py`) is the repaired
approval path and **both its edges are legal**. The **first** writer — `publisher.publish` — was
emitting an illegal edge, and I never looked at it.

> ⛔ **Fifth retraction in this programme, and the first of a RETRACTION.** A retraction is a claim
> like any other and needs its own evidence, not a neighbouring fact.

---

## ⛔⛔ F37 · A seam we threw away was reported as a seam that had nothing

`store._read_optional_seam` catches a read that raises, records it in `learning_input_rejections`,
and returns `()`. ⛔ **The WRITE was built and the READ never was** — and the return value stayed
`()`, so the seam arrived at `run_learning` identical to an empty one. *"No human has judged a card
yet"* and *"the verdict table read raised and we threw it away"* were **one line** in
`degraded_seams`.

Its own comment already named the contract: *"nothing in the codebase ever wrote to it… an input the
system deliberately quarantined was indistinguishable from one that never arrived. **That is the
no-silent-drop contract failing in the one place built to uphold it.**"*

Atlas **`L7-29`**: *"**Expose per-seam freshness, coverage, and empty REASON** → Empty canonical
verdict seam breaches a declared health SLO."*

⛔ **And the ratio question answered itself elsewhere.** `08-PLAN-v2` planned a refusal-rate receipt
once a denominator existed — `org_rule_discovery_runs.counters` already holds `candidates`,
`admitted`, `refused` and `refused_<reason>` per run, in a table that **is** read. The discovery
route's accounting is complete; the gap was the ledger's **other** writer. → [`STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md`](STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md)

## ⛔⛔ F38 · The delivery seam was reported degraded on EVERY run, forever

```python
("deliveries", getattr(batch, "deliveries", ())),   # ⛔ the field is `delivery`
```

The default fired every time, so the seam was always listed and ⛔ **`degraded` was always True.**
*A flag that is always set is a flag nobody reads* — the same shape as `receipts.py`'s own *a gate
that is always red is a gate nobody reads.*

⛔ **A `getattr` with a default converts a wrong attribute name into a plausible value.** On a
dataclass, `batch.delivery` would have raised the first time it ran. ⛔ And the comment directly
above it says *"a run that proposed nothing because its inputs were empty is NOT a healthy run"* —
**the fix was built and one of its three seams was wrong.** The names now live beside
`LearningBatch` and a test asserts each is a real field.

## ⛔⛔ F39 · Guards per package, derived — and `STEP-10` was aimed at the wrong package

```
package     receipts  correctness    lines  lines/guard
feedback           9            5    4,040          448     ← best
reason             8            5   41,363        5,170
deliver            7            5   10,020        1,431
capture            5            5   47,184        9,436
readiness          5            0        —            —
context            2            2   50,877       25,438     ⛔⛔ WORST
executive          2            1    6,230        3,115
platform           1            1   11,950       11,950
packs              1            0    8,188        8,188
```

⛔⛔ **`context/` is 50,877 lines with TWO guards.** `STEP-10` spent a whole step on `deliver/`
because a hand-derived number said 4,715 — **`context/` is 5.4× worse than that**, 13× worse than
`deliver/`'s real figure at the time, and `deliver/` is now the **third-best covered package**.
⛔ `packs/` is 8,188 lines with one PRESENCE receipt and **zero** correctness — the state
`feedback/` was in before `S5`.

⛔ The mapping is **declared**, because an outer-`from` resolver fails on **4 of 40** receipts; and
a third category — `READINESS`, for claims no package can repair — is counted separately rather
than inflating a package's coverage. ⛔ `Receipt.layer` is never read: a test asserts it.

## ⛔⛔ F40 · A stale `__pycache__` could have falsified every mutation run in this session

`S7(a)`'s *"baseline again"* assertion failed with a layer `L8` that appears **nowhere** in the
source. ⛔ The harness mutates a file, runs pytest in a subprocess (which caches the MUTANT's
bytecode), then restores — and a restore landing in the same mtime-second with the same size lets
Python reuse the mutant's `.pyc`. **A restored file was read as the mutant.**

⛔ **The bias is toward FALSE KILLS**: a later run importing an earlier mutant fails for the wrong
reason and is scored CAUGHT.

⛔ **Every harness was re-run** with `PYTHONDONTWRITEBYTECODE=1` and a cache clear per invocation:
`s2 6·0 · s3 8·0 · s4 8·0 · s5 8·0 · s6 9·0 · s7b 9·0 · s7a 8·0` — ⛔ **every count identical to
the original.** Nothing was mis-scored, *and the only reason that is known is that the harness
asserts its baseline AFTER the run as well as before.* `STEP-14`'s lesson, paying twice.

## ✅ F41 · A guard forced its own update

`S6`'s `test_the_remaining_unread_ledgers_are_still_unread` was parametrised over
`["learning_input_rejections", "learning_metrics"]` with the docstring *"when one gets a reader this
fails and the `F11` tally is updated deliberately."* ⛔ `S7` gave the first a reader and **the test
failed, exactly as promised** — so the tally moved from four to one as a deliberate edit rather than
a discovery weeks later.

> ⛔ **A declared silence that fails the build when it stops being true is the only kind worth
> writing.**

---

## ⛔⛔ F42 · The scorecard reaches L6 — and four of eleven badges were out of date in one direction

`08-ATLAS-SCORECARD-L1-to-L5.md` → **`-L1-to-L6.md`**, 45 → **56 claims**, all eleven `L7 Learning`
rows of the master matrix measured against the current code.

```
EXPIRED           4    L6-02 explicit feedback · L6-06 Behavior evolution ·
                       L6-09 publisher/policy seams · L6-11 value analytics
PARTLY EXPIRED    4    L6-01 input health · L6-04 temporary memory ·
                       L6-05 outcome identity · L6-10 pivot/reset
STILL TRUE        3    L6-03 preference inbox · L6-07 Adaptive lifecycle · L6-08 review SLA
```

⛔⛔ **All four expirations are in the same direction: the Atlas calls built things stubs.** `L6-06`
is the clearest — *"Behavior cohort builder returns `[]`"* against a **776-line component wired into
the weekly run**. → [`STEP-S8-DONE-the-scorecard-reaches-the-learning-layer.md`](STEP-S8-DONE-the-scorecard-reaches-the-learning-layer.md)

## ⛔⛔ F43 · Four cells hid a defect the Atlas did not name

| Cell | The Atlas's badge | ⛔ What measuring it found |
|---|---|---|
| `L6-01` | *"live input health **Unknown**"* | the health gate **was broken** — `degraded` was always True (`S7`) |
| `L6-09` | *"broken seams"* — both named ones **fixed** | ⛔ `governed → published` on **every brain publish** (`S6`) |
| `L6-10` | *"does not fully supersede Behavior"* | ⛔ **the module's stated REASON is now false** (`F44`) |
| `L6-11` | *"hardcodes zero"* — **fixed** | ⛔ `macv_ledger` **has never had a writer** (`S2`) |

> ⛔ **A cell the Atlas marks *Present* is not a cell that needs no measurement.** Three of the four
> sit under badges that read as reassuring, and the fourth under one already corrected.

## ⛔⛔ F44 · A stale sentence that justifies a gap — the most expensive place for one

`feedback/reset.py`'s header explains why a pivot does not touch the Behavior brain:

> *"`unit_behavior_evolution` … is presently an **unwired stub that always returns `[]`** — **there
> is no live Behavior Brain content to decay**."*

⛔ **True when written, false now**: `packs/brains/behavior_distill.distill` (776 lines) proposes
`LearningTarget.BEHAVIOR` and is appended to the same weekly run (`S4`/`F26`). **So a pivot can leave
live Behaviour content in place and the module's reason for leaving it no longer holds** — the
Atlas's `L7-20` / `L7-40` concern.

⛔ **Corrected, not repaired**: superseding a durable brain entry is a governed decision and part of
Rohit's Adaptive-lifecycle call. ⛔ **A cross-package guard now ties the prose to the fact** —
nothing connected `reset.py` to `behavior_distill` before, which is why the sentence could rot for a
month. Checked by **attribution, not presence**, because the correction quotes what it corrects.

## ⛔ F45 · The layer-numbering collision, paid for a third time — in this step's own title

`LAYERS.py`: *"always name the package, never the digit alone."* The programme has now paid for
ignoring it three times:

1. `STEP-10`'s receipt count — *"L5 carried 2 of 33"* (→ `08-CORRECTION`)
2. the three `L5`-labelled receipts **I** added to `deliver/`, following a mislabel
3. ⛔ **this step, which I planned as *"`L1-to-L7`"*** — the scorecard numbers `deliver/` as L5, so
   the learning layer is **L6** there, while the source matrix labels the same rows `L7 Learning`

⛔ Caught by the measure-first gate before a single line was written, and the new section states the
mapping in its first paragraph rather than assuming a reader shares it.

---

## ⛔⛔ F46 · `F17` was my own false finding — and its own gate refuted it

```
MOVES WHEN   115 occurrences
MOVES WITH    29 occurrences, across NINE of the thirteen declaration modules
```

⛔ `MOVES WITH` is a **convention**, and it says what `MOVES WHEN` cannot: *"this entry moves when
its PAIR moves"* — two guards over one map from opposite sides, where naming a separate condition
would be a lie. **The existing guard is right to accept both.**

⛔ **The plan's gate — *"measure the distribution BEFORE touching either side"* — stopped me
tightening a guard onto 29 correct entries.** Seventh time in this programme that verifying a
suspicion before writing it prevented a false finding.

⛔ **But a THIRD form existed**: `context_health.py` carried `MOVES ON A SEAM DECISION`, normalised
to `MOVES WHEN`. A new guard (+10 tests) rejects a third form ⛔ **without demanding a mover** —
three tables correctly have none (`PULL_ONLY` ×2, `UNIT_TARGETS`), and demanding one everywhere is
*exactly the mistake the guard above it records making*.

⛔ **The mutation proves the refutation**: narrowing `MOVER_FORMS` to `("MOVES WHEN",)` — the "fix"
`F17` implied — fails on all 29. → [`STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md`](STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md)

## ⛔⛔ F47 · The 104 absence guards: the rule, not the rewrite — and a resolver that answered for 1 of 104

```
584   assert "..." not in <anything>
104   assert "..." not in src|code|source|text|blob|content|body
       78 CODE-shaped · 13 SQL-shaped · 13 that LOOK like prose, most of them code fragments
```

⛔ I built a resolver to find each guard's target file and check the phrase against **that** file's
own prose. ⛔⛔ **It resolved 1 of 104** — the dominant form is
`inspect.getsource(<an imported function>)`, and a function's defining module can only be found by
**importing** it.

> ⛔ **A resolver that answers for 1 of 104 answers nothing.** An earlier version reported *"0 at
> risk"* from that sample — **the most reassuring wrong number this programme could have produced.**
> Fourth name-shaped resolver of the session, and the first caught by checking its COVERAGE rather
> than its output.

⛔ **So the deliverable is the rule, not 78 rewrites.** Mechanical conversions with no measured
defect behind them is speculative work, and each one is a chance to change what a guard means. The
three that broke are fixed and pinned. The rule now lives in **`tests/README.md`**: a claim about
**prose** needs **attribution**; a claim about **code** needs the **AST** (and an attribution window
there is the *wrong tool*, not a weaker one); a **SQL construct** can stay a text check.

## ⛔ F48 · `F18` CLOSED — a real fix with an invented reason

`scripts/wipe_org_data.py` said the old exclusion *"omits MATERIALIZED views — `counterfactual_ledger`
(0072) slipped through."* ⛔ `0072` creates a **plain** view and says why. **A plain view IS listed in
`information_schema.views`**, so that exclusion would have caught it.

⛔ **No second cause was invented**: whatever let it through is not recoverable from the file, and
guessing would repeat the first mistake. The comment now says that, and says why the fix is right
**for a reason that does not depend on the story**: `table_type='BASE TABLE'` excludes every
non-table, present and future — **a positive selection cannot be out of date.**

> ⛔ *A real fix with an invented reason is the harder kind of stale comment to notice*, because the
> code around it is correct.

## ⛔ F49 · `F16` CLOSED — three counts, three meanings, none wrong when written

```
00-START-HERE        "53 tests"   ← ONE file, the day M14 shipped
01-CROSSCHECK        "87 tests"   ← a different scope, 2026-10-01
S5 measured          60 passed, 27 skipped
S9 measured         243 passed, 27 skipped
```

⛔ **The fix is the date, not the number.** Both are dated now and neither page carries a total:
the command is the answer — `.venv/bin/pytest tests/feedback -q -rs`, ⛔ **with `-rs` not optional**,
because the 27 skips are two files needing real Postgres (`H7`) and *a skip is not a pass*.

---

## What these findings change

| Finding | Effect on the plan |
|---|---|
| F9 | ⛔ **no wiring unit.** `feedback/` is wired; this is a **reading** pass |
| F10 | the spine: `U03`, `U04` — the layer's first correctness guards |
| F11 | each correctness receipt takes its evidence from a ledger already written and already indexed |
| F12 | `U04` gives `_by_run` its first query |
| F13 | `U05` — a reader for the refusal ledger, **or** a declared silence with a mover |
| F14 | ⛔ `U05` is gated: a receipt that fires on a known model outage is an alarm nobody can act on |
| F15 | ⛔ `U01` **answered on the day it was planned.** All 27 are DB skips → Harsh, with `H6` |
| F16 | `U09` |
| F17 | `U07`, and the measurement comes before the fix |
| F18 | `U10` |
| F19 | the method is recorded in `05-RECROSSCHECK` §1 so the next pass does not repeat it |
| F20 | `U02` — guards per package stops being prose and becomes data |
| ⛔ **F21** | `S2` **DONE** — the reason corrected and bound to the measurement. ⛔ **The MACV writer is Rohit's**, not a quiet fix |
| ⛔ **F22** | every "this false phrase is gone" guard in the programme is now suspect — `S9` re-checks them |
| ⛔ **F23** | `S3` **DONE** — the absence is representable, refused at two gates, and the skip does not burn the week |
| ⛔ **F24** | closed inside `S3`: the fail-closed and its reader are one unit |
| ✅ **F25** | nothing to do — a suspicion refuted. Recorded because the check is what has value |
| ⛔ **F26** | `S4` **DONE** — Atlas gap #2 **CLOSED by refutation**; the placeholders are DECLARED, not deleted |
| ⛔ **F27** | closed inside `S4` — link 5 reaches across the package boundary |
| ⛔ **F28** | every mutation run in this programme must distinguish an invalid mutation from a survivor |
| ✅ **F29** | nothing to do — a delegation I did not invent. Atlas gap #1's residue stands |
| ⛔ **F30** | `S5` **DONE** — gap #1's residue narrowed from *"no inbox"* to *"no `kind`"*. ⛔ **The surface is Rohit's** |
| ⛔ **F31** | `F10`'s *"0 correctness receipts"* is corrected: **1 of 5**, and it reads a column nobody read |
| ⛔ **F32** | ⛔ `S9` widens again — a guard asserting a CODE fact needs the AST, not an attribution window |
| ⛔ **F33** | the MINE table is rebuilt on the S-series; every scripted edit asserts its anchor |
| ⛔ **F34** | `S6` **DONE** — every refusal is named; `learning_object_evaluations` has its first reader |
| ⛔ **F35** | fixed at the source **and** guarded at the writer; ⛔ the past needs one read-only query |
| ⛔ **F36** | ⛔ `U03` is **un-retracted**; every earlier retraction in this programme now wants re-reading |
| ⛔ **F37** | `S7` **DONE** — the isolation ledger has a reader; unread ledgers **4 → 1** |
| ⛔ **F38** | fixed at the source and the seam names derived from the dataclass, so the typo cannot recur |
| ⛔⛔ **F39** | ⛔ **`context/` is the next layer to re-measure** — 50,877 lines, two guards. **Rohit's call** |
| ⛔ **F40** | every mutation harness now runs with bytecode caching OFF; all seven re-verified |
| ✅ **F41** | nothing to do — the guard did its job and the tally moved deliberately |
| ⛔ **F42** | `S8` **DONE** — the scorecard is `L1-to-L6`, **56** claims |
| ⛔ **F43** | ⛔ a *Present* badge is not a measurement — four cells hid a defect |
| ⛔ **F44** | `reset.py`'s justification corrected and tied to its fact across packages |
| ⛔ **F45** | the new section names the vocabulary in its first paragraph, every time |
| ⛔⛔ **F46** | `S9` **DONE** — ⛔ **`F17` is retracted as a false finding of mine**; the convention is declared and a third form is now impossible |
| ⛔ **F47** | ⛔ **`S9` does NOT convert the 104** — the rule is in `tests/README.md`, and the three that broke are pinned |
| ⛔ **F48** | `F18` closed — the cause corrected, and no second cause invented |
| ⛔ **F49** | `F16` closed — dated, and the command is the answer |

→ [`06-PLAN-the-second-pass.md`](06-PLAN-the-second-pass.md)
