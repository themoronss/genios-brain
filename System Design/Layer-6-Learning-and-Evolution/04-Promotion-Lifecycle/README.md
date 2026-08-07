# Part D · Promotion Lifecycle

The lifecycle wraps an immutable `learning.v2` proposal. Consent, retention, lineage and
visibility are checked before a value-bearing proposal is stored; accepted proposals then move
only through the closed state machine. Policy revision, actor, reason and publication lineage are
durable audit facts rather than request-time context.

| Subpart | Purpose |
|---|---|
| [State Machine](01-State-Machine/README.md) | Closed paths, terminals and audited predecessor restoration |
| [Validation and Governance](02-Validation-and-Governance/README.md) | Preflight retention/ACL gates, evidence validation and frozen policy authority |
| [Human Review](03-Human-Review/README.md) | ACL-scoped review, current-policy revalidation and owner-only organization changes |
| [TTL and Expiry](04-TTL-and-Expiry/README.md) | Exact retention ceiling and tenant-scoped forgetting |
| [Versioning, Supersession and Rollback](05-Versioning-Supersession-and-Rollback/README.md) | Serialized publication, append-only lineage and safe reversal |
| [Audit and Weekly Atomicity](06-Audit-and-Weekly-Atomicity/README.md) | Transition/rejection ledgers, reclaimable claims and transaction boundaries |

Runtime has one deliberate lifecycle exception: after validation/governance it must publish as a
Temporary lease and later expire. It can never branch to HumanReview; the owner API, migration
normalization and database constraint all fail closed on a policy that attempts that detour.

Observed/Candidate have a separate weekly revisit rule. An identical held object may be evaluated
again using the new claimed run's pinned policy and clock, with Candidate protected from regression.
Review, published and all other later/terminal states remain lifecycle-owned and cannot reopen.
`learning_object_evaluations` records each actual per-run verdict without mutating evidence.
