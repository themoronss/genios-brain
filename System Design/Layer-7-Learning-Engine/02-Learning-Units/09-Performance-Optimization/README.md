# 9 · Performance Optimization

**Status:** Built

Measures channel transport reliability, attempts, deferrals and latency without confusing open/held work with failure.

| Boundary | Value |
|---|---|
| Input | DeliveryFacts grouped by channel |
| Output | Metrics LearningObject per channel |
| Primary code | `feedback/units.py::performance_optimization` |
| Honest gap | Broader cross-surface interaction and execution attribution is an upstream analytics gap, not fabricated here. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Metrics Collector | bounded `DeliveryFact` cohort from the durable outbox |
| Performance Analyzer | per-channel delivered/failed/open classification |
| Threshold Monitor | validation/governance policy after proposal construction |
| Optimization Planner | not an automatic mutator; Metrics output informs governed future policy |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
