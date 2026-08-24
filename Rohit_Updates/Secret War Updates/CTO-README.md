# CTO Operating README — Turning the Secret War Audit into GeniOS

- **Audience:** CTO, technical leads, product owner, and the coding agent executing the approved work
- **Purpose:** convert this audit package into a controlled implementation program
- **Authority:** this file is an operating guide, not proof that the documented behavior exists in runtime
- **Default release posture:** no broad activation until the relevant capability passes its explicit exit gates

---

## 1. The 60-second truth

GeniOS is not meant to be an activity feed, a CRM reminder engine, a search result, or an LLM-generated opinion. The customer expects an executive intelligence system that can reconstruct the current business situation, understand roles and commitments, apply accepted domain judgment, recommend the best remaining move, coordinate safe execution, verify completion, and learn from the observed outcome.

The present codebase contains useful infrastructure across that chain, but **presence is not the same as operational intelligence**:

```text
event ingestion
    -> current reality
    -> business situation
    -> accepted domain expertise
    -> ranked decision
    -> governed execution
    -> verified completion
    -> outcome learning
```

If any arrow is missing, the product can produce a polished card that is still wrong. Therefore, the CTO must manage this work as an end-to-end decision system, not as seven independent feature folders.

The immediate strategy is:

```text
ONE accepted Sales capability
    x ONE roleful scenario family
    x ONE complete L1-L7 path
    x deterministic golden replays
    x measured customer outcome
    -> only then expand
```

---

## 2. What the customer is actually buying

Every promoted intelligence item MUST answer all of the following:

```ts
type GoldStandardIntelligence = {
  current_situation: GroundedFactSet;
  business_subject: {
    person_or_account: string;
    relationship_role: string;
    request_or_commitment: string;
    current_owner: string;
  };
  unresolved_item: string;
  why_now: {
    trigger: string;
    elapsed_time_or_deadline?: string;
    business_stakes: string;
  };
  evidence: EvidenceReceipt[];
  expertise: {
    capability_key: string;
    version: string;
    review_state: "accepted";
  };
  decision: {
    primary: Action | Wait | Suppress | Review;
    alternative?: Action | Wait | Suppress | Review;
    stop_condition?: string;
    rationale: string;
  };
  execution: {
    owner: "human" | "agent";
    approval_required: boolean;
    observable_completion: string;
  };
  outcome: {
    observation_window: string;
    success_signal: string;
    counterfactual_or_baseline: string;
  };
  confidence: {
    evidence: number;
    identity: number;
    temporal: number;
    expertise: number;
    decision: number;
    missing_inputs: string[];
  };
};
```

The core invariant is:

```text
No grounded current state
OR no resolved business subject
OR no accepted expertise
OR no authority
OR no observable completion condition
    => do not promote an action recommendation
```

The safe output in those cases is `Observation`, `Review source`, `Wait`, or `Suppress`—never a confident invented action.

---

## 3. How the CTO should read this package

Do not read all files linearly. Use this order:

