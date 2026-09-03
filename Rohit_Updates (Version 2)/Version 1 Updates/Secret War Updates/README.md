# Secret War Updates — GeniOS Intelligence Audit and Build Decision

This package is an evidence-bounded audit of the seven-layer GeniOS intelligence chain, built from `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8` and written on `rohit-yc-brain`. It answers the central question: **why does the current product produce activity-shaped cards instead of consistently useful, expert, executable intelligence—and what exact vertical sequence fixes it?**

The blunt answer is in the [Executive decision](08-Cross-Layer-Synthesis/12-Executive-Decision-and-Phased-Plan.md): the architecture is substantial, but broad prescriptive authority is not ready. Layer 3 is shadow-wired/default-off and has a material corpus-authoring/admission gap: Sales is **46 total / 43 stubs / 3 non-stub authored drafts / zero reviewed or accepted**; Support is **49 / 40 / 9 / zero reviewed or accepted**; Admin is **57 / 57 / zero non-stub / zero reviewed / zero accepted / zero routes**. This was shadow-first from inception, not a speed-driven rollback. Layer 4 presently gives Organization, Behavior and Adaptive **hash-only influence** rather than typed semantic judgment, while downstream action, delivery and learning contracts are not yet welded into one outcome-accountable chain.

Layer 7 also has three authority-stopping seams: Organization review approval does not publish an active brain version (`approved_unpublished`); persisted policy reload omits `blocked_targets` and `blocked_subject_prefixes` (`policy_incomplete`); and recommendation learning can propose Adaptive even though explicit Adaptive expiry is illegal, while an omitted-expiry proposal **may publish durably**. The current code does not pass the required Adaptive lifecycle replay: it has **no automatic short-horizon** TTL/decay guard and does not emit or enforce `adaptive_ttl_unresolved`. That label is the required fail-closed disposition, not a claim about current behavior. These are current code truths, not hypothetical product polish issues.

## How to read

1. Start with the [evidence and claim classes](00-Methodology/01-Evidence-Authority-and-Claim-Classes.md). `[CODE]`, `[ATLAS]`, `[CUSTOMER]`, `[MODELLED]` and `[TEST]` are intentionally different authorities.
2. Read the [customer intelligence contract](00-Methodology/04-Customer-Intelligence-Contract.md) to see what a useful card must prove.
3. Read the relevant Layer 1–Layer 7 pack. Every layer uses the same six lenses: architecture, customer/HKS, current behavior, loopholes, LLM/cost, and improvements/acceptance.
4. Use the [cross-layer typed contract](08-Cross-Layer-Synthesis/02-Typed-Contract-and-Provenance-Matrix.md), [four-brains audit](08-Cross-Layer-Synthesis/03-Four-Brains-Storage-Ownership-and-Replay.md), and [gold-standard contract](08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md) to follow one decision end to end.
5. Inspect the Golden replays for concrete failure mutations: Theresa, Boardy, rescheduling, already-resolved work, internal recaps, missing expertise, governed handoffs, privacy, pivot/adaptation and counterfactual value.
6. Finish with the [root-cause order](08-Cross-Layer-Synthesis/09-Root-Cause-Dependency-and-Remediation-Order.md), [blockers](08-Cross-Layer-Synthesis/10-Deployment-Blockers-and-Design-Debt.md), [scorecard](08-Cross-Layer-Synthesis/11-Evaluation-ROI-and-Health-Scorecard.md), and Executive decision.

Specifications, reference HTML, screenshots and modelled applications are not presented as live customer proof. The product baseline also remains visibly red (`9 failed, 1314 passed, 39 skipped, 1 warning`); this documentation build did not change product code.

## Layer packs

