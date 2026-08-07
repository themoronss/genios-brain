# 11 · Slack / Teams Delivery

**Status:** Built

Delivers formatted cards/digests to registered Slack or Teams webhook destinations.

| Boundary | Current truth |
|---|---|
| Runtime authority | `channels/slack.py`, `channels/teams.py`, channel routes |
| Result | adapter/pull outcome projected into the shared DeliveryResult ledger |
| Business outcome | never inferred from transport alone |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
