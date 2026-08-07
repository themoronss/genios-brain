# Delivery Tracker

**Status:** Partial

Tracks durable transport state and exposes immutable DeliveryObject/DeliveryResult projections.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | `deliver/outbox.py`, `deliver/results.py`, card events |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
