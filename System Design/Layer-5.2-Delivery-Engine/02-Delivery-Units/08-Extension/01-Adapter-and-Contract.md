# Adapter and contract

The orchestrator can map live `gmail`, `email_editor`, `crm` or `browser` presence to the
`extension` destination. The surface adapter marks the committed payload available, and an
authenticated extension retrieves the same `DeliveryObject` from the inbox.

Presence leases report activity, focus/busy state and current surface with mandatory expiry. The
client renders an inline suggestion and posts idempotent lifecycle receipts; it may not choose a
different audience, mutate business priority or execute an external-effect action without the
Layer 5 approval path.
