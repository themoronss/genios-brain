# Review queue and API

Knowledge proposals enter `knowledge_suggestions`; all human-review LearningObjects remain
queryable by state. The owner-only review endpoint accepts an explicit approve/reject decision,
actor and optional note.

Tenant scope and current state are checked under transaction before transition.
