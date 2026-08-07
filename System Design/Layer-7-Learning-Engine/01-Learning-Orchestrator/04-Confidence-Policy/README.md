# Confidence Policy

**Status:** Built

Determines whether evidence is sufficiently repeated, diverse, fresh, valuable and internally consistent.

| Boundary | Current truth |
|---|---|
| Input | integer evidence counts, distinct days, confidence, noise, conflict, freshness and business value |
| Output | validated, held or rejected assessment used by lifecycle planning |
| Authority | `feedback/governance.py::validate_learning` and evidence contract |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
