# Learning Governance

**Status:** Built

Applies enterprise permission after evidence validation and before any publication.

| Boundary | Current truth |
|---|---|
| Input | validated LearningObject plus tenant enablement, blocked subjects/targets, review rules and TTL ceiling |
| Output | governed, human-review or rejected decision with reason |
| Authority | `feedback/governance.py::govern_learning`, store-loaded tenant policy |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
