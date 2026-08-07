# Input and selection context

The maintenance heartbeat supplies a timezone-aware run time. `_learning_orgs` includes every
tenant found in current learning policies, active temporary memories, the learning-event inbox or
active packs. This is broader than connector-enabled tenants so an expired lease cannot survive
because ingestion is off.

For each tenant, `run_learning` receives the graph/store, organization and evaluation time. Tests
may provide a frozen `LearningBatch`; production loads it from the same transaction that owns the
weekly claim and policy share lock.

The in-process scheduler's heartbeat interval is configured by `sync_interval_hours`. It need not
fire exactly at Monday midnight: every heartbeat derives the same Monday 00:00 UTC period key, so
the first successful attempt in that week is authoritative. Deployments may replace the loop with
an external worker only if it preserves the same frequent retention and weekly-claim semantics.
