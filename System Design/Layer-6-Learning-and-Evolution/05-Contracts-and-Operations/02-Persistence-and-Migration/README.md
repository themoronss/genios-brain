# Persistence and Migration

Provides one tenant-scoped durable authority for policies, immutable policy revisions, normalized
inputs, runs, immutable proposals, per-run evaluation verdicts, refusal/lifecycle audit and outputs.

**Primary authority:** `feedback/store.py`, `migrations/0045_atlas_l6_learning.sql` and the additive
`migrations/0047_l6_learning_hardening.sql`.

## Component modules

1. [Tables and Indexes](01-Tables-and-Indexes.md)
2. [Store Responsibilities](02-Store-Responsibilities.md)
3. [Production Proof](03-Production-Proof.md)
