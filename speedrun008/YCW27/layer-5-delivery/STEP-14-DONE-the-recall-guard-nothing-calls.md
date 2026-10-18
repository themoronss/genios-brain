# Step 14 — DONE · the recall guard nothing calls

**Unit:** `M13.C3.U14` · **Owner:** me · ✅ **2026-10-01** · 12 tests · ⛔ **one mutation survived the first pass — §4**
⛔ **This programme built the defect, and my first diagnosis of it was wrong about two of the three.**

## 1 · What is there

`deliver/lane_recall.py` — M13 `STEP-02`, written **2026-09-30**, titled *"nothing dies quietly"*,
**24 tests**, full suite green. Three public functions:

| | |
|---|---|
| `recall_verdict` | *"Do the per-lane tallies add up to the cards this pass built?"* — `built` + `refreshed`, not `built` alone |
| `low_confidence_is_never_silent` | *"Walk the real router: no decision under the floor may land in a silent lane."* Returns the counter-examples, so a failure names the confidence and the lane |
| `every_lane_is_visible_or_deliberately_silent` | *"Totality, both directions, over the display vocabulary.* A lane in neither set is a lane whose visibility nobody decided" |

⛔ **Nothing in the engine imports the module. Its three functions have 9 test callers and 0 engine
callers.** Three files mention `lane_recall` and **all three are comments**:

| | |
|---|---|
| `lane_display.py:126` | `#: trusting that they do — `lane_recall.recall_verdict` does exactly that.` |
| `pipeline.py:516` | `# … `lane_recall.recall_verdict` a tautology, since the tally and the comparison would …` |
| `reason/domain_shadow.py:1308` | `# … the argument `deliver/lane_recall` makes about …` |

## 2 · ⛔ Why this is the worst of the findings

The second comment is the one that stings. `pipeline.py:516` is **reasoning about this function's
correctness** — explaining how the tally was deliberately shaped so that `recall_verdict` would not be
a tautology. **The code was designed around a guard that never runs.**

And the shape of it:

> ⛔ **Ninth instance of built-tested-green-and-called-by-nothing in this programme, and the second of
> its own making.** `01-CROSSCHECK §1` found the first: `signals.output_lane` written by the router and
> read by nothing. The unit that closed it — M13 `STEP-01`/`STEP-02` — produced this one.
>
> **Doctrine: a finding's fix is the most likely place for the next instance of the same finding.** It
> ships under the confidence of having just understood the problem, and the question that got asked was
> *"what should this compute?"* rather than *"who calls it?"*

`lane_recall.py`'s own header says **"THIS UNIT WAS REWRITTEN… A CORRECTION TO THE PLAN."** The rewrite
was right about what to build. It never answered who invokes it.

## 3 · ⛔ The measurement this step does FIRST, because the answer is not obvious

A recall guard is not a function you call once. It is a **comparison across a pass**, so the question is
*where does a pass end?*

| Candidate | Must measure |
|---|---|
| `pipeline.py` at the end of a build pass | it has the tallies in hand — `lane_display.tally_lane` is called there. ⛔ But a guard inside the thing it guards can be skipped by the same early return that skips the tally |
| `outbox.drain`'s sweep totals | the sweep is where `shadow_resolve_v2`'s counters accumulate, so there is precedent for a measurement living there |
| a receipt in `platform/receipts.py` | ⛔ **the strongest candidate.** A recall guard asks a question of production data, which is exactly what a receipt is — and L5 has only two receipts for 9,431 lines ⛔ **[CORRECTED: five — [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md)]** |
| `reason/domain_shadow.py` | its comment already invokes `lane_recall`'s argument, and it is where the lane is written |

⛔ **The receipt option would also close part of `STEP-10`**, and that is a reason to prefer it, not a
reason to skip the measurement. *A gate is decomposed, not read.*

## 4 · What to build

| | |
|---|---|
| whichever caller §3 measures to be right | the call site, with the verdict **acted on** — a verdict computed and discarded is the same defect one layer up |
| `platform/receipts.py` | ⛔ likely: a receipt carrying `low_confidence_is_never_silent`'s question. It must be **able to fail** — *a receipt that cannot fail is not a gate* |
| `deliver/delivery_health.py` | ⛔ **delete the three `KNOWN_UNWIRED` entries** the moment they are wired. L4 deleted `monitor.blocking_action` from `UNREACHED` on exactly this trigger, and the both-directions test fails the build if they are left behind |
| `tests/deliver/test_the_recall_guard_runs_on_a_pass.py` | ⛔ NEW |

