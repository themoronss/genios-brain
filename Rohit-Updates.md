# Rohit Updates

## Layer 6 learning hardening completion (8 August 2026)

**Current verdict:** the Atlas/Theory-aligned internal Layer 6 engine is implemented and locally
verified. Read [`Rohit_Updates/Layer 6.md`](Rohit_Updates/Layer%206.md) for the detailed CTO
handoff and
[`System Design/Layer-6-Learning-and-Evolution/`](System%20Design/Layer-6-Learning-and-Evolution/README.md)
for the part → subpart → component map. This section supersedes the Layer 6 implementation,
migration, test and rollback statements in the dated entries below it.

What is now true:

- `learning.v2` is an immutable, content-addressed contract with independent evidence, first/last
  observation time, end-to-end trace, explicit fail-closed visibility, source lineage and subject
  principal. The four brains are Organization, Behavior, Adaptive and Runtime; metrics and
  knowledge suggestions are separate artifact targets. Expert Brain is unrepresentable.
- The bounded loader verifies exact feedback revisions, Layer 5 outcomes, as-of Layer 5.2
  attempt/event history plus frozen `ExecutionObject` identity/hash, and enterprise-event source
  lineage. Terminal dashboard judgments atomically version the canonical feedback ledger;
  `wrong:bad_timing` is canonical timing/neutral evidence, while dashboard requeue and dashboard/
  extension snooze remain non-verdict audit/lifecycle events. Malformed optional rows are isolated
  into a sanitized rejection ledger.
- All eleven units are present. Confidence uses independent evidence; neutral activity cannot
  inflate it; preference conflicts are deterministic and actor-scoped; user preferences are capped
  to a private ACL for one source-authorized subject and Behavior/Adaptive preserve that cap;
  outcomes/performance are ACL-cohorted; retry clocks cannot change semantic learning identity.
- Policy/evaluation time stay outside immutable evidence identity. A later claimed week may
  re-evaluate an identical object only from Observed/Candidate under its pinned current policy/time;
  Candidate never regresses, review/published/later/terminal duplicates never reopen, and each
  actual verdict is appended to a run-policy-time-bound evaluation ledger. The reason records the
  final lifecycle/publisher result—including publish success, no-material-change or metric conflict;
  skipped later-state duplicates are counted unchanged rather than reopened.
- Consent, blocked targets/subjects, lineage, actor visibility, organization authority and Runtime
  TTL are checked before proposal persistence. Policy revisions are immutable/pinned; disabled
  tenants still expire old memory without claiming or retaining a new run. Runtime human-review
  policy is rejected by API and database because a valid lease must publish temporary and expire.
- Performance freshness uses each delivery's latest durable lifecycle or receipt timestamp,
  including failed, deferred, suppressed and cancelled endings. Only `failed` with no prior
  `delivered_at` is transport-negative; ACCEPTED → FAILED after delivery remains transport-delivered
  and is handled as an execution/business outcome. Delivery selection includes rows created in the
  source window or carrying an in-window lifecycle event, so recent activity on an older delivery
  is not dropped.
- Publishers use tenant advisory locks, monotonic history versions, exact ACL/trace propagation and
  honest no-op/conflict outcomes. Rollback restores the exact safe predecessor when current
  visibility/consent/policy permit it, otherwise it rolls back to an empty active slot.
- Every Layer 6 mutation starts with tenant `orgs FOR SHARE`; reset/delete uses `orgs FOR UPDATE`.
  Policy precedes object/memory/advisory locks. Review discovers then locks policy/object and
  rechecks; rollback locks discovered policy keys sorted before subject/object topology; dashboard/
  intelligence feedback writers use tenant → graph → card.
- APIs now have separate read/review/rollback scopes, filter visibility in SQL before pagination,
  revalidate review/rollback authority under lock and provide bounded idempotent direct memory.
- Migration `0047_l6_learning_hardening.sql` adds the policy ledger, v2 projections/constraints,
  structured event inbox, sanitized rejection ledger, per-run object-evaluation ledger, sink lineage
  and tenant-safe FKs, including a direct evaluation-ledger tenant erasure cascade. It parses
  as 138 PostgreSQL statements and follows the Layer 5.2 migration `0046`.

Verification: **50/50 canonical Layer 6 tests, 144/144 expanded cross-seam tests and 1,896
full-repository tests passed**; compilation, migration parsing, System Design link checking and
`git diff --check` are green. The one warning is the unrelated Starlette/httpx deprecation.

Only integration/deployment work remains for Harsh: rehearse 0046→0047 and multi-worker behavior on
populated PostgreSQL, including reset/delete contention against learning, expiry, policy/memory,
review/rollback and both feedback writers; connect real provider/client receipt and approved
structured-event producers; ratify tenant policy/privacy/retention; build allowlisted consumers for
Organization, Behavior, Adaptive and Runtime snapshots; add production observability; and attach a
human-owned Git/PR workflow to approved knowledge suggestions. Optional LLM use stops at typed
extraction, and Redis may only be a disposable cache over PostgreSQL authority.

---

## Layer 5.2 delivery control-plane completion (8 August 2026)

**Current verdict:** the Atlas-aligned internal Layer 5.2 control plane is implemented and locally
verified. Read [`Rohit_Updates/Layer 5.2.md`](Rohit_Updates/Layer%205.2.md) for the detailed CTO
handoff and [`System Design/Layer-5.2-Delivery-Engine/`](System%20Design/Layer-5.2-Delivery-Engine/README.md)
for the part → subpart → component implementation map. This section supersedes the Layer 5.2
implementation/test statements in the dated entries below it.

What changed in code:

- `execution.v2` now freezes the narrowest selected-source visibility; stored v1 execution hashes
  remain compatible and their ACL is re-derived from immutable reasoning lineage at every delivery
  boundary, failing closed when lineage cannot be resolved.
- The active path is `ExecutionObject → Delivery Orchestrator → one logical outbox row → fenced
  physical attempt → DeliveryResult`. Raw `/v1/signals*` agent work endpoints are authenticated
  `410 Gone` migration sentinels rather than a second execution plane.
- Current audience, recipient, destination, channel, format, priority, timing and policy are
  resolved by Layer 5.2. Exact-agent `delivery.read`, a same-agent active API key, recipient ACLs,
  current presence and decrypted adapter-valid credentials are enforced consistently at discovery,
  materialization and final send.
- Physical attempts and lifecycle facts are append-only. Attention reservation and the `started`
  attempt commit atomically before provider I/O; claims are fenced; retries are bounded; ambiguous
  Slack/Teams acknowledgement stops for manual reconciliation; owner replay requires explicit
  duplicate-risk acknowledgement where necessary.
- Migration `0046_l52_delivery_control_plane.sql` installs execution lineage, route/claim/lifecycle
  state, attempt/event ledgers, atomic attention windows, legacy ambiguity quarantine and replay
  audit. The migration runner now holds a global PostgreSQL advisory lock across the ledger and DDL.
