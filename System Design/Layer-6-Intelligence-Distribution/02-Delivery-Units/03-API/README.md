# 3 · API Delivery

**Status:** Partial

Exposes authenticated REST pull for inbox, typed results, context and analytics.

| Boundary | Current truth |
|---|---|
| Runtime authority | `api/delivery_routes.py`, `channels/surface.py` |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
