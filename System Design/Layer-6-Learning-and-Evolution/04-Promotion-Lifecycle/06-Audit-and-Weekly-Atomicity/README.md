# Audit and Weekly Atomicity

Makes repeated schedulers, policy/time decisions, held-object re-evaluation, malformed-input
refusal and partial failures explainable and reclaimable without retaining forbidden raw payloads.

## Component modules

1. [Transition Ledger](01-Transition-Ledger.md)
2. [Weekly Claim and Transaction](02-Weekly-Claim-and-Transaction.md)

**Primary authority:** `genios_engine/contracts/learning.py`,
`genios_engine/feedback/orchestrator.py`, `genios_engine/feedback/governance.py`,
`genios_engine/feedback/store.py` and `migrations/0047_l6_learning_hardening.sql`.
