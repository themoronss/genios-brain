# Edge cases and gaps

- A delivery freezes its `daily_budget`; later preference/config changes affect newly materialized work, not an already-auditable decision.
- Unknown provider outcomes intentionally retain capacity and may make the measured budget conservative.
- 0046 quota seeding is safe only under the mandatory quiescent cutover. An old worker that calls a
  provider after the baseline snapshot would make any database-only count incomplete.
- Correctness does not require Redis, but hot recipient/organization contention and transaction latency must be load-tested against the production PostgreSQL topology.
- Expired window rows have an index but no implemented retention/cleanup job. Operations must add and monitor that job.
- Timezone and daylight-saving behavior is implemented, but the supported production timezone set and clock discipline still need deployment checks.
- The rate limiter protects Delivery Engine interruptions; it cannot account for messages sent outside this ledger.
