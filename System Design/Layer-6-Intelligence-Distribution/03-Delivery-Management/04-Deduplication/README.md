# Deduplication

**Status:** Partial

Prevents repeated producers/sweeps from enqueueing the same logical delivery on the same channel.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | outbox unique identity and synthetic card/event keys |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
