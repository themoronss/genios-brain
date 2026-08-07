# Confidence Policy

**Status:** Built

Separates raw observation count from independent support, keeps neutral evidence from manufacturing
certainty, and evaluates configurable repetition, diversity, confidence, noise, conflict,
freshness and business value gates.

| Boundary | Current truth |
|---|---|
| Input | immutable `LearningEvidence`, first/last seen times and tenant policy snapshot |
| Evidence identity | exact sorted source refs, independent refs and trace IDs |
| Scoring | deterministic integer basis points; no floating inference at validation time |
| Freshness | recomputed as of evaluation/review time from `last_seen_at` over a 28-day decay window |
| Output | Observed, Candidate, Validated or Rejected reason-coded verdict |
| Authority | `feedback/units.py::_evidence`; `feedback/governance.py::validate_learning` |

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
