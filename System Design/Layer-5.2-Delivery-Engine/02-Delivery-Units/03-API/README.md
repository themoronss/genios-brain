# 3 · API Delivery

**Status:** Engine-ready; authenticated REST path active; optional protocols not built

Exposes execution-bound deliveries and results through tenant/scoped REST resources. It is a
durable pull boundary, not a second delivery ledger or an unauthenticated callback.

| Boundary | Current truth |
|---|---|
| Runtime | `api/delivery_routes.py`, `deliver/results.py`, `channels/surface.py` |
| Active route | authenticated inbox, object/result reads, receipts, attempts and analytics |
| Result | the same outbox row projected into typed `DeliveryObject` and `DeliveryResult` |
| Business outcome | never inferred from transport alone |
| Integration | GraphQL, streaming, MCP and packaged SDKs are optional future clients |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
