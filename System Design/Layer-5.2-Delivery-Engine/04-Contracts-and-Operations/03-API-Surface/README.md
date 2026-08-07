# API Surface

Exposes organization-scoped configuration, delivery evidence and agent pull/receipt surfaces without moving admission or transport policy into HTTP handlers.

**Primary authority:** `api/delivery_routes.py`, `api/channel_routes.py`, `api/agent_mgmt_routes.py`, platform authentication dependencies

## Authorization model

- Owner-only management and organization-wide reads: preferences, effective settings, held work, results, analytics, attempts, dead letters, capabilities, channel configuration and replay. `get_current_org` explicitly rejects scoped credentials.
- Scoped agent operations: context PUT/GET, API pull inbox and lifecycle receipts are bound to the
  authenticated `agent_id` and exact declared scope; an owner credential may also use these routes.
- Raw `/v1/signals*` poll/artifact/claim/result handlers are authenticated `410 Gone` sentinels.
  They cannot be used as a second agent execution API.
- Handler authorization does not replace ownership predicates in SQL; both are required.

Native human-seat self-service identity is not yet a dedicated principal model. Current scoped
self-binding is agent-based, while organization owners retain the management surface.

## Component modules

1. [Preferences and Context](01-Preferences-and-Context.md)
2. [Results Inbox and Analytics](02-Results-Inbox-and-Analytics.md)
3. [Channel Configuration](03-Channel-Configuration.md)
