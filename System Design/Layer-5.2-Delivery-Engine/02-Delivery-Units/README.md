# Part B · The 11 Delivery Units

The Atlas units are target boundaries, not eleven promises that eleven external products are
already deployed. The engine exposes the same distinction through
`GET /api/org/{org_id}/delivery/capabilities`:

- **Engine-ready**: Layer 5.2 can represent, govern, persist, retry and report the unit.
- **Available channel seam**: at least one adapter or authenticated pull surface is compiled into
  the engine. This does not imply the runtime endpoint reports it operational for this tenant.
- **Provider/client-dependent**: credentials, endpoints, installed UI, device tokens or external
  provider verification remain outside this repository.

Runtime capability is fail-closed, not “a config row exists.” The endpoint decrypts sealed
channel/agent configuration with the active `GENIOS_CRYPTO_KEY` and applies the same URL, host,
secret-length, agent-id and active-scope checks used by the concrete adapters. Corrupt ciphertext,
the wrong key or malformed configuration reports the channel non-operational without exposing the
credential or decryption error. Materialization calls these same validators before adding a route,
so an unavailable credential cannot still be frozen into a delivery plan.

| # | Atlas unit | Engine-ready | Available channel seam | Remaining integration | Folder |
|---|---|---:|---:|---|---|
| 1 | Human | Yes | Yes: in-app, dashboard, Slack, Teams | Browser/desktop/mobile clients | [Human](01-Human/README.md) |
| 2 | Agent | Yes | Yes: signed agent push and scoped API inbox | Active agent with `delivery.read`; exact active API key or valid endpoint/secret | [Agent](02-Agent/README.md) |
| 3 | API | Yes | Yes: authenticated REST pull and webhook | GraphQL/stream/MCP/SDK only if selected | [API](03-API/README.md) |
| 4 | Application | Yes | Yes: application/in-app pull | Web/desktop/IDE/CLI client | [Application](04-Application/README.md) |
| 5 | Notification | Yes | Contract maps to in-app; runtime unit remains non-operational | APNs/FCM/system notification provider | [Notification](05-Notification/README.md) |
| 6 | Dashboard | Yes | Yes: dashboard/in-app pull | Dashboard rendering and complete interaction telemetry | [Dashboard](06-Dashboard/README.md) |
| 7 | Webhook | Yes | Yes: signed public-HTTPS adapter | Tenant endpoint, secret and receiver operations | [Webhook](07-Webhook/README.md) |
| 8 | Extension | Yes | Yes: extension pull + presence | Browser/CRM/email extension client | [Extension](08-Extension/README.md) |
| 9 | Mobile | Yes | Yes: mobile pull + presence | Mobile client plus APNs/FCM for native push | [Mobile](09-Mobile/README.md) |
| 10 | Email | Yes | **No native adapter** | Verified provider/domain, preferences and feedback webhooks | [Email](10-Email/README.md) |
| 11 | Slack / Teams | Yes | Yes: provider adapters | Tenant webhook/OAuth configuration and provider proof | [Slack and Teams](11-Slack-and-Teams/README.md) |

## Shared execution boundary

Every canonical unit consumes a durable `DeliveryObject` derived from an `ExecutionObject` and
returns the common `ChannelResult`/`DeliveryResult` vocabulary. An adapter may format and perform
one transport attempt; it may not choose the audience, reopen Layer 5 reasoning, change business
priority, bypass policy/timing, or infer business success from transport acceptance.

Human and agent routes remain isolated. Human deliveries exclude the agent channel. Agent
deliveries require an active registry identity whose allowed actions include `delivery.read`; the
API route also requires an active key for that exact agent with the same scope. They may use only
the signed-agent/scoped-API ladder and never fall back into a human inbox. The older
`/v1/signals*` poll/artifact/claim/result routes authenticate their historical scopes and return
`410 Gone`; they are migration sentinels, not a compatibility execution plane.
