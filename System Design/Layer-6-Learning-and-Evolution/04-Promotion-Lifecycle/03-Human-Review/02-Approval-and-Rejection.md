# Approval and rejection

Approval does not trust the policy decision made when the queue row was created. Under the current
policy lock it re-runs preflight, evidence validation, time-relative freshness and governance. It
also refuses a stale dynamic-brain proposal when a newer evidence window is already active for the
same subject.

The lock order is tenant → discovered policy `FOR SHARE` → proposal `FOR UPDATE`/recheck. Only an
approved, revalidated proposal may then enter the publisher's subject advisory lock. This avoids
policy/object inversion while still closing review-versus-policy, publication and erasure races.

An eligible approval moves the object through promotion and, for dynamic brain targets,
publication. Rejection remains available even if learning was subsequently disabled and
terminates the proposal with actor/note audit. Knowledge Suggestion approval updates the pending
suggestion atomically; it still does not edit Expert Brain or repository code.

Organization approval/rejection is owner-only. Behavior/Adaptive and Knowledge review may be
delegated through the scoped review credential, but never beyond the object's ACL.
