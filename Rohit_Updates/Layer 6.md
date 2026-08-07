# Layer 6 — Learning & Evolution Engine

**Last updated:** 8 August 2026

**Branch:** `antler-inception`

**Product identity:** Layer 6; implementation package `genios_engine/feedback/`; import rank 7

**Verification:** 50/50 canonical three-file Layer 6 tests, 144/144 expanded cross-seam tests and
1,896 full-repository tests passed locally with one unrelated Starlette/httpx deprecation warning

**Migrations:** `0045_atlas_l6_learning.sql` + additive hardening migration
`0047_l6_learning_hardening.sql`

## Current verdict for the CTO

The **internal Layer 6 engine is implemented and locally verified** against the Atlas and Theory II:
durable inputs, exact lineage, the Learning Orchestrator, all 11 named units, immutable
`LearningObject` v2, deterministic validation, versioned tenant policy, consent and visibility
preflight, audited lifecycle, five publisher seams, expiry, review, rollback, APIs, scheduler and
erasure behavior are present.

The latest closed semantics are also explicit: personal preferences can only become private learned
state for one ACL-resolved subject; Runtime leases can never wait in review; terminal dashboard
judgments atomically version the canonical feedback ledger; `wrong:bad_timing` remains canonical but
neutral for quality; snooze/requeue stay outside the verdict ledger; delivery freshness follows the
latest lifecycle event even when no receipt exists; and only a failure before first delivery is
transport-negative. Identical held objects are now safely re-evaluated under a later claimed run's
current pinned policy/time: only Observed/Candidate are eligible, Candidate never regresses, later
lifecycle states never reopen, and every actual decision enters an append-only per-run ledger.
That ledger stores the final transition/publisher outcome—not merely the last planned policy edge—
so publish success, no-material-change and metric identity conflicts remain distinguishable.

The final concurrency contract is also closed in code. Every Layer 6 mutation begins with tenant
`orgs FOR SHARE`; account reset/delete owns `orgs FOR UPDATE`. Policy locks precede object, memory
and subject advisory locks. Review discovers then locks policy/object and rechecks; rollback locks
all discovered policy keys sorted before subject/object topology. Dashboard and intelligence
feedback writers use tenant → graph → card before writing audit/verdict state.

This does **not** mean production adaptation is already closed. The engine can safely produce and
publish learned state, but four typed lower-layer consumers, real upstream receipt/event producers,
production PostgreSQL migration/concurrency proof and a human-owned knowledge PR workflow still
need deployment or product integration. Those are listed precisely in Part 12; they are not hidden
inside a generic “future work” statement.

**One-line architecture:** Layer 6 learns from outcomes rather than clicks, records proposals before
changing state, lets governance override confidence, expires temporary memory, and can never edit
the Expert Brain.

System Design: [Layer overview](../System%20Design/Layer-6-Learning-and-Evolution/README.md) ·
[component status](../System%20Design/Layer-6-Learning-and-Evolution/STATUS.md) ·
[orchestrator](../System%20Design/Layer-6-Learning-and-Evolution/01-Learning-Orchestrator/README.md) ·
[11 units](../System%20Design/Layer-6-Learning-and-Evolution/02-Learning-Units/README.md) ·
[publishers](../System%20Design/Layer-6-Learning-and-Evolution/03-Evolution-Publisher/README.md) ·
[lifecycle](../System%20Design/Layer-6-Learning-and-Evolution/04-Promotion-Lifecycle/README.md) ·
[contracts and operations](../System%20Design/Layer-6-Learning-and-Evolution/05-Contracts-and-Operations/README.md)

---

## Part 0 — Layer identity and boundary

There is no product Layer 7. Layer 5.2 is Delivery and Layer 6 is Learning & Evolution. The value
`7` attached to `feedback/` in the dependency topology is only an import rank.

| Concern | Current authority |
|---|---|
| Product layer | Layer 6 · Learning & Evolution |
| Package | `genios_engine/feedback/` |
| Boundary contract | `genios_engine/contracts/learning.py` |
| HTTP surface | `genios_engine/api/learning_routes.py` under `/v1/learning` |
| Baseline schema | `migrations/0045_atlas_l6_learning.sql` |
| Hardening schema | `migrations/0047_l6_learning_hardening.sql` |
| Maintenance wiring | `genios_engine/api/routes.py` |
| System Design | `System Design/Layer-6-Learning-and-Evolution/` |

