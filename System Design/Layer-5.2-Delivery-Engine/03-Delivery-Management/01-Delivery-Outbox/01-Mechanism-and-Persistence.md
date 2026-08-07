# Mechanism and persistence

## 1. Materialize one logical delivery

The minute delivery heartbeat calls `run_distribution(...)`. For each tenant,
`enqueue_execution_deliveries(...)` takes the tenant/materializer locks, reconstructs the stored
`ExecutionObject`, verifies its identity and authority, resolves current source visibility,
audience, destination, channel, format, timing and priority, and inserts one `delivery_outbox`
row. The row and its first append-only `queued` event commit together. A stable logical
`dedupe_key` absorbs repeated sweeps.

Cards may be linked presentation records, but they cannot independently authorize this insert.
Initial execution delivery and each current `execution.reminded` event have separate deterministic
keys. Multiple possible destinations become `route_plan` entries on that one row rather than
multiple notifications.

## 2. Claim with a fencing token

The worker orders already-due rows by effective priority and age, distributes claims fairly across
organizations, and uses PostgreSQL `FOR UPDATE SKIP LOCKED`. Claiming changes the row to
`in_flight` and records `claim_token`, `claimed_at` and `claimed_until`. Every later mutation is
conditioned on the same token, so an expired worker cannot complete a successor's claim.

Before dispatch, the worker locks the logical outbox row first, then the matching physical attempt
row. This single lock order is shared by normal completion and claim recovery.

## 3. Admit and journal before network I/O

The worker re-runs policy/timing, re-plans the current route under tenant and authority locks, and
validates the currently decrypted destination using the same predicate exposed by capability
discovery. For intrusive routes it conditionally reserves the exact rolling-hour slot (tenant-wide
for the shared Slack/Teams stream, recipient-scoped for other intrusive channels) and the
recipient-local-day attention slot.

The reservation and a new `delivery_attempts(outcome='started')` row commit atomically before the
adapter is called. Consequently, a crash after dispatch leaves physical ambiguity that recovery
can see; it cannot leave an invisible provider call or an untraceable quota spend.

## 4. Complete, retry or reconcile

- A successful provider acknowledgement marks the exact attempt delivered, advances the logical
  transport/lifecycle snapshots and appends the delivered event.
- A definite retryable failure records the attempt, releases its attention reservation and moves
  `next_attempt_at` without consuming a deferral as a failure.
- A definite terminal failure may move the same row to the next route only after current authority
  and destination are re-proved.
- An unknown result retains attention. Slack/Teams ambiguity stops for manual reconciliation;
  idempotent webhook/agent receivers may use the stable receiver key on a bounded retry.
- Owner replay is an explicit generation/state transition. Started, unknown, delivered or legacy
  ambiguous evidence requires duplicate-risk acknowledgement.

## 5. Persistent authorities

| Store | Authority |
|---|---|
| `delivery_outbox` | one logical intent, current route cursor, claim and lifecycle snapshot |
| `delivery_attempts` | append-only physical invocation evidence |
| `delivery_events` | idempotent lifecycle-transition evidence |
| `delivery_rate_windows` | atomic attention reservations |
| `delivery_materialization_failures` | operator-visible failures before a safe outbox row exists |

Migration `0046_l52_delivery_control_plane.sql` installs the lineage, fencing, attempt, event,
quota and reconciliation schema. Its legacy quarantine is a cutover boundary, not an online
old/new-worker compatibility mechanism.
