# 5 · Reminder

**Status:** Built

Decides whether an open, still-relevant commitment should be reminded now without creating fatigue.

| Boundary | Value |
|---|---|
| Input | current execution/action progress, deadline window, reminder history and explicit time |
| Output | a reminder decision, urgency rung and grounded reminder facts |
| Primary code | `genios_engine/executive/reminder.py`, `execution_store.py` |
| Invariant | A reminder is about unresolved business relevance, not elapsed calendar time alone. |
| Honest gap | No Redis acceleration and no cross-commitment digest batching; durable PostgreSQL due queries remain authoritative. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
