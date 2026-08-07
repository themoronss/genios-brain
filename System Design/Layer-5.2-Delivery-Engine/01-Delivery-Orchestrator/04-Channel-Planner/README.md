# Channel Planner

**Status:** Active for supported adapters and authenticated pull surfaces

Answers **“through which concrete channel and in what representation should this travel?”** It
maps the selected destination to channel physics, format and interruptibility without changing
the execution’s facts or commitment.

| Boundary | Current truth |
|---|---|
| Input | selected route, current context, execution confidence/priority and grounded source payload |
| Output | channel, channel class, format kind, interrupt flag and adapter payload |
| Runtime | `deliver/orchestrator.py`, `deliver/gate.py`, `deliver/channels/` |
| Provider truth | target-dependent; see the 11 Delivery Units |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
