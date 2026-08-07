# Learning Planner

**Status:** Built

Schedules the complete canonical analysis-unit sequence for each claimed tenant run.

| Boundary | Current truth |
|---|---|
| Input | LearningBatch, tenant policy and explicit run time |
| Output | ordered LearningObject candidates with source unit identity |
| Authority | `feedback/orchestrator.py`, `feedback/units.py::ALL_ANALYSIS_UNITS` |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
