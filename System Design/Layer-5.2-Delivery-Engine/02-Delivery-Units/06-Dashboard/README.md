# 6 · Dashboard Delivery

**Status:** Engine-ready; dashboard pull route active; full UI/telemetry client-dependent

Makes an execution-bound delivery durably queryable on the dashboard without requiring an
external provider push.

| Boundary | Current truth |
|---|---|
| Runtime | `channels/surface.py`, delivery inbox/results/analytics APIs |
| Active route | `dashboard` and `in_app` authenticated pull surfaces |
| Result | durable availability plus explicit UI lifecycle receipts |
| Business outcome | never inferred from transport alone |
| Integration | complete dashboard renderer and universal telemetry remain client work |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
