# Delivery Policy

**Status:** Active

Answers **“is this tenant/recipient/channel delivery permitted at all?”** It is a hard,
reason-coded gate rather than advisory metadata.

| Boundary | Current truth |
|---|---|
| Input | candidate plus resolved tenant/seat/channel policy |
| Output | `SEND`, timed tenant `DEFER`, or terminal `SUPPRESS` |
| Runtime | `deliver/policy.py`, `deliver/gate.py`, preference APIs |
| Non-goal | payload interpretation, ownership or execution liveness |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
