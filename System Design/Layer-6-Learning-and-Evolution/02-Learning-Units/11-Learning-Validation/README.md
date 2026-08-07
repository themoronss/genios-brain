# 11 · Learning Validation

**Status:** Built

Applies consent/lineage preflight and deterministic evidence quality checks to every proposal. It
returns a verdict; it does not emit a second LearningObject or publish anything.

| Boundary | Value |
|---|---|
| Input | immutable v2 LearningObject, pinned tenant policy and explicit evaluation/review time |
| Preflight | enabled/blocked policy, ACL, exact lineage, subject visibility and Runtime lease |
| Evidence | independent support, distinct days, confidence, noise, conflict, value and freshness |
| Output | Observed, Candidate, Validated or Rejected reason-coded result |
| Primary code | `feedback/governance.py::validate_learning` |
| Operations requirement | production cohorts should calibrate policy values through revisioned updates |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Evidence Validator | exact source/independence/trace and count contract plus preflight lineage |
| Confidence Validator | minimum confidence basis points |
| Conflict Resolver | rejects excessive conflict; it does not invent a winning claim |
| Noise Filter | maximum noise basis points |
| Promotion Validator | returns reasoned validation state before separate governance/lifecycle |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
