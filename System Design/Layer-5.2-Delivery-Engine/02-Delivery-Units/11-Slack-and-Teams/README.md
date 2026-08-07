# 11 · Slack / Teams Delivery

**Status:** Engine-ready; adapters active; tenant/provider configuration required

Delivers grounded execution cards/reminders to tenant-registered Slack or Microsoft Teams
webhook/Workflow destinations. A raw legacy digest cannot independently authorize new delivery.

| Boundary | Current truth |
|---|---|
| Runtime | `channels/slack.py`, `channels/teams.py`, channel routes, durable outbox |
| Active route | Slack incoming webhook and Teams webhook/Workflow adapters |
| Result | provider acceptance/failure projected into attempts and DeliveryResult |
| Business outcome | never inferred from transport alone |
| Integration | tenant credentials/configuration, workspace permissions and live-provider proof |

## Component modules

1. [Adapter and contract](01-Adapter-and-Contract.md)
2. [Lifecycle, edge cases and gaps](02-Lifecycle-Edge-Cases-and-Gaps.md)
