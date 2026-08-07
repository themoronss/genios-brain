# Shape, evidence and identity

A `learning.v2` LearningObject carries tenant, unit, closed target, subject, frozen proposed value,
LearningEvidence, first/last/observed times, trace id, visibility, lineage-complete flag, optional
subject principal, policy key, optional Runtime expiry, metadata and schema version. `observed_at`
equals `last_seen_at`; identity is content-addressed from this semantic envelope.

Evidence preserves observations, distinct days, positive/negative counts, confidence, noise,
conflict, freshness, business value, exact source references, independent-origin references and
source trace ids. Confidence uses labeled independent support: neutral/open rows and repeated rows
from one origin cannot manufacture certainty.

Stored freshness is fixed at the evidence observation and current freshness is evaluated later
from `last_seen_at`. Identical facts therefore produce the same LearningObject across scheduler
retries or later weekly runs even when the evaluation clock or policy revision changes. Those
lifecycle inputs deliberately do not enter evidence identity; their exact per-run decision belongs
to `learning_object_evaluations`.
