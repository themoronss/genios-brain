# 11 · Learning Validation

**Status:** Built

Determines whether each proposal has enough repetition, diversity, confidence, freshness and value without excessive noise/conflict.

| Boundary | Value |
|---|---|
| Input | LearningObject evidence plus tenant/default LearningPolicy |
| Output | Observed, Candidate, Validated or Rejected result with stable reason |
| Primary code | `feedback/governance.py::validate_learning` |
| Honest gap | Policy thresholds require production calibration, but the enforcement path is complete. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Evidence Validator | observation/source-ref/count contract |
| Confidence Validator | minimum confidence basis points |
| Conflict Resolver | rejects excessive conflict; it does not invent a winning claim |
| Noise Filter | maximum noise basis points |
| Promotion Validator | returns reasoned validation state before governance/lifecycle |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
