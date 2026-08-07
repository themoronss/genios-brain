# Promotion and versioning

Stores an ACL-cohort-scoped metric keyed by tenant, metric subject and bounded period. The metric
subject contains an audience hash so incompatible visibility cohorts cannot collide. An exact
duplicate LearningObject is idempotent; a database identity collision from a different object is
reported as `rejected/metric_identity_conflict`, never falsely transitioned to Published.

Publication is invoked only after the legal validation/governance lifecycle. The publisher cannot
accept an arbitrary target or bypass transition audit.
