# L5 Delivery (`deliver/`) · M13 · ⛔ **15 DONE · 1 WITHDRAWN · 1 LEFT (Harsh's)**

**Read in this order:** `01-CROSSCHECK.md` (2026-09-30, before the build) →
`05-RECROSSCHECK-the-silences-of-the-delivery-spine.md` (2026-10-01, after it) →
⛔ `06-AUDIT-the-measurement-that-corrected-itself.md` →
⛔ `07-AUDIT-the-second-delivery-architecture.md` → `02-PLAN.md` → the step files.

⛔ **This file said `COMPLETE` until 2026-10-01.** It was true of the four units `tree.yaml` specifies.
It was not true of the layer: re-measuring `deliver/` after the build found four unreached public
functions, no declared-silence module, and **two production receipts for 9,431 lines.** ⛔ **[CORRECTED 2026-10-02: five, four of them working — [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md)]** A stale status
reads as a status somebody checked, and this programme has paid for that three times.

---

## Built — M13's four units, 2026-09-30

| Step | Unit | State |
|---|---|---|
| 01 | `M13.C2.U03` the lane on the card | ✅ 31 tests |
| 02 | `M13.C2.U04` the recall guard — ⛔ **rewritten** | ✅ 24 tests |
| 03 | `M13.C1.U01` the claim extractor | ✅ shared 34 tests |
| 04 | `M13.C1.U02` widen the invention validator | ✅ shared 34 tests |

**89 new tests.** Full suite green.

---

## ✅ Built 2026-10-01 — STEP-05, 13, 14, 06, 07, 08, 09, 15, 10, 11 · ⛔ **`KNOWN_UNWIRED` EMPTY · L5 receipts 2 → 5 · scorecard 35 → 45 claims**

| Step | What landed | Tests | Mutations |
|---|---|---|---|
| **05** | `deliver/delivery_health.py` — 25 declared silences in **three** tables | 16 | 8, all red |
| **13** | ⛔ `qualified_call_counts` in `executive/unreached.py` — **L4's inventory 5 → 10** | 9 | 5, all red |
| **14** | ⛔ the recall guard **runs** — `recall_verdict` wired into `build_cards_for_org` | 12 | 5, all red |
| **06** | the cutover guard + the *unsettled-attempt* receipt + ⛔ `recover_expired_claims`'s **first tests ever** | 18 | 5, all red |
| **07** | ⛔ **four** stale statements — one of them inside the test that guards the behaviour | 6 | 5, all red |
| **08** | the headline names a person — ⛔ one line, **two decisions** the plan did not have | 14 | 6, all red |
| **09** | the gate records why it refused — ⛔ a **three-part** unit, and **the reader is half of it** | 13 | 6, all red |
| **15** | a card becomes deliverable when a channel appears — ⛔ **the plan's own fix would have caused harm** | 12 | 6, all red |
| **10** | L5 receipts **2 → 5** — ⛔ **two of five candidates could not fail** | 11 | 6, all red |
| **11** | the scorecard covers L5 — ⛔ **5 superseded badges and 1 OMISSION** | — | — |
| **17** | ⛔ **every package says what it does not call** — 10 modules, 109 entries, ONE guard | 71 | — |

⛔ **Every one of the three had its own premise corrected by its own first measurement**, which is
the plan working rather than failing:

| Step | Planned | ⛔ Measured |
|---|---|---|
| 05 | 4 unreached, one table | **24 unreached, three kinds** — the "4" counted `tests/` as callers |
| 13 | *"expected: nothing changes in L4"* | L4's 5 existing entries were clean — and **five more were missing**, including a whole unreached module (`executive/readiness.py`) |
| 14 | three unwired functions | **one** real gap. Two take no data at all — *a function that takes no data cannot be measuring production* |
| 06 | *"the cutover has no measurement"* | ⛔ it has one — `outbox.shadow_resolve_v2`. *A measurement can be present under a name you did not search for* |
| 07 | two stale comments | ⛔ **four**, and the fourth was in a **test docstring** — the wrong sentence had propagated into the guard |
| 08 | *"wire it"* — one line | ⛔ one line, and it needed the **precedence** it joins and the **scope** it applies to. Plus a fifth stale docstring, inside the function being fixed |
| 09 | *"wire it or declare it"*, *"lowest severity of the four"* | ⛔ **three** parts, and **neither** candidate sink was right. The function was not keeping its own docstring's third promise, and nothing read the table it writes to |
| 15 | *"the risk nobody has checked: bound it on `expires_at`"* | ⛔ **the docstring had already answered it, in the opposite direction** — a bounded revive leaves the row dead, and *a dead row cannot tell "we chose not to send" from "we lost it"*. **Retracted** |
| 10 | four receipt candidates, *"each measured first"* | ⛔ **two of five could not fail** · the window needed the **scheduler's** interval (6h, not my 1h) · and L4's docstring promised an L5 count guard **that did not exist** |
| 11 | *"a document correction, not code"* | ⛔ it was — **plus a code change**: the full suite failed a `tests/executive/` test my targeted runs never touched. *Two targeted test runs are not a suite run* |
| 17 | *"a level, nine units, 147 functions"* | ⛔ **one guard, eleven packages, 109 functions** — a **third** wiring mechanism (reference) removed 46, and a **fourth** (duck-typed) cannot be measured at all |

