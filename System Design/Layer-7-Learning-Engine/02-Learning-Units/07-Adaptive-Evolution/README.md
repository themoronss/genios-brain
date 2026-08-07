# 7 · Adaptive Evolution

**Status:** Partial

Separates current operating preferences into Adaptive Brain proposals rather than stable behavior claims.

| Boundary | Value |
|---|---|
| Input | Preference objects in priority, notification, execution-preference or runtime-personalization categories |
| Output | Adaptive-target LearningObject |
| Primary code | `feedback/units.py::adaptive_evolution` |
| Honest gap | Generic Adaptive publication is durable/API-visible but not consumed by lower execution/reasoning runtime. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Adaptive Analyzer | closed current-operating category filter |
| Adaptive Confidence | inherited evidence plus Unit 11 policy validation |
| Preference Updater | versioned tenant+subject Adaptive entry |
| Adaptive Publisher | shared Evolution Publisher |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
