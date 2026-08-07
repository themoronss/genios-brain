# Promotion and versioning

Publishes only explicit, lineage-complete objects whose exact TTL passed preflight before any value
was persisted. The direct owner command first binds `(tenant, actor, source_ref)` to the normalized
`learning_event_inbox`; an identical retry reuses the stored observation time, while key reuse with
different semantics returns conflict.

The sink carries visibility and trace. Logical reads exclude the value at `expires_at`; the
tenant-scoped retention pass commits expiry separately from weekly analysis and transitions the
LearningObject from `temporary` to `expired`.

Publication is invoked only after the legal validation/governance lifecycle. The publisher cannot
accept an arbitrary target or bypass transition audit.
