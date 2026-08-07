# 6 · Dashboard Delivery

**Status:** Partial

Makes intelligence durably queryable for a dashboard without requiring a provider push.

| Boundary | Current truth |
|---|---|
| Runtime authority | `channels/surface.py`, delivery inbox/results/analytics APIs |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