## 5 · The tests

| Test | Assertion |
|---|---|
| `test_a_pass_computes_a_recall_verdict` | the guard runs |
| `test_the_verdict_is_acted_on_and_not_discarded` | ⛔ the real risk: `recall_verdict(...)` called and its result dropped |
| `test_a_dropped_card_makes_the_verdict_fail` | ⛔ seed the failure. A guard that cannot go red on a real miss is decoration |
| `test_the_guard_runs_even_when_the_pass_builds_nothing` | ⛔ an empty pass is exactly when a silent drop hides |
| `test_the_declaration_no_longer_claims_these_are_unwired` | the both-directions guard from STEP-05 |

## 6 · Verify

```
.venv/bin/pytest tests/deliver/test_the_recall_guard_runs_on_a_pass.py \
                 tests/deliver/test_nothing_dies_of_low_confidence.py -q
.venv/bin/pytest tests/deliver/ tests/platform/ -q
```

## 7 · Mutations

| # | Mutation | Must go red |
|---|---|---|
| M1 | call the guard, discard the result | `test_the_verdict_is_acted_on_and_not_discarded` |
| M2 | skip the guard when the pass built zero cards | the empty-pass test |
| M3 | compare against `built` alone instead of `built + refreshed` | ⛔ the fault `recall_verdict`'s own docstring records |
| M4 | leave the `KNOWN_UNWIRED` entries in place | STEP-05's `now_called` test |

## 8 · Expected outcome

The guard this programme wrote to prove nothing dies quietly actually runs, its verdict is acted on, and
three `KNOWN_UNWIRED` entries are deleted rather than explained.


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔ The measurement came first, and it corrected the step

`§3` listed four candidate call sites and said the answer was not obvious. **The measurement made it
obvious, and it also shrank the step by two thirds.** `lane_recall.py`'s own header states:

> **"PURE. No I/O, no clock, no model."**

And the three signatures:

```
recall_verdict(counts: Mapping[str, Any]) -> RecallVerdict          ← takes the pass's tallies
low_confidence_is_never_silent(*, floor_bp=DEFAULT_...) -> ...      ← takes NO data
every_lane_is_visible_or_deliberately_silent() -> ...               ← takes NO ARGUMENTS AT ALL
```

| Function | Verdict |
|---|---|
| `recall_verdict` | ⛔ **a real gap.** It consumes a pass's counters, and `pipeline.build_cards_for_org` holds them |
| `low_confidence_is_never_silent` | ⛔ **NOT a defect.** It walks the router over the confidence range — a question about **code**, identical on every run |
| `every_lane_is_visible_or_deliberately_silent` | ⛔ **NOT a defect.** A closed-set totality check over two frozen tables |

> ⛔ **A function that takes no data cannot be measuring production.** Both property guards are
> build-time guards whose test callers are the correct and only ones. Filing them as unwired defects
> — which is what `07-AUDIT` and `03-FINDINGS` F17 did — would have led to **wiring a settled
> question into a per-org, per-tick loop**, re-deriving the same answer about unchanged code forever.

**So `KNOWN_UNWIRED` went from 5 entries to 2**, and the two property guards moved to `UNREACHED`
with the corrected reason written into each.

## 2 · ⛔ And the one real gap was designed for, in writing

`pipeline.py`, ~80 lines above its own `return out`:

> *"Counting at composition time would make the lane mix describe a population that includes cards
> nobody received — and would make **`lane_recall.recall_verdict` a tautology**, since the tally and
> the comparison would then be incremented by the same line. **Two independently incremented
> counters that must agree is the only version of this check worth having.**"*

The author shaped the tally so a verdict would be meaningful, and never added the call.

> ⛔ **A comment that reasons about a guard's correctness is not evidence the guard runs.**

## 3 · What was built

| | |
|---|---|
| `deliver/pipeline.py` | ⛔ `recall_verdict(out)` at the end of `build_cards_for_org`, writing `out["lane_recall"]` and `out["lane_recall_balanced"]`, warning when unbalanced |
| `deliver/delivery_health.py` | `recall_verdict`'s entry **deleted** (it is wired); the two property guards reclassified into `UNREACHED` |
| `tests/deliver/test_the_recall_guard_runs_on_a_pass.py` | ⛔ NEW, **12 tests** |

```
KNOWN_UNWIRED   5 -> 2      (card_builder.resolved_person_name, outbox.revive_undeliverable)
UNREACHED       9 -> 11
DECLARED       26 -> 25
```

