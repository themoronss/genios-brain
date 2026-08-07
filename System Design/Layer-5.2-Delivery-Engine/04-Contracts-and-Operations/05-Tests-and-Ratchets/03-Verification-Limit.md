# Verification limit

The full repository suite completed with **1,861 passed** and one Starlette/httpx deprecation
warning on 2026-08-08. This is strong deterministic regression evidence for the inspected working
tree; it is not a claim that every deployment integration is operational.

The local suite does not prove:

- migration 0046 upgrade/backfill/`VALIDATE CONSTRAINT` behavior on production-shaped PostgreSQL data;
- concurrent claim, final-rate-slot, fallback, replay, receipt and expiry behavior under the live database isolation level;
- real Slack/Teams permissions, generic/agent webhook DNS and egress policy, provider idempotency or rate-limit behavior;
- SMTP/email, APNs/FCM or other adapters that still require external integration;
- secret backfill, `GENIOS_CRYPTO_KEY` distribution, rotation and disaster recovery;
- native human-client pull/receipt behavior, cross-device impression telemetry or complete Layer 5 outcome attribution; or
- rate-window retention, production dashboards, alerts and SLOs.

Release readiness therefore requires a staging PostgreSQL migration rehearsal, concurrency/load suite, provider credential smoke tests, webhook security/egress review, secret-rotation drill and observability/runbook sign-off. The capabilities endpoint should remain the runtime truth for which engine units are operational versus merely implemented.
