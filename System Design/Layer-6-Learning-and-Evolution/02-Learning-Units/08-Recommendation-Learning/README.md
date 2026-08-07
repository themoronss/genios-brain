# 8 · Recommendation Learning

**Status:** Built

Converts grounded capability/play outcome measurement into an Adaptive recommendation-efficacy
proposal. It preserves successes, failures, neutral/unproven outcomes, progress and attention cost
rather than learning from delivery or click-through alone.

| Boundary | Value |
|---|---|
| Input | Outcome Analysis LearningObjects |
| Derivation | exact parent value/evidence/ACL; only target and subject namespace change |
| Output | Adaptive recommendation LearningObject per capability/play/ACL cohort |
| Primary code | `feedback/units.py::recommendation_learning` |
| Integration requirement | downstream selector must read the versioned Adaptive recommendation entry |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