| Layer | Architecture / Atlas | Customer / HKS | Current behavior | Loopholes / edge cases | LLM / cost | Improvements / exit gates |
|---|---|---|---|---|---|---|
| Layer 1 — Knowledge | [Architecture](01-Layer-1-Knowledge/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](01-Layer-1-Knowledge/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](01-Layer-1-Knowledge/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](01-Layer-1-Knowledge/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](01-Layer-1-Knowledge/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](01-Layer-1-Knowledge/06-Improvements-Acceptance-and-Metrics/README.md) |
| Layer 2 — Context Intelligence | [Architecture](02-Layer-2-Context-Intelligence/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](02-Layer-2-Context-Intelligence/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](02-Layer-2-Context-Intelligence/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](02-Layer-2-Context-Intelligence/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](02-Layer-2-Context-Intelligence/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](02-Layer-2-Context-Intelligence/06-Improvements-Acceptance-and-Metrics/README.md) |
| Layer 3 — Domain Expertise | [Architecture](03-Layer-3-Domain-Expertise/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](03-Layer-3-Domain-Expertise/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](03-Layer-3-Domain-Expertise/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](03-Layer-3-Domain-Expertise/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](03-Layer-3-Domain-Expertise/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](03-Layer-3-Domain-Expertise/06-Improvements-Acceptance-and-Metrics/README.md) |
| Layer 4 — Reasoning | [Architecture](04-Layer-4-Reasoning/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](04-Layer-4-Reasoning/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](04-Layer-4-Reasoning/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](04-Layer-4-Reasoning/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](04-Layer-4-Reasoning/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](04-Layer-4-Reasoning/06-Improvements-Acceptance-and-Metrics/README.md) |
| Layer 5 — Executive | [Architecture](05-Layer-5-Executive/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](05-Layer-5-Executive/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](05-Layer-5-Executive/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](05-Layer-5-Executive/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](05-Layer-5-Executive/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](05-Layer-5-Executive/06-Improvements-Acceptance-and-Metrics/README.md) |
| Layer 6 — Delivery (Atlas 5.2) | [Architecture](06-Layer-6-Delivery-Atlas-5.2/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](06-Layer-6-Delivery-Atlas-5.2/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](06-Layer-6-Delivery-Atlas-5.2/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](06-Layer-6-Delivery-Atlas-5.2/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](06-Layer-6-Delivery-Atlas-5.2/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](06-Layer-6-Delivery-Atlas-5.2/06-Improvements-Acceptance-and-Metrics/README.md) |
| Layer 7 — Learning (Atlas 6) | [Architecture](07-Layer-7-Learning-Atlas-6/01-Architecture-and-Atlas-Delta/README.md) | [Expectation](07-Layer-7-Learning-Atlas-6/02-Customer-Expectation-and-HKS/README.md) | [Success/failure](07-Layer-7-Learning-Atlas-6/03-Current-Successes-Failures-and-Expected-Behavior/README.md) | [Fail closed](07-Layer-7-Learning-Atlas-6/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md) | [LLM/cost](07-Layer-7-Learning-Atlas-6/05-LLM-Use-Cases-and-Cost/README.md) | [Acceptance](07-Layer-7-Learning-Atlas-6/06-Improvements-Acceptance-and-Metrics/README.md) |

## Methodology index

| # | Artifact | Purpose |
|---|---|---|
| 1 | [Evidence authority and claim classes](00-Methodology/01-Evidence-Authority-and-Claim-Classes.md) | Prevent design, code, test, customer symptom and outcome from being conflated |
| 2 | [Layer numbering and semantic map](00-Methodology/02-Layer-Numbering-and-Semantic-Map.md) | Reconcile Atlas and runtime layer names |
| 3 | [Source and commit manifest](00-Methodology/03-Source-and-Commit-Manifest.md) | Pin every inspected source and reference boundary |
| 4 | [Customer intelligence contract](00-Methodology/04-Customer-Intelligence-Contract.md) | Define the founder-facing decision standard |
| 5 | [Status legend and audit method](00-Methodology/05-Status-Legend-and-Audit-Method.md) | Define Absent, Stub, Present, Wired, Live, Tested and Outcome-proven. "Shadow" is not an eighth state — it is shorthand for Present+Wired+Tested with `live_delivery_enabled=False` |

## Cross-layer synthesis index

