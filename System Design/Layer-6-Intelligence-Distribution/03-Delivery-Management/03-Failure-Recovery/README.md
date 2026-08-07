# Failure Recovery

**Status:** Built

Selects a registered fallback only after the primary adapter has failed terminally.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | `deliver/outbox.py::enqueue_failover`, `destination.py` |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
