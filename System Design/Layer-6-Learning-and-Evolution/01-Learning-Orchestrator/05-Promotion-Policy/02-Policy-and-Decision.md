# Policy and decision

The normal validated path is:

`observed → candidate → validated → governed → promoted → published`.

Branches are explicit:

- insufficient repetition remains `observed`; insufficient days/confidence remains `candidate`;
- an identical later-week proposal may re-enter policy evaluation only from `observed` or
  `candidate`; Candidate never regresses to Observed, while review/published/later/terminal states
  never reopen;
- failed evidence or permission becomes `rejected`;
- Runtime becomes `temporary`, is published as a lease in the same governed operation and later
  moves only to `expired`; it cannot stop in `human_review`;
- configured human targets and constrained-visibility durable targets become `human_review`;
- approving a reviewed brain object revalidates current policy/ACL/freshness, moves it to
  `promoted`, then publishes it; and
- approving Knowledge Suggestion marks the suggestion approved/promoted but does not publish to a
  brain or edit an Expert pack.

Brain publication uses a per-tenant/brain/subject advisory lock. A material value, confidence or
ACL change creates the next version and supersedes the old active object. An exact no-op is
rejected. Rollback deactivates the bad version and may restore only the verified, visible,
still-allowed direct predecessor.

The owner API rejects Runtime in `require_human_targets`, and migration `0047` removes that legacy
setting before freezing the first policy snapshot. The database policy constraint prevents it from
being reintroduced outside the API.

Every new-object evaluation and eligible held-object re-evaluation appends one
`learning_object_evaluations` row for that claimed run. The row binds prior/result state and reason
to the run's exact policy key/revision and evaluation time; the immutable LearningObject is never
rewritten merely because policy or time changed. The recorded reason is the final outcome returned
by transition/publication—not merely the last policy step—so `published_to_dynamic_target`,
`no_material_change`, `metric_identity_conflict` and held/rejection reasons remain distinguishable.
