# Priority Scheduler

**Status:** Built

Claims eligible durable work in stable priority/due order while respecting daily budget, burst holds and retry backoff.

| Boundary | Current truth |
|---|---|
| Input | queued rows, band/priority, due time, attempts/deferrals and recipient budget state |
| Output | a claimed row for one adapter attempt, or a later eligible time |
| Authority | `deliver/outbox.py`, `deliver/router.py`, `deliver/timing.py` |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
