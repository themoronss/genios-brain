# Mechanism and persistence

## Route recovery

The materialized `route_plan` and `route_index` define ordered alternatives. After a definite terminal failure, `_advance_route(...)` verifies that another route exists, increments the index and `retry_generation`, resets generation attempts, and recomputes channel, destination, channel class, format, interrupt behavior, route reason and rendered payload. All of this happens on the existing outbox row; recovery does not create a competing logical delivery.

Every send generation must still pass current execution liveness and expected-hash validation. Closed, cancelled or changed authority causes cancellation rather than recovery.

## Explicit replay

An owner may replay only a `failed_terminal` row. Replay locks the row, inspects its append-only
attempt ledger and retains the logical identity and all historical evidence. A definite
non-delivery queues a fresh retry generation. `started`, `unknown`, already-`delivered`, or
pre-control-plane legacy uncertainty requires
`acknowledge_ambiguous_delivery_risk=true`; acknowledged ACK-loss preserves the existing generation
and stable receiver idempotency key. The lifecycle event records whether risk was acknowledged,
and legacy acknowledgement receives `manual_replay_approved_at`.

Migration 0046 marks both pending and already-terminal legacy rows reconciliation-required because
their aggregate attempt count cannot prove whether an old process called the provider. The first
v2 drain terminalizes pending rows with `legacy_attempt_evidence_missing`; neither class may be
replayed silently.

## Materialization failures

Malformed source payload, missing eligible agent route or another pre-outbox planning failure is upserted into `delivery_materialization_failures` with occurrence count, error/detail, first/last-seen times and resolution state. A later successful repair marks that diagnosis resolved instead of silently losing the original failure.
