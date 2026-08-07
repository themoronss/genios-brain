# Deduplication

**Engine status:** Built for logical enqueue and ledger mutations. End-to-end exactly-once delivery remains receiver-dependent.

Deduplication prevents repeated sweeps, event reprocessing, fallback and receipt retries from creating competing logical truth. It does not claim that every external provider can suppress a second physical request after an ambiguous acknowledgement.

| Input | Output | Authority |
|---|---|---|
| execution materialization, provider attempt or lifecycle receipt | one logical row, auditable physical attempts and idempotent events | migration 0046 constraints, orchestrator, outbox and tracker |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)
