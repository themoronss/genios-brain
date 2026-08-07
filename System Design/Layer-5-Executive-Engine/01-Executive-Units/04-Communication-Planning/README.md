# 3 · Communication Planning

**Status:** Built

Freezes the work-owner/audience seed, tone, presentation intent and backwards-compatible route
hints as part of the commitment. Layer 5.2 resolves the current recipient, concrete channel and
interruption decision at delivery time.

| Boundary | Value |
|---|---|
| Input | execution context, planned actions, band/confidence and an injected seat directory |
| Output | `Assignment`, `CommunicationPlan` and a frozen escalation ladder input |
| Primary code | `genios_engine/executive/assignment.py`, `communication.py` |
| Invariant | Layer 5 owns who must do the work; Layer 5.2 owns who receives the current delivery and how it travels, but may not silently reassign the commitment. |
| Honest gap | Live provider/destination availability is evaluated downstream. General agent/per-action allocation is not built. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
