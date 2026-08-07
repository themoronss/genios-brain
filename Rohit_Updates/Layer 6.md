# Atlas Layer 6 — Learning & Evolution Engine

**Last updated:** 7 August 2026

**Branch:** `antler-inception`

**Tests:** **17 focused Atlas learning tests**; full repository suite **1795 passed**.

**Status:** all 11 learning units, governance, publication, API and scheduler are implemented;
generic learned-state consumption by lower runtime layers is still an explicit integration gap.
**For the CTO:** Part 8 is the deployment and proof runbook.

**The one-line summary for a CTO:** GeniOS now turns explicit feedback, actual execution outcomes,
normalized enterprise events and delivery performance into immutable learning proposals, validates
and governs them, then publishes only permitted dynamic state—without giving an LLM or the runtime
permission to edit the Expert Brain.

Layer 5 answers **“did the commitment actually work?”**

Layer 5.2 answers **“did delivery work, and what attention did it cost?”**

Atlas Layer 6 answers **“what may the system safely learn from that evidence?”**

---

## Part 0 — Number translation

The Atlas calls this product capability **Layer 6**. The repository already uses code Layer 6 for
`deliver/`, so the implementation lives in:

| Product identity | Code identity |
|---|---|
| Atlas Layer 6 · Learning & Evolution | `genios_engine/feedback/` |
| Repository layer number | 7 |
| Boundary contract | `genios_engine/contracts/learning.py` |
| API | `genios_engine/api/learning_routes.py` under `/v1/learning` |
| Migration | `migrations/0045_atlas_l6_learning.sql` |
| System Design | `System Design/Layer-7-Learning-Engine/` |

The package name is the stable identity. We did not renumber `deliver/`, break the import ratchet or
create an ambiguous second package called Layer 6.

---

## Part 1 — What existed before, and what the Atlas required

The previous `feedback/` implementation was not empty. It already had a strong narrow calibration
loop:

| Existing capability | Why it remains valuable |
|---|---|
| One current canonical human verdict per card | Revisions are explicit; impressions are not labels |
| Exact pack/capability/rule lineage | A judgment cannot train a different rule version |
| Wilson lower bounds | Small cohorts cannot claim false precision |
| `rule_mutes` | Persistently poor rules can be silenced with auditability |
| Bounded `lvl3_config.rule_offsets` | Weekly ±5 and total ±15 adjustment, honoring pins |
| Weekly database claim | Process retries and replicas cannot calibrate twice |

That subsystem answers **“is this exact rule still precise?”** The Atlas asks a broader question:
what recurring behavior, preferences, outcomes, delivery performance and knowledge drift may be
learned across the product?

The missing pieces were:

- a generic immutable LearningObject;
- explicit Learning Selector, Planner, Brain Resolver and Confidence/Promotion policy;
- all 11 named learning units;
- separate validation and enterprise governance;
- the full promotion lifecycle and transition audit;
- Organization, Behavior and Adaptive publishers;
- expiring Runtime memory;
- delivery/outcome metrics;
- human-review-only Knowledge Evolution;
- owner APIs, preview, rollback and scheduler wiring.

Those structural pieces now exist. The remaining distinction is important: the new generic brain
rows are published and API-visible, but lower runtime layers do not consume them yet. The older
`rule_mutes`/`rule_offsets` calibration path is still the only learned state that currently changes
Reasoning behavior.

---

## Part 2 — The architecture now implemented

```text
28-day durable input window
    → Learning Selector
    → fixed 10-analysis-unit plan
    → immutable LearningObjects
    → Unit 11 Learning Validation
    → tenant Governance
    → audited promotion lifecycle
    → versioned brain / TTL memory / metric / review suggestion
```

| Atlas component | Current implementation | Authority |
|---|---|---|
| Learning Selector | `feedback/store.py::load_batch` | Selects only durable tenant-scoped facts in the bounded window |
| Learning Planner | `ALL_ANALYSIS_UNITS` | Fixed canonical order; inapplicable units return no object |
| Brain Resolver | Each unit assigns a closed `BrainTarget` | No caller/model chooses the destination |
| Confidence Policy | Integer evidence + `validate_learning` | Counts, days, confidence, noise, conflict, freshness and value |
| Promotion Policy | `lifecycle_path` | Builds only legal state transitions |
| Governance Unit | `govern_learning` | Applies enablement, blocked subjects and human-review rules after validation |
| Learning Scheduler | `run_learning` + `learning_runs` claim | At most one atomic run per tenant per UTC week |
| Evolution Publisher | `feedback/store.py::publish` | Writes only the closed set of dynamic targets |

