# Promotion and versioning

Stores a metric value keyed by tenant, metric subject and bounded period. Duplicate publication for the same period is idempotent.

Publication is invoked only after the legal validation/governance lifecycle. The publisher cannot
accept an arbitrary target or bypass transition audit.
