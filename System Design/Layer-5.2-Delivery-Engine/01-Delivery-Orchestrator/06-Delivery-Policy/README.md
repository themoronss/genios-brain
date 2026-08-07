# Delivery Policy

**Status:** Built

Decides whether a tenant/seat/channel candidate is permitted to travel at all.

| Boundary | Current truth |
|---|---|
| Input | candidate plus resolved tenant/seat/channel policy |
| Output | `SEND` or terminal `SUPPRESS` with a stable reason code |
| Authority | `deliver/policy.py`, `deliver/gate.py` |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
