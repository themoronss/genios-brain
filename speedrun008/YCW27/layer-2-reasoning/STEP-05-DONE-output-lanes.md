# Step 5 — ✅ DONE · the five output lanes, and the router

> **Tree:** `M11.C2.U01–U04` · **Section S3** · 4 units · **170 tests**
> ⛔ **Read §9 first** — my first design broke four replay tests in files I never touched.

---

## 1 · What was expected

*"The five output lanes, and the router that chooses one deterministically."* Atlas v2:
**decision · investigation · conflict · monitor · suppress**.

## 2 · What is actually true

Genuinely missing — `"investigation"` **0 hits**, `OUTPUT_LANE` **0**, `LANES =` **0**. But four of the
five words were already taken, in three unrelated enums:

| Word | Already means | Where |
|---|---|---|
| `suppress` | a delivery decision, and a feedback outcome | `contracts/delivery.py:87`, `contracts/outcomes.py:56` |
| `monitor` | an execution mode | `contracts/execution.py:131` |
| `conflict` | two sources disagreeing — an L3 hold reason | `context/situation_publisher.py` |
| `lane` | ⛔ a **PACK** lane — whether a card can cite an expert | `reason/uncited_lanes.py` |

## 3 · Two hard constraints, both from measured collisions

**⛔ 1 · The lanes are NOT `DecisionOutcome`.** Six members there —
`decision · no_action · defer · insufficient_context · blocked · failed` — and the contract defends
them: *"A projection that only carries `decision` loses five sixths of the vocabulary."*

| | Question it answers |
|---|---|
| `DecisionOutcome` | did we reach a decision, and if not why |
| `OutputLane` | what kind of output should the human see |

**Orthogonal.** A `decision` outcome routes to DECISION **or** MONITOR depending on confidence, so one
field cannot carry both.

**⛔ 2 · Named `OutputLane`, never a bare `lane`.** `uncited_lanes.py`'s own docstring records what the
conflation cost: *"Layer 2 lost five readings to exactly that ambiguity."* A `Lane` beside it would be
read as the same concept by the next person.

## 4 · What was built

| Unit | Artifact |
|---|---|
| `U01` | `contracts/reasoning.py` · `OutputLane` + `OUTPUT_LANES` |
| `U02` | `reason/output_lane.py` · `route()` — pure, no model |
| `U03` | same · `reachable_lanes()` — **totality, both directions** |
| `U04` | `reason/decision_maker.py` (routes) · `reason/domain_shadow.py` + `migrations/0189` (projects) |

## 5 · ⛔ The precedence, and why conflict is first

```
1. conflict open            -> CONFLICT      beats everything, INCLUDING confidence
2. FAILED                   -> SUPPRESS      ours to fix, not a business question
3. BLOCKED  + actionable    -> INVESTIGATION the reader can clear it
   BLOCKED  + not           -> SUPPRESS      ours too
4. INSUFFICIENT_CONTEXT     -> INVESTIGATION naming the gap IS the output
5. DEFER                    -> MONITOR       deliberately waiting
6. NO_ACTION                -> SUPPRESS      deliberately nothing
7. DECISION  >= floor       -> DECISION
   DECISION  <  floor       -> MONITOR       a move without the standing to assert it
```

**⛔ Conflict outranks a 10,000 bp decision.** A confident decision is the **most** dangerous thing to
publish over an open disagreement, not the least: publishing either side while it stands erases the
disagreement by omission — the principle `CONFLICT_OPEN` enforces one layer down. Confidence is not
allowed to outrank it.

**⛔ A decision under the floor becomes MONITOR, not SUPPRESS.** Going quiet would say *"over"* when the
thing is still live. Asserting anyway is how a card teaches a founder to distrust the product.

**⛔ SUPPRESS is recorded silence, not absence.** The lane is stored on the decision, so *"we withheld,
deliberately, for this reason"* is answerable later. Suppression that left no trace is the defect this
programme has found in six other places.

**DEFER → MONITOR and NO_ACTION → SUPPRESS** is why both lanes exist: *"deliberately waiting"* and
*"deliberately nothing"* are different promises.

## 6 · Totality, both directions

