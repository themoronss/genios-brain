# 2 · Execution Planning

**Status:** Built

Converts execution context and declared play steps into typed, dependency-aware actions with deadlines and autonomy boundaries.

| Boundary | Value |
|---|---|
| Input | `ExecutionContext`, declared play steps and explicit planning time |
| Output | ordered `PlannedAction` values, dependency waves, resource metadata and a stable plan hash |
| Primary code | `genios_engine/executive/planning.py` |
| Invariant | Action kind and autonomy are decided by fixed rules; read-only content cannot gain an external side effect. |
| Honest gap | Live capacity/resource allocation is not performed; availability is declared metadata and later ownership is seat-directory based. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
