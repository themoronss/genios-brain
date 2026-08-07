# 9 · Performance Optimization

**Status:** Built

Measures Layer 5.2 channel transport reliability, attempts, deferrals, latency and append-only
engagement timestamps as of the evaluation clock. Queued/deferred/suppressed/cancelled/expired work
remains distinct, and only `failed` rows without a prior `delivered_at` become negative transport
evidence. A post-delivery ACCEPTED → FAILED execution outcome remains transport-delivered.

| Boundary | Value |
|---|---|
| Input | exact-execution `DeliveryFact` values grouped by channel and source ACL |
| Window inclusion | outbox created in-window **or** lifecycle event occurred in-window, always no later than evaluation time |
| As-of model | latest delivery event time plus attempts/engagement no later than evaluation time |
| Freshness | latest lifecycle clock counts for every state, including failed/deferred/suppressed/cancelled |
| Confidence | delivered positive; only pre-delivery failed negative; open/held/other states neutral |
| Output | Metrics LearningObject per channel/ACL cohort |
| Primary code | `feedback/units.py::performance_optimization` |
| Integration requirement | providers/clients must record complete lifecycle and engagement events |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Metrics Collector | bounded, as-of DeliveryFact cohort from outbox/events/attempts |
| Performance Analyzer | per-channel delivered/failed/open/deferred/suppressed/cancelled/expired classification |
| Threshold Monitor | validation/governance policy after proposal construction |
| Optimization Planner | not an automatic mutator; Metrics output informs governed future policy |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
