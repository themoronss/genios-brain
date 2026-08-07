# Learning Scheduler

**Status:** Built

Runs Layer 6 from the maintenance heartbeat while a PostgreSQL UTC-week claim—not process memory—
is the duplicate-work authority. Retention is intentionally independent of the weekly learning
claim and of tenant learning enablement.

| Boundary | Current truth |
|---|---|
| Trigger | in-process maintenance scheduler, or equivalent external caller |
| Tenant set | policy/state/inbox tenants plus tenants with an active pack |
| Run identity | stable tenant + Monday 00:00 UTC period start |
| Retry | completed week is idempotent; failed week is reclaimable with incremented attempt count |
| Held-object revisit | later claimed week re-evaluates only identical Observed/Candidate objects under its pinned policy/time |
| Evaluation audit | one object/run ledger row with prior/result state, final sink-level reason and insertion flag |
| Duplicate accounting | later-state duplicates are skipped and surfaced as `objects_unchanged`; they never reopen |
| Retention | due memories expire first in their own committed transaction, even when learning is disabled |
| Output | completed/failed run record, pinned policy revision and reasoned aggregate counts |
| Authority | `platform/scheduler.py`; `api/routes.py::run_maintenance_sweep`; `feedback/orchestrator.py::run_learning` |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
