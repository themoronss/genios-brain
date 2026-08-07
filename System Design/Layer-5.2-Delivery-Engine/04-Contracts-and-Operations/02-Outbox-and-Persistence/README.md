# Outbox and Persistence

Provides the Delivery Engine's durable control plane: logical materialization, fair claiming, authority-aware admission, physical attempt journaling, lifecycle events, atomic attention reservations, replay and pre-outbox failure diagnostics.

**Primary authority:** `deliver/orchestrator.py`, `deliver/outbox.py`, `deliver/tracker.py`, migrations 0032, 0034, 0042, 0044 and 0046

| Persistent authority | Purpose |
|---|---|
| `delivery_outbox` | One logical delivery snapshot and current transport/lifecycle state |
| `delivery_attempts` | Append-only physical invocation journal |
| `delivery_events` | Idempotent lifecycle evidence |
| `delivery_rate_windows` | Exact rolling-hour and recipient-local-day attention reservations, seeded at 0046 cutover |
| `delivery_materialization_failures` | Durable failures before an outbox row can exist |
| `delivery_presence` | Tenant-scoped expiring timing context |

## Component modules

1. [Enqueue and Claim](01-Enqueue-and-Claim.md)
2. [Defer Suppress Cancel](02-Defer-Suppress-Cancel.md)
3. [Schema and Presence](03-Schema-and-Presence.md)