- The platform runs a dedicated minute-scale delivery heartbeat instead of coupling delivery
  latency to the heavier maintenance cadence.

Atlas structure correction: Delivery Management has **8 managers**, not 7. The System Design now
contains `01-Delivery-Outbox` followed by Tracker, Retry, Recovery, Deduplication, Rate Limiter,
Analytics and Delivery Object Builder as separate nested component folders.

Verification: **1,896 tests passed**, `compileall` passed and `git diff --check` passed. The single
warning is the unrelated third-party Starlette/httpx deprecation.

Only external/deployment proof remains: quiescent populated-PostgreSQL migration rehearsal with no
mixed legacy/v2 workers; real multi-worker contention and provider ACK-loss/reconciliation tests;
tenant credentials; product presence/receipt publishers; real dashboard/application/extension/
mobile clients; human-to-seat identity binding for recipient-scoped multi-seat access; email and
APNs/FCM providers; and production observability/SLO operations.

---

## Addendum — Atlas revised to v3.1 (8 August 2026)

**Nothing below this section was rewritten.** The entries that follow are dated records of what
was true and what was verified on the day they were written, and falsifying a status report to
match a later document is worse than leaving it slightly stale. This addendum states what the
Atlas revision changed and which sentences below it supersedes.

**No code changed.** Every item is either a correction *to the Atlas* to match shipped behaviour,
or a newly named gap. Test status from 7 August stands.

**Corrections made to the Atlas, because the code was already right**

- Scores are integer basis points, not floats. The Atlas used `0.87`; the code has used
  `priority_bp` / `confidence_bp` throughout.
- Layer 4 persists an immutable, replayable reasoning trace. The Atlas claimed it was stateless
  *and* unrecorded; migration `0026` has recorded it since it landed.
- `Cancelled`, `Expired`, `Failed` and `Suppressed` are four different endings that teach different
  lessons. `DeliveryResultStatus` already carried all four.
- `SEND` / `DEFER` / `SUPPRESS` is a closed set composed by intersection, and a `DEFER` consumes no
  retry attempt. That was `contracts/delivery.py` behaviour before it was Atlas text.
- The transactional outbox is now a named management system rather than an unnamed detail, taking
  Layer 5.2 Part C from seven entries to **eight**.

**Supersedes, in the tables below**

- "→ three dynamic brains" (Layer 6 row) — the Evolution Publisher has **five publishers writing
  four targets**: Organization, Behavior, Adaptive and Runtime. Metrics is telemetry, not a brain.
- "7 management systems" wherever it appears for Layer 5.2 — now **8**.
- Any reference to `ExecutionObject.delivery_targets` — the Atlas field is now `audience_intent`
  and is explicitly semantic. Concrete `channel_id` / `interrupt` remain as v1/v2 compatibility
  hints the Layer 5.2 orchestrator does not read (`EXECUTION_VERSION` is now `execution.v2`;
  stored v1 objects still round-trip). Runtime behaviour is unchanged.

**New gaps the revision exposed** — recorded in
[`05-Gaps.md`](System%20Design/Cross-Cutting-Contracts-Platform-API/05-Gaps.md) as items 8–10 and
explained in
[`06-Atlas-Envelope-Alignment.md`](System%20Design/Cross-Cutting-Contracts-Platform-API/06-Atlas-Envelope-Alignment.md):

1. **No end-to-end `trace_id`.** Lineage is traversable hop by hop but not queryable in one
   predicate. This is the only real absence.
2. **`visibility` is not carried on the delivery objects.** Rule 10 is still enforced — Layer 5.2
   re-reads it from the persisted execution — but a consumer holding only a `DeliveryResult` needs
   a join to answer it.
3. **`schema_version` has two shapes** — `int` in Layer 1, namespaced `str` in Layers 5/5.2.

The Atlas also gained a **Layer 0** chapter covering `contracts/ · platform/ · api/`, the
heartbeat, the latency budget, cross-layer failure semantics and tenancy/retention/erasure. That
material already existed in
[`System Design/Cross-Cutting-Contracts-Platform-API/`](System%20Design/Cross-Cutting-Contracts-Platform-API/README.md);
the Atlas was the document missing it.

---

## Current CTO handoff — Atlas Layers 5, 5.2 and 6

Status: **implemented, reconciled with the Atlas, documented from live code and locally verified.**

Last updated: 2026-08-07 · _partially superseded by the 8 August addendum above_

**Documentation correction (7 August 2026):** the first documentation pass flattened these three
large Atlas layers into a short list of pages. That was not an adequate system-design map. The
live folders now follow `layer → part → subpart/unit → component module`: Layer 5 has 92 Markdown
documents, Atlas Layer 5.2 has 117, and Atlas Layer 6 has 141. Every named Atlas component now has
a physical location, code/status evidence, edge cases and an explicit gap boundary.

The product map is canonical below. The integers 1–7 in `genios_engine/LAYERS.py` are dependency
**import ranks**, not a second set of product-layer numbers:

| Product/Atlas layer | Code package | System Design folder | Detailed CTO note |
|---|---|---|---|
| Layer 5 · Executive Engine | `genios_engine/executive/` (code L5) | `System Design/Layer-5-Executive-Engine/` | [`Rohit_Updates/Layer 5.md`](Rohit_Updates/Layer%205.md) |
| Layer 5.2 · Delivery Engine | `genios_engine/deliver/` (import rank 6) | `System Design/Layer-5.2-Delivery-Engine/` | [`Rohit_Updates/Layer 5.2.md`](Rohit_Updates/Layer%205.2.md) |
| Layer 6 · Learning & Evolution | `genios_engine/feedback/` (import rank 7) | `System Design/Layer-6-Learning-and-Evolution/` | [`Rohit_Updates/Layer 6.md`](Rohit_Updates/Layer%206.md) |

### Planned → current → integration

| Layer | What the Atlas planned | What is true now | What still needs production integration |
|---|---|---|---|
| 5 | 10 deterministic Executive Units + multi-owner Coordination → one ExecutionObject | All ten units exist; immutable ExecutionObject, runtime dependency waves, owner/channel plan, stale guard, reminders, escalation, lifecycle, outcome collection, API and scheduler are connected | Concrete per-action multi-owner seat/agent assignment, digest batching, Redis acceleration and live-PostgreSQL proof |
| 5.2 | Context-aware delivery orchestrator + 11 target units + tracking/retry/recovery/analytics → DeliveryResult | SEND/DEFER/SUPPRESS gate; recipient preferences; leased presence; typed DeliveryObject/Result; Slack, Teams, signed webhook and pull surfaces; terminal-failure-only failover; analytics; existing outbox remains the ledger | Native email, APNs/FCM, automatic trusted presence publisher, real provider/outage tests and live-PostgreSQL proof |
| 6 | 11 governed Learning Units → four dynamic brains, TTL memory, metrics and knowledge suggestions; never edit Expert Brain | All 11 units, immutable `learning.v2`, exact input lineage, policy revisions, pre-persistence governance, audited lifecycle, Organization/Behavior/Adaptive/Runtime publishers, metrics, human-review Knowledge Evolution, APIs and scheduler are connected | Typed lower-layer consumers; real receipt/event producers; tenant policy/privacy sign-off; human-owned Git/PR workflow; 0046→0047 live-PostgreSQL/concurrency/observability proof; optional Redis/LLM extraction |

