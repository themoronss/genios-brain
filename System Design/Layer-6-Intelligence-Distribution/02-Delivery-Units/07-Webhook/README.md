# 7 · Webhook Delivery

**Status:** Built

POSTs an adapter payload to a registered HTTPS destination with a verifiable signature.

| Boundary | Current truth |
|---|---|
| Runtime authority | `channels/webhook.py`, `destination.py`, `outbox.py` |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
