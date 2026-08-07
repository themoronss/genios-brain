# Immutability and round-trip

Values/evidence are frozen and canonicalized; aware timestamps and basis-point/count ranges are
validated. Semantic serialization round-trip must preserve LearningObject identity.

Lifecycle state is stored separately so review/publication/rollback never rewrites the proposal
that evidence supported.