### The closed product loop now present in code

```text
Layer 4 DecisionObject
    → Layer 5 ExecutionObject + tracked commitment
    → Layer 5.2 DeliveryObject / DeliveryResult
    → explicit feedback + execution_outcomes + enterprise events
    → Atlas Layer 6 governed LearningObject
    → versioned Organization / Behavior / Adaptive state
```

The critical correction from the earlier notes is that `execution_outcomes` is no longer an
unread table. Learning loads the indexed outcome cohort and uses it in Outcome Analysis,
Recommendation Learning and Knowledge Evolution. `completed_unproven` remains neutral and visible;
it is not fabricated into either success or failure.

### Verification snapshot

- Full local repository suite: **1,896 passed**. This supersedes the 7 August count.
- Layer 5 focused collection: **195 tests**.
- Delivery-focused collection (`test_delivery*`, outbox and Executive bridge): **142 tests**.
- Learning canonical Atlas/authority/hardening collection: **50/50 tests** — 14 Atlas, 3 authority
  and 33 hardening; expanded Layer 6 cross-seam collection: **144/144 tests**.
- SQL table/column ratchets, account-erasure cascades and layer-topology checks: green.
- `git diff --check`: green.
- Existing non-blocking warning: Starlette's `httpx` test-client deprecation.
- Still unproven locally: applying migrations through `0047` and exercising the
  corresponding SQL/claims with live PostgreSQL and real external delivery credentials.

### CTO deployment order

1. Review the three detailed notes above, each layer's `STATUS.md`, and its nested System Design
   part/unit/component tree.
2. Apply migrations through `0047_l6_learning_hardening.sql` using the normal migration runner;
   rehearse populated-database `0046 → 0047` ordering with mixed-version workers quiesced.
3. Run one tenant's Executive sweep twice; first run may create commitments, second must create zero
   duplicates.
4. Exercise Delivery `/effective`, a leased context, each configured real adapter and controlled
   terminal failure/failover.
5. Inspect `/v1/learning/preview`, then allow the weekly claimed run; verify that weak evidence is
   held, organization/knowledge changes require review, and no Expert Brain write exists.
6. Keep native email/mobile push disabled until provider, identity, unsubscribe/token and receipt
   lifecycles are chosen and tested.

Everything below this section is retained historical context. Where an older Layer 5 note says
outcomes are unread or a Layer 5.2 note says only one adapter exists, the linked dated layer note
and the System Design folder above are the current authority.

---

## Layer 4 — Reasoning Engine implementation

> **Superseded on 2026-08-07.** This section describes the 7-unit kernel as it stood on 2026-08-06.
> Layer 4 has since been completed to the full architecture — 17 units on a common framework, the
> Decision Maker extracted, the confidence floor built — and one replay-determinism defect was found
> and fixed. **Read `Rohit_Updates/Layer 4.md` instead**; it carries the current state, the three
> locks that still hold the engine in shadow, and the deployment runbook. The description below
> remains accurate for the parts it covers and is kept as history.

Status: implemented in the current codebase and verified locally.

Last updated: 2026-08-06

### What is now true

Layer 4 is no longer one rule loop or an LLM-assisted recommendation function. It is a selective,
deterministic cognitive runtime:

```text
Goal + bounded ContextSnapshot + versioned CapabilityManifest
    -> declared micro-reasoner DAG
    -> temporal / relationship / signal-composition / risk / gate / policy / priority /
       confidence / planning results
    -> candidate construction
    -> hard eliminations before ranking
    -> integer-only utility calculation
    -> recommended play + alternatives + uncertainty + do-nothing consequence
    -> immutable trace + tenant-scoped persistence
    -> replay / shadow / simulation
```

The orchestrator is the sole Layer 4 decision authority. An LLM can phrase a grounded explanation
downstream, but cannot select an action, change candidate order, invent confidence, bypass a policy,
or authorize execution.

### Implemented architecture

1. Goal Engine
   - A capability carries an explicit `Goal`, success criteria, and constraints.
   - Runtime does not silently replace the business goal with an artifact request.

2. Context Engine boundary
   - Every run receives an immutable, bounded, content-addressed `ContextSnapshot`.
   - Evaluation time is explicit and timezone-aware.
   - Facts, observations, neighborhood state, missing data, and evidence are deep-frozen.
   - Every evidence reference is validated against the exact frozen fact value and its declared
     root/neighbor partition; an unrelated, moved, or altered value cannot be cited.
   - Replay uses the stored snapshot and never rereads the live graph.

3. Knowledge Engine boundary
   - Expertise is compiled into a versioned `CapabilityManifest` and capability-scoped
     `IntelligenceObject`s.
   - Only reasoners declared by the capability are resolved.
   - Capability versions are immutable per tenant and the exact manifest bytes are retained.

4. Thinking Engine
   - Added pure, independently testable micro-reasoners for temporal change, relationship coverage,
     audited signal composition, risk, constraints, priority, confidence decomposition, and planning.
   - A compatibility reasoner runs existing pack rules without changing their match or score.
   - The legacy score/confidence gate and learned per-rule offset now execute inside the traced DAG;
     they are no longer an invisible post-decision condition.
   - A reasoner sees only explicitly declared DAG dependencies; hidden order-dependent dependencies
     are impossible.

5. Math and Decision Engine
   - Candidate artifacts use integer basis points only.
   - NaN, infinity, floats in semantic artifacts, malformed weights, non-finite timestamps, and
     implicit numeric truncation fail closed.
   - Constraints and policy eliminations happen before ranking.
   - Ranking uses a fixed weighted utility calculation and a total-order tie-break on `play_id`.
   - Required reasoner failure stops the decision; optional failure is explicit degradation with a
     bounded confidence cap.
   - A false activation gate produces a traced no-action result and skips downstream reasoners.

6. Validation, Planning, and Confidence
   - Read-only, evidence-required, human-approval, and verified-recipient policies plus play
     preconditions are centrally checked; unknown/typo policies are rejected at manifest load.
   - Every play declares observable success events and an outcome window.
   - Confidence is decomposed from source quality, completeness, corroboration, and evidence
     coverage; it is never supplied by the explanation model.
   - Every decision includes alternatives, missing data, uncertainty, expiry, and the consequence of
     doing nothing.

