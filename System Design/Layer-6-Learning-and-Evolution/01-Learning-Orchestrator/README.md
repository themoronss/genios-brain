# Part A · Learning Orchestrator

**Implementation status:** Built. Deployment still has to apply migration `0047`, keep the
maintenance worker enabled (or replace it with an equivalent external worker), and populate the
durable input seams. Those are integration/operations requirements, not missing orchestrator
branches.

The orchestrator coordinates learning; it never performs a learning unit's analysis itself. Its
implemented flow is:

1. acquire the tenant `orgs` row `FOR SHARE`, then expire due Runtime memories in an independent
   committed retention transaction;
2. reacquire the tenant root, lock and snapshot policy, then claim the tenant's UTC-week run;
3. select a 28-day, as-of-time `LearningBatch` from immutable lower-layer records;
4. execute the ten analysis units in fixed order;
5. preflight ACL, lineage, consent and TTL before storing any proposed value;
6. persist a new immutable `LearningObject`, or lock an identical existing object and re-evaluate
   it only when its current state is Observed/Candidate;
7. apply Unit 11 and governance at this run's frozen policy/evaluation time, append the exact
   evaluation verdict, and publish or hold through legal `LearningState` transitions; and
8. commit the run summary atomically. A failed attempt rolls back all run work and records only a
   sanitized, retryable failure row.

Re-evaluation never rewrites evidence. Candidate is monotonic and cannot fall back to Observed;
objects already in review, publication, temporary or any terminal/later lifecycle state are
duplicate no-ops and cannot be reopened by the scheduler.

The lock hierarchy is load-bearing: mutation starts at tenant root; policy precedes object, memory
and subject advisory locks. Account reset/delete owns the conflicting `orgs FOR UPDATE` root, so it
cannot erase a tenant concurrently with Layer 6 recreating child state.

| Atlas subpart | Current implementation | Folder |
|---|---|---|
| Learning Selector | Exact-source, fail-closed batch construction | [01](01-Learning-Selector/README.md) |
| Learning Planner | Fixed ten-unit plan plus Unit 11 lifecycle validation | [02](02-Learning-Planner/README.md) |
| Brain Resolver | Closed brain and non-brain target vocabulary | [03](03-Brain-Resolver/README.md) |
| Confidence Policy | Independent-evidence and as-of freshness gates | [04](04-Confidence-Policy/README.md) |
| Promotion Policy | Audited state machine, review, publication and rollback | [05](05-Promotion-Policy/README.md) |
| Learning Scheduler | Replica-safe UTC-week claim plus mandatory retention | [06](06-Learning-Scheduler/README.md) |
| Learning Governance | Versioned consent, ACL and retention policy | [07](07-Learning-Governance/README.md) |

`BrainTarget` names the four Atlas brains only: Organization, Behavior, Adaptive and Runtime.
`LearningTarget` is the wider publication vocabulary and additionally contains `metrics` and
`knowledge_suggestion`. Metrics and suggestions are sinks, not brains. Runtime is a leased memory
surface that must publish to Temporary immediately and expire; API/database policy make a
human-review detour unrepresentable. Organization, Behavior and Adaptive are the durable versioned
learned brains. There is intentionally no Expert Brain publisher.

**Code authority:** `contracts/learning.py`, `feedback/orchestrator.py`, `feedback/store.py`,
`feedback/governance.py`, `feedback/units.py`, `api/learning_routes.py`, and migration `0047`.