## ⛔ Planned, NOT BUILT — awaiting Rohit's go-ahead

| Step | Unit | Finding | Owner |
|---|---|---|---|
| 12 | the *lane* receipt cannot run | ⛔ **blocked on H1 — `0190` breaks `insert_card`** | **Harsh** |
| ⛔ 17 | **nine packages nobody asked** | ⛔ **147 public functions engine-wide**, unreached and declared nowhere. **A level, one unit per package** | me |

Steps 13–17 did not exist before STEP-05 measured. ⛔ **`STEP-17` is the largest finding in the
programme and the last thing in it, not the next**: only `executive/` and `deliver/` have a
reachability guard, and the other nine packages hold **147** undeclared unreached public functions
between them. See [`../18-AUDIT-the-engine-wide-reachability-gap.md`](../18-AUDIT-the-engine-wide-reachability-gap.md).
⛔ **147 is not 147 defects** — L5's 24 were 12 un-cut-over, 7 deliberate, 5 defects.

**Left:** ⛔ `17` is the only one of mine, and it is the **last** thing in the programme — nine
packages, 147 functions, a level rather than a unit. `16` is Rohit's, `12` and `H6` are Harsh's.
`12` and ⛔ **`H6`** are Harsh's, `16` is Rohit's.

⛔ **4 of STEP-06's 18 tests have NOT been run** — `tests/test_delivery_spine.py` needs real
PostgreSQL and this checkout has none, so all 7 of its tests skip. **A skip is not a pass.** Logged
as `HANDOFF-HARSH.md` **H6**: one command, no deployment.

⛔ **And one of my own mutation runs proved nothing.** STEP-14's harness never re-ran clean, so a
stale `STEP-05` assertion inflated every count by one — and hid a **surviving** mutation (making the
recall guard raise and kill the build pass). Fixed, re-measured, and written into `03-FINDINGS.md`
F24 and both completion records. ⛔ **Establish the baseline, or the harness is theatre.**

---

## The findings, shortest form

⛔ **`deliver/` is the most heavily built layer in the product and the most lightly guarded.** Nothing
in it is wrong the way L4's queue was wrong. What it lacks is the machinery every sibling package has
for saying what it deliberately does not do — `reason/unit_health.py`,
`context/lane_health.DORMANT_LANES`, `executive/unreached.py`, and in `deliver/` nothing.

⛔ **The live-harm finding I did not get to write.** `recover_expired_claims` looked like a silent
double-send: `claim_due` frees an expired row regardless and writes a new fence, while the recovery
matches the old one. One more grep killed it — `spine.claim_due` is called by **nothing in production**,
and `outbox.py:838` already says *"the v2 path has never written a row yet."* **An uncalled function on
an un-cut-over path is not a bug; it is an unguarded cutover.** Fifth time measuring the callers first
prevented a wrong finding.

⛔ **Three Atlas L5 badges are superseded, two of them by this programme, four days ago.**
Claim-level validation (`target` → built), lanes on the card (*"L5's biggest gap"* → built), and the
three delivery failures to design out (`target` → all three already guarded).

---

## The two findings that changed M13's original plan

⛔ **There is no scalar publication floor in `deliver/`.** `U04` said to replace it. `gate.py` is moment
+ permission, `bands.py` cuts an urgency band from pack config, and the score gate is at
`reason/runner.py:1133` — where its `below_gate` receipt is **already read** by `executive/explain.py`.
Replacing it would have meant building it first in order to remove it. `U04` became the recall guard.

⛔ **The invention validator exists, and I nearly wrote that it did not.** `render.py:334`, called at
`:861`, re-exported by `executive/validate.py:69`, tested. A conclusion drawn from one name's absence —
the same mistake as `no_model_wired` (L1) and the graph-revision guard (L3).

---

## Files M13 added

```
genios_engine/deliver/lane_display.py       the lane, in the reader's words
genios_engine/deliver/lane_recall.py        prove nothing died quietly
genios_engine/deliver/claims.py             copy -> tagged claims
genios_engine/deliver/claim_validator.py    the validator, per claim
migrations/0190_card_lane.sql               cards.output_lane + lane_reason
```

## ⛔ What Harsh has to do

**`0190` must be applied.** It is the fifth unapplied migration (`0186`, `0187`, `0188`, `0189`,
`0190`). Until then `cards.output_lane` does not exist and `insert_card` **fails on write** — masked
only because no production signal has been routed since the API spend limit began refusing calls on
2026-09-25. See `STEP-12`.

## What this layer deliberately does NOT do

Gate delivery on the lane. A `suppress` lane is displayed and counted, not hidden — because under the
API spend limit no production signal has ever been routed, so that column has never once been written.
Carry, measure, then decide.