1. **Establish evidence discipline.** Read [Evidence Authority and Claim Classes](00-Methodology/01-Evidence-Authority-and-Claim-Classes.md). It separates code facts, test facts, design expectations, customer expectations, and proposals.
2. **Fix the semantic map.** Read [Layer Numbering and Semantic Map](00-Methodology/02-Layer-Numbering-and-Semantic-Map.md) so that layer names are not used ambiguously.
3. **Pin the evidence baseline.** Read [Source and Commit Manifest](00-Methodology/03-Source-and-Commit-Manifest.md). Every code or test claim is commit-sensitive.
4. **Understand the customer contract.** Read [Customer Intelligence Contract](00-Methodology/04-Customer-Intelligence-Contract.md).
5. **Make the executive choices.** Read [Executive Decision and Phased Plan](08-Cross-Layer-Synthesis/12-Executive-Decision-and-Phased-Plan.md).
6. **See the non-negotiable blockers.** Read [Deployment Blockers and Design Debt](08-Cross-Layer-Synthesis/10-Deployment-Blockers-and-Design-Debt.md).
7. **Inspect the exact intelligence output.** Read [Gold Standard Intelligence Contract](08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md).
8. **Inspect the dependency chain.** Read [Root Cause, Dependency, and Remediation Order](08-Cross-Layer-Synthesis/09-Root-Cause-Dependency-and-Remediation-Order.md).
9. **Inspect Domain Expertise deeply.** Read [Layer 3 Architecture and Atlas Delta](03-Layer-3-Domain-Expertise/01-Architecture-and-Atlas-Delta/README.md), then the other five Layer 3 folders.
10. **Inspect the four brains.** Read [Four Brains Storage, Ownership, and Replay](08-Cross-Layer-Synthesis/03-Four-Brains-Storage-Ownership-and-Replay.md).
11. **Define release proof.** Read [Evaluation, ROI, and Health Scorecard](08-Cross-Layer-Synthesis/11-Evaluation-ROI-and-Health-Scorecard.md) and the twelve scenario files beginning with [Theresa Investor Reconsideration](09-Golden-Replays/01-Theresa-Investor-Reconsideration-and-Update-Cadence.md).

Use the [package README](README.md) as the full index after this first pass.

### Never interpret the documents this way

| Misreading | Correct interpretation |
|---|---|
| “The YAML exists, so expertise is active.” | A corpus file is only authored content. It becomes expertise only after validation, review, acceptance, admission, routing, invocation, and observable influence. |
| “The compiler can load it, so the product uses it.” | Loader capability is not runtime wiring, and runtime wiring is not proof that the result affects the decision. |
| “A brain hash is present, so that brain reasoned.” | A hash proves selection/provenance only. A typed semantic effect must be visible in goals, constraints, policy, candidates, eligibility, or rank. |
| “The card rendered, so intelligence worked.” | Rendering proves delivery. It does not prove correctness, usefulness, completion, or customer outcome. |
| “The screenshot looks wrong, so the UI is the root cause.” | The UI may expose an upstream identity, temporal, correlation, expertise, or reasoning failure. Trace the decision backward. |
| “A test suite has no new failures, so the feature is ready.” | Baseline failures and skips remain unresolved evidence. Release requires the capability-specific gates below. |

---

## 4. Current technical truth that must shape the plan

The code claims below are a historical audit snapshot pinned to `harsh/mvp@b739bd5`. The test counts were reproduced on 2026-08-22 against `rohit-yc-brain@27b73f6` and `harsh/mvp@b739bd5`. The coding agent MUST record and refresh every drift-prone claim against the latest approved Harsh MVP commit before changing runtime behavior.

Brain aliases used throughout this package are exact, not additional components:

```text
Company Brain        = Organization Brain
Domain Expertise     = Expert Brain
Behavioral Brain     = Behavior Brain
Adaptive Brain       = Adaptive Brain
```

| Area | Current audited state | CTO interpretation |
|---|---|---|
| New Layer 3 | Present and shadow-wired, default-off | This is not a speed-driven rollback to the old implementation. It is an incomplete promotion path. |
| Sales corpus | 46 entries: 43 stubs, 3 non-stub drafts, 0 reviewed, 0 accepted | Breadth exists; production-grade Sales expertise does not. |
| Support corpus | 49 entries: 40 stubs, 9 non-stub drafts, 0 reviewed, 0 accepted | Partially authored, not accepted expertise. |
| Admin corpus | 57 entries: 57 stubs, 0 reviewed, 0 accepted; no routes | Structural placeholder only. |
| Resolver admission | A `stub: false` draft can be admitted | Review and acceptance are not yet enforced as authority gates. |
| Organization Brain | Selected and hashed at the Layer 3 to Layer 4 boundary | Semantic influence on policy/constraints is not demonstrated. |
| Behavior Brain | Selected and hashed at the Layer 3 to Layer 4 boundary | Semantic influence on candidate choice/ranking is not demonstrated. |
| Adaptive Brain | Selected and hashed at the Layer 3 to Layer 4 boundary | Semantic influence and safe lifecycle behavior are incomplete. |
| Governance | Important publish/reload/expiry gaps remain | A successful write is not sufficient proof of enforceable runtime governance. |
| 2026-08-22 test snapshot on `rohit-yc-brain@27b73f6` | 9 failed, 1314 passed, 39 skipped, 1 warning | Not green. The skips are not passes, and the warning is not a failure by itself. |
| 2026-08-22 test snapshot on `harsh/mvp@b739bd5` | 9 failed, 1385 passed, 46 skipped, 1 warning | Also not green. Counts are branch-specific historical evidence, not permanent product metrics. |

