# 9 · Mobile Delivery

**Status:** Engine-ready; mobile pull/presence route active; native push not built

Provides an authenticated mobile inbox and presence seam through the durable surface adapter.
It does not claim APNs/FCM delivery.

| Boundary | Current truth |
|---|---|
| Runtime | `channels/surface.py`, presence and inbox APIs |
| Active route | `mobile` pull surface and leased presence |
| Result | durable availability plus explicit mobile lifecycle receipts |
| Business outcome | never inferred from transport alone |
| Integration | mobile app, device registry and APNs/FCM provider lifecycle |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
