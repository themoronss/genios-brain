# Step 4 — ✅ DONE · activity is not outcome (Rule 11)

> **Tree:** `M12.C2.U04` · 16 tests · ⛔ **built differently from the plan, for a measured reason**

## 1 · What was expected

> *"One situation walks signal → card → approval → execution → verified outcome, and the walk is a test,
> not a demo."* · artifact: `tests/test_e2e_all_layers.py`

## 2 · What is actually true — measuring changed the answer twice

**1 · The walk exists and stops early.** `tests/test_e2e_all_layers.py` drives a real email through the
layers on one shared Postgres and reaches `run_executive` at line 217. Grepped for `approve`,
`execution_outcomes`, `verified`, `run_lifecycle`: **none appear as assertions.**

**2 · ⛔ The rule is already enforced, in two places, and neither had a test naming it.**

| Where | What it refuses |
|---|---|
| `lifecycle.next_state` | `RUNNING` + every step ticked + no evidence → **`WAITING`**, never `COMPLETED`. Its comment: *"a sweep may recognise work in flight, it may never decide on someone's behalf that they have finished."* |
| `collect.classify_outcome` | `COMPLETED` + no `outcome_kind` → **`completed_unproven`**, never `succeeded` |

## 3 · ⛔ Why the tail is NOT in the pg walk

The existing walk is `pg`-marked and skipped in every run without `GENIOS_TEST_DATABASE_URL`. My own
plan listed that as **unsound verify #3**. Adding the tail there would have been writing a test that
mostly does not run — and the rule it proves is the one that decides whether a founder is told something
is done when it is not.

> So the tail is **pure and runs everywhere**. The pg walk keeps its own job — proving the seams line up
> on real persisted output — and one test here asserts it still has its executive stage, so the two
> cannot drift apart about who covers what.

⛔ **This is a deviation from the plan, made after measuring, and recorded rather than quietly taken.**

## 4 · Verify

```
$ uv run --no-sync pytest tests/executive/test_activity_is_not_outcome.py -q
................                                                         [100%]
16 passed in 0.09s
```

## 5 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| every step ticked, no evidence | ⛔ **`WAITING`**, never `COMPLETED` | ✅ the assertion that carries Rule 11 |
| **every** progress value × evidence state × open state | ⛔ never `COMPLETED` | ✅ 45 combinations swept |
| some progress | `RUNNING` | ✅ a sweep MAY recognise work in flight |
| no progress | nothing moves | ✅ |
| a terminal verdict + full progress + evidence | the **verdict** leads | ✅ progress cannot override an ending |
| `COMPLETED` with no evidence | `completed_unproven` | ✅ **not** `succeeded` |
| `COMPLETED` with evidence | `succeeded` | ✅ |
| `completed_unproven` for learning | ⛔ **not positive** | ✅ or a play whose outcome never arrives would calibrate as a good one |
| an expiry | untouched ≠ in progress | ✅ different lessons |
| **every** terminal state | produces a label | ✅ totality — an unlabelled ending is one L6 cannot learn from |
| `done_but_unproven` | a **named** state | ✅ no amount of completion rate surfaces that gap |
| steps complete vs outcome observed | separate questions | ✅ collapsing them **is** the defect |
| the guard's vocabulary | more than a boolean | ✅ four reasons not to send stay four |
| the pg walk | still owns the seams | ✅ |

## 6 · What this does NOT prove

⛔ **It does not prove the tail runs end to end on real data.** That needs
`GENIOS_TEST_DATABASE_URL` and a tenant with an approval in it — and a tenant with an approval needs
Step 2's organisation record and Step 3's activation row, both of which are Rohit's.

What it proves is that **when** that data exists, a completion with no evidence cannot be called a
success. The rule is closed; the end-to-end demonstration waits on the tenant.

## 7 · For Rohit / Harsh

Nothing. When you have a routable tenant, run the pg walk with a database URL and the seams get their
own proof:

```
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… uv run --no-sync pytest tests/test_e2e_all_layers.py -q
```
