# Human Review

Requires an authenticated, ACL-authorized decision before sensitive proposals can progress.
Scoped reviewers may act through `learning.review`; Organization changes remain owner-only.

Concurrency authority is explicit: tenant root, discovery-only object read, policy `FOR SHARE`,
then object `FOR UPDATE` and full recheck before any publication lock.

## Component modules

1. [Review Queue and API](01-Review-Queue-and-API.md)
2. [Approval and Rejection](02-Approval-and-Rejection.md)

**Primary authority:** `genios_engine/api/learning_routes.py`,
`genios_engine/feedback/orchestrator.py`, `genios_engine/feedback/governance.py` and
`genios_engine/feedback/store.py`.
