# 2 · Outcome Analysis

**Status:** Built

Measures capability/play effectiveness, progress, time-to-close and attention cost from grounded
Layer 5 execution outcomes. Neutral terminal labels remain visible but never count as success,
failure or confidence support.

| Boundary | Value |
|---|---|
| Input | `OutcomeFact` values grouped by capability, play and identical source ACL |
| Grounding | outcome joins exact execution ID, decision hash, capability and play |
| Labels | success, failure and neutral sets are closed and separate |
| Output | Metrics LearningObject per capability/play/ACL cohort |
| Primary code | `feedback/units.py::outcome_analysis` |
| Integration requirement | Layer 5/connectors must close real outcomes instead of treating clicks or deliveries as efficacy |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
