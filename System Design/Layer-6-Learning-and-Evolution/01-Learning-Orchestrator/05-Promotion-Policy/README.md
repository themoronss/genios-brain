# Promotion Policy

**Status:** Built

Builds and persists the only legal state path from observation to a held, reviewed, temporary or
published result. Evidence validation and enterprise permission stay separate, and no confidence
score can bypass consent or human review.

| Boundary | Current truth |
|---|---|
| Input | preflight-approved `LearningObject`, policy revision and evaluation time |
| State authority | closed `ALLOWED_LEARNING_TRANSITIONS` contract |
| Re-evaluation | later weekly runs may reconsider only identical Observed/Candidate objects; Candidate never regresses and later states never reopen |
| Review | Organization and Knowledge Suggestion by default; constrained durable targets by policy; Runtime is never reviewable |
| Decision audit | one append-only evaluation row per evaluated object/run with policy/time, prior/result state and final sink-level reason |
| Publication | versioned brains, TTL memory, metric row or suggestion queue according to target |
| Reversal | brain supersession and explicit human rollback with verified predecessor restoration |
| Authority | `feedback/governance.py::lifecycle_path`; `feedback/store.py::apply_path/publish`; orchestrator review/rollback |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
