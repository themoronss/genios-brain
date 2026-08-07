# Input, Validator and Retriever

## Input / Validator

Input is the result of Preference Learning, not raw user activity. Only these categories enter:
`communication_style`, `decision_style`, `meeting_habit`, `execution_habit`, and
`relationship_pattern`. The parent has already proven explicit preference shape, actor scope,
source ACL, trace and independent evidence.

## Retriever

The unit calls the same deterministic `preference_learning(batch)` plan and filters its objects. It
copies parent value, `LearningEvidence`, first/last seen times, trace, visibility,
lineage-complete flag and subject principal. It stores the parent learning ID in metadata.

No second source query, behavior inference or observation duplication occurs. User cohorts remain
actor-scoped and retain the parent's private resolved-subject cap; organization-scoped parent
preferences remain organization-scoped. A rejected unresolved/source-excluded user preference
cannot become valid merely by entering Behavior Evolution.
