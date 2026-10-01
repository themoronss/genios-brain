# Layer 4 — start here

`executive/` — **27 files, 6,167 lines** (26/5,990 on 29 Sep; `readiness.py` landed after).
**Milestone M12. ✅ COMPLETE — 77 new tests.**

> ## ⛔ RE-CROSSCHECKED 2026-10-01 — read [`05-RECROSSCHECK-why-the-queue-is-empty.md`](05-RECROSSCHECK-why-the-queue-is-empty.md) FIRST
>
> **L4 does not need building.** It is built, correct, and correctly idle. There are **TWO
> separate blocks**, at two different places, and neither is a defect in `executive/`:
>
> | | Block | Where | Evidence |
> |---|---|---|---|
> | **1** | ⛔ **the input** — `GENIOS_L4_LLM_DECISION_MAKER = true` + the Anthropic spend limit + `llm_decision_maker`'s declared *"Failure is DEFER, never the formula"* → every decision defers → **0 new commitments since 2026-09-25** | one layer up, in L2 | `formula_utility` **5,469** healthy · `llm_utility` **0** · `final_utility_bp` **0** on all 8,044 candidates |
> | **2** | ⛔ **the ladder** — no reporting line, so `manager_of` returns `None` → **124 day-7 manager escalations scheduled, 0 ever fired** | inside L4, and it is STEP-02's finding confirmed | `org_seats.manager_seat_id` 0 of 3 · `seat_responsibilities` 0 rows |
>
> Block 1 is **DECISION #5** in `../02-DECISIONS.md` — three options, one line, Rohit's.
> Block 2 is organisation data, not code.

> Who decides — and how does a decision become owned, dated, tracked work?

A conclusion is an opinion. **A commitment is an opinion with an owner, a deadline, a channel, a ladder
and a clock attached.**

---

## Read in this order

| File | What it is |
|---|---|
| ⛔ [`05-RECROSSCHECK-why-the-queue-is-empty.md`](05-RECROSSCHECK-why-the-queue-is-empty.md) | **start here.** The chain traced link by link, the two blocks, the Atlas's 11 claims checked, and the six-unit plan |
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
| 5 | [⛔ The receipt that says the product stopped](STEP-05-DONE-the-receipt-that-says-the-product-stopped.md) | ✅ **DONE** · **U1** · ⛔ it goes **RED**, and that is the success condition | 16 |
| 6 | [⛔ 410 approvals nobody can attribute](STEP-06-DONE-410-approvals-nobody-can-attribute.md) | ✅ **DONE** · **U2** · ⛔ **the plan for this unit was WRONG and the measurement corrected it** | 10 |
| 7 | [A reminder names the step it waits on](STEP-07-DONE-a-reminder-names-the-step-it-waits-on.md) | ✅ **DONE** · **U3** · ⛔ **UNREACHED 6 → 5** · the first tests `blocking_action` ever had | 11 |
| 8 | [A baseline is a statement about the past](STEP-08-DONE-a-baseline-is-a-statement-about-the-past.md) | ✅ **DONE** · **U4** · ⛔ **F9 RETRACTED** — the fix would have destroyed correct calendar data; its retraction found the real defect | 6 |

## ⛔ What is planned next — six units, four buildable

| # | Unit | State |
|---|---|---|
| **U0** | **DECISION #5** — raise the limit · flip the switch · or build the third path | ⛔ **Rohit's. No card is produced until this is answered** |
| ~~**U1**~~ | ✅ **DONE** — receipt **#31**, *"the current reasoning era selects, not only defers"*. 16 tests · 5 mutations · ⛔ **RED at 3,582, correctly**. See [STEP-05](STEP-05-DONE-the-receipt-that-says-the-product-stopped.md) |
| ~~**U2**~~ | ✅ **DONE as receipt #32**, ⛔ **not as wiring.** Measured: 410 of 794 actions need sign-off against **zero** authority rules, and neither table has an approver column. The wiring is blocked on H1 *and* on the org publishing a rule; the plan's instruction to delete the `unreached` entry would have deleted the only record of why. See [STEP-06](STEP-06-DONE-410-approvals-nobody-can-attribute.md) |
| ~~**U3**~~ | ✅ **DONE.** ⛔ The defect was worse than described: `reminder_facts` named `actions[0]` with **no completion filter**, and that value reached a Slack message. Latent — 0 of 794 actions completed — and it fires on the first completion. **UNREACHED 6 → 5.** See [STEP-07](STEP-07-DONE-a-reminder-names-the-step-it-waits-on.md) |
| ~~**U4**~~ | ✅ **DONE, and F9 is RETRACTED.** The 37 future rows are a **recurring calendar event** and are correct; bounding at ingest would have discarded every future meeting. ⛔ The real defect was one layer over: `reason/baselines.py` was the only read over that column with **no bound**, and 3 people crossed `MIN_SAMPLES` on one calendar instance each, losing their `cold_start`. See [STEP-08](STEP-08-DONE-a-baseline-is-a-statement-about-the-past.md) |
| **U5** | **F-5** 708 outputs carry no `ranking_weights_version` | buildable · L2 |
| **U6** | **G3** brief push + **G4** preventive push | ⛔ **blocked on a product number** |

⛔ **The reporting line (block 2) is organisation data, not a unit.** `readiness.py:66` already
says exactly what to do: *set `org_seats.manager_seat_id` for the standing line, or file a dated
`reports_to` responsibility.*

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
