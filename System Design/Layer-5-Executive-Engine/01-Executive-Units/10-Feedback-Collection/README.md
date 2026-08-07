# 9 · Feedback Collection

**Status:** Built

Converts terminal execution truth into an immutable outcome label that Atlas Layer 6 can learn from without guessing.

| Boundary | Value |
|---|---|
| Input | execution state, action progress, observed business outcome, cancellation cause and attention history |
| Output | `ExecutionOutcome` persisted in `execution_outcomes` |
| Primary code | `genios_engine/executive/collect.py`, `execution_store.py` |
| Invariant | Unproven completion is neutral; silence and transport state are never fabricated into success. |
| Honest gap | Label quality is bounded by available business evidence and explicit human cancellation reasons. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
