# 8 · Recommendation Learning

**Status:** Partial

Converts measured play effectiveness and attention cost into an Adaptive efficacy proposal.

| Boundary | Value |
|---|---|
| Input | Outcome Analysis LearningObjects |
| Output | Adaptive recommendation LearningObject per capability/play |
| Primary code | `feedback/units.py::recommendation_learning` |
| Honest gap | Proposal/publisher exist; no generic downstream selector currently changes recommendations from these entries. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
