# Results, inbox and analytics

## Evidence reads

Owner-authenticated organization routes list/get `delivery-result.v2`, return `delivery-analytics.v2`, expose physical attempt history and list dead letters. Scoped keys cannot inherit these organization-wide reads. Dead letters include terminal outbox rows and unresolved pre-outbox materialization failures so operators can see both failure classes.

Owner replay accepts only a terminal outbox failure. It cannot replay a materialization diagnosis
that has no logical delivery row. If physical-attempt evidence is `started`, `unknown` or already
`delivered`, or if migration marked legacy transport uncertainty, the API returns `409` until the
owner explicitly sends `acknowledge_ambiguous_delivery_risk=true`. That acknowledgement is written
to lifecycle metadata; legacy approval also receives a durable audit timestamp.

## Agent pull and receipts

`delivery.read` exposes the durable inbox. A scoped caller must request `channel=api` and exactly
its authenticated agent recipient; unlike an owner query it cannot receive organization-wide or
human-audience rows. Route materialization separately proves that the selected active agent has
`delivery.read` in `agent_registry.allowed_actions` and that the same exact agent has an active API
key with the scope. This closes both organization-wide pull leakage and cross-agent capability
leakage.

`delivery.receipts.write` accepts authenticated `viewed`, `ignored`, `accepted`, `executed` or `failed` evidence. Scoped callers can mutate only their own recipient deliveries; owners may operate across the organization. Idempotency key and lifecycle transition checks are enforced below the route.

The capabilities endpoint reports engine readiness, operational state, supported channels and
integrations still required. Operational provider state means sealed credentials were successfully
decrypted and passed the concrete adapter's URL/host/secret/id validation; corrupt ciphertext or a
wrong key reports unavailable without leaking the failure. These reads project current runtime
truth and do not establish another state authority.
