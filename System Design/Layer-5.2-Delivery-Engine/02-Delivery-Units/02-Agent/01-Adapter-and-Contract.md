# Adapter and contract

Canonical agent materialization resolves an active org-scoped registry record whose
`allowed_actions` contains the exact `delivery.read` scope. Signed push requires a valid public
HTTPS endpoint, secret and agent id. API pull additionally requires an active `api_keys` row for
that exact selected agent with `delivery.read`; an organization-wide “some agent has a key” check
cannot activate another recipient.

The `agent` adapter sends an `execution.delivery` envelope with `agent_id`, HMAC-SHA256 signature
and stable generation idempotency key. Its payload is `genios.agent-delivery.v1`, containing the
canonical complete `ExecutionObject` v2, execution id/hash, optional reminder-event context and
explicit `autonomy_allowed`, `read_only` and approval-gate action ids. The scoped API alternative is
`GET /api/org/{org_id}/delivery/inbox?channel=api&recipient={agent_id}` followed by idempotent
`POST .../delivery/results/{delivery_id}/events` receipts.

Agent routes are fail-closed: their ladder contains only `agent` and eligible `api`. Generic
webhook exists as an engine capability but is not used as the canonical agent fallback, and no
agent delivery can become a human in-app/dashboard message.

The legacy raw-signal endpoints no longer support polling or execution. `/v1/signals`, artifact,
claim and result handlers first authenticate their old scope, then return `410 Gone` and identify
the scoped delivery inbox replacement. The retained `agent_api.py` functions and synchronous
`push_card_to_agents` helper are non-production compatibility code; neither is wired into the
execution-bound materializer.
