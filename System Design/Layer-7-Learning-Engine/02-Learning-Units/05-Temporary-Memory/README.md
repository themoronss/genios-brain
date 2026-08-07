# 5 · Temporary Memory

**Status:** Partial

Turns an explicit memory directive into leased Runtime context that must expire.

| Boundary | Value |
|---|---|
| Input | EnterpriseFact with `explicit_memory=true`, value and future expires_at |
| Output | Runtime LearningObject with one-observation explicit evidence |
| Primary code | `feedback/units.py::temporary_memory`, store/API |
| Honest gap | PostgreSQL TTL publication/API are built; Redis cache and lower runtime consumption are absent. |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
