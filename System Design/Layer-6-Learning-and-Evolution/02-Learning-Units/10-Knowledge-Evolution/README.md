# 10 · Knowledge Evolution

**Status:** Built suggestion path

Creates a human-review-only `review_play` suggestion when a capability/play has sustained poor,
grounded outcomes. This is the complete automated Layer 6 boundary: it intentionally cannot publish
to or edit an Expert Brain/pack.

| Boundary | Value |
|---|---|
| Input | Outcome Analysis objects with at least eight labeled outcomes |
| Trigger | labeled success rate below 4,000 bp; neutral outcomes do not satisfy the floor |
| Output | Knowledge Suggestion LearningObject and pending review-queue record |
| Primary code | `feedback/units.py::knowledge_evolution` |
| External workflow | approved suggestion needs a human authoring/PR/spec process; this is deliberate governance |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Knowledge Drift | sustained low outcome rate over a grounded play cohort |
| Capability / Object / Playbook Suggestions | current builder emits `review_play`; richer suggestion types are not implemented |
| Version Suggestions | immutable suggestion + transition history; no Git version authoring |
| Human approval | scoped review API with ACL/current-policy revalidation; never an Expert publisher |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
