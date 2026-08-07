# Policy and decision

For ordinary learning, default policy evaluates in this order:

1. fewer than 3 independent observations → `observed / repetition_pending`;
2. fewer than 2 distinct days → `candidate / distinct_days_pending`;
3. noise above 2,500 bp → rejected;
4. conflict above 2,500 bp → rejected;
5. confidence below 6,500 bp → candidate;
6. business value below 1,000 bp → rejected;
7. current freshness at zero → rejected; otherwise validated.

The common confidence function uses only labelled positive/negative facts and independent support:
agreement basis points × support basis points. Support is capped and neutral/open rows do not
increase it. Pattern Learning uses average upstream source confidence × independent support. All
math is integer and deterministic.

Explicit Runtime memory follows a separate one-shot validation path after preflight proves the
directive and TTL; permanence repetition thresholds do not apply to leased context.

Policy thresholds and current freshness are evaluated at the claimed run's frozen policy revision
and evaluation time; neither belongs to immutable evidence identity. Consequently an identical
Observed/Candidate proposal can be reconsidered in a later weekly run. A stricter repetition rule
cannot regress Candidate to Observed, but current preflight or rejection rules may still reject a
held object. The per-run evaluation ledger records the actual resulting state and reason.
