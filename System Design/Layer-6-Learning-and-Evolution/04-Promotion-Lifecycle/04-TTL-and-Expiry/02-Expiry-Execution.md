# Expiry execution

`expire_memories` locks due active rows, marks `temporary_memories.expired_at` and appends the
LearningObject transition to Expired. Its query and writes are explicitly tenant-scoped.

Expiry commits in its own retention transaction before weekly analysis. It therefore still runs
when learning consent is disabled, and a later analysis/publication failure cannot resurrect a
lease that already elapsed.

No cache is authoritative today. A future cache must be subordinate to the database expiry.
