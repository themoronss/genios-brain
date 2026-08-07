# TTL and Expiry

Makes temporary memory temporary through contract validation, pre-persistence retention policy,
an inbox-backed idempotent command and a tenant-scoped database lifecycle.

## Component modules

1. [TTL Validation](01-TTL-Validation.md)
2. [Expiry Execution](02-Expiry-Execution.md)

**Primary authority:** `genios_engine/contracts/learning.py`,
`genios_engine/api/learning_routes.py`, `genios_engine/feedback/governance.py`,
`genios_engine/feedback/orchestrator.py` and `genios_engine/feedback/store.py`.
