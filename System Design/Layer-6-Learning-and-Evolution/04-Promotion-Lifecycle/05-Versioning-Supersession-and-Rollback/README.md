# Versioning, Supersession and Rollback

Preserves append-only history while changing the effective dynamic entry. Publication and rollback
serialize on tenant+brain+subject and keep explicit predecessor lineage. Both inherit tenant-root
and policy-first ordering; rollback discovers all policy keys and locks them sorted before subject
and object topology.

## Component modules

1. [Version and Supersession](01-Version-and-Supersession.md)
2. [Rollback](02-Rollback.md)

**Primary authority:** `genios_engine/contracts/learning.py`,
`genios_engine/feedback/orchestrator.py` and `genios_engine/feedback/store.py`.
