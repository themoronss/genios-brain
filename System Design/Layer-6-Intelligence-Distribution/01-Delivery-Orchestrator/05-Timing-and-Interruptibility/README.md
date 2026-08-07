# Timing and Interruptibility

**Status:** Built

Determines whether an intrusive delivery may happen now or must wait for a humane safe window.

| Boundary | Current truth |
|---|---|
| Input | delivery candidate, resolved timezone/quiet hours, busy presence, burst history and explicit time |
| Output | `SEND` or `DEFER` with reason and next eligible time |
| Authority | `deliver/timing.py` |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
