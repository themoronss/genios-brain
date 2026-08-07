# Layer 6 · Learning & Evolution

This folder documents product **Layer 6** and `genios_engine/feedback/`. The package has internal
import rank 7 only because it follows Layer 5.2 Delivery in the dependency DAG; **there is no
product Layer 7**. Its tree mirrors the Atlas:
**Learning Orchestrator → 11 Learning Units → Evolution Publisher → Promotion Lifecycle**.

> **Question:** What should the system safely change about itself from durable evidence?

## Canonical tree

```text
Layer-6-Learning-and-Evolution/
├── 00-Overview.md
├── STATUS.md
├── 01-Learning-Orchestrator/
│   ├── 01-Learning-Selector/ ... 07-Learning-Governance/
├── 02-Learning-Units/
│   ├── 01-Feedback-Learning/ ... 11-Learning-Validation/
├── 03-Evolution-Publisher/
│   ├── 01-Behavior-Brain-Publisher/
│   ├── 02-Adaptive-Brain-Publisher/
│   ├── 03-Organization-Brain-Publisher/
│   ├── 04-Runtime-Memory-Publisher/
│   └── 05-Learning-Metrics-Publisher/
├── 04-Promotion-Lifecycle/
├── 05-Contracts-and-Operations/
└── _reference/
```

There is deliberately **no Expert Brain publisher**. The closed contract has no `expert` target.

## Read order

1. [Overview](00-Overview.md)
2. [Status ledger](STATUS.md)
3. [Part A · Learning Orchestrator](01-Learning-Orchestrator/README.md)
4. [Part B · 11 Learning Units](02-Learning-Units/README.md)
5. [Part C · Evolution Publisher](03-Evolution-Publisher/README.md)
6. [Promotion Lifecycle](04-Promotion-Lifecycle/README.md)
7. [Contracts and Operations](05-Contracts-and-Operations/README.md)
8. [Atlas alignment](_reference/Atlas-Alignment.md),
   [closed loop](_reference/Integration-with-Layers-5-and-5.2.md),
   [scenarios](_reference/Learning-Scenarios.md) and [gaps/runbook](_reference/Bugs-Runbook-and-Gaps.md)

| Identity | Value |
|---|---|
| Product layer | Layer 6 |
| Internal import rank | 7 in `genios_engine/LAYERS.py` |
| Package | `genios_engine/feedback/` |
| Contract | `genios_engine/contracts/learning.py` |
| API | `genios_engine/api/learning_routes.py` |
| Migration | `migrations/0045_atlas_l6_learning.sql` |

[← System Design index](../README.md)