### ⛔ It may never raise, and the rule was already in the file

`pipeline.py`'s own `collapse_unmeasured` block states it: *"a receipt that can abort the thing it is
a receipt for turns an accounting failure into a product failure."* An unbalanced tally means cards
went somewhere nobody is looking; **dropping the pass over it means they went nowhere at all.** So:

| | |
|---|---|
| unbalanced | ⛔ recorded in `out`, warned through the logger idiom this file already uses at line 364, **never raised** |
| the guard itself throws | `out["lane_recall_unmeasured"] = 1` — the same rule as `collapse_unmeasured`: *a pass that could not measure itself must not look identical to one that measured zero* |

## 4 · ⛔ Mutations — and the first run of them proved nothing

### ⛔ I NEVER ESTABLISHED A BASELINE, SO EVERY NUMBER BELOW WAS WRONG BY ONE

The harness restored each file and **never re-ran the suite clean**. So I never learned that one test
had been failing the whole time: `test_the_defects_are_not_filed_as_decisions`, written in `STEP-05`,
still demanded `lane_recall.recall_verdict` be in `KNOWN_UNWIRED` — and this step correctly
**deleted** that entry when it wired the function. Every result was that stale failure plus whatever
the mutation caused.

| # | Mutation | first reported | ⛔ actual, against a 52-passed baseline |
|---|---|---|---|
| M1 | compute the verdict, never write it to `out` | 6 failed | 🔴 **5 failed** |
| M4 | **raise on an unbalanced verdict** | 1 failed | ⛔⛔ **52 passed — THE MUTATION SURVIVED** |
| M5 | put `recall_verdict` back into `KNOWN_UNWIRED` | 2 failed | 🔴 **2 failed** |

> ⛔ **M4's "1 failed" was the stale test and nothing else.** A mutation that makes the recall guard
> **kill the build pass** was caught by nothing, and I reported it as caught.
>
> **A mutation harness that does not re-run clean cannot tell you what it caught.** This programme
> already knew the neighbouring rule — *a harness that restores by copying a file must clear
> `__pycache__`* — and this is the same failure one level up: in the control, not the cache.

### ⛔ Why M4 survived, which is a defect in the wiring and not only in the test

The guard sits inside `try/except Exception` so a broken measurement cannot kill the pass. M4's
`raise` lands **inside that try**, so the pass's own safety net swallowed a defect in the half that
ACTS on the verdict, set `lane_recall_unmeasured = 1`, and returned normally. Every assertion still
held, because all of them were written before the raise.

> ⛔ **"I could not measure this" and "I measured it and it is wrong" are different sentences**, and
> the guard had one state where it needed two — the rule `collapse_unmeasured` exists for, applied to
> the flag rather than the count.

**The repair:** `test_an_unbalanced_tally_is_recorded_and_the_pass_still_returns` now also asserts
`"lane_recall_unmeasured" not in out`. M4 re-run: 🔴 **1 failed.** Baseline re-verified: 12 passed.

### Final table

| # | Mutation | Result |
|---|---|---|
| M1 | compute the verdict, never write it to `out` | 🔴 5 failed |
| M4 | raise on an unbalanced verdict | 🔴 **1 failed — only after the test was strengthened** |
| M5 | put `recall_verdict` back into `KNOWN_UNWIRED` | 🔴 2 failed |

⛔ **M2 and M3 are not restated with corrected numbers, because they were not re-run.** What is
recorded is what was measured: **M2 and M3 remain unverified.**

## 5 · Verify

```
.venv/bin/pytest tests/deliver/test_the_recall_guard_runs_on_a_pass.py -q          # 12 passed
.venv/bin/pytest tests/deliver/test_nothing_dies_of_low_confidence.py \
                 tests/deliver/test_the_delivery_layer_says_what_it_does_not_call.py -q
```

## 6 · Doctrine

| Rule |
|---|
| ⛔ **a function that takes no data cannot be measuring production** |
| ⛔ **a comment that reasons about a guard's correctness is not evidence the guard runs** |
| **a receipt that can abort the thing it is a receipt for turns an accounting failure into a product failure** |
| **a pass that could not measure itself must not look identical to one that measured zero** |
| **a finding's fix is the most likely place for the next instance of the same finding** |

⛔ **And one correction to F17 as it was written:** the headline *"the recall guard is an orphan"* was
right about the module and wrong about two thirds of its contents. The module WAS imported by
nothing; only one of its three functions was supposed to be.
