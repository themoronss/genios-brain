# L6 · RE-CROSSCHECK — the loop that runs, and is never questioned

**Written for:** Rohit and Harsh · **Date:** 2026-10-02 · **No code written yet.**
**Supersedes nothing.** `01-CROSSCHECK.md` (2026-09-30) was M14's crosscheck and its findings
stand. This is a **second pass over the whole layer**, measured the way L5's `05-RECROSSCHECK` was,
after that pass found fourteen things a "COMPLETE" layer still carried.

```
feedback/      14 files · 3,111 lines      the smallest layer in the product
               (12 files · 2,737 lines when 01-CROSSCHECK was written — M14 added 374)
tests/feedback 60 passed · ⛔ 27 SKIPPED
receipts       4, every one labelled L7
```

---

## 1 · Method, and what was excluded

Every number below comes from one of three sources, and the command is given with each:

| | Source |
|---|---|
| reachability | `platform/reachability.py` — the machinery `STEP-17` extracted. A function is reached four ways and only three can be measured: a **call**, a **decorator**, a **reference**. Duck-typed dispatch is hand-checked |
| table read/write | `ast`-free grep over `genios_engine/` **and** `scripts/`, for `insert into X` / `update X` against `from X` / `join X` |
| receipts | `platform/receipts.py`, read as data — `claim`, `layer`, `sql`, `expect(0)`, `expect(1)` |

⛔ **One method error was found and corrected inside this pass.** The reader count
`from X`/`join X` **undercounts any table reached through a name constant**:
`context/authority_view.py:55` holds `AUTHORITY_TABLE = "authority_rules"` and builds the query
from it, so `authority_rules` read as having one reader (a receipt) when it has three. Every
"read by nothing" claim below was therefore **re-verified by a direct grep for the bare table
name**, not by the pattern. *A resolver that is merely stricter is not more correct.*

---

## 2 · ⛔⛔ THE HEADLINE · the loop runs — and every guard it has asks only whether it ran

### 2a · It runs. This is the opposite of L5.

L5's re-crosscheck found a four-tier delivery control plane with **no production evidence above
tier 1**. The equivalent question here has the opposite answer:

| | Where | What |
|---|---|---|
| the learning sweep | `api/routes.py:1274-1278` | `run_learning_sweep(_graph.engine, now=now)` — **inside the heartbeat** |
| calibration | `api/routes.py:1247-1264` | `run_calibration` per org × per active pack, **inside the same heartbeat** |
| org-rule discovery | `api/upload_routes.py:489`, `api/knowledge_routes.py:94` | `background_tasks.add_task(sweep_org_rule_discovery, org)` — on document upload |

And the heartbeat comment states the design: *"Weekly per tenant, enforced by a PostgreSQL
tenant/week claim (not process memory), so it is safe to call every heartbeat: a completed week is
a no-op."*

> ⛔ **`feedback/` is wired, scheduled and reached.** Eleven of its public functions are called or
> referenced from outside the package. There is no cutover gap here and no dead control plane.

### 2b · ⛔ And not one of its four guards asks whether the result is right

Every receipt is either a **presence** check (`expect(0)` False — zero is a failure) or a
**correctness** check (`expect(0)` True — any row is a failure). Measured:

| Package | Receipts | correctness | presence |
|---|---|---|---|
| `deliver/` | 8 | **5** | 3 |
| ⛔ **`feedback/`** | **4** | ⛔ **0** | **4** |

```
[L7] the learning engine has executed          expect(0)=False  → "has it run?"
[L7] calibration has executed                  expect(0)=False  → "has it run?"
[L7] the counterfactual ledger joins end to end expect(0)=False → "does the join reach?"
[L7] a human verdict has reached the loop       expect(0)=False → "has anything arrived?"
```

> ⛔⛔ **The learning loop is guarded only against not running.** Nothing asks whether a published
> brain value was governed, whether a proposal took a legal transition, whether a rule was muted on
> enough evidence, or whether an expired lease actually expired. **Four guards, four of them
> satisfied by a single successful tick.**

⛔ **This is not an oversight in the receipts; it is a property of what a presence receipt can
say.** A loop that runs weekly and writes four append-only ledgers can be entirely wrong and pass
all four. And `3,111 / 4 = 778` lines per guard is the **best ratio of any layer measured** — which
is exactly why guards-per-line was never going to find this. *Guards per line counts guards; it does
not read them.*

---

## 3 · ⛔⛔ The four ledgers nobody reads are the four that would answer the correctness questions

`feedback/` writes **19 tables**. Four are read by **nothing** — not by the engine, not by
`scripts/`, not by an API route, not by a receipt:

