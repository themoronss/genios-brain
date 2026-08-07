# 3 · Pattern Learning

**Status:** Built baseline

Finds repeated normalized enterprise observations by pattern key and kind without claiming
causality or interpreting raw prose. The current Atlas baseline is a deterministic recurrence
detector; richer sequences/correlations can be added later as separately versioned models.

| Boundary | Value |
|---|---|
| Input | non-memory `EnterpriseFact` values grouped by key, kind and source ACL |
| Grounding | graph observation → exact graph source refs → source events, or structured inbox event |
| Confidence | average source confidence × independent source-group support |
| Output | Organization-target pattern LearningObject requiring review by default |
| Primary code | `feedback/units.py::pattern_learning` |
| Extension boundary | temporal sequences, multi-entity correlations and causal models are not fabricated by this baseline |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