Layer 6 may observe durable lower-layer data and publish controlled state as data. Lower layers must
not import `feedback/`; a future consumer must read a typed snapshot through a topology-safe seam.
The existing narrow calibration path already follows this rule by writing `rule_mutes` and bounded
`tenant_packs.lvl3_config.rule_offsets`, which Layer 4 reads as data.

---

## Part 1 — Planned requirement and the implemented shape

The Atlas names seven orchestrator components, eleven Learning Units and five publisher seams. The
implementation preserves those distinctions:

```text
DeliveryResult + explicit Feedback + execution Outcomes + normalized Enterprise Events
                              ↓
                     Learning Selector
                              ↓
                      Learning Planner
                              ↓
              ten deterministic analysis units
                              ↓
                  immutable LearningObject v2
                              ↓
        Unit 11 Validation → Governance → Promotion Policy
                              ↓
       dynamic brain / TTL memory / metric / human suggestion
```

The orchestrator coordinates; it does not invent a learning. The units calculate; they do not
write mutable brain state. The publisher writes only after validation and governance. An LLM has no
authority in scoring, validation, target selection, promotion, publication or rollback.

| Atlas orchestrator component | Implemented authority |
|---|---|
| Learning Selector | `feedback/store.py::load_batch` |
| Learning Planner | `ALL_ANALYSIS_UNITS` in canonical order |
| Brain Resolver | Closed target selected inside each unit |
| Confidence Policy | Integer evidence plus `validate_learning` |
| Promotion Policy | `lifecycle_path` and guarded transitions |
| Learning Scheduler | `run_learning`, weekly database claim and platform heartbeat |
| Learning Governance | Versioned `LearningPolicy`, preflight and `govern_learning` |

---

## Part 2 — Input truth, lineage and rejection behavior

Layer 6 reads a bounded 28-day cohort. Every accepted fact is tenant-scoped, time-bounded and tied
to independently verifiable source identity. Missing lineage is not silently converted into
organization-visible evidence.

| Input seam | Exact current behavior |
|---|---|
| Explicit card feedback | Reads the current canonical verdict and frozen revision; terminal dashboard `run_play` / `do_it_myself` / `wrong` atomically version it; `wrong:bad_timing` is timing/neutral for learning; dashboard requeue and dashboard/extension snooze remain non-verdict lifecycle/timing audit; actor and subject principal stay separate; organization preferences require server-recorded owner authorization |
| Layer 5 outcomes | Reconstructs the durable outcome/commitment history and preserves succeeded, negative and neutral/unproven labels |
| Layer 5.2 delivery | Includes outbox rows created in-window or having an in-window lifecycle event; reconstructs lifecycle/attempts as of evaluation time, verifies exact persisted `ExecutionObject` identity/hash, and uses receipt plus latest lifecycle clocks—including failed/deferred/suppressed/cancelled—for freshness |
| Enterprise events | Requires `graph_source_refs → source_events` lineage and inherits the narrowest source visibility |
| Explicit memory/events | Uses the idempotent `learning_event_inbox` with source reference, trace, visibility, independence key and lease |

If a row is malformed, cross-tenant, hash-inconsistent, lacks exact source lineage or carries an
invalid visibility envelope, that row is isolated. A sanitized `learning_input_rejections` entry
records source identity/hash and a reason code without retaining the forbidden raw value. One bad
optional input therefore cannot poison the rest of a tenant run.

Important semantic rules:

- `completed_unproven` is neutral, never fabricated into success.
- Suppressed, deferred, cancelled and queued delivery work is not a provider failure.
- Only `status=failed` with no prior `delivered_at` is transport-negative; ACCEPTED → FAILED after
  delivery remains transport-delivered and its execution/business failure belongs to outcomes.
- A view, ignore, accept or execute signal exists only when its durable clock exists.
- Dashboard requeue and dashboard/extension snooze remain audit/lifecycle facts; only terminal
  judgments enter the canonical feedback verdict/revision cohort. `wrong:bad_timing` is one such
  versioned judgment, but Feedback Learning treats it as timing/neutral rather than negative quality.
- Multiple database rows originating from one execution/source do not become multiple independent
  observations.
- Missing or partial ACL lineage becomes private and incomplete, then fails preflight where the
  target requires stronger authority.
