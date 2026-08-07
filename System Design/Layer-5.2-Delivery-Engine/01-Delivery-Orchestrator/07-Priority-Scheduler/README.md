# Priority Scheduler

**Status:** Active

Answers **“which already-due delivery gets a worker next?”** It maps immutable business priority
to the Atlas five-class delivery queue and claims work with tenant fairness and starvation aging.

| Boundary | Current truth |
|---|---|
| Input | queued/deferred rows, priority rank, age, due time and fenced claim state |
| Output | one expiring claim token per selected row |
| Runtime | `deliver/scheduler.py`, `deliver/outbox.py`, `deliver/rate_limit.py` |
| Fairness | per-org round robin plus four-hour priority aging |
| Heartbeat | dedicated `delivery_interval_seconds` loop; one minute by production default |

Delivery has its own minute-scale daemon loop and does not inherit the multi-hour ingestion/
maintenance cadence. Deployments that disable the in-process scheduler must supply an equivalent
minute-scale worker; a six-hour cron cannot satisfy retry, quiet-window or claim clocks.

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
