# Mechanism and persistence

## Logical identity

Migration 0046 enforces one `(org_id, dedupe_key)` outbox row. Initial execution delivery uses `execution:<execution_id>:initial`; an execution event uses `execution:<execution_id>:event:<event_id>`. Producer replay therefore resolves to the existing logical delivery across channels, not merely to the same first channel.

Fallback advances `route_index` on that same row. It cannot create a duplicate outbox item. Its physical history remains separated by `retry_generation` and `delivery_attempts`.

## Physical and event identities

The provider-facing idempotency key is stable within a route generation: `delivery_id:retry_generation:channel`. A new fallback route or explicit replay increments the generation so intentional new work has a new key.

Lifecycle receipt replay is protected independently by unique `(org_id, delivery_id, idempotency_key)` event identity. This makes retries safe when clients preserve their original key.
