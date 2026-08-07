# Authority and schema ratchets

Tests ensure immutable/hash-verified objects, closed brain/publication targets and states, legal
transitions, ACL-scoped reads/review, owner-only organization changes, current-policy review,
tenant expiry, weekly claims/reclaims, serialized monotonic brain versions, rollback predecessor
lineage, organization cascades and layer topology.

Migration ratchets cover immutable policy snapshots, the v2 payload/projection check, independent
evidence, normalized inbox, sanitized rejection audit, ACL propagation to every sink, same-tenant
foreign keys, run-policy-bound object evaluations and account-reset ordering. Lifecycle ratchets
cover held duplicate re-evaluation under current policy/time, Candidate non-regression and later/
terminal duplicate no-op behavior, plus exact sink-level evaluation reasons for successful publish,
no-material-change and metric identity conflict.

Concurrency ratchets assert the tenant-root lock precedes policy/child mutation, review discovers
before policy/object locking, rollback locks discovered policies in sorted order before subject/
object topology, erasure starts with tenant `FOR UPDATE`, and feedback writers use tenant → graph →
card. These are structural proofs; real populated-PostgreSQL contention remains deployment work.

A textual/schema ratchet is not live-database proof, but it prevents silent removal of required
seams.
