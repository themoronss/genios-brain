# Delivery Outbox

**Engine status:** Built. Quiescent migration rehearsal, live PostgreSQL contention and provider
reconciliation remain deployment evidence.

The Delivery Outbox is the first of the Atlas's eight Delivery Management components and the
durable spine of Layer 5.2. Nothing in the active path is handed straight from an
`ExecutionObject` to an adapter. The orchestrator resolves one permitted delivery and persists
that decision as one logical outbox row; only a fenced worker may later start a physical attempt.

| Input | Output | Authority |
|---|---|---|
| current, hash-verified `ExecutionObject` plus live route/policy context | one durable logical delivery, then a claimed physical attempt | `deliver/orchestrator.py`, `deliver/outbox.py`, migration `0046_l52_delivery_control_plane.sql` |

## Invariants

- One execution initial/event intent has one tenant-scoped `dedupe_key`, even when several routes
  are available.
- Materialization and its initial `queued` lifecycle fact commit in the same transaction; an
  adapter is never called from that transaction.
- Claims use an expiring fencing token. A worker may complete only the claim and attempt it owns.
- Attention reservation and the append-only `started` attempt commit together before a provider
  call.
- Every send re-proves current execution authority, recipient visibility, route and credential
  truth under locks.
- A definite non-delivery may release attention and advance the same row's fallback cursor. An
  ambiguous acknowledgement is retained for reconciliation and cannot silently fan out through
  another channel.
- Transport attempts are append-only; replay changes generation/state, never historical evidence.

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)

The schema/API-level view of these same tables is documented under
[Contracts and Operations](../../04-Contracts-and-Operations/02-Outbox-and-Persistence/README.md).
