# L6 Learning (`feedback/`) · M14 · **COMPLETE**

**Read in this order:** `01-CROSSCHECK.md` → `02-PLAN.md` → the three `STEP-*-DONE-*.md`.

| Step | Unit | State |
|---|---|---|
| 01 | `M14.C1.U01` the attribution vocabulary | ✅ |
| 02 | `M14.C1.U02` eleven reasons, all five readers | ✅ |
| 03 | `M14.C1.U03` the layer debit — ⛔ **narrowed** | ✅ |

**53 tests**, `tests/feedback/test_the_right_layer_is_debited.py`. Full suite green.

## The finding that changed the plan

M14 ships *"a wrong card debits the layer that failed, and a timing complaint never lowers a correct
rule's precision."*

⛔ **The second clause was already true, in three independent places** —
`calibrate.TAXONOMY["wrong:bad_timing"]["precision"] == "none"`, `units.py:135`, and
`_PRECISION_SQL`'s reason list — with a fourth documenting it from the consuming side. It was work to
**not break**, not work to do. `U03` became the layer debit plus the **guard** over the thing that
already worked, because a property enforced in three places can be broken in three places and none
of them failed a build.

## The near-disaster of the widening

`feedback/units.py` branched on one literal, `reason == "bad_timing"`. Going from three reasons to
eleven without touching it would have made **four new "the card was right" reasons debit the rule's
accuracy** — the exact defect this milestone exists to end, created for four new reasons by the step
meant to fix it for one. And `_PRECISION_SQL`'s two-reason list would have left **four real quality
failures recorded by a founder and counted by nothing.**

⛔ Both directions. Both closed. Both tested.

## New files

```
genios_engine/contracts/learning_attribution.py   11 reasons, one layer each
genios_engine/feedback/attribution.py             the router, and the guard
```

Modified: `feedback/calibrate.py`, `feedback/units.py`, `deliver/actions.py`,
`deliver/card_builder.py`, `context/correlation_history.py`.

## ⛔ What is yours to decide

**Eleven radio buttons under "Wrong" is a worse experience than three.** A founder asked to classify
*our* failure will pick the first plausible option, and precise-looking data gathered that way is
worse than coarse data gathered honestly. The eleven are right as a machine vocabulary; whether all
eleven are *shown* is your call. `_WRONG_REASON_GROUPS` gives a surface four headings a person can
pick, and narrowing what is displayed is a one-line change on a surface — never a change to the
vocabulary underneath.

**`BUILDER_VERSION` was bumped** to `card-builder.v6-lane-and-eleven-reasons`, so every untouched
card in production will be recomposed on the next sweep. That is the documented behaviour of the
field, and it is how the lane and the new reasons reach cards a founder is already looking at.