- Every user-scoped preference is capped to `private + [resolved subject]`; unresolved subjects or
  source ACLs that exclude them are rejected, and Behavior/Adaptive preserve the cap.

---

## Part 3 — The orchestrator transaction model

One normal learning pass performs this sequence:

1. Take tenant `orgs FOR SHARE`, then expire due Runtime memories in a separately committed
   tenant-scoped transaction. A later analysis failure cannot resurrect an expired lease.
2. Reacquire tenant root, load/lock the current policy and freeze its exact revision for the run.
3. If tenant learning consent is disabled, stop after expiry. Do not claim a run and do not retain
   new proposals.
4. Claim the tenant/week in PostgreSQL. A completed week is idempotent; a failed week is reclaimable
   with a bounded attempt counter and sanitized error class.
5. Load and verify the bounded input cohort.
6. Run the ten analysis units in fixed canonical order.
7. Execute privacy/consent/lineage/ACL/target/TTL preflight **before proposal persistence**.
8. Persist each new accepted immutable object; if the identical object already exists, lock it and
   continue only when its current state is Observed/Candidate.
9. Recalculate current freshness and run Unit 11 under this run's frozen policy/evaluation time.
   Candidate is a monotonic floor and never regresses to Observed.
10. Apply the legal lifecycle path and publish, queue review, hold or reject deterministically.
    Review, published, temporary and every other later/terminal duplicate is a no-op and cannot
    reopen; the run counts it as `objects_unchanged`.
11. Append one evaluation row with run, policy key/revision, evaluation time, final prior/result
    state, `object_inserted` and the exact sink-level reason from `apply_path_result` in the same
    transaction.
12. Complete the run atomically with counts. A claimed-run failure is recorded only in a fresh
    transaction after the failed transaction has rolled back.

The database claim, not process memory, is the multi-replica authority. The scheduler enumerates
tenants from learning policies, active memories, structured inbox rows and active packs, so a tenant
does not disappear from retention merely because it currently has no active connector.

The transaction-wide order is tenant → policy → LearningObject/memory/subject advisory. The failed
run audit reacquires tenant then policy and does not recreate child authority if erasure already
deleted the organization. Account reset/delete uses the incompatible tenant `FOR UPDATE` root.

---

## Part 4 — `LearningObject` v2 contract

Every unit emits a content-addressed, round-trip-verified proposal. Lifecycle columns are separate,
so state transitions never rewrite its evidence or semantic identity.

| Contract group | v2 contents |
|---|---|
| Identity | schema version, tenant, unit, target, subject, semantic hash and stable learning ID |
| Proposed value | Canonical deep-frozen finite JSON |
| Evidence | observations, independent refs, distinct days, positive/negative counts, confidence, noise, conflict, freshness, business value, source refs and source trace IDs |
| Time | first seen, last seen/observed and Runtime-only expiry |
| Access | explicit `visibility {scope, principals, derived_from}`, lineage-complete flag and optional subject principal |
| Policy | policy key on the object; exact policy revision pinned alongside persistence |
| Audit | end-to-end learning trace plus immutable transition history |

`learning.v1` remains readable and hash-compatible for stored history. New proposals use
`learning.v2`. Migration 0047 projects the security- and decision-relevant v2 fields into columns
and adds database checks that those projections match the immutable payload.

The type distinction is deliberate:

```text
BrainTarget    = organization | behavior | adaptive | runtime
LearningTarget = BrainTarget + metrics + knowledge_suggestion
```

Metrics and knowledge suggestions are artifacts, not brains. There is no `expert` target in either
enum, publisher dispatch or API filter.

---

## Part 5 — All 11 Learning Units

