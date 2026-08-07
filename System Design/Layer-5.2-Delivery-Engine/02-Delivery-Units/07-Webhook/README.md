# 7 · Webhook Delivery

**Status:** Engine-ready; signed adapter active; tenant receiver/configuration required

POSTs the grounded delivery payload to a tenant-registered public HTTPS endpoint with HMAC
integrity and a stable idempotency key.

| Boundary | Current truth |
|---|---|
| Runtime | `channels/webhook.py`, `destination.py`, `outbox.py`, channel configuration APIs |
| Active route | signed generic webhook adapter |
| Result | provider acceptance/failure projected into attempts and DeliveryResult |
| Business outcome | never inferred from transport alone |
| Integration | customer endpoint, secret management, receiver verification and egress operations |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
