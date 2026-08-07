[← Folder map](README.md)

# Atlas Layer 6 alignment

| Atlas requirement | Status | Code evidence |
|---|---|---|
| `DeliveryResult + Feedback + Enterprise Events` input | Implemented | `store.load_batch` reads delivery, canonical feedback, execution outcome and graph ledgers |
| Learning Selector + Planner | Implemented | `load_batch`, `ALL_ANALYSIS_UNITS`, `run_units` |
| Brain Resolver | Implemented | closed `BrainTarget` assigned by each unit |
| Confidence + Promotion Policy | Implemented | integer evidence + `LearningPolicy` + `lifecycle_path` |
| Scheduler | Implemented | maintenance wiring + `learning_runs` weekly claim |
| Governance Unit | Implemented | evidence checks separated from enterprise permission |
| 11 Learning Units | Implemented | 10 deterministic analyzers + Unit 11 Learning Validation |
| Full promotion path | Implemented | contract transition map + guarded SQL + transition ledger |
| Organization Brain | Publisher implemented; runtime consumption open | versioned `learned_brain_entries`; no lower-layer reader yet |
| Behavior Brain | Publisher implemented; runtime consumption open | versioned `learned_brain_entries`; no lower-layer reader yet |
| Adaptive Brain | Publisher implemented; runtime consumption open | versioned `learned_brain_entries`; no lower-layer reader yet |
| Runtime Context / temporary memory | Publisher + TTL implemented; runtime consumption open | explicit `temporary_memories` with authoritative PostgreSQL TTL; no lower-layer reader yet |
| Learning metrics | Implemented | `learning_metrics` |
| Behavior/Adaptive/Organization/Runtime/Metrics publishers | Implemented | `store.publish` and `_publish_brain` |
| No Expert Brain publisher | Enforced | no Expert enum target; Knowledge branch raises if publication is attempted |
| Knowledge suggestions + human review | Implemented | `knowledge_suggestions`, owner review endpoint, no pack/Git write |
| LLM restricted from operational learning | Enforced by implementation | units/governance contain no LLM dependency; all scoring/promotion is deterministic |
| Versioning and rollback | Implemented | active version uniqueness, supersession, rollback transition |
| PostgreSQL + Redis TTL | Partial | PostgreSQL authority implemented; Redis acceleration remains optional work |

## Completion interpretation

The Atlas **analysis, governance and publication safety contract is implemented**. Generic dynamic
brain and Runtime values are not yet consumed by lower runtime layers, so the broad learning loop
is not operationally closed beyond the older `rule_mutes`/bounded `rule_offsets` calibration path.
Remaining integration also includes optional Redis acceleration, richer typed feature extraction
and a human-owned Git PR workflow. PostgreSQL already enforces TTL, and the absence of automatic
Git mutation is the intended Expert Brain boundary.
