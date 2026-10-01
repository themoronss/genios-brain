# L5 STEP 02 · `M13.C2.U04` — ⛔ **rewritten** · the recall guard · **DONE**

## Why it was rewritten

`tree.yaml` says *"the scalar publication floor is replaced by lane routing."* Measured 2026-09-30:

| Where | What is actually there |
|---|---|
| `deliver/gate.py` | moment + permission. Its only "floor" clamps a deferral's `not_before` |
| `deliver/bands.py` | an urgency band off the score, from pack config |
| `reason/runner.py:1133` | ⛔ **the score gate** — `out["below_gate"] += 1` |
| `executive/explain.py` | already **reads** its receipt: *"real, but not important enough yet"* |

⛔ **There is no scalar confidence floor in `deliver/`.** Replacing it would have meant building it
first in order to remove it. The Atlas's *"confidence 0.64, below the 0.70 gate"* describes the
**old** engine; its own before/after column says so.

What is real is the unit's other half — *"the recall guard proves nothing is lost"* — and nothing
proved it. `route`'s docstring promises a sub-floor decision *"does not become SUPPRESS"*. **A
docstring does not fail a build.**

## What was built

`deliver/lane_recall.py` — `VISIBLE_LANES` / `SILENT_LANES`, `recall_verdict()`,
`low_confidence_is_never_silent()`, `every_lane_is_visible_or_deliberately_silent()`.
`platform/receipts.py` — one new receipt (**27** total).

**24 tests**, `tests/deliver/test_nothing_dies_of_low_confidence.py`.

## What it proves

| | |
|---|---|
| a decision under the floor reaches `MONITOR`, never a silent lane | at **any** floor a tenant could set, walking the **real router** — a re-implementation of the rule would pass forever while the thing it describes drifted |
| every lane is visible or deliberately silent | an undecided visibility gets decided later by whichever reader looks first |
| the six lane tallies sum to `built + refreshed` | ⛔ **not `built` alone** — a refresh composes a card too, and the fix for a recurring false alarm is always to loosen the check |
| a lane key that stopped being declared fails | the totals would still add up while a whole lane went unmeasured |
| a card lost reads differently from a card double-counted | opposite causes; one message for both teaches nothing |
| every delivered card carries a lane or is labelled `unrouted` | the receipt, and it asks for **NULL** — `unrouted` is an answer and passes |

⛔ `MONITOR` and `unrouted` are both **visible**. Today `unrouted` is the majority case: under the
spend limit no production signal has ever been routed, so a layer that withheld unrouted cards
would deliver nothing at all, silently.

## The finding, kept as a test

`test_there_is_still_no_scalar_publication_floor_in_deliver` fails if anybody adds `confidence_bp`
to `gate.py` or `bands.py` — so a future author has to come and read why `U04` was rewritten rather
than silently reintroducing the thing lanes replaced.