The nine reproduced failures currently group into three root causes:

1. one stale corpus-ledger assertion;
2. four executive-authority assertions missing the required latest graph-version constraint;
3. four SQLite migration failures caused by PostgreSQL-style arguments reaching SQLite.

Do not hide, delete, skip, or weaken these tests to obtain a green label. Either fix the responsible contract or explicitly quarantine the unrelated baseline with a named owner, reason, and deadline before evaluating a new unit. Quarantine may isolate diagnosis; it MUST NOT convert a release or QA gate to green.

---

## 5. Decisions the CTO must lock before broad coding

| Decision | Required answer | Why it blocks the product |
|---|---|---|
| First authority boundary | Which exact situation and capability can produce an action, and which situations remain observation-only? | Without it, generic rules overreach into fundraising, investor, introduction, and relationship scenarios. |
| Expertise lifecycle | Who authors, reviews, accepts, versions, deprecates, and rolls back a capability? | `stub: false` cannot be treated as expert authority. |
| Four-brain semantics | Which typed fields can Company, Domain, Behavior, and Adaptive brains change? | Hash-only participation creates provenance theater, not intelligence. |
| Organization publication | Does approval immediately publish, or is publication a separate atomic state transition? | `approved_unpublished` cannot silently appear as active policy. |
| Adaptive lifecycle | What is the mandatory scope, expiry, rollback, and promotion policy for every adaptive rule? | Durable or ambiguous learning can contaminate decisions across time or tenants. |
| Policy reload parity | Which fields must survive persistence and reload byte-for-byte? | Dropped blocked targets or subject prefixes can reopen forbidden actions. |
| Completion state machine | What evidence changes `planned -> delegated -> sent -> acknowledged -> completed -> outcome_observed`? | A click or draft must not close a real-world loop. |
| LLM authority | Which operations may use model judgment, and which gates remain deterministic? | Fluent generation must never create permissions, facts, completion, or expertise authority. |
| Outcome proof | What observation window, success signal, baseline, and counterfactual are required? | Activity metrics cannot prove customer value. |

Record each answer as a small, versioned contract or ADR before the corresponding implementation unit starts.

---

## 6. How the coding agent will work on this

This README gives the agent context. It is **not blanket authority** to modify every layer or deploy changes. The CTO or product owner should issue one scoped milestone at a time.

The audit and decision package lives on `rohit-yc-brain`. Product implementation MUST begin from the latest CTO-approved `harsh/mvp` source commit in a scoped branch/worktree and merge into the explicitly named product integration branch. The agent must not assume that `rohit-yc-brain` is the runtime implementation target merely because this README is stored there.

### Agent execution contract

For every approved unit, the coding agent MUST:

1. fetch the latest approved Harsh MVP source and record the exact commit;
2. work in an isolated branch or worktree;
3. identify the customer scenario, failing invariant, owning layer, and downstream consumers;
4. write an executable failing contract test or replay derived from the modelled golden-replay specification before implementation;
5. make the smallest end-to-end change that closes that failure;
6. preserve evidence receipts, tenant boundaries, identity roles, timestamps, and version provenance;
7. fail closed when required inputs or authority are missing;
8. run unit, connection, integration, migration, and scenario checks appropriate to the change;
9. compare the built behavior with the requested customer outcome;
10. return changed files, exact commands/results, remaining skips/failures, feature-flag state, rollback path, and known unknowns.

The coding agent MUST NOT:

