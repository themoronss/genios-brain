# Edge cases and gaps

- Duplicate receipt retries are safe only when the client reuses its idempotency key. A new key records new evidence even if the lifecycle state is unchanged.
- A late receipt cannot reverse `ignored`, `executed`, `expired`, `suppressed` or `cancelled`; callers must reconcile the conflict instead of rewriting history.
- A provider acknowledgement advances transport, but it does not fabricate `viewed` or later engagement states.
- Card actions and delivery receipts are related evidence streams, not interchangeable APIs. Product clients still need to emit the appropriate authenticated delivery receipt.
- The tracker is transaction-safe by construction, but real PostgreSQL races between receipts, expiry, replay and drain still require deployment concurrency tests.
- `executed` means the recipient invoked the delivery affordance. Layer 5 remains authoritative for whether the business execution completed successfully.
