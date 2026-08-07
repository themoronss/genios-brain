# Output, edge cases and gaps

**Output:** a fenced in-flight row for one adapter attempt, a deferred row with a later due time,
or a terminal/dead-letter state with retained attempt history.

**Edge cases and gaps**

- Provider calls are at-least-once when acknowledgement is ambiguous. Webhook-capable receivers
  receive a stable idempotency key for the logical route generation.
- An ambiguous result never cross-channel fails over.
- Owner replay preserves old attempts/events. A definite failure starts a new retry generation;
  ambiguous ACK-loss replay deliberately preserves the stable generation idempotency key.
- The scheduler uses Postgres rather than a separate distributed priority queue; sustained
  production contention, provider quotas and very high-volume fairness remain deployment proof.
- Migration 0046 marks every pre-control-plane pending legacy row reconciliation-required. The v2
  drain converts it to `failed_terminal` without a provider call; only then may an owner inspect
  the uncertainty and explicitly acknowledge duplicate risk for replay.
