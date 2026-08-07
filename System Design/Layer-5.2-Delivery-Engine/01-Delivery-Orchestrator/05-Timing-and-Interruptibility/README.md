# Timing and Interruptibility

**Status:** Active

Answers **“may this spend human attention now?”** It distinguishes a wrong moment from a broken
transport: timing produces `SEND` or `DEFER`, never terminal suppression.

| Boundary | Current truth |
|---|---|
| Input | candidate, timezone/quiet hours, live busy state, burst history and explicit time |
| Output | `SEND` or `DEFER(reason_code, not_before)` |
| Runtime | `deliver/timing.py`, `deliver/gate.py`, atomic reservations in `deliver/rate_limit.py` |
| Retry law | deferral spends no provider attempt |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
