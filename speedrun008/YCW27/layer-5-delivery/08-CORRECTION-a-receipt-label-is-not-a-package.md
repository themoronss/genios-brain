# ⛔ CORRECTION · a receipt's layer label is not the package it guards

**Date:** 2026-10-02 · **Owner:** me · **Corrects:** `STEP-10`, `F9`, `F30`, `F31`, `01-CROSSCHECK`,
`05-RECROSSCHECK`, `06-AUDIT`, `STEP-14`, `STATUS.md`, `07-LEDGER`, `19-PENDING`
**Found by:** the L6 re-crosscheck, while asking which receipts guard `feedback/`

---

## 1 · The claim that was wrong

Every document above carries some form of this sentence:

> **L5 is 9,431 lines and carried 2 of the programme's 33 receipts — 4,715 lines per guard against
> L4's 881 — and one of the two ERRORs, so the layer that physically touches the customer had ONE
> working production guard.**

⛔ **Three numbers in it are wrong.** `deliver/` carried **5** receipts, not 2. Lines per guard was
**1,886**, not 4,715. And **four** of the five worked, not one.

## 2 · How the error was made

`Receipt.layer` is a hand-written string. I counted `deliver/`'s guards by filtering on it:

```python
[r for r in receipts(None) if r.layer == "L5"]      # ⛔ counts a LABEL, not a package
```

⛔ **And `genios_engine/LAYERS.py` warns about exactly this, in its own docstring:**

> *"Note the two collisions that make an unqualified layer number ambiguous — Atlas 5.2 is our
> `deliver` (6), and Atlas 6 is our `feedback` (7) — **so always name the package, never the digit
> alone**."*

The receipts name the digit alone. I read the digit as a package, which is the one reading that
file forbids.

## 3 · What the labels actually are

Measured by reading each receipt's SQL and resolving every `from`/`join` target to the package that
writes that table:

| Label | Tables it queries | Package(s) | |
|---|---|---|---|
| `L1` ×6 | `sync_cursors`, `parked_events`, `source_events`, `document_jobs`, `information_schema` | `capture/` | consistent |
| `L2` ×7 | `graph_facts`, `l2_convergence`, `org_seats` **+** `reasoning_reasoner_results`, `reasoning_run_outputs`, `reasoning_candidates` | ⛔ `context/` **and** `reason/` | **two packages** |
| `L3` ×2 | `expertise_packages`, `tenant_packs` | `packs/` | ⛔ PRODUCT scheme (Atlas L3 is `context/`) |
| `L4` ×7 | `reasoning_runs`, `reasoning_candidates`, `reasoning_run_outputs` **+** `execution_actions`, `org_seats` | ⛔ `reason/` **and** `executive/` | **two packages** |
| `L5` ×5 | `cards` ×2, `delivery_outbox`, `delivery_attempts` **+** `executions` | ⛔ `deliver/` **and** `executive/` | **two packages** |
| `L6` ×4 | `cards` ×2, `org_channels`, `delivery_outbox` | ⛔ **`deliver/`** | PRODUCT scheme |
| `L7` ×4 | `learning_runs`, `calibration_runs`, `counterfactual_ledger`, `card_feedback_verdicts` | **`feedback/`** | PRODUCT scheme |

> ⛔ **The label follows NEITHER vocabulary consistently.** `L3` is `packs/`, which is the PRODUCT
> column; `L2` and `L4` each span two packages; `L5` spans two. It is a hand-written tag that
> drifted, and it was never a package attribute to count.

## 4 · The corrected numbers for `deliver/`

Every receipt whose outer `from` is one of `deliver/`'s four tables — `cards`, `delivery_outbox`,
`delivery_attempts`, `org_channels`:

| | Claim | Label | Table | Column source | Runs? |
|---|---|---|---|---|---|
| 1 | every delivered card carries a lane, or is labelled unrouted | `L5` | `cards.output_lane` | `0189`/`0190` | ⛔ **ERRORs — unapplied** |
| 2 | cards distinguish a warning from an order | `L6` | `cards.level` | pre-existing | ✅ |
| 3 | no card gives an order with an empty draft | `L6` | `cards.artifact`, `abstained_because` | `0064` | ✅ |
| 4 | there is a channel this tenant can be reached on | `L6` | `org_channels` | pre-existing | ✅ |
| 5 | the delivery control plane has run | `L6` | `delivery_outbox` | `0044` | ✅ |
| 6 | no delivery attempt is left unsettled long enough to be ambiguous | `L5` | `delivery_attempts` | `0043` | ✅ ⛔ **mine, `STEP-06`** |
| 7 | no card outlives its own window in a live state | `L5` | `cards.state`, `cards.expires_at` | `0008` | ✅ ⛔ **mine, `STEP-10`** |
| 8 | a card parked for want of a channel is revived when one appears | `L5` | `delivery_outbox` ⋈ `org_channels` | `0044` | ✅ ⛔ **mine, `STEP-10`** |