The orchestrator does not learn. It coordinates pure units and persists their decisions. One
tenant run is one database transaction: claim, inputs, objects, transitions, publication and
completion commit together or roll back together.

---

## Part 3 — The immutable output contract

Every unit emits a `LearningObject`, not a direct brain mutation.

| Field group | Purpose |
|---|---|
| Identity | tenant, unit, target, subject and schema version |
| Proposed value | deep-frozen semantic payload |
| Evidence | observations, distinct days, positive/negative counts, confidence, noise, conflict, freshness, business value and source refs |
| Time | explicit observed time; expiry only for Runtime memory |
| Policy/metadata | policy key and grounded context |

The object is content-addressed, round-trip verified and immutable. Its lifecycle is stored
separately so review, promotion, supersession and rollback never rewrite the proposal or its
evidence.

`BrainTarget` is a closed enum:

```text
organization · behavior · adaptive · runtime · metrics · knowledge_suggestion
```

There is deliberately no `expert` value. Knowledge Evolution cannot accidentally reach an Expert
publisher because the contract has no vocabulary for that operation.

---

## Part 4 — The 11 learning units

| # | Unit | Reads/calculates | Output |
|---|---|---|---|
| 1 | Feedback Learning | Latest explicit canonical card verdicts; positive, negative and neutral remain distinct | Metrics |
| 2 | Outcome Analysis | Layer 5 outcomes, progress, close time, reminders and escalations | Effectiveness + attention-cost metrics |
| 3 | Pattern Learning | Repeated normalized graph `subject + kind` across distinct days | Organization candidate |
| 4 | Preference Learning | Explicit structured preference key/value/scope only | Behavior or Organization candidate |
| 5 | Temporary Memory | Explicit memory directive with mandatory future expiry | Runtime TTL object |
| 6 | Behavior Evolution | Stable communication, decision, meeting, execution or relationship behavior | Behavior candidate |
| 7 | Adaptive Evolution | Current priority, notification, execution or runtime personalization | Adaptive candidate |
| 8 | Recommendation Learning | Per capability/play result and attention cost | Adaptive efficacy candidate |
| 9 | Performance Optimization | Delivery success/failure, attempts, deferrals and latency | Metrics |
| 10 | Knowledge Evolution | At least 8 labelled outcomes and sustained success below 40% | Human-review play suggestion |
| 11 | Learning Validation | Repetition, days, confidence, noise, conflict, freshness, value and TTL | Hold, reject or validate |

All calculations after fact construction use deterministic integer arithmetic. A future Atlas-
allowed LLM may structure free text **before** a `FeedbackFact` exists; it may not score evidence,
choose a target, validate, promote or publish.

### Outcome truth from Layer 5

| Layer 5 label | Learning interpretation |
|---|---|
| `succeeded` | Positive |
| `expired_untouched`, `expired_in_progress`, `cancelled_by_human` | Negative |
| `completed_unproven`, `cancelled_by_world`, `cancelled_by_system` | Neutral/unproven |

`completed_unproven` is never relabeled as success just because all action boxes were ticked. It
remains visible so a play that produces activity but not evidence can be identified as busywork.

### Delivery truth from Layer 5.2

Performance Optimization reads durable outbox status, attempts, deferrals, channel and clocks.
Queued, deferred, suppressed and cancelled work is not fabricated into a transport failure. Only
actual `failed_terminal` adapter exhaustion counts against transport reliability.

---

## Part 5 — Validation, governance and the promotion lifecycle

Validation answers **“does the evidence support this?”** Governance answers **“may this tenant
retain or publish it?”** High confidence never overrides enterprise policy.

Default policy:

| Control | Default |
|---|---|
| Minimum observations | 3 |
| Minimum distinct days | 2 |
| Minimum confidence | 6500 bp |
| Maximum noise | 2500 bp |
| Maximum conflict | 2500 bp |
| Minimum business value | 1000 bp |
| Maximum temporary TTL | 720 hours |
| Human review | Knowledge Suggestion and Organization Brain |

