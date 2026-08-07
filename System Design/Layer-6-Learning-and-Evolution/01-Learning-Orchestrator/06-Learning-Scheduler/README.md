# Learning Scheduler

**Status:** Built

Executes at most one atomic learning run per tenant per UTC week.

| Boundary | Current truth |
|---|---|
| Input | organization, policy, explicit evaluation time and database transaction |
| Output | a completed/failed run record and deterministic counts of proposals/states/publications |
| Authority | `feedback/orchestrator.py::run_learning`, `feedback/store.py` weekly claim |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