| Ledger | Migration | Written at | What the migration says it is for |
|---|---|---|---|
| `learning_transitions` | `0045` | `publisher.py:34` ⛔ **and `api/learning_routes.py:141`** | *"append-only state history (never rewrites the object)"* |
| `learning_object_evaluations` | `0046` | `orchestrator.py:197` | *"every actual per-run decision (new or held object)"*, pinned to run + policy revision |
| `learning_input_rejections` | `0046` | `store.py:193`, `org_rule_ingest.py:181` | *"sanitized isolation of a malformed/lineage-less input"* |
| `learning_metrics` | `0045` | `publisher.py:151` | *"measurement artifacts (not a brain)"* |

### ⛔ And each one already carries the column the missing receipt needs

| The question nobody asks | The ledger that already holds the answer |
|---|---|
| did any learning object take an **illegal** transition? | `learning_transitions (from_state, to_state)` — and `contracts/learning.py` already defines `ALLOWED_LEARNING_TRANSITIONS` |
| did a run **publish without a material change**, or hit an identity conflict? | `learning_object_evaluations.sink_reason` — `published_to_dynamic_target \| no_material_change \| metric_identity_conflict` |
| was anything published **outside the governing policy revision**? | `learning_object_evaluations (run_id, policy_revision, prior_state, result_state)` |
| is the loop **refusing everything it is fed**? | `learning_input_rejections (seam, reason_code)` |

> ⛔ **The data needed to guard the learning loop is already being written, in indexed append-only
> ledgers, and nothing asks it a question.** This is *a record nobody reads is presence without
> effect — the reader is half the unit*, at the scale of a whole layer rather than one function.

### ⛔ `learning_object_evaluations` carries TWO indexes for queries nobody wrote

```sql
create index if not exists learning_object_evaluations_replay
    on learning_object_evaluations (org_id, learning_id, evaluated_at);
create index if not exists learning_object_evaluations_by_run
    on learning_object_evaluations (org_id, run_id);
```

**An index is a statement that a query exists.** `_replay` names a replay path, and the migration's
own comment promises *"object replay never mutates the proposal"* — there is no replay query in the
engine, in `scripts/`, or in an API route. Two indexes are being maintained on every insert for
two readers that were never built.

### ⛔ And the sharpest instance states the defect in its own docstring

`feedback/org_rule_ingest.py:174`, `record_refusal`:

> *"A refusal that lives only in a return value is indistinguishable from a candidate the model
> never produced."*

That reasoning is correct, and it is why the refusal was promoted out of a return value into
`learning_input_rejections`. ⛔ **The ledger it was promoted into has no reader** — so the refusal
is now indistinguishable from a candidate the model never produced, one layer further down. The fix
moved the record; it never built the reader.

---

## 4 · The model-off path, and where its failures go

⛔ **`feedback/` has exactly one model-call site:** `org_rule_ingest.run_org_discovery`, whose
docstring gives doc 02 §L3.2-U1's six steps — *"trigger, model call, deterministic validation,
propose into L6 at OBSERVED, govern through the existing pipeline, and — on confirmation, not here —
serve."* Everything else in the layer is deterministic; `attribution.py:35` says so explicitly:
*"PURE. No I/O, no clock, no model."*

The Anthropic spend limit has refused every model call since **2026-09-25 11:09 UTC**, so this is
the one path in `feedback/` that is currently model-off. Its failures are recorded, and **the two
outcomes go to different places**:

| Outcome | Recorded in | Read by |
|---|---|---|
| the model raised | `org_rule_discovery_runs`, `outcome='extractor_failed'` | ✅ `org_rule_ingest.py:235` — its own writer |
| a candidate was **gated out** | ⛔ `learning_input_rejections` | ⛔ **nothing** |
| the document is not rule-bearing | both, `outcome='kind_not_rule_bearing'` + a refusal row | partly |

⛔ **So a model outage is visible and a refusal is not.** The cost gate before the model call is
good design — *"Paying for a T2 extraction to read a wiki page is how a per-document unit becomes a
per-document bill"* — and its own accounting is the half that has no reader.

---

## 5 · What is NOT wrong

| | Why it survives |
|---|---|
| M14's three units | the attribution vocabulary, eleven reasons across all five readers, and the layer debit. 11 reasons → one layer each, closed both directions |
| the precision rule | *"a timing complaint never lowers a correct rule's precision"* is enforced in **three** places and documented from a fourth. M14 added the guard over the thing that already worked |
| the governance bounds | `MUTE_PRECISION = 0.25` with `MUTE_MIN_JUDGMENTS = 12` (a cold rule cannot be muted on noise), `OFFSET_STEP = 5`, `OFFSET_BOUND = 15` (learning cannot run away), Wilson intervals so 8 judgments do not read like 800 |
| the weekly claim | a PostgreSQL tenant/week claim rather than process memory, so a restart cannot double-run a tenant |
| `counterfactual_ledger` | ⛔ a **VIEW** (`0072`), not a table — nothing writes it **by design**: *"every source is already append-only/versioned, so materialising a copy would be a second thing to keep honest."* Its receipt tests whether a seven-table join chain reaches end to end, which is a real gate |
| the 5 declared silences | `feedback_health.py`, both directions guarded. Two are build-time property guards and are correctly filed as such — *a function that takes no data cannot be measuring production* |
| the import direction | `feedback/consumer.py` records a real correction: a consumption contract only the producing layer could import was *"a decoy seam"*, and the vocabulary moved to `contracts/` |

