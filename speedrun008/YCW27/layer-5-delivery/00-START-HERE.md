# L5 Delivery (`deliver/`) · M13 · **COMPLETE**

**Read in this order:** `01-CROSSCHECK.md` → `02-PLAN.md` → the four `STEP-*-DONE-*.md`.

| Step | Unit | State |
|---|---|---|
| 01 | `M13.C2.U03` the lane on the card | ✅ 31 tests |
| 02 | `M13.C2.U04` the recall guard — ⛔ **rewritten** | ✅ 24 tests |
| 03 | `M13.C1.U01` the claim extractor | ✅ shared 34 tests |
| 04 | `M13.C1.U02` widen the invention validator | ✅ shared 34 tests |

**89 new tests.** Full suite green.

## The two findings that changed the plan

⛔ **There is no scalar publication floor in `deliver/`.** `U04` said to replace it. `gate.py` is
moment + permission, `bands.py` cuts an urgency band from pack config, and the score gate is at
`reason/runner.py:1133` — where its `below_gate` receipt is **already read** by
`executive/explain.py`. Replacing it would have meant building it first in order to remove it. `U04`
became the recall guard, which is the half of the unit that was real and unproven.

⛔ **The invention validator exists, and I nearly wrote that it did not.** `render.py:334`,
called at `render.py:861`, re-exported by `executive/validate.py:69`, tested. A conclusion drawn from
one name's absence (`reminder_facts`) — the same mistake as `no_model_wired` (L1) and the
graph-revision guard (L3).

## New files

```
genios_engine/deliver/lane_display.py       the lane, in the reader's words
genios_engine/deliver/lane_recall.py        prove nothing died quietly
genios_engine/deliver/claims.py             copy -> tagged claims
genios_engine/deliver/claim_validator.py    the validator, per claim
migrations/0190_card_lane.sql               cards.output_lane + lane_reason
```

## ⛔ What you have to do

**`0190` must be applied.** It is the fifth unapplied migration (`0186`, `0187`, `0188`, `0189`,
`0190`). Until then `cards.output_lane` does not exist and `insert_card` **fails on write**.

## What this layer deliberately does NOT do

Gate delivery on the lane. A `suppress` lane is displayed and counted, not hidden — because under the
API spend limit no production signal has ever been routed, so that column has never once been
written. Carry, measure, then decide.