7. Audit and replay
   - Exact capability bytes, context payload, ordered reasoner results, candidate adjustments,
     checks/eliminations, ranking, and decision are stored as one tenant-scoped bundle.
   - Emitted signals now reference the authoritative reasoning run.
   - Persistence is idempotent and an idempotency key cannot be reused for different semantic input.
   - Sensitive context payloads have separate TTL retention while non-content audit metadata remains.
   - Negative, blocked, insufficient-context, and failed executions are retained as non-authoritative
     audit evidence rather than disappearing into logs.
   - Replay independently recomputes capability, policy, selector, context, request, DAG input,
     reasoner-result, candidate, check, decision, and aggregate run hashes before it executes.
   - Capability, context payload, run, results, candidates, checks, and output are written through one
     database transaction; a failed final write cannot leave a sensitive orphan context.

8. Shadow and simulation
   - `live`, `shadow`, `simulation`, and `replay` are explicit execution modes.
   - Shadow, simulation, and replay can compute a winner but can never authorize delivery.
   - Counterfactual scenarios apply deep-frozen fact/relationship overrides to the captured snapshot,
     remove stale evidence for overridden values, and return per-play utility deltas without mutating
     the graph.

9. Adversarial authority hardening
   - `matched` accepts only a real boolean; `0`, `1`, strings, and other truthy/falsy values fail
     closed before a gate can authorize anything.
   - Request and policy IDs are content-addressed and cannot be supplied as unrelated opaque labels.
   - Runtime tenant P90 overlays receive a new exact config snapshot; signals and reasoning runs are
     forbidden by composite foreign keys from claiming different config provenance.
   - A graph-version drift guard aborts and requests a fresh sweep if graph state changes while the
     bounded context is being selected.
   - Query retrieval uses total ordering and only a signal whose run, output, and config linkage are
     valid may select an action.
   - Query/analyze decision IDs bind the full returned envelope, including explicit facts and the
     optional explanation; persistence collisions fail closed.
   - Explanation-model output is treated as untrusted prose, validated for unsupported actions,
     entities, numbers, and terms, and replaced with deterministic reasoning when it fails.
   - Multi-signal explanations load every contributing run instead of presenting one run's trace as
     if it explained all conclusions.
   - A shared authority proof now binds every actionable signal to one completed live run, its
     rank-one eligible candidate, output decision hash, exact active pack/config bytes, current
     graph version, capability manifest, and unexpired decision window.
   - Pack configuration carries a monotonic authority revision. Evaluation and publication lock the
     exact revision, so a concurrent pack activation, version change, or learned-threshold update
     invalidates the in-flight result instead of publishing under changed policy.
   - Signal projection fields are treated as denormalized claims: reason code, score, score inputs,
     evidence, and play are re-derived from the immutable audit bundle at every trust boundary.
   - Card construction, queueing, push delivery, intelligence retrieval, human action, agent poll,
     artifact access, claims, and results all revalidate that same proof instead of trusting a stale
     open signal or card.
   - Delivery and action mutations hold a tenant graph-version lock and settle their card, signal,
     claim, metering, human-event, and audit-event changes transactionally.
   - Agent results require the exact owning, unexpired claim. Revoked or concurrently resolved
     authority records an honest late-result no-op but cannot mutate the card or signal.
   - Superseded and shadow decisions retire earlier live signals/cards, so historical authority
     cannot survive a new no-action, blocked, expired, or shadow evaluation.
   - Outcome calibration and foresight learning accept only historically audited signal lineage;
     malformed, unbound, pre-card, or post-expiry events cannot poison learned scores or play rates.
   - Learning uses one current, durable human verdict per card plus an append-only revision history.
     Every judgment is bound to the exact pack, capability, authority revision, and rule version that
     produced the card; impressions are not labels, and weekly calibration commits atomically with
     bounded offsets and conservative Wilson confidence bounds.
   - Context snapshot schema v2 binds the root entity type into the content address. Storage and
     replay reject payload/row/manifest disagreement about tenant, graph version, selector, root,
     evaluation time, or root type.
   - Persistence does not trust caller-supplied candidates or checks: it reconstructs the declared
     DAG, dependency hashes, activation gates, policy checks, adjustments, ranking, confidence, and
     selected play from the immutable capability, context, and reasoner outputs before commit.
   - Signal identity is pack-aware, and publication uses a tenant watermark plus current authority
     locks so an older or concurrently invalidated evaluation cannot overwrite a newer decision.
   - Scoped machine credentials are deny-by-default on legacy owner routes. Agent/card surfaces use
     explicit scopes, derive the actor from the credential, enforce assignment and claim ownership,
     and cannot pause or resume a workspace.
   - Delivery retries re-prove the exact live decision. Digest rows are intents whose content is
     regenerated from current non-actionable authority at send time, while expensive card rendering
     is protected by a durable lease and a fenced insert token.
   - Tenant erasure now includes reasoning traces, sensitive context payloads, capabilities, and
     config snapshots in dependency-safe order. Scheduled maintenance purges expired context bytes,
     and replay rejects expired payloads even before physical purge.

### First native capability

`sales.deal_cooling` is now a native Layer 4 capability with:

- four capability-scoped Intelligence Objects;
- seven version-pinned reasoners in a deterministic DAG;
- temporal and open-deal relationship activation gates;
- three read-only alternatives:
  - `restore_momentum`;
  - `multithread_account`;
  - `clarify_next_step`;
- human approval, evidence, and verified-recipient policies;
- observable outcomes such as prospect reply, meeting booked, stakeholder added, next step recorded,
  and stage advanced;
- deterministic selection plus explicit eliminated alternatives.

It is wired into the real graph sweep in explicit shadow mode. Correctly partitioned root deal facts
are used directly; callers no longer duplicate `deal.status` into neighbour facts to make the
relationship reasoner run. Stakeholder coverage counts only distinct adjacent person-like nodes
with an explicit current verification fact; generic company, meeting, commitment, and unverified
edges no longer inflate relationship confidence.

`sales.deal_health` is also a native audited composition capability. A compound card can be emitted
only when at least two distinct, trace-linked parent signals pass `core.signal_composition`; it then
ranks `review_deal` and `monitor_deal`, persists its own reasoning bundle, and stamps the composite
signal with that run. The old unaudited composite shortcut has been removed.

### Safe migration of the existing engine

The current pack runtime was not rewritten. It now enters Layer 4 through a strangler adapter:

- legacy `Rule` and `NodeContext` inputs are normalized into strict manifests and snapshots;
- existing `evaluate()` and `score_rule()` behavior is preserved behind `legacy.rule`;
- parity tests prove identical match results, score, and `U/I/R/C/terms_bp` inputs;
- cooldown, learned offsets, tenant budget, signal lifecycle, card rendering, and feedback contracts
  remain compatible;
- emitted per-rule legacy signals receive the new reasoning-run link;
- tenant pack state and the capability's immutable live-delivery flag are enforced centrally, so a
  shadow capability is audited but cannot emit;
- an audit write failure suppresses the recommendation instead of emitting an unaudited card.

The on-demand intelligence path was also restricted: deterministic open signals choose the fixed
action and confidence; its LLM prompt can return only an optional explanation. Query derivations now
carry the source reasoning-run IDs, both query and analyze persist before returning, cache identity
changes with authoritative signal state, and the explain endpoint exposes every actual reasoner and
constraint trace.

