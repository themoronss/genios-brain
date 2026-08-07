# Atlas Layer 6 · Learning & Evolution — live implementation map

This folder documents code package `genios_engine/feedback/`, which is **code Layer 7** because
the repository counts Delivery as Layer 6. In the Atlas this same product capability is
**Layer 6 · Learning & Evolution**. Package name is the stable identity; both numbers are shown
so implementation and product design cannot drift silently.

> **Question:** What should the system change about itself?

| Atlas contract | Live implementation |
|---|---|
| Input | canonical feedback + `execution_outcomes` + graph observations + delivery results |
| Core | 10 analysis units + Learning Validation + Governance |
| Output | immutable `LearningObject` → Organization / Behavior / Adaptive brains, Runtime TTL, Metrics, or human-review suggestion |
| Expert Brain | **Never edited. There is no Expert publisher.** |
| Runtime | weekly atomic scheduler run; explicit memories can enter immediately with a bounded TTL |

The Atlas publishers are live, governed and versioned. Generic Organization/Behavior/Adaptive
entries and Runtime memories do not yet have a lower-layer consumer; the existing narrow
`rule_mutes`/bounded `rule_offsets` calibration path is the learned state currently consumed by
Reasoning.

## Read in this order

| # | Document | Purpose |
|---|---|---|
| 00 | [Overview](00-Overview.md) | Whole layer, one sitting |
| 01 | [Judgment taxonomy](01-The-Judgment-Taxonomy.md) | Explicit label vs timing vs silence |
| 02 | [Precision and Wilson bounds](02-Precision-and-Wilson-Bounds.md) | Conservative rule calibration |
| 03 | [Lineage and weekly claim](03-Lineage-and-The-Weekly-Claim.md) | Replay identity and atomicity |
| 04 | [Mutes, nudges and ledger](04-Mutes-Nudges-and-The-Ledger.md) | Existing bounded calibration subsystem |
| 05 | [Gaps](05-Gaps.md) | Honest remaining limitations |
| 06 | [Architecture and orchestrator](06-Architecture-and-Orchestrator.md) | Selector → planner → policy → publisher |
| 07 | [The 11 learning units](07-The-11-Learning-Units.md) | Inputs, calculations and outputs per unit |
| 08 | [Validation and governance](08-Validation-and-Governance.md) | Promotion state machine and enterprise controls |
| 09 | [Brains and publishers](09-Brains-and-Publishers.md) | Versioning, TTL, suggestions and rollback |
| 10 | [Storage, API and scheduler](10-Storage-API-and-Scheduler.md) | Tables, endpoints and runtime wiring |
| 11 | [Atlas alignment](11-Atlas-Alignment.md) | Requirement-by-requirement evidence |
| 12 | [Integration with Layers 5 and 5.2](12-Integration-with-Layers-5-and-5.2.md) | Exact outcome, delivery and learned-state seams across the closed loop |

## Code map

| Concern | Authority |
|---|---|
| Cross-layer contract | `genios_engine/contracts/learning.py` |
| 10 analysis units | `genios_engine/feedback/units.py` |
| Unit 11 + tenant governance | `genios_engine/feedback/governance.py` |
| Persistence + evolution publisher | `genios_engine/feedback/store.py` |
| Selector/planner/scheduler orchestration | `genios_engine/feedback/orchestrator.py` |
| Existing rule calibration | `genios_engine/feedback/calibrate.py` |
| Tenant surface | `genios_engine/api/learning_routes.py` |
| Schema | `migrations/0045_atlas_l6_learning.sql` |
| Verification | `tests/test_learning_atlas.py`, `tests/test_learning_authority.py` |

[← System Design index](../README.md)
