# Learning Planner

**Status:** Built

Runs the Atlas unit plan in a fixed, inspectable order. The planner receives a frozen batch; units
that lack relevant inputs return no proposal. It does not let an agent, model or request select an
arbitrary unit or destination.

| Boundary | Current truth |
|---|---|
| Input | one validated `LearningBatch` and its exact evaluation time |
| Plan | ten analysis/building units in the declared Atlas order |
| Unit 11 | shared `validate_learning` step applied to every proposal during lifecycle planning |
| Output | ordered immutable `LearningObject` proposals carrying their source `LearningUnit` |
| Authority | `feedback/units.py::ALL_ANALYSIS_UNITS`, `run_units`; `feedback/governance.py::lifecycle_path` |

Preview and execution use the same unit functions and lifecycle policy. Preview is read-only; the
claimed run persists and applies the planned path.

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
