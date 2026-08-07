# 2 · Outcome Analysis

**Status:** Built

Measures capability/play effectiveness, progress, time-to-close and attention cost from Layer 5 ground truth.

| Boundary | Value |
|---|---|
| Input | `OutcomeFact` values grouped by capability and play |
| Output | Metrics LearningObject per capability/play cohort |
| Primary code | `feedback/units.py::outcome_analysis` |
| Honest gap | Coverage depends on Layer 5 and upstream connectors recording real outcome evidence. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
