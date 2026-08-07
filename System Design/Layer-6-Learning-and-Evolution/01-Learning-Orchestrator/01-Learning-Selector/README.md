# Learning Selector

**Status:** Built

Loads one bounded, tenant-scoped durable evidence batch from feedback, execution, delivery and enterprise-event sources.

| Boundary | Current truth |
|---|---|
| Input | organization, explicit evaluation time and the configured observation window |
| Output | a canonical `LearningBatch` consumed by the fixed analysis plan |
| Authority | `feedback/store.py::load_batch` |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
