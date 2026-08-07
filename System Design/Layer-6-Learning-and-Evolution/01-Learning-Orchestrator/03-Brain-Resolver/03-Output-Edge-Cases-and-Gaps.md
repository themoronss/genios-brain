# Output, edge cases and gaps

**Output:** a `LearningObject` with a closed `LearningTarget`; when the target is a brain, it is
also a member of `BRAIN_TARGETS`/`BrainTarget`.

Important distinctions:

- Metrics and Knowledge Suggestion are not brains and cannot use brain rollback;
- Runtime is an Atlas brain concept but is implemented as expiring context, not a versioned durable
  learned-brain row;
- a Knowledge approval promotes the suggestion's review state only—`expert_brain_changed` remains
  false; and
- changing a brain value, confidence or visibility is material and creates a new version;
  an identical active value is rejected as `no_material_change`.

**Deliberate boundary:** Expert pack/content mutation remains outside automated Layer 6. A human or
separate governed authoring workflow must act on an approved knowledge suggestion.
