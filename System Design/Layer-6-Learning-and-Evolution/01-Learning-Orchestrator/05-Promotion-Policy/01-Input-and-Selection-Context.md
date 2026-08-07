# Input and selection context

Promotion receives an immutable, preflight-approved `LearningObject`, the locked tenant policy
revision, an explicit evaluation time and the reason-coded validation/governance decisions.

The persisted object begins at `observed`. Its payload, semantic hash, target, unit, source refs,
independent support, trace, visibility, seen window, policy key/revision and subject principal are
frozen together. State changes are written to the append-only transition ledger with actor, reason,
time and bounded detail.

Publication destinations are target-specific:

- Organization/Behavior/Adaptive → versioned `learned_brain_entries`;
- Runtime → `temporary_memories` and `temporary` state;
- Metrics → idempotent `learning_metrics` period row; and
- Knowledge Suggestion → `knowledge_suggestions` in human review, never generic publish.
