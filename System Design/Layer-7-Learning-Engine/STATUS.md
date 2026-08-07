# Atlas Layer 6 implementation status

## Part A · Learning Orchestrator

| Atlas component | Status | Evidence | Remaining edge |
|---|---|---|---|
| Learning Selector | **Built** | `feedback/store.py::load_batch` | Input quality follows upstream fact structuring |
| Learning Planner | **Built** | `ALL_ANALYSIS_UNITS`, orchestrator | Fixed complete plan; units may return no candidate |
| Brain Resolver | **Built** | closed `BrainTarget` assigned by each unit | No Expert target exists |
| Confidence Policy | **Built** | integer evidence + `validate_learning` | Threshold tuning needs production evidence |
| Promotion Policy | **Built** | `lifecycle_path` | Organization/knowledge review remains human |
| Learning Scheduler | **Built** | weekly claim + `run_learning` | Live multi-replica/PostgreSQL proof remains |
| Learning Governance | **Built** | `govern_learning` + tenant policy | Policy rollout/ownership remains operational |

## Part B · 11 Learning Units

| # | Unit | Status | Current edge |
|---|---|---|---|
| 1 | Feedback Learning | **Built** | Canonical explicit feedback only; free-text structuring is upstream work |
| 2 | Outcome Analysis | **Built** | Evidence quality depends on Layer 5 outcome coverage |
| 3 | Pattern Learning | **Partial** | Repeated subject+kind patterns; richer temporal/entity correlations absent |
| 4 | Preference Learning | **Partial** | Structured explicit key/value/scope only |
| 5 | Temporary Memory | **Partial** | TTL persistence/API built; no Redis cache or lower runtime consumer |
| 6 | Behavior Evolution | **Partial** | Governed publisher built; generic Behavior Brain not consumed below |
| 7 | Adaptive Evolution | **Partial** | Governed publisher built; generic Adaptive Brain not consumed below |
| 8 | Recommendation Learning | **Partial** | Efficacy candidates publish; generic consumer/materializer absent |
| 9 | Performance Optimization | **Built** | Transport metrics built; broader interaction attribution incomplete upstream |
| 10 | Knowledge Evolution | **Partial** | Human-review suggestion built; no automatic Git/PR authoring |
| 11 | Learning Validation | **Built** | Threshold calibration remains an operational policy task |

## Part C · Evolution Publisher

| Target | Status | Durable result | Runtime consumption |
|---|---|---|---|
| Behavior Brain | **Partial** | versioned `learned_brain_entries` | no generic lower-layer reader |
| Adaptive Brain | **Partial** | versioned `learned_brain_entries` | no generic lower-layer reader |
| Organization Brain | **Partial** | review-gated versioned entry | no generic lower-layer reader |
| Runtime Memory | **Partial** | expiring `temporary_memories` | API-visible; no runtime reader/cache |
| Learning Metrics | **Built** | `learning_metrics` | durable measurement; not authority |
| Knowledge Suggestion | **Partial** | human-review proposal | no Git/PR workflow |
| Expert Brain | **Intentional boundary** | no publisher, no enum target | immutable by this layer |

## Honest completion statement

The governed proposal, validation, promotion and publication machinery is implemented. The product
does not yet have a fully closed generic adaptation loop because the new brain entries and Runtime
memory have no controlled lower-layer consumers. Only the older narrow calibration outputs
currently influence Reasoning behavior.
