# 5 · Notification Delivery

**Status:** Engine-ready contract; runtime capability non-operational; native push provider absent

Covers notification-shaped delivery through the governed Layer 5.2 path. The contract can render
to authenticated in-app availability, but the runtime capability registry deliberately returns no
configured Notification channel until a genuine native provider exists. Ordinary in-app delivery
remains a Human/Application surface; Slack/Teams are their own Atlas unit.

| Boundary | Current truth |
|---|---|
| Runtime | orchestrator, timing/policy gate and `in_app` surface adapter |
| Active route | none reported for the Notification unit; in-app exists under Human/Application |
| Result | availability and later client receipts in the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |
| Integration | APNs, FCM and operating-system notification providers remain |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
