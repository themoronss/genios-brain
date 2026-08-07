# Rate Limiter

**Status:** Built

Protects recipient attention with daily budget and short-window burst controls.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | `deliver/router.py`, `deliver/timing.py`, gate context |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
