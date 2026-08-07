# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Preflight first refuses disabled/blocked policy, incomplete/empty source lineage, invalid constrained
audience, non-org evidence for Organization, evidence invisible to a Behavior/Adaptive subject, or a
non-explicit/excessive Runtime lease. This runs before value persistence.

Default ordinary checks then require 3 **independent** observations, 2 distinct days, at least
6,500 confidence bp, no more than 2,500 noise bp, no more than 2,500 conflict bp, at least 1,000
business-value bp and nonzero current freshness. Freshness decays deterministically over 28 days
from `last_seen_at` and the explicit evaluation/review time.

## Evaluator

Low repetition remains Observed; insufficient days/confidence remains Candidate. Excessive noise or
conflict, inadequate business value, stale evidence and preflight failures reject with separate
reason codes. Valid explicit Runtime memory uses a one-shot Validated result because its TTL, not
permanence repetition, bounds retention.

Validation cannot promote or widen an ACL. Governance follows only after a Validated result.
