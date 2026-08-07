# States and paths

States are observed, candidate, validated, governed, temporary, human_review, promoted, published,
rejected, expired, superseded and rolled_back. `ALLOWED_LEARNING_TRANSITIONS` is the closed edge
set used by the store.

Normal durable publication follows Observed → Candidate → Validated → Governed → Promoted →
Published. Runtime uses Temporary → Expired. Review targets pass through HumanReview.
