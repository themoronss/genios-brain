# 3 · Pattern Learning

**Status:** Partial

Finds repeated normalized enterprise-event pattern key plus kind across distinct days.

| Boundary | Value |
|---|---|
| Input | non-memory `EnterpriseFact` values |
| Output | Organization-target pattern LearningObject |
| Primary code | `feedback/units.py::pattern_learning` |
| Honest gap | Current grouping is intentionally simple; richer temporal sequences, multi-entity correlations and causal claims are absent. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
