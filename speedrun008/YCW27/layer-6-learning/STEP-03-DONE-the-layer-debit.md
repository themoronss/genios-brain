# L6 STEP 03 · `M14.C1.U03` — ⛔ **narrowed** · the layer debit · **DONE**

## Why it was narrowed

The unit reads *"the router — reason to layer to the thing that changes, and `bad_timing` reaches L5
timing rather than the rule's precision."*

⛔ **The second clause was already true in three independent places** before this work:

```
calibrate.TAXONOMY["wrong:bad_timing"]  ->  {"label": "timing", "precision": "none"}
feedback/units.py:135                   ->  judged = acted + wrong   # bad_timing does not
                                                                     # grade accuracy
calibrate._PRECISION_SQL                ->  in ('not_relevant','wrong_facts')
```

and `packs/brains/adaptive_lease.py` documents the same rule from the consuming side. Building it
would have meant building it twice.

**This is the tenth correction to the programme's planning documents.**

## What was built instead

`genios_engine/feedback/attribution.py` — `route()`, `AttributionReport`, `LayerDebit`,
`timing_never_grades_accuracy()`, `every_legacy_reason_still_grades_the_way_it_did()`.

**53 tests**, `tests/feedback/test_the_right_layer_is_debited.py`.

⛔ **The more valuable half is the guard.** A property enforced in three places can be broken in
three places, and **none of them failed a build if it was.** Now two functions check it and the
tests call them — and they read `TAXONOMY` directly rather than restating its contents, because a
copy of a rule passes forever while the rule drifts.

## What the report says

| | |
|---|---|
| ranked by debits, tie-broken by **earliest layer** | ⛔ not alphabetical: a bad input reaches the reader through every layer after it, so fixing the last one fixes one symptom |
| `accuracy_debits` carried apart from `debits` | *"which layer is failing"* and *"which rule should get quieter"* have different answers, and one number cannot give both |
| an unknown reason is **counted and said out loud** | filing it against a layer nobody chose gives a confident number pointing at the wrong team; dropping it makes a client sending garbage look like a quiet week |
| a non-complaint (a click, a snooze) counted apart | so the totals close, and a quiet week is distinguishable from a report that lost rows |
| the same fix said forty times is one thing to do | deduplicated |

## ⛔ A debit changes nothing, and that is the design

L6 already changes exactly one thing — a rule's precision offset, bounded by `OFFSET_BOUND = 15` so
learning cannot run away. An attribution deliberately changes **no weight**. Wiring it to one would
let one founder's misclassification retune a whole layer, and a founder classifying *our* failure,
given eleven options, is the least reliable input in the system.

A test walks the module's AST and fails if it references `OFFSET_STEP`, `OFFSET_BOUND`,
`MUTE_PRECISION`, `run_calibration` or `store` — *"an attribution that writes is not a direction to
look."*

What it produces is a ranked answer to **"where is this tenant's pipeline actually failing?"** — the
question `0188`'s funnel counters were built to ask and currently answer only by volume.

## ⛔ Two of my own tests were blunt greps, in one file

`test_the_guard_reads_the_taxonomy_rather_than_restating_it` asserted `"denominator" not in src` and
failed on **its own docstring**, which uses the phrase *"the precision denominator"* to explain the
rule. `test_the_report_changes_no_weight_anywhere` matched `OFFSET_BOUND` in the module docstring,
where it appears to explain that learning is bounded **and an attribution is not.**

Both rewritten as AST walks. Twice in one file is why the rule is *"assert on structure"* and not a
preference.
