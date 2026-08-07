# Part C · Delivery Management

Delivery Management is the Atlas's eight-system durable control plane around the Delivery
Engine's routing and adapter units. It owns the outbox, lifecycle evidence, claims, attempts,
retry timing, fallback progression, attention reservations, result projection and delivery
analytics. It does not own the underlying business execution.

## Implementation map

| Atlas subpart | Engine status | Implemented authority | Remaining integration evidence |
|---|---|---|---|
| [Delivery Outbox](01-Delivery-Outbox/README.md) | Built | `deliver/orchestrator.py`, `deliver/outbox.py`, migration 0046 | Quiescent cutover, live contention and provider reconciliation proof |
| [Delivery Tracker](02-Delivery-Tracker/README.md) | Built | `deliver/tracker.py`, `deliver/results.py` | Native-client receipt wiring and live concurrency proof |
| [Retry Manager](03-Retry-Manager/README.md) | Built | `deliver/outbox.py` | Real provider throttling and outage drills |
| [Failure Recovery](04-Failure-Recovery/README.md) | Built | route index, authority revalidation and owner replay | Provider-specific failover validation |
| [Deduplication](05-Deduplication/README.md) | Built for logical delivery | database identity, attempt journal and provider key | Receiver cooperation is required for ambiguous-ACK exactly-once behavior |
| [Rate Limiter](06-Rate-Limiter/README.md) | Built | atomic `delivery_rate_windows` reservations | Live PostgreSQL contention, cleanup and capacity proof |
| [Delivery Analytics](07-Delivery-Analytics/README.md) | Built for recorded evidence | `deliver/analytics.py`, lifecycle timestamps | Surface-specific impression telemetry and business attribution |
| [Delivery Object Builder](08-Delivery-Object-Builder/README.md) | Built | `contracts/delivery.py`, `deliver/orchestrator.py`, `deliver/results.py` | New provider configuration and deployment readiness |

## Boundary

Transport state and engagement state are deliberately separate. A provider acknowledgement can prove that an adapter accepted a request; `viewed`, `ignored`, `accepted` and `executed` require explicit lifecycle evidence. Even `executed` is a delivery interaction state, not proof that the Layer 5 business execution succeeded. Layer 5 remains outcome authority, and Layer 6 may learn only from the durable facts the Delivery Engine actually recorded.