State machine:

```text
Observed → Candidate → Validated → Governed
                                  ├→ Temporary → Expired
                                  ├→ HumanReview → Promoted
                                  ├→ Promoted → Published
                                  └→ Rejected
Published → Superseded | RolledBack
```

Every arrow is defined in the contract, rechecked by guarded SQL and appended to
`learning_transitions` with actor, reason, detail and time.

Runtime memory is the narrow one-observation exception: it must be explicit, target only Runtime,
carry a future expiry and stay below the tenant ceiling. It cannot become permanent. Expiry is
PostgreSQL-authoritative and runs before the weekly learning claim.

---

## Part 6 — Publishers, versioning and the real integration boundary

| Target | Durable result | Current runtime effect |
|---|---|---|
| Organization | versioned `learned_brain_entries` | Published/API-visible; lower-layer consumer not built |
| Behavior | versioned `learned_brain_entries` | Published/API-visible; lower-layer consumer not built |
| Adaptive | versioned `learned_brain_entries` | Published/API-visible; lower-layer consumer not built |
| Runtime | expiring `temporary_memories` | Stored/API-visible; Context/Reasoning consumer not built |
| Metrics | bounded `learning_metrics` | Durable measurement; no decision authority |
| Knowledge Suggestion | `knowledge_suggestions` at HumanReview | Human handoff only; approval does not edit Expert Brain |

Only one active version may exist per `(tenant, brain, subject)`. Publishing a newer value locks
and supersedes the old version. Rollback deactivates the selected version and records a transition;
it does not silently reactivate older behavior.

This is the key CTO integration call:

- **Closed today:** exact-rule calibration writes `rule_mutes` and bounded
  `tenant_packs.lvl3_config.rule_offsets`; Reasoning reads both as data.
- **Not closed yet:** generic Organization/Behavior/Adaptive/Runtime output needs typed,
  allowlisted lower-layer materializers. A generic JSON read would bypass target scope, lineage,
  policy and TTL, so it should not be added casually.

---

## Part 7 — Storage, APIs and scheduler

Migration `0045_atlas_l6_learning.sql` creates eight tenant-cascading tables:

```text
learning_policies · learning_runs · learning_objects · learning_transitions
learned_brain_entries · temporary_memories · knowledge_suggestions · learning_metrics
```

API surface:

| Endpoint | Purpose |
|---|---|
| `GET /v1/learning/overview` | State, active-brain, review and memory counts |
| `GET /v1/learning/objects` | Filterable learning/evidence history |
| `GET /v1/learning/brains` | Active values or version history; never Expert |
| `GET /v1/learning/suggestions` | Knowledge review queue |
| `GET /v1/learning/memories` | Active TTL context or history |
| `GET /v1/learning/preview` | Read-only exact proposed path under current policy |
| `POST /v1/learning/memories` | Owner creates explicit leased memory |
| `POST /v1/learning/objects/{id}/review` | Owner approves/rejects HumanReview |
| `POST /v1/learning/objects/{id}/rollback` | Owner deactivates a published dynamic value |
| `GET/PUT /v1/learning/policy` | Read/replace tenant controls |

The existing maintenance heartbeat runs distribution, exact-lineage calibration, then broad Atlas
learning. It selects active Executive/connection tenants. Each tenant failure is isolated. The
database claim—not process memory—prevents double publication during the same UTC week.

---

## Part 8 — CTO deployment and proof runbook

### Step 1 — Apply migrations through 0045

```bash
.venv/bin/python -m genios_engine.platform.migrate
```

Verify:

```sql
select filename from schema_migrations
 where filename in (
   '0041_l5_execution.sql',
   '0042_l6_delivery_gate.sql',
   '0044_l52_atlas_delivery.sql',
   '0045_atlas_l6_learning.sql'
 ) order by filename;  -- 4 rows

\d learning_objects
\d learning_transitions
\d learned_brain_entries
\d temporary_memories
```

No new environment variable or worker is required. The existing database and scheduler settings
drive the pass.

### Step 2 — Preview before allowing publication