### Primary implementation files

- `genios_engine/contracts/reasoning.py` — strict cross-layer contracts.
- `genios_engine/reason/orchestrator.py` — selective DAG execution and decision authority.
- `genios_engine/reason/reasoners/` — pure micro-reasoners.
- `genios_engine/reason/adapters/` — exact legacy compatibility boundary.
- `genios_engine/packs/capabilities/deal_cooling.py` — first native capability.
- `genios_engine/packs/capabilities/deal_health.py` — audited compound-signal capability.
- `genios_engine/reason/audit.py` and `store.py` — atomic trace persistence.
- `genios_engine/reason/authority.py` — shared signal/run/candidate/config/graph authority proof.
- `genios_engine/reason/replay.py` — snapshot reconstruction and semantic replay comparison.
- `genios_engine/reason/simulation.py` — deterministic counterfactual scenarios.
- `migrations/0025_config_snapshot_tenant_scope.sql` — tenant-owned configuration history.
- `migrations/0026_l4_reasoning_trace.sql` — Layer 4 run, result, candidate, check, and output tables.
- `migrations/0029_l4_capability_and_signal_trace.sql` — immutable capabilities and signal-to-run link.
- `migrations/0030_l4_replay_and_signal_integrity.sql` — selector retention, status fidelity, replay,
  and signal/run/config integrity constraints.
- `migrations/0031_l4_signal_authority_projection.sql` — candidate/decision/expiry signal binding,
  output identity, tenant cascade ownership, and projection constraints.
- `migrations/0033_org_data_cascade.sql` — complete dependency-safe tenant deletion ownership.
- `migrations/0034_l4_learning_authority.sql` — pack-aware signal identity, snapshot-v2 root binding,
  publication watermarks, outbox authority lineage, fenced card-build leases, canonical feedback,
  and atomic calibration lineage.

### Verification gate

- Full repository test suite: **418 passed**.
- Layer 4 contract, authority, parity, orchestration, persistence, replay, simulation, and capability
  tests: green.
- Python compilation and application import smoke test: green.
- Migrations `0025` through `0034` are covered by the repository's migration contract tests.
- `git diff --check`: green.

### Deliberate boundaries

- No autonomous outbound message or CRM mutation was added.
- The external execution/handoff endpoint deliberately fails closed until an idempotent,
  approval-bound executor exists; no network side effect can occur through the placeholder path.
- No LLM is used for matching, risk, scoring, ranking, confidence, policy, or winner selection.
- No causal/predictive claim is fabricated without validated outcome data.
- The next promotion step is to apply the new migrations, run `sales.deal_cooling` in shadow on real
  Gmail + CRM + Calendar context, inspect precision and missing-data suppressions, and only then turn
  on live card delivery.

---

## GeniOS Refinement and Execution Plan

Status: retained below as the dependency-ordered source plan. Layer 4 is now implemented as described
above; the remaining phases are still governed by their exit gates.

Last reviewed: 2026-08-06

---

## 1. Executive decision

We should not rewrite the repository. The current code already contains useful foundations:

- a traceable ingestion pipeline;
- a persistent context graph;
- deterministic rule evaluation and scoring;
- versioned domain packs;
- suppression, cooldown, card, feedback, and agent primitives;
- tenant-aware API and governance foundations.

The main problem is sequencing. We have built a fairly wide backend before proving one complete customer-value loop. From this point forward, the order must be:

```text
Trusted source evidence
    -> correct context graph
    -> deterministic conclusion
    -> 2-3 prescriptive plays
    -> human-approved action
    -> observed business outcome
    -> calibrated future recommendation
    -> defensible value ledger
```

The next milestone is not more rules or more architectural components. It is one undeniable end-to-end outcome for one design partner.

---

## 2. Canonical product architecture

The attached architecture is directionally strong, but a few boundaries need tightening so that layers do not overlap.

| Layer | Single responsibility | Current home | Required refinement |
|---|---|---|---|
| L1 Enterprise Signals | Acquire, normalize, deduplicate, classify, and retain raw enterprise events | `capture/`, `contracts/` | Add the minimum live sources and guarantee event-to-graph propagation |
| L2 Context Graph | Store evidence-backed entities, relationships, observations, facts, and time-aware state | `context/`, migrations | Repair identity, fact versioning, corroboration, spans, and replay |
| L3 Capability Expertise | Compile universal, organization, behavioral, and adaptive expertise per capability | Mostly `packs/` | Evolve packs into versioned capability manifests and overlays |
| L4 Deterministic Reasoning | Select relevant context and compute candidates, risk, priority, confidence, and alternatives | `reason/` | Introduce reasoner interfaces, orchestration, traces, and counterfactuals |
| L5 Executive Intelligence | Turn a decision into an evidence-backed, action-ready intelligence object | Partly `deliver/card_builder.py` | Create a stable decision/card contract with 2-3 real plays |
| Layer 5.2 Delivery | Route intelligence to humans, agents, APIs, digests, and the product surface | `deliver/`, API routes | Separate packaging from routing and ship one real user surface |
| Layer 6 Learning | Observe outcomes, update bounded statistics, detect drift, and propose governed changes | `feedback/`, feedback migrations | Learn from outcomes instead of clicks and implement the value ledger |

Governance is a cross-cutting control plane over product Layers 1, 2, 3, 4, 5, 5.2 and 6: identity, authorization, tenant isolation, audit, policy, retention, kill switches, budgets, approvals, and rollback.

### Boundary corrections

1. Memory is not a raw source. GeniOS memory is the combination of the event ledger, context graph, decision history, and outcome history.
2. A user request should not rebuild or mutate the whole graph. Ingestion updates the persistent graph; a request creates a relevant, versioned context view or snapshot.
3. L2 may store evidence-level confidence per fact. Decision confidence belongs to L4/L5.
4. Attention, priority, risks, and opportunities are derived reasoning outputs. They may be persisted in the graph with provenance, but L4 owns their computation.
5. Executive Memory should be a read model over decisions and open items, not a new competing store.
6. The LLM may parse and render. It must not choose the winning action, manufacture confidence, rank plays, or silently change policy.

---

## 3. Product wedge: what we prove first

### Initial user

Founder, revenue leader, or sales manager at a design-partner company.

### Minimum source set

1. Gmail: conversations, replies, commitments, objections, and stakeholder activity.
2. HubSpot or the partner's CRM: deal state, value, stage, owner, next step, close date, and contacts.
3. Google Calendar: meetings, attendance, cancellations, and next scheduled interaction.

Notion, Drive, documents, external web data, Slack, Jira, finance, HR, and the remaining source catalogue stay outside the first proof unless a selected capability absolutely requires them.

### First three capabilities

1. `sales.deal_cooling`
   - Detect a valuable active deal that has lost momentum relative to its normal cadence.
   - Combine CRM state, email activity, stakeholder coverage, and the next scheduled meeting.

