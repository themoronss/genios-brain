# Policy and decision

`BrainTarget` is intentionally narrower than `LearningTarget`:

- `BrainTarget` models the four Atlas concepts: Organization, Behavior, Adaptive and Runtime;
- `LearningTarget` models every allowed persistence seam, adding Metrics and Knowledge Suggestion;
- only Organization, Behavior and Adaptive can enter versioned `learned_brain_entries`;
- Runtime requires `expires_at` and can enter only `temporary_memories`;
- Metrics can enter only `learning_metrics`; and
- Knowledge Suggestion can enter only the human-review queue and can never call `publish`.

Contract validation also forbids TTL on non-Runtime objects and forbids the Knowledge unit from
using any target other than Knowledge Suggestion. Publisher dispatch repeats these closed checks.