```bash
curl -s -H "Authorization: Bearer $OWNER_TOKEN" \
  https://<host>/v1/learning/preview | jq
```

Inspect each object's unit, target, confidence and proposed state path. Weak repetition should end
at Observed/Candidate. Organization and Knowledge targets should end at HumanReview under the
default policy.

### Step 3 — Prove the input seams

For one non-production tenant, confirm the 28-day window contains:

```sql
select label, count(*) from execution_outcomes where org_id='<org>' group by 1;
select channel, status, count(*) from delivery_outbox where org_id='<org>' group by 1,2;
select count(*) from card_feedback_verdicts where org_id='<org>';
select kind, count(*) from graph_observations where org_id='<org>' and status='active' group by 1;
```

If a source is empty, its unit should emit nothing—not invent evidence.

### Step 4 — Observe the claimed run

After the maintenance heartbeat:

```sql
select period_start,status,objects_observed,objects_published,objects_held,objects_rejected
from learning_runs where org_id='<org>' order by period_start desc limit 2;

select unit_name,target_brain,current_state,count(*)
from learning_objects where org_id='<org>' group by 1,2,3 order by 1,2,3;
```

A second heartbeat in the same week should return the stored run result and publish nothing twice.

### Step 5 — Prove safety boundaries

1. Confirm `/v1/learning/brains` only accepts Organization, Behavior and Adaptive.
2. Review a Knowledge suggestion and verify the response contains
   `expert_brain_changed: false`.
3. Create a short Runtime memory, wait for expiry/heartbeat and verify `expired_at` plus the
   `temporary → expired` transition.
4. Roll back one test dynamic brain value and verify history remains while the active row ends.
5. Search the deployment diff: there must be no Expert publisher and no automatic pack/Git edit.

### Step 6 — Production monitoring

Watch:

- `learning_runs.status != 'completed'`;
- rejected objects by reason code;
- HumanReview queue age;
- temporary memories past `expires_at` with no `expired_at`;
- multiple active versions for the same brain/subject (the unique index should prevent this);
- unexpected growth in neutral `completed_unproven` outcomes;
- delivery performance split by actual adapter failure vs policy/attention holds.

---

## Part 9 — What is still left

| Priority | Gap | Required integration |
|---|---|---|
| P0 before claiming full closed-loop adaptation | Generic brain + Runtime consumption | Define typed, policy-scoped materializers for Context/Reasoning/Executive/Delivery; preserve lineage and expiry |
| P0 deployment proof | Live PostgreSQL and real input smoke | Apply 0045, run one tenant, inspect claims/transitions/publications |
| P1 runtime optimization | Redis acceleration | Disposable cache only; PostgreSQL remains TTL authority |
| P1 input quality | Free-text preference structuring | Allowed extractor before deterministic facts, with provenance and review |
| P1 knowledge workflow | Git/PR authoring | Human-owned workflow consumes approved suggestions; engine never edits Expert Brain |
| P2 richer patterns | Typed upstream features | Calendar/time/sequence features instead of semantic guessing from raw prose |
| P2 operations | Tenant cadence and deliberate version restore | Add only with durable period identity and explicit actor intent |

---

## Appendix — the 60-second CTO version

**What changed:** the old calibration-only learner is now surrounded by the Atlas architecture:
four durable input seams, 11 deterministic units, immutable LearningObjects, validation,
governance, a complete audited lifecycle, versioned dynamic publishers, TTL memory, metrics,
human-only knowledge suggestions, APIs, rollback and a weekly atomic scheduler run.

**What is safest about it:** silence is not evidence, one occurrence is not permanent learning,
strong confidence cannot bypass enterprise policy, and the contract has no Expert Brain target.

**What is actually closed:** Layer 5 outcomes and Layer 5.2 delivery facts now enter learning; the
existing rule calibration path writes state that Reasoning already consumes.

**What is not closed yet:** the new generic Organization/Behavior/Adaptive values and Runtime
memory are durable and governed but do not yet influence lower runtime layers. That consumer layer
is the next real integration—not Redis and not more dashboards.

**First production proof:** migrate through 0045, preview one tenant, let the weekly claim run,
inspect every state transition, approve one safe review object, expire one memory and verify that
no Expert Brain bytes changed.
