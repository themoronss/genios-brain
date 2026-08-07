# Governance controls

Tenant policy may disable learning, block complete targets or subject prefixes, require human
review for specified targets, require review for constrained visibility, and bound Runtime TTL.
Default human-review targets include Organization and Knowledge Suggestion. Organization learning
also requires organization/public evidence; confidence cannot broaden an ACL.

Runtime is not a reviewable target. The owner API rejects it in `require_human_targets`, the
database CHECK forbids it, and migration `0047` removes legacy occurrences before freezing the
initial revision. A valid explicit Runtime value must enter the temporary lease store immediately
and later expire; review delay would violate that retention contract.

An organization-scoped preference is accepted only when its canonical feedback revision carries
the server-frozen `organization_authorized` bit written from owner authentication. Caller-provided
preference JSON cannot grant that authority.

A user-scoped preference is capped separately: its derived ACL is always private to the one
resolved subject. If the source ACL excludes that subject or resolution is ambiguous/missing,
lineage becomes incomplete and preflight rejects the value. Behavior and Adaptive derivations
inherit the same cap without widening.

Migration 0047 gives every policy an increasing revision and writes its full snapshot to immutable
`learning_policy_revisions`. Runs and LearningObjects reference the exact revision used. Policy
reads that govern a run, review or rollback use a shared lock; policy updates serialize on the
current row and increment the revision.

Turning learning off prevents new run claims, calibration mutations and value-bearing proposal
persistence. It does not disable mandatory expiry of already-leased memory.

High confidence never overrides governance.