| # | Unit | Evidence and result |
|---|---|---|
| 1 | Feedback Learning | Positive, negative, timing and neutral metrics from versioned terminal judgments; `wrong:bad_timing` is canonical timing/neutral, while snooze/requeue and silence are not verdict labels |
| 2 | Outcome Analysis | Business outcomes, progress, close time, reminders and escalations; ACL-cohorted metrics |
| 3 | Pattern Learning | Repeated normalized subject/kind patterns over independent sources and distinct days; Organization candidate |
| 4 | Preference Learning | Explicit structured key/value/category/scope only; deterministic conflict; user output is private to one ACL-resolved subject, organization output requires owner authority |
| 5 | Temporary Memory | Explicit directive only, Runtime target only, mandatory future expiry and no human-review branch |
| 6 | Behavior Evolution | Stable communication, decision, meeting, execution or relationship candidate preserving the parent subject ACL cap |
| 7 | Adaptive Evolution | Current priority, notification, execution or runtime personalization candidate preserving the parent subject ACL cap |
| 8 | Recommendation Learning | Capability/play success and attention-cost efficacy; Adaptive candidate |
| 9 | Performance Optimization | Attempts, deferrals, latency, receipts and latest lifecycle freshness; pre-delivery failure only is transport-negative, while post-delivery execution failure remains delivered; metrics only |
| 10 | Knowledge Evolution | Sustained poor labelled outcomes create a human-review suggestion; never an Expert write |
| 11 | Learning Validation | Repetition, independent evidence, days, confidence, noise, conflict, current freshness, value and TTL checks |

Pattern and preference units are functionally present for the currently available typed inputs.
Richer sequence, calendar and multi-entity features are an **upstream producer enhancement**, not a
missing unit or permission to infer from raw prose.

All scores are integer basis points. Neutral observations do not inflate confidence. Semantic
object identity uses the source-observation time; retry/evaluation wall clocks cannot manufacture a
new proposal ID.

---

## Part 6 — Validation, governance and enterprise safety

Validation asks **“does the evidence support this proposal?”** Governance asks **“may this tenant
retain or publish it?”** Governance can always narrow or refuse a high-confidence proposal.

Default policy controls include:

| Control | Default posture |
|---|---|
| Minimum support | 3 independent observations across 2 distinct days |
| Confidence/noise/conflict/value | Integer thresholds; all must pass |
| Temporary memory | Explicit only, bounded by tenant maximum TTL |
| Runtime review | Forbidden by owner API and database policy; valid leases publish temporary immediately |
| Organization target | Human review by default |
| Knowledge suggestion | Human review is mandatory and cannot be removed from policy |
| Constrained visibility | Human review by default |
| Target/subject blocks | Tenant can block targets and subject prefixes before persistence |

Migration 0047 turns the current policy into a revisioned authority. Every insert/update records an
immutable JSON snapshot, every run/object points to the exact revision, revisions cannot be updated
or directly deleted while the tenant exists, and normal workspace reset preserves consent/policy.
Only full tenant erasure cascades policy history.

Preflight rejects before proposal storage when consent is disabled, the target/subject is blocked,
lineage is incomplete, a user preference cannot resolve one source-authorized subject, an
Organization proposal is not backed by organization-visible facts, an organization preference lacks
owner authority, or a Runtime lease is missing/invalid/outside the policy ceiling. Runtime in a
human-review target policy is rejected before it can create a review-held lease.

---

## Part 7 — Lifecycle, publishers and rollback

```text
Observed → Candidate → Validated → Governed
                                  ├→ Temporary → Expired
                                  ├→ HumanReview → Promoted → Published
                                  ├→ Promoted → Published
                                  └→ Rejected
Published → Superseded | RolledBack
Superseded → Published       only when an exact predecessor is safely restored by rollback
```

Every transition is append-only with actor, reason, detail and time; the current-state update is
guarded against races.

Policy/evaluation time are lifecycle inputs, not LearningObject identity. When identical evidence
returns in a later week, only an Observed/Candidate row is re-evaluated. Candidate cannot fall back
to Observed; every later state is skipped. `learning_object_evaluations` records each actual
new/held-object decision separately, so reproducibility does not require mutating the proposal. Its
reason is the final publisher/lifecycle result, including `published_to_dynamic_target`,
`no_material_change` or `metric_identity_conflict`, rather than a generic last policy label.

| Publisher seam | Durable result | Safety behavior |
|---|---|---|
| Organization Brain | Versioned `learned_brain_entries` | Human review default; one active version per tenant/brain/subject |
| Behavior Brain | Versioned `learned_brain_entries` | Advisory-locked monotonic versioning and exact ACL preservation |
| Adaptive Brain | Versioned `learned_brain_entries` | Same no-op, supersession and lineage rules |
| Runtime Memory | `temporary_memories` | Immediate temporary publication, no review branch, PostgreSQL-authoritative lease and tenant-scoped expiry |
| Learning Metrics | `learning_metrics` | Measurement only; identity collision is rejected, never falsely reported as published |
| Knowledge Suggestion | `knowledge_suggestions` | Stops at review; approval records the handoff and still reports `expert_brain_changed: false` |

