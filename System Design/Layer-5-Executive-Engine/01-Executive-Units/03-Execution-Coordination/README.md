# 2.5 · Execution Coordination

**Status:** Partial

Projects action state into ready, waiting, blocked and completed work and enforces dependency order during completion.

| Boundary | Value |
|---|---|
| Input | stored `ExecutionObject`, current action states, actor identity and explicit time |
| Output | `CoordinationSnapshot` / `CoordinatedAction` projection and an allow-or-reject completion decision |
| Primary code | `genios_engine/executive/coordination.py`, `execution_store.py` |
| Invariant | An action cannot complete before every dependency and cannot be completed by an unauthorized actor. |
| Honest gap | The Atlas multi-owner swimlane is only partial: dependencies are runtime-real, but actions are not yet allocated to different seats/agents with separate ladders. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
