# Delivery user journey

1. Layer 5 creates an owned ExecutionObject and a grounded communication event.
2. The bridge materializes a delivery candidate with stable identity.
3. Current tenant/seat/channel preferences and a non-expired presence lease are resolved.
4. Audience intent is verified against Layer 5; a registered destination is selected.
5. Policy and timing independently produce SEND, DEFER or SUPPRESS.
6. A deferral changes only the next eligible time; it does not consume a provider attempt.
7. On SEND, the outbox claims the row and invokes the target adapter.
8. Success, retryable failure or terminal failure is recorded.
9. Terminal failure may use a registered fallback only after authority is re-proved.
10. Results/analytics become visible by API and enter the learning batch.

Edge journeys—quiet hours, busy presence, opt-out, reassignment, subject closure, retry exhaustion,
fallback and stale leases—are detailed in the owning component folders.
