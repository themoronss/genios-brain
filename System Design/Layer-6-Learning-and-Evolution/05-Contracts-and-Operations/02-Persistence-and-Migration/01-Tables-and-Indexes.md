# Tables and indexes

Migration 0045 creates learning_policies, learning_runs, learning_objects, learning_transitions,
learned_brain_entries, temporary_memories, knowledge_suggestions and learning_metrics.

Indexes support queue/subject reads, transition history, one active brain version and active-memory
expiry. Organization foreign keys enforce account-erasure cascades.
