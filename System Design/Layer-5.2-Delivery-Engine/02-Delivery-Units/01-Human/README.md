# 1 · Human Delivery

**Status:** Engine-ready; active engine routes; frontend/provider completion varies by surface

Presents an execution-bound delivery to a current human seat through an authenticated surface or
registered human push destination. “Human” is the audience boundary; concrete transport remains
owned by the relevant unit/adaptor.

| Boundary | Current truth |
|---|---|
| Runtime | `deliver/orchestrator.py`, `channels/surface.py`, pull inbox, Slack/Teams/webhook adapters |
| Active routes | `in_app`, `dashboard`, Slack and Teams; contextual application/extension/mobile when present |
| Result | transport acceptance/availability plus separate human lifecycle receipts |
| Business outcome | never inferred from transport alone |
| Isolation | human route ladders exclude the `agent` channel |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
