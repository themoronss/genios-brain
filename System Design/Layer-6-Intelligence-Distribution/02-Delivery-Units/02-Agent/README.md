# 2 · Agent Delivery

**Status:** Built

Lets registered agents poll intelligence, claim one signal atomically, report results, or receive signed webhook pushes.

| Boundary | Current truth |
|---|---|
| Runtime authority | `agent_api.py`, `push.py` |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
