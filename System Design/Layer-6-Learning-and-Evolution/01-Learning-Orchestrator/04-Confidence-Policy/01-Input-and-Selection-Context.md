# Input and selection context

Each `LearningEvidence` contains:

- total observations and distinct calendar days;
- positive and negative labelled counts;
- confidence, noise, conflict, stored freshness and business-value basis points;
- sorted unique source refs;
- sorted unique independent refs; and
- sorted unique source trace IDs.

`independent_observations` is derived from independent refs and can never exceed total
observations. Repeated rows from one card, execution or source group therefore cannot satisfy the
repetition gate by themselves.

`first_seen_at`, `last_seen_at` and `observed_at == last_seen_at` are part of the immutable v2
object. Stored freshness describes evidence at observation time; current freshness is recomputed
from `last_seen_at` and the explicit evaluation/review clock without changing object identity.
