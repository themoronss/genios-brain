# 4 · Application Delivery

**Status:** Partial

Provides a durable `application` pull channel that an authenticated application can consume.

| Boundary | Current truth |
|---|---|
| Runtime authority | `channels/surface.py` |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