- activate all YAML rules because they exist;
- treat a draft or non-stub rule as accepted expertise;
- use an LLM to bypass permissions, policy, identity, freshness, tenant, or approval gates;
- infer that the email sender is always the business subject;
- merge unrelated people because an introduction connector appears in many threads;
- create a recommendation from stale, contradicted, already-resolved, or future-dated evidence;
- mark an action complete because a user clicked a button or an agent generated a draft;
- tune scoring or confidence until the underlying state and authority are correct;
- broaden the task silently when it discovers adjacent debt;
- call a unit complete while its required checks are skipped or failing.

### Unit loop

```text
CLAIM scope
  -> REPRODUCE the customer failure
  -> PIN evidence and expected contract
  -> TEST fail-first
  -> IMPLEMENT smallest vertical slice
  -> VERIFY deterministic gates
  -> REPLAY adversarial scenarios
  -> CROSS-CHECK built vs requested
  -> RELEASE claim
  -> HAND OFF evidence
```

---

## 7. The first bounded vertical slice

Start with the proposed Sales pilot lane already identified in this audit:

```yaml
domain: Sales
situation: buying_signal
situation_id: sales.sit.inbound_fit_check
primary_capability: sales.qualification.lead_qualification
companion_capability: sales.market_and_targeting.icp_definition
release_mode: shadow_then_named_design_partner
default_for_other_situations: observation_only
```

Before runtime promotion, both capability files require:

- complete authored content rather than stubs;
- schema and semantic validation;
- named domain reviewer;
- explicit `accepted` state and version;
- an accepted transitive dependency closure: every retained rule, object, playbook, and dependency is accepted at an immutable content hash, or deliberately pruned;
- positive and negative route fixtures;
- deterministic compiler admission;
- evidence of semantic influence in Layer 4;
- abstention when facts, identity, freshness, or authority are inadequate;
- one governed execution path;
- completion reconciliation;
- outcome observation and customer review.

Theresa/investor reconsideration, Boardy introductions, fundraising, regional-program relationships, and other outside-coverage cases MUST remain `Observation`, `Review`, `Wait`, or `Suppress` until a separately reviewed capability explicitly covers them. Their presence in Gmail or Calendar does not make them Sales authority.

---

## 8. Implementation sequence and exit gates

### Phase 0 — Stabilize and label the baseline

**Build:** refresh the source manifest; reproduce the current failures; fix or explicitly own the three failure groups; inventory flags, legacy paths, and data stores.

**Exit gate:** every baseline test has one honest state—passing, intentionally excluded with owner/deadline, or blocking. No unlabeled skip is counted as green, and an intentional exclusion never makes release QA green.

### Phase 1 — Make Layer 1 and Layer 2 reconstruct current reality

**Build:** roleful identity, thread and relationship boundaries, event-time and ingestion-time handling, request/commitment ownership, contradiction handling, resolution evidence, and current-state reduction.

**Exit gate:** already-replied, rescheduled, cancelled, delegated, cross-channel-resolved, connector-mediated, internal-only, and stale-history replays produce the correct current state.

### Phase 2 — Turn Layer 3 files into accepted expertise

**Build:** author the two pilot capabilities, enforce lifecycle state, tighten routing, reject stubs/drafts, and create deterministic compiler receipts.

**Exit gate:** only the exact accepted version and its accepted immutable transitive dependency closure are admissible; unsupported scenarios abstain; every recommendation cites the capability key, version, and dependency hashes actually applied.

### Phase 3 — Make all four brains semantically real

**Build:** typed inputs and effects for Company Brain, Domain Expertise, Behavior Brain, and Adaptive Brain.

**Exit gate:** controlled mutation of each brain changes only its authorized downstream fields, produces a traceable decision delta, and cannot override a harder authority source.

### Phase 4 — Produce a real Layer 4 decision

**Build:** candidate generation, eligibility, disqualification, ranking, alternatives, wait/stop logic, confidence vector, and explicit missing inputs.