| # | Artifact | Decision supported |
|---|---|---|
| 1 | [Master Atlas-vs-code coverage](08-Cross-Layer-Synthesis/01-Master-Atlas-vs-Code-Coverage-Matrix.md) | What exists, what is partial, and what is absent across all layers |
| 2 | [Typed contract and provenance](08-Cross-Layer-Synthesis/02-Typed-Contract-and-Provenance-Matrix.md) | Exact producer/consumer/identity/fail-closed obligations |
| 3 | [Four brains: storage, ownership and replay](08-Cross-Layer-Synthesis/03-Four-Brains-Storage-Ownership-and-Replay.md) | Where Expert, Organization, Behavior and Adaptive brains live and whether they influence runtime |
| 4 | [Gold-standard intelligence contract](08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md) | Minimum fields for an actionable recommendation |
| 5 | [Abstention and recovery matrix](08-Cross-Layer-Synthesis/05-Failure-Closed-Abstention-and-Recovery-Matrix.md) | When to abstain, review, park, suppress and recover |
| 6 | [LLM allocation](08-Cross-Layer-Synthesis/06-LLM-Allocation-Current-vs-Atlas-vs-Proposed.md) | Component-level model use, fallback, replay and cost |
| 7 | [Customer/application mapping](08-Cross-Layer-Synthesis/07-Customer-Application-Expectation-Mapping.md) | Translate the five reference applications into bounded system responsibilities |
| 8 | [HKS/scenario responsibility](08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md) | Assign each scenario to Layers 1–7 without silent handoff |
| 9 | [Root causes and remediation order](08-Cross-Layer-Synthesis/09-Root-Cause-Dependency-and-Remediation-Order.md) | Identify the vertical critical path |
| 10 | [Deployment blockers and design debt](08-Cross-Layer-Synthesis/10-Deployment-Blockers-and-Design-Debt.md) | Decide go/no-go boundaries and required ADRs |
| 11 | [Evaluation, ROI and health scorecard](08-Cross-Layer-Synthesis/11-Evaluation-ROI-and-Health-Scorecard.md) | Separate deterministic quality, live trust and economic proof |
| 12 | [Executive decision and phased plan](08-Cross-Layer-Synthesis/12-Executive-Decision-and-Phased-Plan.md) | Choose what to build first, what not to do, and exact exit gates |

## Golden replays

| # | Replay | Critical failure class |
|---|---|---|
| 1 | [Theresa investor reconsideration](09-Golden-Replays/01-Theresa-Investor-Reconsideration-and-Update-Cadence.md) | Material-update trigger versus fabricated rejection/urgency |
| 2 | [Boardy-mediated introduction](09-Golden-Replays/02-Boardy-Mediated-Introduction.md) | Connector versus business subject and exact action target |
| 3 | [Counterparty availability/reschedule](09-Golden-Replays/03-Counterparty-Availability-and-Reschedule.md) | Proposer/responder actor direction and supersession |
| 4 | [Already replied/cross-channel resolved](09-Golden-Replays/04-Already-Replied-and-Cross-Channel-Resolved.md) | Stale duplicate action versus request-scoped completion |
| 5 | [Internal/group meeting recap](09-Golden-Replays/05-Internal-Group-Meeting-Recap.md) | External-value eligibility versus reflexive recap |
| 6 | [Filled/closed/rejected/deferred](09-Golden-Replays/06-Filled-Closed-Rejected-or-Deferred-Relationship.md) | Lifecycle precedence and unjustified reopening |
| 7 | [Missing expertise: observation only](09-Golden-Replays/07-Missing-Expertise-Observation-Only.md) | No prescriptive action when coverage is absent |
| 8 | [Agent handoff/origin loop](09-Golden-Replays/08-Agent-Handoff-and-Origin-Loop.md) | Approval, idempotency, origin and loop prevention |
| 9 | [Client isolation/never-commercial](09-Golden-Replays/09-Client-Isolation-and-Never-Commercial.md) | Tenant ACL, purpose restriction and cost ownership |
| 10 | [Pivot/sparse behavior/adaptive expiry](09-Golden-Replays/10-Pivot-Sparse-Behavior-and-Adaptive-Learning.md) | **Current code does not pass**: explicit non-Runtime expiry is rejected, omitted expiry may publish durably, and there is no automatic short-horizon TTL/decay guard; `adaptive_ttl_unresolved` is the required [ATLAS]/[MODELLED] acceptance behavior |
| 11 | [Revenue/counterfactual proof](09-Golden-Replays/11-Revenue-Impact-and-Counterfactual-Proof.md) | Proxy inflation versus attributable external outcome |
| 12 | [Antler-shaped regional authority](09-Golden-Replays/12-Antler-Exploratory-Relationship-and-Regional-Authority.md) | Program, region, applicant-state and authority isolation |

## Reading outcome

After reading the package, the implementation decision should be unambiguous: **do not activate every new rule or increase LLM usage globally.** Build exactly one deeply authored ordinary-Sales lane first: `Sales / buying_signal / sales.sit.inbound_fit_check / sales.qualification.lead_qualification`, with `sales.market_and_targeting.icp_definition` as its named-reviewer accepted companion. Carry it through current reality → accepted expertise → gold decision → governed execution → canonical delivery → measured outcome → replayable learning. Theresa, investor, introducer and fundraising scenarios—and everything else outside verified coverage—must remain visible Observation only, review, wait, suppress or no-action.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "08-Cross-Layer-Synthesis/12-Executive-Decision-and-Phased-Plan.md" (M5.C3.L-logic.V0.U01)
-->
