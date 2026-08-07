# Delivery Context Resolver

**Status:** Partial

Combines recipient/channel preferences, recent delivery history and the newest valid presence lease at drain time.

| Boundary | Current truth |
|---|---|
| Input | organization, seat, channel candidate, priority/band and explicit evaluation time |
| Output | a grounded delivery context containing timezone, quiet window, channel policy, busy/activity/current-surface state and burst facts |
| Authority | `deliver/presence.py`, `deliver/gate.py` |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
