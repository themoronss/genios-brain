[← Folder map](README.md)

# Architecture and Learning Orchestrator

The orchestrator owns sequencing, not analysis. `orchestrator.py` selects a 28-day input batch,
loads tenant policy, invokes the fixed unit plan, persists objects, applies validation/governance,
and hands permitted objects to `store.py::publish`.

| Atlas component | Live mechanism |
|---|---|
| Learning Selector | `load_batch`: chooses canonical feedback, outcomes, observations and delivery rows inside the window |
| Learning Planner | `ALL_ANALYSIS_UNITS` fixed canonical order; irrelevant units return no objects |
| Brain Resolver | each unit assigns a closed `BrainTarget` |
| Confidence Policy | integer evidence calculation + `validate_learning` |
| Promotion Policy | `lifecycle_path` + tenant `LearningPolicy` |
| Learning Scheduler | `run_maintenance_sweep` + `learning_runs(org, period_start)` claim |
| Governance Unit | `govern_learning`, then an audited state transition |

## Transaction boundary

One organization's run is one transaction. Claim, source read, object persistence, lifecycle,
publication and completion either commit together or roll back together. A retry after rollback
can claim again. A retry after commit receives the stored result and cannot double-publish.

Temporary-memory expiry runs before the weekly claim, so TTL enforcement is not delayed merely
because evolution already ran that week.

## Input authority

- `card_feedback_verdicts` supplies latest explicit canonical judgments. Passive impressions are
  excluded from learning labels.
- `execution_outcomes` supplies success, failure, progress, time and attention cost.
- `graph_observations` supplies normalized enterprise event repetition; the unit does not read raw
  email or ask a model what pattern exists.
- `delivery_outbox` supplies delivered/failed/open/suppressed state, attempts, deferrals and latency.

The orchestrator writes only code-Layer-7 tables. Lower layers consume dynamic state through data,
not by importing `feedback/`, preserving the repository layer DAG.
