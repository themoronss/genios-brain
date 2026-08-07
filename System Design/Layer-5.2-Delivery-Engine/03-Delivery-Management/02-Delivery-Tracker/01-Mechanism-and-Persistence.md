# Mechanism and persistence

## Two related state machines

The outbox keeps a physical transport state such as `queued`, `in_flight`, `delivered` or `failed_terminal`, and a logical lifecycle state:

`queued → deferred/delivered/failed/expired/suppressed/cancelled`

After delivery, authenticated evidence may advance through `viewed`, `accepted` and `executed`; `ignored` and `expired` are also terminal recipient outcomes. Repeated evidence for the current state is allowed when it has a new idempotency key, but illegal reversals are rejected.

## Receipt transaction

`append_event(...)` locks the organization-scoped outbox row, validates the transition, event clock and lifecycle chronology, inserts a uniquely keyed `delivery_events` row, and updates the lifecycle snapshot and timestamp atomically. Non-delivery actors cannot submit a timestamp more than five minutes in the future. The same `(org_id, delivery_id, idempotency_key)` cannot mutate state twice.

The public result is then projected from this same row. It includes transport attempts, deferrals, delivery and engagement clocks, reason codes, metrics and diagnostic metadata without creating a second mutable truth.

## Expiry

The expiry sweep can terminalize due `queued`, `deferred`, `delivered`, `viewed` and `accepted` lifecycles. If physical work is still `queued` or `in_flight`, it is cancelled and its claim is cleared. An already-recorded provider attempt remains immutable audit evidence.
