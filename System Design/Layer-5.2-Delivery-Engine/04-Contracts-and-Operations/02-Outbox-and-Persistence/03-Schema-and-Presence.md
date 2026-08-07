# Schema and presence

## Migration lineage

- 0032 introduces organization channels and the delivery outbox.
- 0034 adds execution-authority lineage.
- 0042 adds delivery preferences and gate materialization.
- 0044 adds tenant-scoped expiring presence leases.
- 0046 adds the v2 Delivery Engine control plane.

Migration 0046 adds card-to-execution linkage; encrypted configuration columns; execution/event
lineage; audience, destination, format, route, priority, dedupe and frozen-budget fields; claims,
retry generations and legacy-reconciliation audit fields; lifecycle timestamps; `delivery_events`;
`delivery_attempts`; `delivery_rate_windows`; and `delivery_materialization_failures`.

This is deliberately not a mixed-worker migration. The SQL takes a `SHARE ROW EXCLUSIVE` lock on
`delivery_outbox`, marks every pending and already-terminal legacy row whose physical attempt
ledger is unknowable, and seeds the atomic rate table from deliveries already sent in the current
rolling hour and each recipient's current local day. The platform migration runner separately
holds the global `genios-schema-migrations` PostgreSQL advisory lock so two application instances
cannot advance schema versions concurrently.

It enforces organization-scoped logical uniqueness, route bounds, claim shape, retry/priority/budget domains, lifecycle chronology and execution lineage. Composite organization foreign keys and cascade behavior preserve tenant boundaries. Several checks are created `NOT VALID`: they protect new writes, but operations must backfill and explicitly validate legacy rows in production.

## Presence and secrets

Presence leases self-expire so a stale client cannot keep the user permanently busy. Timing decisions always use bounded stored context rather than trusting an indefinitely live process flag.

New secret-bearing channel and agent configurations are Fernet-sealed and require `GENIOS_CRYPTO_KEY`; routing metadata remains inspectable. Legacy plaintext is readable only for rolling migration compatibility. Production requires resave/backfill, key distribution/rotation and a documented rollback path before plaintext columns can be retired.

Legacy delivery producers/drainers must be stopped and their last provider timeout reconciled
before 0046 starts; the table lock cannot fence an external POST already in progress. After the
migration, deploy only v2 workers and then resume. Local tests do not prove that live PostgreSQL
cutover, constraint validation, claim/rate contention or the operational secret migration.
