# 4 · Preference Learning

**Status:** Partial

Proposes user or organization preference state only from repeated explicit structured key/value/scope facts.

| Boundary | Value |
|---|---|
| Input | explicit FeedbackFacts with preference key, value, scope and category |
| Output | Behavior or Organization LearningObject |
| Primary code | `feedback/units.py::preference_learning` |
| Honest gap | No free-text preference extraction is performed here; upstream must create trustworthy structured facts. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
