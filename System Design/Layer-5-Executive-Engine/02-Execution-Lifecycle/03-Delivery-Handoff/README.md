# Delivery Handoff

Moves grounded reminder/escalation events into Atlas Layer 5.2 without reversing imports.

## Component modules

1. [Bridge Contract](01-Bridge-Contract.md)
2. [Identity and Exactly Once](02-Identity-and-Exactly-Once.md)
3. [Stale Queue Safety](03-Stale-Queue-Safety.md)

**Primary authority:** `genios_engine/executive/lifecycle.py`,
`genios_engine/executive/execution_store.py` and `genios_engine/executive/sweep.py`, narrowed by
the component page.
