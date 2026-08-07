# Rate Limiter

**Engine status:** Built. Live PostgreSQL load proof and retention operations remain.

The rate limiter atomically reserves scarce attention immediately before an intrusive chat send.
It enforces an exact rolling-hour stream plus a recipient-local calendar-day budget without relying
on process-local counters. Slack and Teams share the organization's hourly chat stream because an
incoming webhook interrupts a shared channel; daily budgets remain per recipient.

| Input | Output | Authority |
|---|---|---|
| claimed, authority-live intrusive chat delivery | atomic reservation or timed deferral | `deliver/outbox.py` attention reservation, `delivery_rate_windows` |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