**Exit gate:** the chosen action beats its alternatives for stated reasons; unsupported prescription rate is zero in the release replay set.

### Phase 5 — Govern Layer 5 and Layer 6 execution

**Build:** typed plan, owner selection, approval policy, delegation feasibility, delivery receipt, completion predicate, and reconciliation.

**Exit gate:** GeniOS distinguishes drafted, approved, sent, acknowledged, completed, and failed. No UI click alone closes the loop.

### Phase 6 — Close Layer 7 governance and learning

**Build:** atomic publication semantics, policy reload parity, adaptive scope/TTL/rollback, outcome windows, counterfactual recording, correction feedback, and promotion criteria.

**Exit gate:** every active policy or learning is scoped, versioned, replayable, expirable, and reversible; prohibited targets remain prohibited after reload.

### Phase 7 — Prove value with a design partner

**Build:** shadow run, user comparison, controlled release, correction capture, and outcome measurement for the bounded Sales lane.

**Exit gate:** the customer confirms that the system surfaced a decision they would otherwise have missed or delayed, with acceptable correction burden and a measurable business outcome.

---

## 9. Golden replays are modelled release contracts

The Markdown files in `09-Golden-Replays` specify required fixtures, mutations, receipts, and outcomes. They are not executable test evidence until the coding agent implements and runs those replays against the relevant runtime path.

At minimum, promotion must cover these failure families:

| Replay family | Required behavior |
|---|---|
| Theresa / investor reconsideration | Preserve the relationship and promised update cadence; do not rewrite it as “one last chance” or an unsupported rejection narrative. |
| Boardy-mediated introduction | Resolve the introduced parties and their individual threads; never assign every obligation to the connector. |
| Availability and reschedule | Understand that a proposed time is not an unfulfilled deliverable after the meeting has occurred or changed. |
| Already replied / cross-channel resolved | Suppress the loop when later evidence proves the obligation was handled elsewhere. |
| Internal group recap | Do not tell the user to send a customer recap when no external counterparty exists. |
| Closed, rejected, filled, or deferred relationship | Respect terminal and deferred states; do not manufacture urgency. |
| Missing expertise | Return observation-only with the missing capability named. |
| Agent handoff | Recommend delegation only when an eligible agent, scope, permission, and acceptance path exist. |
| Client isolation / never-commercial | Preserve tenant and policy boundaries in retrieval, reasoning, and execution. |
| Pivot / sparse behavior | Avoid treating obsolete behavior as a permanent preference. |
| Revenue and counterfactual | Separate “action happened” from “action caused useful business movement.” |
| Antler exploratory relationship | Respect regional and relationship authority; do not convert exploratory context into a sales prescription. |

The full modelled scenario specifications and expected contracts live under `09-Golden-Replays`. The coding agent MUST translate the applicable specification into executable fixtures and preserve the resulting test receipts. A release candidate fails if it passes the happy path but violates any applicable negative or abstention case.

---

## 10. LLM use by layer

The correct question is not “what percentage of each layer should be LLM?” It is “which fields require probabilistic interpretation, and which decisions require deterministic authority?” Measure token and latency budgets after correctness is established.

| Layer | LLM may help with | LLM must not decide |
|---|---|---|
| L1 Knowledge | extraction, entity candidates, summarization, proposed fact structure | source provenance, tenant boundary, immutable event identity |
| L2 Context | role hypotheses, request/commitment extraction, contradiction candidates | final identity merge, freshness gate, resolved/unresolved state without evidence |
| L3 Expertise | authoring assistance, example generation, semantic lint suggestions | review acceptance, capability authority, route eligibility |
| L4 Reasoning | candidate generation, rationale drafting, ambiguity explanation | hard disqualification, permission, policy override, fabricated confidence |
| L5 Executive | plan-language drafting and trade-off explanation | owner authority, approval requirement, forbidden action |
| L6 Delivery | channel-aware message drafting and adaptation | sending without authorization, claiming delivery/completion |
| L7 Learning | outcome-summary and hypothesis generation | causal proof, global promotion, scope expansion, TTL bypass |