Publisher locking is acquired in one consistent order. A materially new dynamic value gets
`max(history)+1`, while its restoration link points to the actual active value it supersedes. This
distinction preserves monotonic history and correct rollback after an earlier rollback. A
byte-identical value is rejected as `no_material_change` rather than creating version noise.
Inside the same subject lock, a proposal older than the active value is rejected, closing the race
between human review and a concurrent newer publication.

Review uses tenant root → discovery-only object read → policy `FOR SHARE` → object `FOR UPDATE` and
full recheck before publisher locking. Rollback uses tenant root → discovery-only publication/
predecessor reads → all policy rows in lexical order → subject advisory → current/predecessor object
and entry locks, then rechecks topology. Discovery data never authorizes a mutation.

Rollback is now restorative and safe: it locks the subject, deactivates the selected active value,
then restores the exact predecessor only when that predecessor is verified, visible to the actor,
compatible with current consent/policy and not superseded by a newer value. Otherwise it rolls back
to an empty active slot. History remains intact in both cases.

---

## Part 8 — API and human authority

| Endpoint | Scope / purpose |
|---|---|
| `GET /v1/learning/overview` | `learning.read`; ACL-filtered counts |
| `GET /v1/learning/objects` | `learning.read`; SQL visibility filter before `LIMIT` |
| `GET /v1/learning/brains` | `learning.read`; active/history view, no Expert vocabulary |
| `GET /v1/learning/suggestions` | `learning.read`; visible review queue |
| `GET /v1/learning/memories` | `learning.read`; active/history leased memory |
| `GET /v1/learning/preview` | `learning.read`; deterministic read-only path under current policy |
| `POST /v1/learning/memories` | authenticated explicit memory; bounded canonical JSON and idempotency key |
| `POST /v1/learning/objects/{id}/review` | `learning.review`; current policy/ACL/state rechecked under lock |
| `POST /v1/learning/objects/{id}/rollback` | `learning.rollback`; current version/ACL/policy rechecked under lock |
| `GET/PUT /v1/learning/policy` | owner policy read/update; locked monotonic revision |

Owners have full tenant learning authority. Scoped principals need the explicit learning scope and
must pass object visibility; Organization review/rollback remains owner-only. API list/overview
queries apply the ACL predicate in SQL before pagination, preventing hidden rows from distorting
counts or starving a page.

Direct memory values are bounded to 16 KiB, finite canonical JSON, bounded nesting and bounded
container count. `(tenant, actor, source_ref)` is idempotent; reuse with different semantics returns
`409`. Observation time is the stored inbox time, so retries keep the same learning identity.

---

## Part 9 — Storage and migration map

`0045_atlas_l6_learning.sql` introduced the baseline Layer 6 ledgers:

```text
learning_policies · learning_runs · learning_objects · learning_transitions
learned_brain_entries · temporary_memories · knowledge_suggestions · learning_metrics
```

`0047_l6_learning_hardening.sql` is additive and supplies:

- immutable policy revisions and pinned run/object policy authority;
- unique run policy/time identity plus append-only `learning_object_evaluations`, whose composite
  foreign key proves the exact run/policy revision/evaluation time used and whose history index
  supports object replay inspection; a direct tenant FK cascades it during full erasure;
- legacy Runtime-review normalization before the first frozen snapshot, plus API/DB prevention;
- v2 time, independence, trace, visibility, lineage, subject and lifecycle projections;
- exact payload/projection, visibility-shape, tenant-lineage and supersession constraints;
- `learning_event_inbox` for trusted structured events/memory;
- sanitized `learning_input_rejections`;
- owner authorization on feedback revisions;
- ACL/trace propagation to every publisher sink;
- reclaimable failed runs, active-value history and rollback lineage;
- tenant-cascading foreign keys while preserving policy during workspace reset.

The migration currently parses as 138 independent PostgreSQL statements. It must be applied after
the Layer 5.2 migration `0046_l52_delivery_control_plane.sql`, because Layer 6 validates and reads
the hardened delivery/execution lineage that 0046 completes.

---

## Part 10 — Existing calibration loop

The pre-Atlas deterministic calibration subsystem remains valuable and is not confused with the
generic publishers:

