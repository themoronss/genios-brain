# 8 · Execution Tracking

**Status:** Built

Owns the mutable commitment state, action state, append-only history, timeline and progress views around an immutable `ExecutionObject`.

| Boundary | Value |
|---|---|
| Input | guarded transition/action commands, execution identity, actor and explicit time |
| Output | current state plus durable event/history/metrics projections |
| Primary code | `genios_engine/executive/lifecycle.py`, `execution_store.py`, `api/executive_routes.py` |
| Invariant | Only declared state-machine edges are legal; identity and historical events are never rewritten to make a transition appear clean. |
| Honest gap | Schema and fakes are tested; live PostgreSQL contention and operational load remain deployment proof. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| State Manager | `lifecycle.py` plus guarded store transitions |
| History | append-only `execution_events` |
| Timeline | ordered event/detail API projection |
| Progress Tracker | action states plus `monitor.py::ProgressReport` |
| Execution Metrics | progress, reminder/escalation counts and immutable outcome facts |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, planning and calculation](02-Analysis-Planning-and-Calculation.md)
3. [Evaluation, build, execution and output](03-Evaluation-Build-Execution-and-Output.md)

The files group adjacent Atlas pipeline boxes; they do not claim nonexistent runtime services.
