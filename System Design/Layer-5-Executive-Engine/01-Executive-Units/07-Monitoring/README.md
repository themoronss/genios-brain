# 6 · Monitoring

**Status:** Built

Observes action progress and business evidence, detects stalls, and distinguishes activity from a proven outcome.

| Boundary | Value |
|---|---|
| Input | stored execution/actions/events/outcomes plus current observation time |
| Output | `ProgressReport`, blocking action and lifecycle recommendation |
| Primary code | `genios_engine/executive/monitor.py` |
| Invariant | Checked boxes are not automatically business success; `completed_unproven` remains a first-class state. |
| Honest gap | The unit cannot prove events that upstream capture/context never records. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