2. `sales.promise_overdue`
   - Detect a commitment made by either side that has passed its promised date without evidence of completion.
   - Show the exact commitment sentence and time reference.

3. `sales.next_step_missing`
   - Detect an active deal with interest or recent engagement but no concrete owner/date/next event.
   - Distinguish a real missing next step from a stale or already-closed deal.

These capabilities cover temporal reasoning, relationship reasoning, cross-source corroboration, constraints, prioritization, and outcomes without requiring a giant domain catalogue.

### Required card experience

Every emitted card must answer, in ten seconds:

- What changed?
- Why does it matter now?
- What exact evidence supports it?
- What is missing or uncertain?
- What are the 2-3 available plays?
- Which play is recommended, and by what deterministic calculation?
- What happens if the user does nothing?
- What outcome will be checked, and when?

The first release remains read-only. GeniOS may create a draft or structured handoff, but external mutation requires explicit human approval.

---

## 4. Architecture principles we will enforce

### 4.1 Generic core, narrow proof

The core interfaces must be domain-neutral, while expertise remains domain-specific and data-driven.

Correct:

```text
PriorityReasoner + sales.deal_cooling capability manifest
```

Incorrect extremes:

```text
SalesPriorityEngine hardcoded into the core
Generic architecture for 100 domains before one domain works
```

### 4.2 Capability vertical slices, not four independent brains

Universal, organization, behavioral, and adaptive knowledge should be compiled into a capability-scoped Intelligence Object.

```text
Capability: sales.deal_cooling
  Universal: sales-cadence and stakeholder-risk principles
  Organization: stage definitions, ICP, approval rules, sales process
  Behavioral: owner's real communication and follow-up patterns
  Adaptive: outcome rates and learned thresholds for this tenant/segment
```

The runtime retrieves this compiled object rather than scanning four broad knowledge stores.

### 4.3 Heavy ingestion, selective runtime

- Normalize and enrich incrementally when events arrive.
- Maintain read models and graph indexes ahead of a request.
- Select the smallest relevant graph neighborhood.
- Activate only the capability's declared reasoners and calculators.
- Persist the input snapshot and output trace for replay.

### 4.4 Version everything that affects a decision

Each decision must record:

- source event and payload version;
- extraction prompt, model, and parser version;
- graph fact and edge versions;
- capability and rule version;
- organization and behavioral overlay versions;
- scoring/configuration snapshot;
- evaluation time;
- renderer/template version;
- outcome definition version.

### 4.5 Outcomes are not clicks

`run_play`, `do_it_myself`, `not_relevant`, and `later` are user reactions. They are not business outcomes.

An outcome is independently observable, for example:

- the prospect replied;
- a next meeting was booked;
- a deal stage advanced;
- a commitment was completed;
- the deal closed or was lost;
- a risk remained unresolved after the outcome window.

---

## 5. Target contracts

Before adding more features, define and version these domain-neutral contracts:

1. `SourceEvent`
   - immutable normalized event plus tenant, source, external identity, event time, ingest time, and raw-payload reference.

2. `EvidenceRef`
   - source event, payload hash, exact character span or structured field path, quoted text/value, source time, and access policy.

3. `EntityRef`
   - stable tenant-scoped identity, entity type, canonical keys, aliases, and merge history.

4. `FactAssertion`
   - stable fact identity, subject, predicate, typed value, valid time, recorded time, confidence inputs, authority, and all evidence references.

5. `ContextSnapshot`
   - immutable, bounded graph view selected for one capability evaluation.

6. `CapabilityManifest`
   - triggers, context selector, expertise overlays, reasoners, calculators, policies, plays, output schema, and outcome definitions.

7. `ReasonerResult`
   - inputs, deterministic calculation trace, candidates, eliminated candidates, reason codes, and confidence decomposition.

8. `IntelligenceDecision`
   - situation, importance, recommended candidate, alternatives, evidence, uncertainty, expected outcome, and expiry.

9. `PlayDefinition`
   - preconditions, steps, owner type, effort, risks, expected outcome, observation window, and historical segment statistics.

10. `OutcomeObservation`
    - decision/play linkage, observable success event, source evidence, window, status, and attribution confidence.

11. `ValueLedgerEntry`
    - outcome linkage, value formula, inputs, assumptions, evidence, confidence, and whether value is realized, protected, or estimated.

No API or database table should invent a weaker private version of one of these contracts.

---

## 6. Delivery roadmap

The phases below are dependency-ordered. We move forward only after the exit gate of the current phase passes.

### Phase 0 — Establish a trustworthy engineering baseline

Goal: make the checked-out repository reproducible and establish one truthful baseline before architectural work.

Tasks:

1. Reconcile the six commits currently present on `origin/harsh/mvp` but absent from the checked-out branch. Review them; do not blindly merge around local work.
2. Replace invalid `requirements.txt` pins and the machine-specific editable path in `requirements-lock.txt`.
3. Choose one dependency source of truth: preferably `pyproject.toml` plus a reproducible generated lock.
4. Update the README to describe the current Layers 1–6 plus Layer 5.2 implementation and real setup process.
5. Add CI for Python 3.11 and 3.12 with install, migration, unit tests, integration tests, static checks, and import/startup smoke tests.
6. Add an ephemeral Postgres test environment and apply every migration from a blank database.
7. Validate production configuration at startup. Missing crypto, JWT, webhook, database, and internal secrets must fail closed.
8. Fix known contract errors, beginning with the `/context/process` `limit` versus `max_total` mismatch.
9. Record four ADRs: layer boundaries, LLM boundary, graph identity/versioning, and outcome semantics.
10. Capture current coverage by module and make critical-path coverage visible in CI.

Exit gate:

- a fresh machine can install and run tests with one documented command;
- all migrations apply to an empty Postgres database;
- no secret is persisted in plaintext when encryption configuration is absent;
- API startup and core health checks pass;
- critical endpoint signatures are contract-tested;
- baseline unit and integration tests are green.

### Phase 1 — Make the Context Graph trustworthy

Goal: every conclusion can be replayed to exact source evidence, and concurrent ingestion cannot corrupt identity or fact history.

Tasks:

1. Add a tenant-scoped uniqueness strategy for entity canonical keys.
2. Replace select-then-insert identity creation with an atomic upsert or transaction-safe resolver.
3. Introduce explicit identity merge and split history; never silently rewrite prior references.
4. Give each logical fact a stable identity across versions.
5. Store independent assertions and attach every corroborating source instead of discarding equal values.
6. Define conflict semantics: current winner, competing assertions, authority, freshness, and verification state.
7. Store exact text spans or structured field paths in every source reference.
8. Preserve offset maps through preprocessing so evidence can be highlighted in the original payload.
9. Separate observed facts, inferred facts, and reasoning outputs by type and provenance.
10. Make LLM extraction caching depend on content, source type, prompt, model, parser, and schema versions.
11. Add deterministic event replay from raw payload to graph snapshot.
12. Add graph quality checks for duplicates, orphans, impossible timelines, missing evidence, stale facts, and cross-tenant leakage.

