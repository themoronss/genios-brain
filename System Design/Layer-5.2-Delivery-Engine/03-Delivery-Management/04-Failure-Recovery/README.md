# Failure Recovery

**Engine status:** Built. Provider-specific fallback drills remain deployment work.

Failure recovery advances the route index inside the same logical outbox row after a definite terminal adapter failure. It also records materialization failures that occur before a deliverable row can be created.

| Input | Output | Authority |
|---|---|---|
| terminal attempt, route plan and fresh execution authority | next coherent route generation or durable terminal diagnosis | `deliver/outbox.py`, `deliver/orchestrator.py` |

Fallback is sequential, never speculative fan-out. Owner replay is a separate operation for a terminally failed logical delivery.

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
