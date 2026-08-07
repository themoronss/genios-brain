# 10 · Email Delivery

**Status:** Engine-ready contract; no native adapter; not operational

The Atlas target is represented in the capability model and governed by the common delivery
contracts, but no `email` channel is registered in the adapter registry.

| Boundary | Current truth |
|---|---|
| Engine | can represent email class/requirements and would use the common outbox lifecycle |
| Active route | none: `available_channels` is empty and `operational=false` |
| Required integration | verified provider/domain, sender/recipient identity, preferences and feedback webhooks |
| Business outcome | never inferred from transport alone |
| Important distinction | an email-editor extension is Extension Delivery, not native Email Delivery |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
