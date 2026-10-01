# Step 2 — ⛔ RETIRED · a dropped unit leaves a receipt naming its missing input

> **Tree:** `M11.C1.U02` · **Section S1**
> **Retired 2026-09-30, and no test was written either — because one already exists and passes.**

---

## 1 · What was expected

`03-PROGRAM.md` / `tree.yaml` `M11.C1.L-logic.V1.U02`:

> A dropped unit leaves a `SkippedStep` receipt naming the input it lacked and its candidates.
> **Verify:** `pytest tests/reason/adapters/test_a_skip_names_its_missing_input.py`

The plan for this step was: write that test, run it against the existing code, retire the unit on
green.

## 2 · What is actually true

**Both the code and the test already exist.** The test is not the file the tree named — it is
`tests/reason/test_selector_and_registration.py`, and it asserts exactly this unit's claim:

```python
def test_a_unit_whose_every_source_went_is_dropped_and_names_all_of_them():
    """Nothing left to read is still a drop, and the receipt names every source that went."""
    ...
    dropped = {step.reasoner_id: step for step in plan.skipped}
    assert dropped["core.tension"].reason_code == "dependency_not_scheduled"
    assert dropped["core.tension"].missing_fields == ("core.clock", "core.money")
```

`reason_code` is the receipt; `missing_fields` names **every** input that went. That is the unit, in
full.

```
$ uv run --no-sync pytest tests/reason/test_selector_and_registration.py -q
..............                                                           [100%]
14 passed in 0.07s
```

And production carries the rows to prove it runs: **3,102 of 26,396** `reasoning_reasoner_results`
rows are `skipped` with a `skip_reason_code`, measured in
[STEP-01](STEP-01-DONE-prove-the-claims.md).

⛔ **So I wrote no code and no test.** A second test asserting a passing assertion is a duplicate, and
this is the second time in this programme a planned unit turned out to be built — the first was L3's
withdrawn compare-and-set. **Writing the duplicate anyway is how a codebase ends up with two tests
that must be kept in agreement forever.**

## 3 · ⛔ And that same test file proves the gap S2 actually has

The test immediately above it, also passing:

```python
def test_a_unit_that_lost_one_of_three_sources_still_runs_on_the_two_it_kept():
    ...
    assert "core.tension" in plan.reasoner_plan                              # KEPT
    assert [step.reasoner_id for step in plan.skipped] == ["core.money"]     # only core.money
```

Read the second assertion carefully. `core.tension` was **kept**, it **lost** `core.money`, and the
plan's `skipped` list mentions **only `core.money`** — nothing anywhere records that `core.tension` is
now reasoning over two sources instead of three.

> ⛔ **The gap S2 exists to fill is asserted, in the positive, by a passing test in this repository.**
> Not inferred, not measured indirectly — written down as the expected behaviour.

That is a much stronger justification than the one `03-PROGRAM.md` gave S2, which
[STEP-01](STEP-01-DONE-prove-the-claims.md) proved false.

## 4 · What the tree said, and what is wrong with it

| | |
|---|---|
| `tree.yaml` verify | `tests/reason/adapters/test_a_skip_names_its_missing_input.py` |
| that file | ❌ **does not exist, and should not be created** |
| the test that does this | `tests/reason/test_selector_and_registration.py` |

⛔ **The tree row named a file nobody had written and nobody needed to.** Same defect class L3 found in
its own tree rows: a verify command that cannot run is not a verify, and it reads as untested work
when the work is in fact tested somewhere else.

`M11.C1.U02` is **retired**, and its id is never reused.

## 5 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| a unit whose every source went | dropped, with a receipt naming all of them | ✅ already tested, passing |
| the receipt's `reason_code` | `dependency_not_scheduled` | ✅ asserted |
| the receipt's `missing_fields` | every source that went | ✅ asserted, both of them |
| a unit that lost one of three sources | ⛔ kept — **and nothing records the loss** | ✅ asserted, and this is the S2 gap |
| production evidence the receipt runs | non-zero skip rows | ✅ 3,102 of 26,396 |
| code changed | **none** | ✅ |
| tests added | **none** | ✅ |

## 6 · For Rohit — nothing

No code, no migration, no decision. The value of this step is the retirement and the discovery in §3.

## 7 · For Harsh — one line to know

`tests/reason/test_selector_and_registration.py` is the file that covers the selector and the
registration checks. Its docstring describes the two defects this area used to have, and it is the
first place to look before changing anything in `reason/plan.py` or `reason/registry.py`.

---

## Running count of planned units that turned out to be built

| Layer | Unit | Already built at |
|---|---|---|
| L3 | `M10.C1.U03` compare-and-set | `reason/runner.py:570`, 6 passing tests |
| L2 | `M11.C1.U02` the skip receipt | `reason/plan.py:258`, covered by a passing test |

⛔ **Two in two layers.** S1 is not overhead — it is the cheapest unit in the programme.