Exit gate:

- replaying the same fixture produces identical graph snapshot hashes;
- every emitted test fact has at least one valid evidence reference;
- equal assertions from two sources yield a corroboration count of two;
- concurrent creation of the same identity produces one canonical node;
- every quoted email fact highlights the exact original span;
- tenant-isolation tests cover every graph read and write path.

### Phase 2 — Complete the live event-to-card spine

Goal: prove that a real source event creates useful intelligence without a manual maintenance call.

Tasks:

1. Finish and validate the Gmail connector using full message bodies, thread metadata, participants, and attachments.
2. Build the minimum live HubSpot/CRM connector required by the three initial capabilities.
3. Validate Calendar ingestion for future meetings, cancellations, participants, and event changes.
4. Route connector-specific webhooks through the correct parser and connection identity.
5. Make a successful webhook drive L1 -> L2 -> L4 -> L5 -> L5.2 immediately through a durable job/outbox.
6. Keep scheduled sweeps as recovery and reconciliation, not as the primary six-hour intelligence path.
7. Add retries, poison-event quarantine, idempotency, and observable per-stage latency.
8. Build an end-to-end test using representative Gmail, CRM, and Calendar fixtures plus real Postgres.
9. Run the three capabilities in shadow mode for the design partner before notifying users.
10. Build a graph/evidence inspection tool for internal debugging.

Exit gate:

- a new qualifying event creates or updates a card without a manual trigger;
- duplicate webhook delivery creates no duplicate facts, signals, or cards;
- event-to-card p95 is below five minutes for the pilot workload;
- pipeline success is at least 99% excluding intentionally quarantined poison data;
- internal reviewers can open every card and inspect its exact evidence and reasoning trace.

### Phase 3 — Introduce the capability runtime

Goal: make capability-driven selective reasoning real without replacing the working engine.

Tasks:

1. Evolve the existing pack manifest into a versioned `CapabilityManifest`.
2. Let each capability declare:
   - event and schedule triggers;
   - required entity/fact/relationship selectors;
   - universal, organization, behavioral, and adaptive overlays;
   - required reasoners and calculators;
   - policies and hard constraints;
   - candidate plays;
   - output template;
   - success, failure, expiry, and observation windows.
3. Introduce a small `Reasoner` protocol with typed inputs and outputs.
4. Extract the current logic incrementally into reusable reasoners: temporal, relationship, priority, risk, constraint, and confidence.
5. Add an orchestrator that validates a manifest, retrieves a bounded context snapshot, invokes only declared reasoners, and records a full trace.
6. Keep rule evaluation pure. No database access, system clock, or LLM call inside a reasoner.
7. Prefer fixed-point/integer scoring where exact replay matters; define rounding explicitly.
8. Validate manifests before activation and content-address every active snapshot.
9. Add a simulation command that runs new capability versions against historical events without production delivery.
10. Add shadow, canary, promote, rollback, pin, and tenant-override lifecycle states.

Illustrative manifest shape:

```yaml
id: sales.deal_cooling
version: 1.0.0
triggers: [email.received, crm.deal.updated, calendar.event.changed, daily]
context_selector:
  root: deal
  relationships: [account, owner, contacts, meetings]
reasoners: [temporal, relationship, risk, priority, confidence]
calculators: [deal_impact, cadence_deviation]
policies: [read_only, no_unverified_recipient]
plays: [restore_momentum, multithread_account, clarify_next_step]
outcome:
  success_events: [prospect_reply, meeting_booked, stage_advanced]
  window_days: 14
```

Exit gate:

- adding `sales.promise_overdue` requires a new manifest/data package, not a core-engine modification;
- only declared graph fields and reasoners run;
- the same snapshot, manifest, configuration, and evaluation time produce the same result hash;
- invalid or incompatible manifests cannot be activated;
- a previous capability version can be restored without a deployment.

### Phase 4 — Make intelligence genuinely prescriptive

Goal: move from detection plus one suggestion to evidence-backed choice among real plays.

Tasks:

1. Define the stable `IntelligenceDecision` and card schemas.
2. Require 2-3 candidate plays when enough safe alternatives exist.
3. Give every play preconditions, steps, effort, owner type, risks, completion signal, outcome window, and segment statistics.
4. Rank plays deterministically using expected impact, success probability, cost/effort, risk, policy constraints, confidence, and learned tenant statistics.
5. Show honest small-sample labels such as “insufficient tenant history”; never fabricate precision.
6. Include eliminated alternatives and reason codes in the reasoning trace.
7. Add `why`, `why now`, `why this play`, `why not the alternatives`, `missing data`, and `do nothing` consequences.
8. Make rendered text fail validation if it introduces unsupported facts, recipients, amounts, dates, or claims.
9. Keep handoffs read-only: draft email, proposed task, structured agent instruction, or deep link. Require approval for mutation.
10. Add card expiry, supersession, duplicate suppression, attention budgets, and conflict handling.

Exit gate:

- a reviewer can reproduce the winning play score from displayed inputs;
- every material sentence is evidence-backed or explicitly labeled as an assumption;
- unsupported LLM additions fail closed;
- cards do not conflict, duplicate a recent decision, or survive after their evidence expires;
- design-partner users understand a card and its next step within ten seconds.

### Phase 5 — Ship the first distribution surface

Goal: put the intelligence where the design-partner user already works and measure the experience.

Tasks:

1. Choose one primary surface: browser extension/sidebar or a focused web inbox. Do not build every channel.
2. Support Today, Critical, Opportunities, Snoozed, and Resolved views.
3. Show source icons, exact evidence expansion, confidence decomposition, and outcome status.
4. Support four user reactions consistently across UI and agent APIs.
5. Add presence/privacy controls so context-triggered delivery is explicit and inspectable.
6. Keep digests as secondary packaging over the same card contract.
7. Implement structured agent consumption, scopes, claim lease, idempotency, result reporting, and approval boundaries.
8. Instrument delivered, viewed, expanded, acted, ignored, snoozed, superseded, and resolved states.

Exit gate:

- one pilot user receives and resolves real cards through the chosen surface;
- every UI state maps to the same server-side lifecycle contract;
- agent and human consumers receive semantically identical intelligence;
- no notification is sent outside tenant routing, policy, cooldown, or attention-budget rules.

### Phase 6 — Close the outcome, learning, and value loops

Goal: learn what worked and prove value without corrupting deterministic governance.

Tasks:

1. Implement an outcome evaluator independent of user reactions.
2. Observe defined success/failure events after each play's window.
3. Support partial, ambiguous, expired, and confounded outcomes.
4. Separate recommendation precision, play acceptance, execution, and business success metrics.
5. Segment statistics by tenant, capability, play, entity type, stage, and other privacy-safe dimensions.
6. Use Bayesian or shrinkage estimates so tiny samples do not dominate rankings.
7. Feed bounded adaptive statistics into the next versioned capability snapshot.
8. Let learning propose rule/threshold changes; require validation, simulation, and human approval before activation.
9. Detect drift in data, behavior, outcome rates, and organization policy.
10. Implement the value ledger with explicit formulas and evidence.

