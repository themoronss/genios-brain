# Retry Manager

**Status:** Built

Retries transient adapter failures with bounded backoff while keeping timing deferrals separate.

| Input | Output | Authority |
|---|---|---|
| candidate + durable delivery state | updated ledger / typed result / hold | `deliver/outbox.py::next_attempt_delay`, drain/finish logic |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
