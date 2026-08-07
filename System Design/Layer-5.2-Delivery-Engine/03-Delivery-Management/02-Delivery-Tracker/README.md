# Delivery Tracker

**Engine status:** Built. Native-client receipt integration and live database contention remain deployment work.

The tracker records the complete Delivery Engine lifecycle without collapsing transport progress into recipient engagement. `delivery_outbox` is the current snapshot, while `delivery_events` is append-only transition evidence. `DeliveryResult` is projected from that ledger rather than maintained as a second status authority.

| Input | Output | Authority |
|---|---|---|
| claimed outbox row, adapter result, authenticated receipt or expiry sweep | transport/lifecycle snapshot, event and typed result | `deliver/tracker.py`, `deliver/results.py`, `deliver/outbox.py` |

## Invariants

- Transport `status` and engagement `lifecycle_status` are independent fields.
- Every receipt is organization-scoped, transition-checked and idempotency-keyed.
- Lifecycle timestamps are chronological and written in the same transaction as their event.
- Terminal states cannot be revived by an ordinary receipt. A failed delivery returns to `queued` only through explicit owner replay.
- Expiry can end eligible lifecycle states and cancels any still-pending physical transport work.

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