```
                        receipts about deliver/   working   lines    lines per guard
  before YCW27                      5               4       9,431        1,886
  today (2026-10-02)                8               7      10,020        1,252
  ⛔ what I claimed                  2               1       9,431        4,715
```

⛔ **`1,886` was already true before I wrote a line.** I reported it as the number my step
*achieved*. The step's real contribution is **1,886 → 1,252**, and `deliver/` has never been the
2-receipt desert the plan was motivated by.

## 5 · What is NOT retracted

| | Why it survives |
|---|---|
| the two new receipts | measured, real, and each shown to be able to go red. `expect(0) is True`, `expect(1) is False`, asserted per claim |
| the two rejections (`A` a delivery row with no attempt, `D` a card on an adapter-less channel) | rejected because they are **structurally 0 forever** — `outbox.py:935` parks when `get_channel()` is None. ⛔ *A receipt that cannot fail is not a gate*, and that reasoning never touched the count |
| the third rejection (`C` UNDELIVERABLE vs `failed_terminal`) | already a CODE property, guarded at `test_proactive_channel_resolution.py:722` |
| the 12-hour window | derived from `config.sync_interval_hours` measured at **6.0** — a one-hour grace would have reported routine latency as an alarm |
| `cards.expires_at` exists | verified in `migrations/0008_l5_delivery.sql:28`, `timestamptz not null`. Receipt 7 runs |

⛔ **The work stands; the motivation number does not.** Nothing in the step's reasoning depended on
whether `deliver/` had 2 guards or 5 — which is precisely why the wrong number survived review.

## 6 · Why this was not caught earlier

**The count was never stored as data.** It lived in prose, in eleven places, derived once by hand
from a label filter. ⛔ *A claim worth asserting is worth storing as data* — the programme's own
rule, and the one claim that most needed it was a claim about the guards.

And the guard I wrote for `STEP-10` could not catch it: it asserts each new receipt `.layer == "L5"`
and can fail. ⛔ **A guard that asserts the label is correct cannot notice that the label means
nothing** — *a guard must not inherit the blind spot of the thing it guards*, for the second time
in this programme.

## 7 · Doctrine

| Rule |
|---|
| ⛔ **a receipt's layer label is its author's intent; the table it queries is what it guards** |
| ⛔ **"always name the package, never the digit alone" binds the COUNTER as much as the writer** — `LAYERS.py` said it; the count ignored it |
| **a number repeated in eleven documents was derived once** — repetition is not corroboration |
| **a motivation number no step depends on is a number nobody checks** |

## 8 · Open, and Rohit's call

⛔ **Relabelling the receipts is a behaviour change, not a tidy-up.** `receipts(layer)` filters on
that string, so moving `decisions become tracked commitments` from `L5` to `L4`, or the four `L6`
ones to `L5`, changes which receipts an operator's layer-scoped run executes. **I have not touched
a label.** The measurement is recorded here; the relabel needs a decision from you.

## ⛔⛔ 8b · CLOSED 2026-10-02 — the count is DATA now, and it points at `context/`

`genios_engine/platform/receipt_coverage.py` declares, per receipt **claim**, the package it guards
— checked in both directions, so a new receipt with no entry fails the build. **The count is no
longer prose in eleven documents.**

```
package     receipts  correctness    lines  lines/guard
feedback           9            5    4,040          448
reason             8            5   41,363        5,170
deliver            7            5   10,020        1,431
capture            5            5   47,184        9,436
readiness          5            0        —            —
context            2            2   50,877       25,438     ⛔⛔ WORST
executive          2            1    6,230        3,115
platform           1            1   11,950       11,950
packs              1            0    8,188        8,188
```

⛔⛔ **And the number this document corrected was aimed at the wrong package.** `STEP-10` spent a
step on `deliver/` because a hand-derived 4,715 pointed there. **`context/` is 25,438 — 5.4× worse
than the figure that triggered it** — and `deliver/` is now the third-best covered package in the
product.

⛔ `Receipt.layer` is still untouched, and a test asserts `receipt_coverage` never reads it. The
relabel in §8 remains Rohit's.
→ `../layer-6-learning/STEP-S7-DONE-the-count-becomes-data-and-a-lost-seam-gets-a-name.md`

## 9 · Verify

```bash
.venv/bin/python -c "
import re
from genios_engine.platform.receipts import receipts
for r in receipts(None):
    t = re.findall(r'(?:from|join)\\s+([a-z_][a-z0-9_.]*)', ' '.join(r.sql.split()))
    print(r.layer, t, r.claim)"
```

⛔ Use `[a-z_][a-z0-9_.]*`, not `[a-z_]+`: the shorter class stops at the digit in `l2_convergence`
and reports the table as `l`. **The first version of this very measurement got that wrong**, which
is the fourth time in this programme a name-shaped regex has produced a confident wrong answer.
