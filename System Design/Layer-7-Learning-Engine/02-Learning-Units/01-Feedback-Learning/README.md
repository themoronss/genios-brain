# 1 · Feedback Learning

**Status:** Built

Learns counted response metrics from explicit canonical feedback while keeping positive, negative and neutral separate.

| Boundary | Value |
|---|---|
| Input | explicit `FeedbackFact` values grouped by subject key |
| Output | Metrics-target LearningObject with accepted/rejected/neutral counts |
| Primary code | `feedback/units.py::feedback_learning` |
| Honest gap | Silence is ignored, not labeled. Raw free text needs a trusted upstream structurer before it can become a fact. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Feedback Collector | `store.load_batch` canonical feedback query |
| Parser | frozen `FeedbackFact` contract; no raw-prose parser in this unit |
| Categorizer | explicit action sets for positive/negative/neutral |
| Confidence | deterministic evidence/count basis-point calculation |
| Object Builder | immutable Metrics-target `LearningObject` |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
