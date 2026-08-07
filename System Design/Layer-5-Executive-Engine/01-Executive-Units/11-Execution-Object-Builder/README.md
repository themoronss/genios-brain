# 10 · Execution Object Builder

**Status:** Built

Composes the interpreted decision, action plan, ownership, communication and escalation data into one immutable, content-addressed commitment.

| Boundary | Value |
|---|---|
| Input | successful interpretation, planned actions, assignment, communication plan and escalation ladder |
| Output | `BuildResult` containing `ExecutionObject`, or an explicit refusal |
| Primary code | `genios_engine/executive/execution.py`, `contracts/execution.py` |
| Invariant | Identity hashes decision plus plan, deliberately excluding mutable routing; round-trip serialization must preserve the hash. |
| Honest gap | No known Atlas-core gap. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