| | |
|---|---|
| forward | all **96** input combinations reach exactly one lane, each with a reason |
| backward | `reachable_lanes()` enumerates the inputs and returns all five |

⛔ **The backward half is the one usually missing.** A lane nothing routes to is dead vocabulary, and
dead vocabulary gets "fixed" later by somebody widening a condition until it is reachable — at which
point the widening, not the design, decides what a reader sees.

## 7 · ⛔ Two things I trimmed on measurement

**`reasoning_run_outputs` got no columns.** My plan said "the lane on all five `DECISION_PROJECTIONS`".
Columns there would **duplicate a value in the same row**, and a duplicated value can disagree with its
original. Adding them with no writer would be worse — the eighth *"built, green, called by nothing"*.
Migration 0189 says so in a comment, and a test asserts the absence.

> ⛔ **CORRECTED 2026-09-30 (during L5 STEP 01).** The paragraph above originally justified this with
> *"that row already carries the lane: `to_semantic_dict` includes it, so it is inside `decision_hash`."*
> **That reasoning was withdrawn later in the same step** — see §9 below and
> `test_the_lane_is_kept_OUT_of_the_decision_hash`. The lane is **not** in `to_semantic_dict` and **not**
> in `decision_hash`, because `route()` is a pure function of `outcome`, `confidence_bp` and the conflict
> flag, all already hashed: the lane adds **zero** information, and a derived value has no business in a
> content hash.
>
> **The conclusion still stands and the reason is now the simpler one:** `reasoning_run_outputs` gets no
> lane columns because nothing would write them. `0189`'s file header carries the same stale sentence and
> **cannot be edited** — a migration's checksum is its immutability — so that correction is recorded
> append-only in `0190_card_lane.sql`, where a test asserts it is present.

**`reader_actionable_block` is conservatively `False` at the decision seam.** Claiming a block is
reader-actionable when it is not would put our own plumbing in front of a founder as a business
question. That seam does not know, so it says nothing rather than guessing.

## 8 · ⛔ My own test failed for the exact reason the lanes exist

`test_every_lane_is_documented[decision]` failed on its first run: it searched the whole module for
`DECISION = "decision"` and found **`DecisionOutcome.DECISION`**, which appears earlier in the file.

> The collision these tests are about bit the test written for them. Fixed by scoping the search to
> `inspect.getsource(OutputLane)`, with the reason written into the helper.

A second test also failed by grepping for `"model"` and matching the router's own docstring explaining
that no model runs there. Rewritten to check **imports via `ast`** — which is the actual guarantee.

## 9 · ⛔ The correction that cost four replay tests — and it was mine

I first folded the lane into `ReasoningDecision.to_semantic_dict`, reasoning that *"a decision routed
differently IS a different decision, so it belongs in `decision_hash`."* I even wrote a test asserting
it.

**The full suite failed four tests:**

```
FAILED tests/reason/test_ranking.py::test_the_run_replays_byte_for_byte
FAILED tests/reason/test_ranking.py::test_the_compiled_lane_could_not_be_replayed_before_this_wave
FAILED tests/reason/test_selected_runs_are_auditable.py::test_a_selected_bundle_still_verifies_every_persisted_hash
FAILED tests/test_reasoning_audit_replay.py::test_replay_bundle_verifies_every_persisted_semantic_hash_before_execution

genios_engine.reason.store.ReplayIntegrityError: contract decision hash integrity mismatch
```

### My first fix was wrong too

`store.py:2168` documents this exact failure happening before, when the weld added `citations`:

> *"this rebuild used to know about none of them — so the moment Layer 3's weld put `citations` on a
> compiled decision, every compiled bundle failed here with `contract decision hash integrity
> mismatch` and the lane's replay guarantee was gone without a single test going red."*

So I added `output_lane` to the rebuild list and to `audit._output`. **Three of four tests went green**
and a fifth went red: `test_a_legacy_decision_envelope_persists_the_bytes_it_always_persisted`, which
extracts the **pre-wave** `_output` from git and runs it beside the current one.

### ⛔ What was actually wrong

