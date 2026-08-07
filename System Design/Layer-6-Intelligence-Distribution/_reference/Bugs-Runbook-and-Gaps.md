# Atlas Layer 5.2 gaps and production runbook

## Remaining gaps

- Native email adapter, sender identity, unsubscribe and receipt lifecycle.
- APNs/FCM token, permission, expiry and receipt lifecycle.
- Automatic trusted presence publication from every real client/seat.
- Native application, extension, mobile and dashboard clients.
- Cross-channel impression dedupe and complete viewed/ignored/accepted/executed analytics.
- Live PostgreSQL contention proof, real credentials, egress and provider outage tests.

## Deployment proof

1. Apply migrations 0042 and 0044.
2. Configure one tenant's preferences and verify field-by-field specificity.
3. Publish and expire a presence lease; stale presence must stop affecting delivery.
4. Exercise Slack, Teams, signed webhook and pull with real credentials.
5. Loop quiet-hour deferrals; transport attempts must remain unchanged.
6. Force retryable then terminal failure; fallback must occur only at terminal state.
7. Close/reassign the parent execution while queued; stale delivery must cancel/reroute.
8. Inspect result and analytics APIs, and confirm delivery evidence reaches learning.

Email and native mobile push should stay disabled until their provider and identity lifecycles are
implemented and tested.
