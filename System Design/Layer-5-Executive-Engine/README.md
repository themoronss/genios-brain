# Layer 5 · Executive Engine

This is the live implementation map for `genios_engine/executive/`. It follows the Atlas hierarchy
physically: **layer → architectural part → unit → component module**. The folder tree is therefore
also the navigation model and the code-audit checklist.

> **Question:** How does a Layer 4 decision become an owned, timed, monitored commitment?

## Canonical tree

```text
Layer-5-Executive-Engine/
├── 00-Overview.md
├── STATUS.md
├── 01-Executive-Units/
│   ├── 01-Decision-Interpreter/
│   ├── 02-Execution-Planning/
│   ├── 03-Execution-Coordination/
│   ├── 04-Communication-Planning/
│   ├── 05-Execution-Validation/
│   ├── 06-Reminder/
│   ├── 07-Monitoring/
│   ├── 08-Escalation/
│   ├── 09-Execution-Tracking/
│   ├── 10-Feedback-Collection/
│   └── 11-Execution-Object-Builder/
├── 02-Execution-Lifecycle/
├── 03-Contracts-and-Operations/
└── _reference/
```

## Read order

1. [Overview](00-Overview.md) — boundary, owners and end-to-end flow.
2. [Status ledger](STATUS.md) — every Atlas unit and the evidence-backed verdict.
3. [Executive Units](01-Executive-Units/README.md) — the eleven runtime units.
4. [Execution Lifecycle](02-Execution-Lifecycle/README.md) — state machine, sweep and delivery handoff.
5. [Contracts and Operations](03-Contracts-and-Operations/README.md) — contract, storage, API, scheduler and tests.
6. [Atlas alignment](_reference/Atlas-Alignment.md) and [gaps/runbook](_reference/Bugs-Runbook-and-Gaps.md).

## Identity and boundary

| Item | Authority |
|---|---|
| Code package | `genios_engine/executive/` |
| Repository number | Layer 5 in `genios_engine/LAYERS.py` |
| Input | authoritative Layer 4 decision |
| Output | immutable `ExecutionObject` plus an audited commitment lifecycle |
| Downstream handoff | `genios_engine/deliver/executive_bridge.py` |
| Database schema | `migrations/0041_l5_execution.sql` |
| API | `genios_engine/api/executive_routes.py` |
| Import law | Layer 5 never imports `deliver/`; topology tests enforce it |

[← System Design index](../README.md)
