# 4 · Execution Validation

**Status:** Built

Revalidates live authority, subject state, outcome evidence, ownership and clock immediately before every outbound moment.

| Boundary | Value |
|---|---|
| Input | `GuardInput` plus current facts retrieved through the store/injected authority sources |
| Output | one of `PROCEED`, `COMPLETE`, `CANCEL`, `EXPIRE`, `REROUTE`, or `SUPPRESS` with grounded reason |
| Primary code | `genios_engine/executive/execution_guard.py` |
| Invariant | Queue-time validity is never enough; a stale reminder or escalation must not escape because it was once correct. |
| Honest gap | Correctness depends on freshness and coverage of the live facts supplied by lower layers. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