`route()` is a **pure function of fields already in the hash** — `outcome`, `confidence_bp`, and the
conflict markers inside `uncertainty`.

> **A derived value has no business in a content hash.** The lane adds **zero information** to the
> content address while changing the identity of every decision that carries one.

`ReasoningDecision` already makes this exact argument about `reasoning_bundle`, in its own words:
*"the narrative cannot be part of the thing it narrates."* I had the precedent in the same class and
reached for the opposite.

### The resolution, in three places that must agree

| Place | What it does now |
|---|---|
| `contracts/reasoning.py` | ⛔ lane is **NOT** in `to_semantic_dict` |
| `reason/audit.py` | does **NOT** persist it into `decision_core` |
| `reason/store.py` | does **NOT** restore it on rebuild |

Any one of the three disagreeing reproduces `contract decision hash integrity mismatch`.
`test_neither_the_audit_envelope_nor_the_replay_rebuild_carries_the_lane` asserts all three at once.

And the property is now asserted on **real objects**, not on source text: a routed and an unrouted
decision with the same content hash **identically**.

### What I did to my own tests

Four of my tests asserted the wrong property. I did not widen them — I **replaced** them with the true
one and wrote the reason into the docstring, because a test edited to match broken code is worse than no
test. `test_the_lane_is_kept_OUT_of_the_decision_hash` names all four replay tests that caught it.

⛔ **This is why the full suite runs before a step is called done.** The four tests that caught it are in
three files I did not touch, testing a property I did not know I was breaking.

## 10 · Verify

```
$ uv run --no-sync pytest tests/contracts/test_the_output_lanes_are_not_the_outcomes.py -q
18 passed
$ uv run --no-sync pytest tests/reason/test_every_decision_reaches_exactly_one_lane.py -q
135 passed
$ uv run --no-sync pytest tests/reason/test_the_lane_reaches_every_projection.py -q
16 passed
```

## 11 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| all 96 input combinations | exactly one lane each, with a reason | ✅ |
| every lane | reachable | ✅ all five |
| an open conflict + 10,000 bp decision | ⛔ **CONFLICT** | ✅ |
| an open conflict + any outcome | CONFLICT | ✅ the only lane it can produce |
| a decision at the floor | DECISION | ✅ inclusive |
| a decision 1 bp under | MONITOR, **not** SUPPRESS | ✅ and the reason names both numbers |
| confidence on any other outcome | changes nothing | ✅ splits only `DECISION` |
| `DEFER` vs `NO_ACTION` | MONITOR vs SUPPRESS | ✅ different promises |
| `FAILED` | SUPPRESS, *"ours to fix"* | ✅ recorded, not hidden |
| `BLOCKED` + actionable | INVESTIGATION | ✅ |
| the actionable flag on other outcomes | no effect | ✅ |
| a `LaneChoice` with a blank reason | refused | ✅ *"undiagnosable"* |
| the router's imports | no clock, no model, no database | ✅ checked via `ast` |
| an **unrouted** decision | the `decision_hash` it had before | ✅ |
| a **routed** decision | ⛔ **the same hash as an unrouted one** | ✅ the lane is derived, so it adds nothing |
| the audit envelope | does not persist the lane | ✅ |
| the replay rebuild | does not restore the lane | ✅ all three agree |
| a lane with no reason in the database | refused | ✅ both check constraints |

## 12 · For Rohit

**One migration to apply: `0189_output_lane.sql`.** Adds two nullable columns to `signals`.

⛔ **And one naming decision I made and am flagging**, since I recommended it and then acted on it: the
concept is `output_lane`, never a bare `lane`, because of the `uncited_lanes.py` collision. Say the word
if you want it called something else — it is two renames now and many later.

## 13 · For Harsh

`signals.output_lane` and `signals.lane_reason` are now written on every compiled-lane card. `NULL`
means the row was never routed (everything before migration 0189). The card layer can group by lane
directly — it does **not** need to re-derive it, which is the point of the flat projection.

`DEFAULT_DECISION_FLOOR_BP = 6000` is the confidence at which a decision is asserted rather than
watched. That number is a policy choice sitting in code; if it wants to be per-tenant, that is a unit,
not an edit.
