# 5 · Notification Delivery

**Status:** Partial

Covers notification-shaped chat delivery while preserving admission, retry and audit rules.

| Boundary | Current truth |
|---|---|
| Runtime authority | Slack/Teams adapters, chat routing and pull surfaces |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
