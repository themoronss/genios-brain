# Layer 6 implementation status

**Code status:** internal engine built and locally verified.

**Production status:** external consumers, producers, policy sign-off and deployment proof pending.

**Verification:** 50/50 canonical Layer 6 tests; 144/144 expanded cross-seam tests; 1,896
full-repository tests; 138/138 migration statements parsed. One unrelated Starlette/httpx
deprecation warning remains.

“Built” below means the named Layer 6 component exists, is wired and has local ratchets. It does
not rename an external integration as engine code.

## Part A · Learning Orchestrator

| Atlas component | Internal status | Evidence | External/operational edge |
|---|---|---|---|
| Learning Selector | **Built** | bounded fail-closed `feedback/store.py::load_batch` plus inbox | real receipt/event producer coverage |
| Learning Planner | **Built** | canonical `ALL_ANALYSIS_UNITS` order | none inside Layer 6 |
| Brain Resolver | **Built** | units choose a closed `LearningTarget`; four-value `BrainTarget` | consumer contracts for four brains |
| Confidence Policy | **Built** | integer independent evidence + current-freshness validation | production threshold calibration/sign-off |
| Promotion Policy | **Built** | legal lifecycle path, held-object re-evaluation, review and restorative rollback | reviewer operations/SLO |
| Learning Scheduler | **Built** | tenant-root → policy → child-lock order, weekly DB claim, pinned evaluation ledger and reclaimable failure | populated PostgreSQL erasure/contention proof |
| Learning Governance | **Built** | pre-persistence consent/ACL/lineage/TTL checks and pinned policy revision | tenant policy/privacy ownership |

## Part B · 11 Learning Units

| # | Unit | Internal status | Exact boundary |
|---|---|---|---|
| 1 | Feedback Learning | **Built** | terminal dashboard judgments atomically version canonical feedback; `wrong:bad_timing` is timing/neutral; snooze/requeue stay non-verdict events |
| 2 | Outcome Analysis | **Built** | expands automatically only when Layer 5 produces more typed outcomes |
| 3 | Pattern Learning | **Built** | current typed repeated subject/kind behavior; richer temporal/entity features need a producer contract |
| 4 | Preference Learning | **Built** | explicit structured preference only; user scope is capped to a resolved private subject ACL; organization scope is owner-authorized |
| 5 | Temporary Memory | **Built** | inbox, immediate temporary publication, PostgreSQL TTL/expiry and API+DB no-review rule built; runtime consumer/cache external |
| 6 | Behavior Evolution | **Built** | governed proposal/publication built; lower-layer Behavior reader external |
| 7 | Adaptive Evolution | **Built** | governed proposal/publication built; lower-layer Adaptive reader external |
| 8 | Recommendation Learning | **Built** | efficacy calculation/publication built; Adaptive consumer external |
| 9 | Performance Optimization | **Built** | real attempts/receipts plus latest lifecycle clock; only pre-delivery `failed` is transport-negative, while post-delivery failure remains delivered |
| 10 | Knowledge Evolution | **Built** | human-review suggestion is the completed Layer 6 boundary; human-owned Git/PR workflow external |
| 11 | Learning Validation | **Built** | independent support, days, confidence, noise, conflict, freshness, value and TTL |

## Part C · Evolution Publisher

| Publisher seam | Internal status | Durable result | External consumption |
|---|---|---|---|
| Behavior Brain | **Built** | advisory-locked monotonic `learned_brain_entries` | typed lower-layer reader pending |
| Adaptive Brain | **Built** | same version/ACL/supersession/rollback rules | typed lower-layer reader pending |
| Organization Brain | **Built** | human-gated versioned entry | typed lower-layer reader pending |
| Runtime Memory | **Built** | bounded `temporary_memories`, durable expiry | typed TTL reader; optional Redis cache pending |
| Learning Metrics | **Built** | ACL-cohorted `learning_metrics` | telemetry/observability integration; never decision authority |
| Knowledge Suggestion | **Built to layer boundary** | locked human-review proposal | human-owned Git/PR workflow pending |
| Expert Brain | **Forbidden boundary** | no enum, publisher, API or automatic edit path | human-controlled pack lifecycle only |

## Part D · Promotion lifecycle

| Capability | Status | Evidence |
|---|---|---|
| Immutable proposal and verified rehydration | **Built** | `learning.v2`, stable hash/ID and payload-projection checks |
| Validation before governance | **Built** | Unit 11 plus pinned current freshness |
| Held-object re-evaluation | **Built** | only Observed/Candidate can be reconsidered under the claimed run's current policy/time; Candidate never regresses |
| Governance before retention/publication | **Built** | preflight rejection ledger and versioned policy snapshots |
| Human review | **Built** | scoped visibility; Organization owner authority; stale-policy/value checks |
| Version/supersession | **Built** | consistent advisory-lock order and `max(history)+1` |
| Expiry/forget | **Built** | separately committed, tenant-scoped PostgreSQL expiry |
| Rollback | **Built** | exact safe predecessor restoration, otherwise rollback-to-empty |
| Mutation lock topology | **Built** | `orgs FOR SHARE` root; policy before object/memory/advisory; reset/delete uses `orgs FOR UPDATE` |

## Part E · Contracts and operations

| Surface | Status | Remaining proof |
|---|---|---|
| `LearningObject` v2 and visibility/trace envelope | **Built** | production migration validation |
| Policy, evaluation and rejection ledgers | **Built** | per-run policy/time verdicts plus retention/alert operations |
| Structured inbox and direct memory | **Built** | approved general event producers |
| Read/preview/review/rollback/policy APIs | **Built** | production auth/traffic smoke |
| Calibration compatibility | **Built** | same consent gate; existing Layer 4 consumption remains closed |
| LLM policy | **Built as boundary** | optional extractor implementation may be added; no model decision authority |

## Completion statement

The Layer 6 implementation itself is no longer partial: every named orchestrator component, all 11
units, governance/lifecycle and every allowed publisher seam exist and are locally verified. The
**product-wide adaptive loop remains integration-incomplete** until Organization, Behavior,
Adaptive and Runtime state have reviewed typed lower-layer consumers. Production claims additionally
require applying 0046→0047 to populated PostgreSQL, exercising concurrent workers and real producers,
including reset/delete versus learning/feedback mutation contention, and operating
policy/privacy/review/observability. The detailed owner handoff is in
[`Rohit_Updates/Layer 6.md`](../../Rohit_Updates/Layer%206.md).
