# Output, edge cases and gaps

**Output:** a `ValidationResult` whose state/reason is persisted through the lifecycle ledger. A
preflight refusal is instead written to `learning_input_rejections` with stable identity, hash,
unit, target, subject, trace and ACL—but not the forbidden proposed value.

Security and consent behavior:

- API reads repeat both SQL ACL filtering and typed visibility checks;
- private/participant review requires the actor/viewer to pass the source-derived ACL;
- Organization approval and rollback require owner authority;
- approval revalidates current policy, freshness and a newer-active-value guard;
- policy updates use compare-and-set revisioning and immutable snapshots; and
- workspace reset erases learning inputs/objects/publications/rejections but preserves consent
  policy and its revision history.

**Remaining operations requirement:** define who owns tenant policy changes and approval queues,
monitor pending/failed/rejected reason codes, and document incident/rollback procedures. The code
does not infer organizational authority from caller-supplied content.
