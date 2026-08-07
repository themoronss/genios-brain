# States and paths

States are observed, candidate, validated, governed, temporary, human_review, promoted, published,
rejected, expired, superseded and rolled_back. `ALLOWED_LEARNING_TRANSITIONS` is the closed edge
set used by the store.

Before Observed, `preflight_learning` checks consent, blocked targets/subjects, evidence lineage,
visibility and Runtime retention. A refused value is never persisted as a LearningObject; a
sanitized value-free audit projection goes to `learning_input_rejections`.

Normal durable publication follows Observed → Candidate → Validated → Governed → Promoted →
Published. Runtime follows Observed → Candidate → Validated → Governed → Temporary → Expired.
Runtime publication to the lease store occurs when Temporary is reached; it can never branch to
HumanReview. Reviewable durable targets pass through HumanReview before Promoted.
Repetition/confidence holds remain Observed or Candidate without pretending publication happened.

Observed and Candidate are the only scheduler-revisitable states. If a later claimed weekly run
reproduces the identical LearningObject, the orchestrator locks the stored row and applies current
validation/governance using that run's pinned policy revision and evaluation time. Candidate is a
monotonic floor: a later `repetition_pending` result cannot move it back to Observed. Current
preflight or validation may still legally reject a held object. The object payload and identity do
not change; the per-run decision is a separate evaluation record.

Published may move to Superseded or RolledBack. Superseded may return to Published only when an
audited rollback restores the exact predecessor of the bad active version; it is not a general
re-promotion route.