- one current canonical human verdict per card plus append-only revisions; terminal dashboard
  judgments write it atomically, `wrong:bad_timing` remains timing/neutral for calibration, and
  dashboard requeue plus dashboard/extension snooze remain lifecycle/timing audit;
- exact pack/capability/rule lineage;
- Wilson lower bounds for small cohorts;
- `rule_mutes` for persistently weak rules;
- bounded weekly `lvl3_config.rule_offsets` honoring pins;
- database-claimed weekly calibration;
- the same `learning_enabled` tenant consent gate as broad learning.

This is the only learned state already consumed by Layer 4 today. It provides a narrow closed loop
while typed consumers for the four generic brains are integrated.

---

## Part 11 — Verification completed locally

| Verification | Result |
|---|---|
| Canonical Atlas + authority + hardening collection | 50/50 passed: 14 Atlas + 3 authority + 33 hardening |
| Expanded Layer 6 cross-seam collection | 144/144 passed |
| Full repository suite | 1,896 passed |
| Python compilation | passed |
| Migration splitter / parser | 138/138 statements parsed |
| Source/schema ratchets | passed |
| Markdown link verification | passed after System Design completion |
| Whitespace validation | `git diff --check` passed |

Focused coverage includes fail-closed visibility, missing lineage, independent evidence, neutral
confidence, stable IDs, deterministic preference conflict, owner authorization recovery, TTL
preflight/expiry, disabled-consent retention, tenant isolation, stored-hash verification, stale
review rejection, metric conflict, advisory versioning, supersession, predecessor restoration,
policy revision wiring, held-object re-evaluation, Candidate non-regression, terminal duplicate
no-op/unchanged accounting, exact sink evaluation reasons, evaluation-ledger identity and
reset/erasure behavior.

Local tests do not substitute for the production proof in Part 13.

---

## Part 12 — Only integrations and decisions left for Harsh

These are the remaining items. None should be implemented as a generic untyped JSON read or an
automatic Expert-Brain mutation.

| Priority | Remaining integration / decision | Required closure |
|---|---|---|
| P0 | Four typed learned-state consumers | Define allowlisted Organization, Behavior, Adaptive and Runtime snapshot contracts for Context/Reasoning/Executive/Delivery; enforce tenant, visibility, version, rollback, TTL and deterministic fallback |
| P0 | Production database proof | Rehearse 0046 then 0047 on a populated PostgreSQL copy with legacy workers quiesced; contend reset/delete against claims, policy/memory, review/rollback, expiry and both feedback writers; prove canonical lock order, no deadlock/partial wipe/child resurrection |
| P0 | Real producer wiring | Connect authenticated provider/client engagement receipts and any approved enterprise structured-event producer to durable lower-layer ledgers or `learning_event_inbox` |
| P0 | Policy/privacy sign-off | Choose per-tenant thresholds, retention, blocked subjects/targets, reviewer scopes and constrained-visibility posture with product/security/legal owners |
| P1 | Human-owned knowledge workflow | Let a human-approved suggestion create a reviewed Git/PR draft through an external workflow; Layer 6 itself must never edit packs or Expert Brain |
| P1 | Optional LLM extraction | If desired, use an LLM only to structure free text into a provenance-bearing typed fact before deterministic learning; never let it score or promote |
| P1 | Production observability/SLO | Alerts for failed/reclaimed runs, rejection reasons, review age, overdue expiry, version conflicts, rollback and input-source starvation |
| P1 | Broader performance/outcome coverage | Add typed business-outcome and receipt producers beyond the current Layer 5 outcome + Layer 5.2 delivery coverage where product surfaces need them |
| P2 | Redis acceleration | Optional disposable cache for active snapshots/memory only; PostgreSQL remains source of truth and TTL authority |

The key product choice is the consumer contract. Until it is reviewed, published generic state
should remain durable and visible but should not silently influence a decision.

---

## Part 13 — Deployment and proof runbook

### 1. Apply migrations in order

```bash
.venv/bin/python -m genios_engine.platform.migrate
```

Verify the ledger contains at least:

```sql
select filename from schema_migrations
where filename in (
  '0045_atlas_l6_learning.sql',
  '0046_l52_delivery_control_plane.sql',
  '0047_l6_learning_hardening.sql'
) order by filename;
```

Run this first on a populated rehearsal copy with mixed old/new workers stopped. Validate
constraints/FKs, backfilled private visibility and organization-preference authorization behavior.

