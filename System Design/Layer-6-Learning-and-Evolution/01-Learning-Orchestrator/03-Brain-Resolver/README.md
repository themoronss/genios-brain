# Brain Resolver

**Status:** Built

Assigns every proposal to one permitted dynamic destination based on the unit and proposal semantics.

| Boundary | Current truth |
|---|---|
| Input | validated unit-specific subject and proposed value |
| Output | a LearningObject with a closed `BrainTarget` |
| Authority | closed `BrainTarget` in `contracts/learning.py`; unit builders |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
