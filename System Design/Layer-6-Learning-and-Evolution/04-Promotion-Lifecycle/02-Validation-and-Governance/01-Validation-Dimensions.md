# Validation dimensions

Preflight runs before proposal-value persistence. It rejects disabled learning, blocked targets or
subject prefixes, incomplete lineage, missing source evidence, unusable ACLs, organization claims
derived from narrower-than-organization evidence, and user learning whose subject cannot view the
evidence. Runtime also receives its exact TTL/explicitness check here.

Validation then checks independent observations, distinct days, deterministic confidence, noise,
conflict, freshness and business value. Neutral/open rows do not increase confidence and duplicate
rows from one independence origin do not count as independent support. Repetition/confidence can
hold a candidate; excessive noise/conflict, zero current freshness or low value can reject.

Stored freshness describes the evidence at its last observation and therefore does not change the
content identity on a later retry. Current freshness is recomputed from `last_seen_at` and the
evaluation/review clock.

Explicit Runtime memory follows a separate TTL-safe one-observation rule.
