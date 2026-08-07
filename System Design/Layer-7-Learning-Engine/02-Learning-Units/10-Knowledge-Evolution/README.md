# 10 · Knowledge Evolution

**Status:** Partial

Creates a human-review suggestion when a capability/play has sustained poor grounded outcomes.

| Boundary | Value |
|---|---|
| Input | Outcome Analysis objects with at least eight labeled outcomes |
| Output | Knowledge Suggestion LearningObject with review-play reason and cohort |
| Primary code | `feedback/units.py::knowledge_evolution` |
| Honest gap | Suggestion/review state exists; automatic Git branch/PR/spec editing is intentionally not implemented. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Knowledge Drift | sustained low outcome rate over a grounded play cohort |
| Capability / Object / Playbook Suggestions | current builder emits `review_play`; richer suggestion types are not implemented |
| Version Suggestions | immutable suggestion + transition history; no Git version authoring |
| Human approval | owner-only review API; never an Expert publisher |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
