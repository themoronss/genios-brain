# Channel Planner

**Status:** Partial

Turns Layer 5's attention/channel intent into a target adapter and surface representation without changing the promise.

| Boundary | Current truth |
|---|---|
| Input | frozen channel class, current registered destinations, surface/presence context and card payload |
| Output | adapter-ready channel/destination plan |
| Authority | Layer 5 `communication.py`, `deliver/destination.py`, adapters |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
