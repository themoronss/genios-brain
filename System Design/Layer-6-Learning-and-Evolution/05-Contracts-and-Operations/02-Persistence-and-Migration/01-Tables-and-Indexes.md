# Tables and indexes

Migration 0045 creates learning_policies, learning_runs, learning_objects, learning_transitions,
learned_brain_entries, temporary_memories, knowledge_suggestions and learning_metrics.

Migration 0047 is additive and leaves 0045 immutable. It adds:

- immutable `learning_policy_revisions` plus current-policy revision pointers;
- run/object policy bindings, attempt/failure audit and the complete `learning.v2` projection;
- append-only `learning_object_evaluations`, keyed once per tenant/run/object and bound by composite
  foreign key to that run's exact policy key/revision/evaluation time;
- tenant-scoped `learning_event_inbox` for structured events and explicit leased memory;
- sanitized `learning_input_rejections` for malformed inputs and preflight refusals;
- visibility/trace columns on every published sink; and
- explicit entry/object supersession lineage and same-tenant composite foreign keys.

Indexes support trace, run, policy, ACL scope, rejection, queue/subject, transition history,
per-object evaluation history, monotonic brain lineage, one active brain version and active-memory
expiry. Migration ordering first gives `learning_runs` a unique
`(org_id,run_id,policy_key,policy_revision,evaluation_time)` identity, then creates the evaluation
table and its composite run-policy-time/object foreign keys, adds the direct tenant-erasure
constraint, then creates the descending evaluation-history index.
`learning_object_evaluations` has that direct `org_id → orgs(id) ON DELETE CASCADE` constraint
rather than relying only on cascades through runs/objects. Organization cascade keys
cover data-bearing inputs/outputs. Workspace reset removes evaluations,
inbox/rejection data before their parent rows while preserving consent policy and its immutable
revision history.
