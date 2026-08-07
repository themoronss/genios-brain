# Version and supersession

The caller already holds tenant root, relevant policy and proposal locks before the publisher takes
a transaction advisory lock for tenant+brain+subject. It then locks both the latest and active rows
and allocates `max(version)+1`. Version numbers therefore remain monotonic even after a rollback
leaves no active value. The database partial unique index still enforces one active row.

Version allocation and restoration lineage use different references after a prior rollback:
`max(history)+1` preserves monotonic numbering, while `supersedes_entry_id` points to the actual
active value this publication deactivates. A later rollback can therefore restore the real
predecessor instead of following an already rolled-back historical row.

The same locked read obtains the active value's source `last_seen_at`. If it is newer than the
candidate, publication fails closed; the pre-review freshness check is therefore repeated at the
actual serialization boundary.

If value, confidence and visibility are unchanged, publication terminates as `no_material_change`.
An ACL change is material and creates a new version. A real replacement deactivates the prior row
with ended reason `superseded`, transitions its LearningObject, and writes both
`supersedes_entry_id` and `supersedes_learning_id` lineage before activating the successor.

Metrics use their own bounded-period identity and are not dynamic-brain versions. Knowledge
Suggestion never enters this publisher.
