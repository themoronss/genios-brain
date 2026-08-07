# Review queue and API

Knowledge proposals enter `knowledge_suggestions`; all human-review LearningObjects remain
queryable by state only to principals allowed by the carried visibility envelope. The review
endpoint requires `learning.review`; an Organization proposal additionally requires owner
authority. Knowledge review also locks and verifies the matching suggestion is still pending.

Review first takes tenant `orgs FOR SHARE`. It performs a no-lock discovery read only to learn the
immutable policy key, locks that policy `FOR SHARE`, then reads the LearningObject `FOR UPDATE` and
rechecks policy identity, payload/hash, ACL, state and actor. Discovery grants no authority.
Unauthorized constrained objects fail closed as not found rather than revealing their existence.
