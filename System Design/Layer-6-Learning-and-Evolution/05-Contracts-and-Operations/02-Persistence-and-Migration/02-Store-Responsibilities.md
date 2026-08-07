# Store responsibilities

The store ensures/locks policy authority, binds its immutable revision, and loads a typed batch from
canonical feedback revisions, verified execution outcomes, graph/source lineage, normalized inbox
events and delivery-event history. It reconstructs lower-layer immutable envelopes before trusting
their identity, ACL or trace.

Every production Layer 6 mutation enters through `lock_learning_tenant`: tenant `orgs FOR SHARE`
is always first. A needed policy lock comes next, before LearningObject, Runtime memory or
tenant+brain+subject advisory locks. `expire_memories` also takes the tenant root itself because it
is a public maintenance entrypoint. Reset/delete uses the incompatible `orgs FOR UPDATE` root before
walking child tables, eliminating post-erasure recreation and parent/child lock inversion.

Malformed inputs become sanitized hash/reason records. Preflight refusals are audited without the
forbidden proposed value. Accepted objects are round-trip/id/hash verified before persistence; the
store then locks identical held objects, permits re-evaluation only from Observed/Candidate,
prevents Candidate → Observed regression, appends the exact per-run policy/time verdict, applies
guarded transitions, serializes dynamic publication, queues knowledge review, expires tenant
memory and completes/reclaims weekly runs. The stored verdict uses the final sink-level state/reason
from `apply_path_result`, including publication no-op/conflict. Objects already beyond Candidate are
duplicate no-ops counted as unchanged.

Review and rollback use discovery reads only to determine which policies/topology to lock; all
authority is re-read and checked after canonical locks are held. Rollback sorts multiple policy
keys before subject advisory/object locks, making its order deterministic across predecessor chains.

Pure learning units do not write SQL or choose transaction boundaries.