Exit gate:

- every executed play becomes success, failure, partial, ambiguous, or expired after its window;
- calibration uses observed outcomes rather than button clicks;
- all adaptive inputs are bounded, versioned, explainable, and reversible;
- no rule changes silently;
- every claimed rupee of value links to a decision, outcome, formula, evidence, and confidence level.

### Phase 7 — Enterprise hardening and controlled expansion

Goal: make the proven loop safe and reusable across tenants and domains.

Tasks:

1. Add tamper-evident, tenant-scoped audit chains and an integrity verifier.
2. Implement global, tenant, domain/capability, and agent kill switches with fail-closed behavior and tested propagation time.
3. Enforce approval policies at one central mutation/handoff chokepoint.
4. Complete per-data-class retention, deletion, export, and deletion certificates.
5. Add budget limits for LLM, connector, storage, notification, and agent consumption.
6. Add SLOs, alerts, runbooks, backups, restore drills, and disaster-recovery tests.
7. Perform authorization, tenant-isolation, prompt-injection, webhook, and supply-chain security testing.
8. Add sources only when a proven capability requires them.
9. Add new domains by capability packages after Sales meets its outcome and reliability gates.
10. Build external capability authoring only after the internal manifest lifecycle is stable.

Exit gate:

- governance claims are demonstrated by automated tests and audit verification;
- tenant deletion leaves no unapproved residue;
- kill switches stop the targeted scope within the documented SLO;
- a second domain can be added without changing the core contracts or orchestrator.

---

## 7. Immediate ordered backlog

This is the exact starting order once implementation is approved:

1. Review and reconcile the six remote commits ahead of the checked-out branch.
2. Fix packaging, lock generation, README, production configuration validation, and CI.
3. Add real Postgres migration and API integration tests.
4. Fix the `/context/process` argument mismatch and contract-test every pipeline trigger.
5. Add the canonical `EvidenceRef` and exact-span preservation.
6. Make entity resolution atomic with tenant-scoped uniqueness and merge history.
7. Redesign fact persistence around stable fact identity, versions, assertions, and multi-source corroboration.
8. Build deterministic raw-event-to-graph replay and graph snapshot hashing.
9. Connect webhooks to the complete durable L1 -> L2 -> L4 -> L5 -> L5.2 path.
10. Implement the minimum HubSpot/CRM connector.
11. Convert `deal_cooling` into the first capability manifest and shadow-run it.
12. Define three real plays and a CRM-observable outcome window for that capability.
13. Ship the minimal card surface to one design partner.
14. Observe outcomes, calibrate safely, and write evidence-backed value-ledger entries.
15. Only then promote the next two capabilities and expand sources.

---

## 8. Current code: keep, refine, add

### Keep and strengthen

- `capture/pipeline.py`: traced pass/drop/park ingestion spine.
- `capture/acquire/sync_runner.py`: retry and quarantine direction.
- `context/guard.py`: evidence-grounding boundary.
- `reason/engine.py`: pure evaluation with explicit evaluation time.
- `packs/registry.py`: versioned, content-addressed tenant configuration direction.
- `reason/runner.py`: suppression, cooldown, budget, and signal orchestration.
- `deliver/render.py`: renderer invention checks.
- card actions and agent claim/result lifecycle.

### Refine before scaling

- `context/graph_store.py`: atomic identity, stable fact versions, assertions, corroboration, spans.
- `context/runner.py`: contract consistency, durable jobs, replay, and stronger integration tests.
- `packs/sales_v1.py`: split rule catalogue into capability-scoped manifests and real plays.
- `reason/scoring.py`: exact replay semantics, calibration boundaries, and confidence decomposition.
- `reason/intelligence.py`: remove LLM authority over recommendation, ranking, and confidence.
- `deliver/card_builder.py`: stable intelligence contract, alternatives, evidence, uncertainty, outcomes.
- `feedback/calibrate.py`: business outcome learning rather than interaction learning.
- `platform/audit.py`, `platform/auth.py`, and account deletion/retention: fail-closed governance.

### Add

- live CRM connector;
- capability manifest schema and validator;
- reasoner protocol and selective orchestrator;
- exact evidence-span resolver;
- replay/simulation harness;
- outcome evaluator;
- value-ledger service;
- minimal user surface;
- end-to-end Postgres and connector-contract test suites.

---

## 9. Metrics and release gates

### Evidence trust

- 100% of material card claims have evidence or an explicit assumption label.
- 100% of text evidence references resolve to the original payload.
- Zero known cross-tenant reads or writes.
- Duplicate canonical-entity rate below 0.1% in pilot data, with every duplicate reviewable.

### Intelligence quality

- Measure card precision separately from card acceptance and play success.
- Track false-positive reason categories.
- Track missing-data suppression instead of forcing low-confidence output.
- Publish sample size with every adaptive success rate.

### Product value

- First useful intelligence within 24 hours of connecting pilot sources.
- Ten-second median comprehension target for a card.
- Track time from signal to user action and from action to outcome.
- Report realized, protected, and estimated value separately.

### Reliability and cost

- Event-to-card p95 below five minutes for real-time capabilities.
- At least 99% successful processing for valid pilot events.
- Zero duplicate active cards for the same capability episode.
- Cost per ingested event, emitted card, active tenant, and successful outcome is observable.

### Safety and governance

- Zero external mutations without policy and explicit approval.
- Zero plaintext connector secrets.
- 100% of decisions and handoffs have an auditable trace.
- Tested kill-switch and deletion SLOs.

---

## 10. What we intentionally will not build yet

- every source listed in the enterprise-source taxonomy;
- a generic “brain” database for every future domain;
- autonomous workflow execution;
- an open-ended chatbot as the primary product;
- a large executive dashboard before the card loop works;
- voice, WhatsApp, mobile, Slack, Teams, and email delivery simultaneously;
- self-modifying rules;
- complex simulation, causal claims, or prediction without validated outcome data;
- more sales rules until the first three capabilities meet precision and outcome gates;
- cross-tenant learning without explicit privacy architecture and consent.

---

## 11. Definition of “GeniOS v1 is real”

GeniOS v1 is real when a design partner can connect Gmail, CRM, and Calendar, and the system can repeatedly:

1. notice a meaningful cross-tool change;
2. produce a deterministic, evidence-backed conclusion;
3. show exact source proof;
4. recommend 2-3 safe plays and explain the winner;
5. let a human approve or perform the action;
6. observe whether the business outcome occurred;
7. use that outcome to improve bounded future ranking;
8. calculate value honestly;
9. replay the entire decision;
10. prove tenant isolation, policy, audit, and reversibility.

Until this loop works, the project is an intelligence-engine foundation. Once this loop works reliably, it becomes GeniOS.
