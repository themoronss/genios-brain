# 9 · Mobile Delivery

**Status:** Partial

Provides a mobile pull/presence seam through the durable surface adapter.

| Boundary | Current truth |
|---|---|
| Runtime authority | `channels/surface.py`, presence and inbox APIs |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