### 2. Prove input truth

For one non-production tenant, inspect the bounded cohorts for canonical feedback, execution
outcomes, delivery attempts/events, graph-source lineage and structured inbox events. An empty seam
must cause its unit to emit nothing; a malformed seam must create a sanitized rejection, not a
fabricated fact or whole-run failure.

### 3. Preview and claim

Call `/v1/learning/preview`, inspect every unit/target/evidence/path, then run the heartbeat from two
workers. Exactly one worker may claim a fresh tenant/week. Re-run after a controlled failure and
prove the failed claim is reclaimed once with incremented attempt count and no duplicate artifact.

### 4. Prove safety transitions

1. Confirm weak, noisy, conflicting, stale and non-independent evidence is held/rejected.
2. Confirm Organization, constrained durable visibility and Knowledge proposals enter HumanReview;
   prove Runtime policy is rejected and a valid Runtime lease reaches Temporary without review.
3. Submit identical owner organization feedback migrated as unauthorized and prove a new authorized
   revision is created.
4. Publish two safe versions, roll back the latest and prove only the exact safe predecessor is
   restored; then make restoration unsafe and prove rollback-to-empty.
5. Create a short Runtime lease, let expiry commit, force the later weekly run to fail and prove the
   memory stays expired.
6. Review a Knowledge suggestion and prove `expert_brain_changed` remains false and no pack/Git row
   changes.

### 5. Prove access and erasure

Exercise owner and scoped principals against private, participant, organization and public objects.
Verify SQL filtering occurs before limit/count. Run workspace reset and confirm learning artifacts,
inbox and rejection rows are erased while consent policy/revisions remain. Then run full account
erasure and confirm tenant-cascading policy history is removed.

On populated PostgreSQL, race reset/full delete against weekly learning, expiry, policy/direct
memory, review, rollback, dashboard action and intelligence feedback. Prove the tenant-root lock
blocks one side cleanly, review/rollback preserve policy-first ordering, feedback preserves
tenant → graph → card, and no deadlock, partial wipe or post-delete child row is possible.

### 6. Monitor before enabling consumers

Watch failed/reclaimed runs, rejection-code rates, HumanReview age, expired leases still active,
multiple active versions, unexpected neutral-outcome growth, delivery source starvation and
publisher conflicts. Enable each typed lower-layer consumer independently behind a tenant rollout
control with rollback to the prior snapshot.

---

## 60-second handoff

Layer 6 is no longer the old calibration loop presented as a complete learner. It now has the Atlas
shape and the safety mechanics needed to learn: exact inputs, all eleven units, immutable v2
proposals, independent evidence, current freshness, versioned governance, pre-persistence privacy,
audited promotion, four real brain targets, TTL memory, honest metrics, human-only knowledge
suggestions, restoration-aware rollback, safe weekly held-object re-evaluation and a
database-claimed scheduler.

Personal preference state is private to one source-authorized subject and stays capped through
Behavior/Adaptive derivation. Terminal dashboard judgments use the canonical versioned feedback
ledger; `wrong:bad_timing` is canonical but timing/neutral, while snooze/requeue remain
lifecycle-only. Performance freshness uses the actual latest lifecycle event, and only a failure
before first delivery is transport-negative; old deliveries with in-window lifecycle activity are
not lost from the cohort. Runtime is an immediate expiring lease—not a reviewable durable proposal.
Observed/Candidate duplicates can be re-evaluated under a later run's frozen policy/time without
rewriting evidence; Candidate never regresses, later states never reopen, and every actual verdict
is appended to the evaluation ledger with its final sink-level reason.

All Layer 6 mutation paths share the erasure-safe root order: tenant `FOR SHARE`, then policy, then
object/memory/advisory locks; reset/delete uses tenant `FOR UPDATE`. Review and rollback use
discovery only to determine canonical locks and recheck afterward. Dashboard/intelligence feedback
uses tenant → graph → card. Populated-PostgreSQL contention/erasure rehearsal remains deployment
proof for Harsh, not unfinished deterministic Layer 6 logic.

The remaining work is explicit integration: deploy 0046/0047 on real PostgreSQL, connect real
producers, ratify tenant policy, build four typed consumers and attach a human-owned knowledge PR
workflow. Redis and LLM extraction are optional. Expert Brain auto-editing is forbidden.
