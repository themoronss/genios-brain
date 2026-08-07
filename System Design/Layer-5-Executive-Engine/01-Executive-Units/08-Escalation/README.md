# 7 · Escalation

**Status:** Built

Advances a frozen urgency-scaled escalation ladder and resolves the current target safely when an actionable commitment remains unmet.

| Boundary | Value |
|---|---|
| Input | execution age/deadline, escalation history, communication plan, current owner/reporting directory and guard result |
| Output | next `EscalationStep` or no action, with resolved recipient and reason |
| Primary code | `genios_engine/executive/escalation.py`, `assignment.py`, `execution_store.py` |
| Invariant | A ladder is frozen with the plan, but its recipient is resolved from current organization truth at send time. |
| Honest gap | Per-action ladders for independently assigned multi-owner work depend on the unfinished allocator. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
