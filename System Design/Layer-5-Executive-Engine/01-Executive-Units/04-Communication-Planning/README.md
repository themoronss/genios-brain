# 3 · Communication Planning

**Status:** Built

Resolves the effective owner and freezes audience, channel, interruption, tone and escalation intent as part of the commitment.

| Boundary | Value |
|---|---|
| Input | execution context, planned actions, band/confidence and an injected seat directory |
| Output | `Assignment`, `CommunicationPlan` and a frozen escalation ladder input |
| Primary code | `genios_engine/executive/assignment.py`, `communication.py` |
| Invariant | Layer 5 owns who and the attention promise; Atlas Layer 5.2 may adapt transport but may not silently reassign. |
| Honest gap | Live provider/destination availability is evaluated downstream. General agent/per-action allocation is not built. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
