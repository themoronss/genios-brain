# Expiry execution

`expire_memories` locks due active rows, marks `temporary_memories.expired_at` and appends the
LearningObject transition to Expired. It runs before the weekly claim.

No cache is authoritative today. A future cache must be subordinate to the database expiry.
