# Layer 4 — start here

`executive/` — 26 files, 5,990 lines. **Milestone M12. ✅ COMPLETE — 77 new tests.**

> Who decides — and how does a decision become owned, dated, tracked work?

A conclusion is an opinion. **A commitment is an opinion with an owner, a deadline, a channel, a ladder
and a clock attached.**

---

## Read in this order

| File | What it is |
|---|---|
| [`01-CROSSCHECK.md`](01-CROSSCHECK.md) | what is actually true, every number with its command |
| [`02-PLAN.md`](02-PLAN.md) | 3 sections → 6 functions → 5 units, with *why* for each |
| the STEP files | what was expected, what happened, scenario → result |

---

## The steps

| # | Step | Status | Tests |
|---|---|---|---|
| 1 | [The reporting line, tested](STEP-01-DONE-reporting-line.md) | ✅ **DONE** · ⛔ **retired a spec that would break the ladder** | 17 |
| 2 | [Organisation readiness](STEP-02-DONE-organisation-readiness.md) | ✅ **DONE** · ⛔ **the reason the queue is empty** | 30 |
| 3 | [The live pass leaves a receipt](STEP-03-DONE-activation-receipt.md) | ✅ **DONE** | 14 |
| 4 | [Activity is not outcome](STEP-04-DONE-activity-is-not-outcome.md) | ✅ **DONE** | 16 |

Plus the three programme debts closed alongside: `tests/platform/test_migrations_apply.py` (**64**) and
`tests/test_tree_ids_are_addressable.py` (**11**).

---

## ⛔ The headline: 1 of 4 specified units would have broken the ladder

| `tree.yaml` said | Reality |
|---|---|
| `M12.C1.U01` — *"`reports_to` from `seat_responsibilities`, **never** `org_seats.manager_seat_id`"* | ⛔ **BUILT, and the spec is wrong.** The two are a **dated override over a standing line**. Removing the column leaves every seat with no manager, and rung 7 (`escalate → manager`) climbs into nothing |
| `M12.C1.U02` — the door that reports what is missing | ✅ **genuine gap.** 23 receipts, **not one** about organisation data |
| `M12.C2.U03` — activation row + a live-pass receipt | ⚠️ **split.** The row is Rohit's; the receipt was a real gap |
| `M12.C2.U04` — the walk through approval → verified outcome | ⚠️ **the rule was already enforced in two places**, neither named as Rule 11 |

---

## What L4 can now say that it could not

| | Before | After |
|---|---|---|
| why a tenant cannot be routed to | ❌ nothing said | ✅ named, with the consequence **and the fix** |
| *"we could not read it"* vs *"it is absent"* | ❌ same thing | ✅ `unknown` ≠ `missing` |
| whether an activation row did anything | ❌ nothing checked | ✅ a receipt on `reasoning_runs.mode` |
| "who was her manager in June?", asked in September | ✅ worked | ✅ **and is now tested** |
| activity ≠ outcome | ✅ enforced twice | ✅ **and now named as Rule 11** |

---

## ⛔ Two things that stay open, and both are corrections to the tree

| | |
|---|---|
| `M12.C1.U02`'s named verify, `tests/api/test_org_record_loads.py` | ⛔ **not created.** The door became a **receipt** — read on every health pass instead of when somebody thinks to ask. `test_a_tenant_nobody_feeds_is_not_ready` made the same argument one layer down |
| `SeatDirectory`'s docstring says *"kept to three questions"* and the protocol has **seven** | ⛔ **recorded, not fixed.** Deleting four methods callers use would break routing to close a documentation gap; rewriting the docstring is a judgement with an owner. The current surface is pinned so the **eighth** is deliberate |

---

## For Rohit — the one thing only you can do

⛔ **Insert the pilot's activation row and load the organisation record** (seats, the reporting line,
`org_channels`). Nothing here does that, on purpose — a tenant's data is a tenant decision.

What is now built is the machinery that **says exactly what is missing** before you do it, and
**proves the switch did something** after. Run:

```
.venv/bin/python scripts/runtime_receipts.py --org <org_id>      # three new L4 claims appear
```

---

## ⛔ The pattern, four layers running

> **This codebase's comments record decisions its planning documents do not.**

| Layer | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 | plan compile should fail on an unproduced source | it did, and it cost **six units to one absent fact** |
| **L4** | **never read `manager_seat_id`** | it is the **standing line** the dated override sits on |
