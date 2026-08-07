# Delivery Analytics

**Status:** Partial

Aggregates transport outcomes, channel mix, attempts, deferrals, burst holds and measured latency.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | `deliver/analytics.py`, `/delivery/analytics` |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