Cost optimization order:

```text
remove duplicate model calls
  -> narrow context to evidence receipts
  -> cache immutable extraction by source/version
  -> use deterministic gates before expensive reasoning
  -> use smaller models for bounded extraction/classification
  -> reserve strongest reasoning for eligible high-value decisions
  -> measure cost per useful accepted decision, not cost per generated card
```

---

## 11. Definition of done must remain a ladder

Never collapse these statuses:

| Status | Evidence required |
|---|---|
| Present | file, schema, migration, class, or route exists |
| Wired | a production path invokes it under a known flag/configuration |
| Live | an enabled runtime request reaches it and emits a receipt |
| Tested | deterministic positive, negative, fail-closed, reload, and replay checks pass with no required skip |
| Outcome-proven | a customer used or accepted the intelligence and the defined outcome window produced evidence against a baseline/counterfactual |

Likewise, maintain separate state for:

```text
observed -> recommended -> approved -> delegated -> sent
         -> acknowledged -> completed -> outcome_observed
```

No later state may be inferred merely because an earlier state occurred.

---

## 12. CTO scorecard

Track product quality per scenario family and accepted capability version:

- wrong business-subject rate;
- connector-collapse rate;
- stale or already-resolved resurfacing rate;
- unsupported-prescription rate;
- abstention precision and recall;
- accepted-action rate;
- user correction burden;
- completion-reconciliation accuracy;
- time saved to the next correct decision;
- observable business outcome rate;
- counterfactual or baseline coverage;
- cost per useful accepted decision;
- cross-tenant or policy violation count;
- rollback and replay success rate.

Vanity metrics such as cards generated, confidence displayed, emails indexed, or YAML files loaded are diagnostic only. They are not evidence that GeniOS delivered intelligence.

---

## 13. Required coding-agent handoff for every milestone

The agent's completion note must contain this exact evidence shape:

```yaml
milestone:
  customer_scenario: "..."
  owning_layers: ["..."]
  source_commit: "..."
  feature_flag: "..."
changes:
  files: []
  contracts_added_or_changed: []
verification:
  commands: []
  passed: 0
  failed: 0
  skipped: 0
  warnings: 0
  golden_replays: []
authority:
  expertise_key: "..."
  expertise_version: "..."
  reviewer: "..."
  acceptance_state: "..."
runtime:
  evidence_receipt: "..."
  decision_receipt: "..."
  delivery_receipt: "..."
  rollback_path: "..."
remaining:
  blockers: []
  known_unknowns: []
  customer_proof_missing: []
```

A prose claim such as “implemented,” “wired,” or “tests mostly pass” is insufficient without this evidence.

---

## 14. First CTO working session

The first session should end with written answers to these questions:

- [ ] Is the exact pilot scope above approved or changed?
- [ ] Who is the named Sales domain reviewer and final accepter?
- [ ] What is the authoritative lifecycle from draft to accepted to deprecated?
- [ ] What typed field may each of the four brains change?
- [ ] What are the hard precedence rules between those brains?
- [ ] What is the required behavior when expertise is missing?
- [ ] What evidence proves an obligation is resolved?
- [ ] What execution requires human approval?
- [ ] What publication/reload/expiry behavior is non-negotiable?
- [ ] Which golden replays block promotion?
- [ ] What design-partner outcome proves the first lane is useful?
- [ ] Who owns every currently failing or skipped verification?

After those decisions, issue the coding agent **Phase 0 and one vertical-slice unit only**. Do not authorize global rule activation or broad layer rewrites.

---

## 15. Final CTO rule

```text
If GeniOS cannot name:
  the real person or account,
  the relationship and role,
  the exact unresolved request or commitment,
  the accepted expertise being applied,
  why this action is the best remaining move now,
  who can safely execute it,
  what observable event completes it,
  and what outcome would prove value,
then GeniOS has context or activity—not promotable intelligence.
```

Build the first complete, reviewable, replayable decision loop. Prove that it helps one customer make one materially better decision. Then expand capability by capability.
