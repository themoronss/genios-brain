# Input and selection context

Governance consumes the complete v2 envelope: tenant, unit, target, subject, value, evidence,
first/last seen times, trace ID, source-derived visibility, lineage-complete flag, optional subject
principal, policy key and Runtime expiry.

The tenant policy supplies a monotonically increasing revision and:

- learning enabled/disabled;
- minimum independent observations, distinct days, confidence and business value;
- maximum noise and conflict;
- maximum temporary-memory TTL;
- human-review targets, with Runtime forbidden because a lease must publish/expire without a review
  hold;
- blocked targets and subject prefixes; and
- whether constrained-visibility durable learning requires review.

Defaults are explicit. `ensure_policy` creates a revisioned default row, and migration triggers
freeze each insert/update as an immutable policy snapshot. Runs and objects pin the revision they
used. Migration `0047` removes legacy Runtime-review configuration before the baseline snapshot;
the owner API and database constraint both reject its return. Review uses the current policy again
so revoked consent is effective before approval.

Policy locking is never the transaction root. A mutation first takes the tenant `orgs` row
`FOR SHARE`, then locks each required policy row before any LearningObject, Runtime memory or
tenant+brain+subject advisory lock. Reset/delete takes `orgs FOR UPDATE`, making erasure and child
mutation mutually exclusive without reversing child-to-parent foreign-key lock order.
