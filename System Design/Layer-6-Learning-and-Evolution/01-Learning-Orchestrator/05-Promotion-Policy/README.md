# Promotion Policy

**Status:** Built

Builds the only legal promotion path for a validated, governed proposal.

| Boundary | Current truth |
|---|---|
| Input | LearningObject target, validation result and tenant governance decision |
| Output | ordered legal `LearningState` transitions |
| Authority | `feedback/governance.py::lifecycle_path`, learning state contract |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
