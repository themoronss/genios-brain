# Promotion and versioning

Uses the serialized shared publisher for actor-scoped adaptive preferences and governed
recommendation-efficacy objects. Constrained evidence must name a subject principal who could see
the source; otherwise preflight rejects it before proposal value persistence.

There is one active version per audience-safe subject. Versions and supersession remain monotonic
through rollback, and an ACL change is never mistaken for a no-op.

Publication is invoked only after the legal validation/governance lifecycle. The publisher cannot
accept an arbitrary target or bypass transition audit.
