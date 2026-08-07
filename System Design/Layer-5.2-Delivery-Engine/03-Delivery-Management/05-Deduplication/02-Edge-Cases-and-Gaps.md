# Edge cases and gaps

- Database uniqueness prevents duplicate logical rows, not an external provider from processing the same request twice.
- Stable idempotency headers protect only receivers that actually honor them. Slack and Teams incoming-webhook semantics do not establish universal exactly-once delivery.
- After an ambiguous ACK, retrying may duplicate a human impression; immediate fallback may do the same on another surface. The engine retains the reservation and avoids definite-failure fallback because certainty is unavailable.
- A client that generates a new receipt idempotency key for every network retry can create repeated same-state evidence. This is auditable but not collapsed as the same request.
- Card identity, delivery identity and business execution identity are linked but serve different purposes; none should be substituted for another in downstream integrations.
