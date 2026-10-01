# Step 3 — ✅ DONE · a kept unit that lost a source says so

> **Tree:** `M11.C1.U01a/b/c` · **Section S2** · 3 units · **38 new tests** (plus 14 pre-existing selector tests kept green)

---

## 1 · What was expected

`03-PROGRAM.md`: *plan compile **fails** when a scheduled unit declares a source no other scheduled
unit produces.*

## 2 · What is actually true

⛔ That rule existed and was **deliberately removed.** `reason/plan.py:229`:

> *every* declared field had to be absent before a unit was dropped, but *any* dropped dependency
> dropped its dependent. ... **six units lost to one absent fact.**

So building it as written would have been a regression. The settled rule — *a unit is dropped when it
has NOTHING left to read* — stands.

**What was actually broken** is asserted, in the positive, by a passing test in this repository
(`test_selector_and_registration.py:86`):

```python
assert "core.tension" in plan.reasoner_plan                            # KEPT
assert [step.reasoner_id for step in plan.skipped] == ["core.money"]   # only core.money
```

`core.tension` was kept, it lost `core.money`, and **nothing recorded it.** Its reading is computed
over a narrower set of inputs than it declared and reported as if it read them all — the `not_carried`
shape, and the coverage defect one layer down.

## 3 · What was built — a receipt, never a refusal

| Unit | Artifact |
|---|---|
| `U01a` | `reason/plan.py` · `DegradedStep` |
| `U01b` | `reason/plan.py` · computed in `_select`, added to `ExecutionPlan.degraded` |
| `U01c` | `reason/orchestrator.py` · carried into the decision's `uncertainty` |

`DegradedStep` names **what it kept**, not only what it lost: *"lost `core.cost`"* does not say whether
two sources remained or none, and those are different readings.

## 4 · ⛔ A pre-existing test caught my design being backwards on the most important case

The first `DegradedStep` refused an empty `available_sources`, on the theory that a unit with nothing
left to read is always skipped. Then:

```
FAILED tests/reason/test_selector_and_registration.py::test_a_required_dependent_survives_the_loss_of_every_source
```

The starvation rule applies to **OPTIONAL** units only — `_select`: *"a required unit's missing input is
a fact the decision must confront, not one the schedule may hide."* So:

| | every source gone |
|---|---|
| **OPTIONAL** | dropped, and `skipped` receipts it |
| **REQUIRED** | ⛔ **KEPT, running on nothing** — and only `starved` says so |

> ⛔ **My constructor was raising an error on the single most important case the receipt exists to
> record.** Fixed: the refusal is gone, `starved` is a named property, and `explain()` says *"ran on
> NONE of its N declared sources"*.

## 5 · Verify

```
$ uv run --no-sync pytest tests/reason/test_a_kept_unit_says_what_it_lost.py -q
27 passed
$ uv run --no-sync pytest tests/reason/test_a_lost_source_reaches_the_decision.py -q
11 passed
$ uv run --no-sync pytest tests/reason/test_selector_and_registration.py -q
14 passed                       # pre-existing, and one of them caught my design being backwards

$ uv run --no-sync pytest tests/reason tests/test_reasoning_plan.py tests/test_l2_reads_what_l1_publishes.py -q
1021 passed, 96 skipped in 160s
```

## 6 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| ⛔ **4 fact combinations** | the same units kept and dropped as before | ✅ **provably additive** |
| selection dropped nothing | nothing recorded | ✅ both lists empty |
| a capability that did not opt in | nothing recorded | ✅ not "we did not look" — there was nothing to look at |
| lost 1 of 3 sources | kept, and the loss named | ✅ |
| lost 2 of 3 | still a reading, still receipted | ✅ |
| **REQUIRED**, lost 1 of 1 | ⛔ kept, and flagged `starved` | ✅ `share_lost_bp == 10000` |
| **OPTIONAL**, lost all | skipped, **never** degraded | ✅ the starvation rule, from the receipt's side |
| a receipt that lost nothing | refused | ✅ it would make "how many ran on full input?" unanswerable |
| kept + lost ≠ declared | refused | ✅ it would describe a plan that was not made |
| a degraded plan | a different `plan_hash` | ✅ |
| an **intact** plan | ⛔ **no `degraded` key at all** | ✅ see below |
| the receipt's order | sorted | ✅ or the hash depends on dict iteration order |

## 7 · Two decisions worth knowing

**⛔ `degraded` is absent from `to_semantic_dict` when empty.** Adding `"degraded": ()` to every plan
would change `plan_hash` for **every plan ever computed**, breaking replay verification and audit
continuity for runs that degraded nothing. An absent key and an empty tuple mean the same thing; only
one of them costs the trail. `contracts/reasoning.py` already applies this rule to `citations` and
`constraints_applied`, in those words.

**⛔ The `degraded=` flag into the decision maker was deliberately NOT changed.** It feeds confidence,
so folding planner degradations into it would change **decisions** — arguably for the better, since a
required unit running on none of its declared sources is unambiguously a degraded run. But that is a
behaviour change nobody asked for. **Open question, recorded, not decided.**
`test_the_degraded_flag_still_comes_only_from_optional_degradations` asserts the omission so that if
somebody later folds it in, the test fails and is deleted **on purpose** rather than quietly widened.

## 8 · For Rohit

**Nothing to do.** No migration, no config. One open question above (should a starved required unit
lower confidence?) — worth an answer eventually, blocks nothing.

## 9 · For Harsh

`ExecutionPlan.degraded` is new and populated. It reaches the decision's `uncertainty` as
`degraded_sources:<unit>:2of3` or `starved_sources:<unit>:0of1`. If you surface uncertainty on a card,
those two markers are the ones that say *"this reading was computed over less than it declared."*
