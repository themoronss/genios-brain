# 5 · Temporary Memory

**Status:** Built

Turns only an explicit, owner-authenticated memory directive into private, leased Runtime context.
Source-stable idempotency, bounded value shape, maximum TTL preflight and committed expiry are built.

| Boundary | Value |
|---|---|
| Input | explicit `EnterpriseFact` with structured value and future aware expiry |
| API identity | tenant + authenticated actor + caller source ref; retries are idempotent |
| ACL | private to resolved owner principal, with explicit derivation |
| Validation | one-shot Runtime exception only after explicit/lineage/TTL preflight; API and DB forbid human-review policy |
| Lifecycle | governed temporary lease is published immediately, then only expires |
| Output | Runtime LearningObject and `temporary_memories` lease |
| Primary code | `feedback/units.py::temporary_memory`; `/v1/learning/memories`; store expiry |
| Integration requirement | runtime reader/cache may consume active leases; PostgreSQL remains expiry authority |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
