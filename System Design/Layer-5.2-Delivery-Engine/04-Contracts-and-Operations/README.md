# Part D · Contracts and Operations

This branch records the versioned boundaries and operational truth behind the Delivery Engine. It separates implemented engine behavior from the provider, migration and deployment evidence still required before production rollout.

| Subpart | Engine status | Purpose |
|---|---|---|
| [Delivery Contracts](01-Delivery-Contracts/README.md) | v2 built | Candidate, monotonic admission, immutable object and typed result |
| [Outbox and Persistence](02-Outbox-and-Persistence/README.md) | Control plane built | Durable materialization, claims, attempts, events, rate windows and failure diagnostics |
| [API Surface](03-API-Surface/README.md) | Built | Preferences, context, results, inbox, receipts, analytics, attempts, dead letters, replay and channel capabilities |
| [Card Production](04-Card-Production/README.md) | Built for execution-bound cards | Grounded presentation, validation, persistence and typed actions |
| [Tests and Ratchets](05-Tests-and-Ratchets/README.md) | Existing suite green; new control-plane matrix incomplete | Deterministic evidence, architecture/schema checks and production verification limits |

## Operational boundary

The engine is durable and auditable, but a code-complete control plane is not the same as a deployed channel. Email-provider/SMTP and native-push integrations, real provider credentials, live PostgreSQL migration/concurrency proof, secret-rotation operations, network egress hardening, scheduled digest wiring and production observability remain explicit integration work.
