# Destination Router

**Status:** Active

Answers **“where should this delivery go?”** It creates one stable primary plus an ordered,
audience-safe fallback ladder from current context, priority and supported destinations.

| Boundary | Current truth |
|---|---|
| Input | resolved audience/recipient, delivery priority, live presence and registered destinations |
| Output | primary channel plus ordered `route_plan` |
| Runtime | `deliver/orchestrator.py`, `deliver/destination.py`, `deliver/channels/` |
| Safety | human/agent ladders are disjoint; participant/private content stays on scoped surfaces |

## Component modules

1. [Inputs and context](01-Inputs-and-Context.md)
2. [Rules and decision](02-Rules-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
