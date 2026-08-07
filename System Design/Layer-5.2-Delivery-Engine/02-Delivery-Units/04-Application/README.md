# 4 · Application Delivery

**Status:** Engine-ready; application pull route active; product clients required

Provides a durable `application`/`in_app` route for web, desktop, IDE or CLI clients to consume
the same execution-bound delivery.

| Boundary | Current truth |
|---|---|
| Runtime | `channels/surface.py`, delivery inbox and presence APIs |
| Active route | authenticated `application` and `in_app` pull surfaces |
| Result | durable availability projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |
| Integration | concrete web/desktop/IDE/CLI clients are outside this engine repository |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
