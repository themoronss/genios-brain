# Delivery Object Builder

**Status:** Built

Builds immutable typed boundary objects from the candidate and the durable outbox row.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | `contracts/delivery.py`, `deliver/results.py`, enqueue materialization |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
