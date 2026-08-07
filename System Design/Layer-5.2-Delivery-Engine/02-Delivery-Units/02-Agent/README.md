# 2 · Agent Delivery

**Status:** Engine-ready; active signed-push/API routes; registered runtime required

Delivers an `ExecutionObject` projection to a specifically registered machine recipient without
exposing it through a human inbox. The canonical route is signed agent webhook or authenticated
agent API delivery.

| Boundary | Current truth |
|---|---|
| Runtime | `deliver/orchestrator.py`, `channels/agent.py`, scoped delivery inbox/receipts |
| Active route | `agent` and authenticated `api`; exact active identity must have `delivery.read`, and API pull requires an active scoped key for that same agent |
| Result | signed-provider or pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |
| Retired surface | raw `/v1/signals*` poll/artifact/claim/result authenticates then returns `410 Gone` with the delivery-inbox replacement |

The machine payload is `genios.agent-delivery.v1`: a canonical full `ExecutionObject` v2, immutable
execution id/hash, optional reminder event, and explicit autonomy/read-only/approval-gate safety
fields. Agent delivery is not a one-action card summary.

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
