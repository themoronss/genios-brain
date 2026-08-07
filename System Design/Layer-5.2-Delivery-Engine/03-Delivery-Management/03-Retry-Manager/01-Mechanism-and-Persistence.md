# Mechanism and persistence

## Claim and invocation

The drain selects due `queued` or `deferred` lifecycle rows and expired `in_flight` claims in bounded batches with `FOR UPDATE SKIP LOCKED`. A five-minute claim token prevents two workers from treating the same selection as theirs. Priority aging raises waiting work one rank every four hours, while per-organization row numbering prevents a noisy tenant from monopolizing a batch.

Before invoking an adapter, the worker reloads configuration, revalidates execution identity and
expected authority hash, repeats visibility-safe current route planning and applies admission. For
intrusive delivery, the exact rolling-hour reservation, recipient-local-day reservation and
`started` `delivery_attempts` row commit in the same transaction. Only after that durable physical
evidence exists may the provider call begin.

## Attempt journal

An attempt begins as `started`, includes the claim token and stable provider idempotency key, and is
completed as `delivered`, `retryable_failure`, `terminal_failure` or `unknown`. If a stale claim is
reclaimed, the worker updates only the `started` attempt owned by that exact expired token. If no
provider attempt had started, it safely requeues the row; otherwise it closes the attempt as
`unknown/claim_expired` before a successor token begins.

Retryable failures use the bounded 5/30/120/720-minute ladder. A numeric `Retry-After` can replace the next delay while a ladder slot remains; it does not add another slot. Timing deferrals only update `next_attempt_at`, `defer_count` and gate reason; they create no attempt.

Configuration cache keys include organization, channel and agent recipient where applicable, preventing one agent's sealed secret from being reused for another.
