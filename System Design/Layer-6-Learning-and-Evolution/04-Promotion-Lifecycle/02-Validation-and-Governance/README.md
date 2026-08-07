# Validation and Governance

Keeps three questions separate: may this value be retained, does its evidence support the claim,
and may the resulting claim be promoted. Each answer has a closed reason code and the policy
revision used by the run/object is durably bound. For every actual new/held-object evaluation, the
separate evaluation ledger binds the final lifecycle/publisher reason to the exact run policy and
evaluation clock.

## Component modules

1. [Validation Dimensions](01-Validation-Dimensions.md)
2. [Governance Controls](02-Governance-Controls.md)

**Primary authority:** `genios_engine/contracts/learning.py`,
`genios_engine/feedback/governance.py` and `genios_engine/feedback/store.py`.