⛔ **One near-miss of my own, caught before it was written down.** My first table measurement
reported `counterfactual_ledger` as having **no writer anywhere** and I was one step from filing it
as a defect. It is a view. *This is the second time in two layers that a "nothing writes/calls it"
measurement was true and the conclusion would have been false* — the first was
`realtime.purge_expired`, reached by duck-typed dispatch.

---

## 6 · Smaller findings, each measured

| | Finding |
|---|---|
| ⛔ **27 skipped tests in `tests/feedback`** | `60 passed, 27 skipped`. **A skip is not a pass**, and no document in this folder mentions them. What they skip on is not yet established |
| ⛔ **two documents disagree about the test count** | `00-START-HERE.md` says *"53 tests"*; `01-CROSSCHECK.md`'s 2026-10-01 addendum says *"3 steps, all DONE, 87 tests"*. The directory runs 60 + 27 skipped |
| ⛔ **`00-START-HERE.md` says `COMPLETE`** | and this re-crosscheck exists because it was not. ⛔ The same file's own `01-CROSSCHECK` addendum warns that *"a reader scanning for status reads that line as current, and this programme has now paid for that mistake three separate times"* |
| ⛔ **a mover-convention deviation the guard cannot see** | `feedback_health.py` uses **`MOVES WITH`** for `every_legacy_reason_still_grades_the_way_it_did`; the convention elsewhere is `MOVES WHEN`. `test_every_entry_carries_a_reason_and_a_mover` only requires *"at least two parts"*, so it passes. **A guard hole, not a defect** — and the distribution across all ten declaration modules has not been measured |
| ⛔⛔ **RETRACTED 2026-10-02 by `S9`** | **My own false finding.** `MOVES WITH` is in **nine of thirteen** declaration modules (29 vs 115) — a CONVENTION, and the guard is right to accept both. ⛔ A third form DID exist and is now impossible. → ../layer-6-learning/STEP-S9-DONE-the-paperwork-and-a-finding-of-mine-refuted.md |
| ⛔ **a stale comment in `scripts/`** | `wipe_org_data.py:40` says the old exclusion *"omits MATERIALIZED views — `counterfactual_ledger` (0072) slipped through."* `0072` creates a **plain** view and says why it is not materialised. The comment's **reason** is wrong; the fix it justifies (select base tables positively) is correct regardless. Sixth instance of *a stale comment reads as a measurement* |
| `card_feedback_verdicts` is written by `api/`, not `feedback/` | 2 writes in `api/`, 0 in `feedback/`. The human verdict arrives at the transport surface and the loop reads it — correct, and worth stating because it means one of `feedback/`'s four guards measures a table the layer does not own |

---

## 7 · ⛔ A correction this pass forced on L5

Asking *"which receipts guard `feedback/`?"* is what exposed that `Receipt.layer` is a hand-written
digit, not a package. `STEP-10`'s central number was wrong: `deliver/` carried **5** receipts and
**4** of them worked, not 2 and 1. Full record, with the eleven documents it touched:
[`../layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`](../layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md).

⛔ **`feedback/` is guarded by the four receipts labelled `L7`**, which is why this document never
says "L6's receipts".

---

## 8 · The pattern, seven passes running

| Layer | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L2 | plan compile should fail on an unproduced source | it did — **six units to one absent fact** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| L5 | the delivery layer has two guards for 9,431 lines | ⛔ **five, four of them working** — and the label was never a package |
| L6 (M14) | a timing complaint must stop lowering precision | it already did, in **three** places |
| ⛔ **L6 (this pass)** | **the learning layer is `COMPLETE`** | ⛔ **it runs, it is wired, and nothing it writes is ever questioned** |

---

## 9 · What is yours to decide

| | |
|---|---|
| ⛔ **the eleven "Wrong" reasons** | carried over from M14 and still open. *Eleven radio buttons is a worse experience than three.* `_WRONG_REASON_GROUPS` gives a surface four headings; narrowing what is **displayed** is a one-line surface change and never a change to the vocabulary underneath |
| ⛔ **relabelling the receipts** | `receipts(layer)` filters on that string, so moving a receipt between labels changes which ones a layer-scoped operator run executes. **I have not touched a label.** |
| ⛔ **the four unread ledgers** | each is either *a reader was never built* or *a deliberate write-only audit trail*. Three of the four read as the former. ⛔ **Which they are is a decision, and declaring them deliberate without asking would invent a reason** |

→ the plan this produces: [`06-PLAN-the-second-pass.md`](06-PLAN-the-second-pass.md)
