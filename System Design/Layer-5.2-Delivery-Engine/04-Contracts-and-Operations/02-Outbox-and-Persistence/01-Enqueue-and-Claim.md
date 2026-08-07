# Enqueue and claim

## Materialization

The active producer scans execution-bound initial and reminder/escalation events. It reconstructs
the immutable execution, derives v1 visibility from its reasoning context when required, enforces
the resulting source ACL, then resolves audience, eligible recipient, route plan, destination,
format, priority and rendered payload before inserting one organization-scoped outbox row. Initial
and event-specific dedupe keys prevent replay from creating a second logical delivery. A queued
`delivery_events` record is written with the materialization.

Raw signals and standalone cards are not independently fanned out. Agent audiences remain on the
signed `agent` or scoped `api` routes; poll-only agents consume `delivery/inbox?channel=api` and
submit lifecycle receipts. Raw `/v1/signals*` handlers return authenticated `410 Gone`.

## Fair claim

Drain selects only due `queued`/`deferred` lifecycle rows or expired `in_flight` leases. PostgreSQL `FOR UPDATE SKIP LOCKED`, a unique claim token and five-minute expiry bound ownership. Priority ages upward every four waiting hours, and per-organization row numbering gives a batch cross-tenant fairness.

Reclaim closes any unfinished prior attempt as `unknown/claim_expired`. The new worker then reloads
secure channel configuration, proves execution liveness and expected hash, repeats visibility-safe
route planning, applies admission, and atomically commits attention reservations plus a `started`
attempt before calling an adapter.

## Completion

A claim is never a delivery receipt. Every physical adapter invocation receives a stable idempotency key and is separately journaled in `delivery_attempts`. Typed adapter results update the attempt and outbox atomically to delivered, scheduled retry, unknown or terminal failure.

Migration 0046 marks every pending pre-control-plane legacy row as reconciliation-required. The v2
drain terminalizes it with a durable lifecycle reason instead of guessing from the aggregate
attempt count; already-terminal legacy rows receive the same replay-risk marker. Only an owner who
explicitly acknowledges possible duplicate delivery may replay either class.

Configuration and payload errors are isolated per row so one malformed delivery cannot stop the whole drain batch.
