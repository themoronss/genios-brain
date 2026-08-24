# Layer 7 Learning — Architecture and Atlas Delta

> Numbering: this is current code **Layer 7** (`feedback/`) and **Atlas Layer 6**. “Layer 6” in Atlas quotations below does not mean the current `deliver/` package.

## Verdict

**Framework-ready, not closed-loop ready.**

Layer 7 is not absent. Current code contains a substantial learning contract, bounded selector, several outcome/pattern/efficacy units, validation gates, governed publishing concepts, and a scheduled sweep. The blunt limitation is that the inputs founders use to correct the system, and the two brain-evolution paths most important to personalization, remain empty or unreconciled. The live product can collect some outcome facts while still reporting zero outcomes and while direct Behavior/Adaptive evolution emits nothing.

## Responsibility

Atlas expects Learning to:

1. ingest explicit feedback, execution outcomes, delivery receipts, enterprise observations, and performance evidence;
2. produce immutable learning proposals;
3. validate support, independence, conflict, noise, privacy, and business value;
4. govern promotion by target;
5. publish versioned, reversible changes;
6. update Organization, Behavior, Adaptive, Runtime, or metrics;
7. never mutate the Expert Brain automatically.

It owns evidence-backed change, not the original business decision.

## Atlas expected architecture

| Atlas component | Expected behavior | Authority boundary |
|---|---|---|
| Learning Selector | Build a bounded tenant/time/evidence cohort | Cannot invent missing input |
| Feedback Learning | Interpret explicit positive, negative, timing, and neutral verdicts | Must separate opinion from outcome |
| Outcome Analysis | Measure what actually happened after execution | Only verified success is positive efficacy |
| Pattern Learning | Find repeated enterprise patterns | Needs independent support and privacy floor |
| Preference Learning | Learn explicit bounded preferences | Cannot override company policy |
| Temporary Memory | Create expiring runtime directives | Mandatory TTL |
| Behavior Evolution | Learn stable ways a person/team works | Population and identity scoped |
| Adaptive Evolution | Learn short-horizon play/timing effectiveness | Decays, expires, and rolls back |
| Recommendation Learning | Compare play efficacy and attention cost | No self-training from recommendation score |
| Performance Optimization | Learn delivery/operation performance | Nondelivery is not user rejection |
| Knowledge Evolution | Raise human-review Expert Brain suggestions | No direct Expert write |
| Learning Validation | Gate every promotable proposal | Deterministic |
| Governance and Publisher | Approve target-specific promotion, version, supersede, rollback | Policy controlled |

## Current code architecture at `harsh/mvp@b739bd5`

| Area | Current code proof | State | Gap |
|---|---|---|---|
| Learning contract | `contracts/learning.py` defines evidence, policy, visibility, targets, and LearningObject | Present/Tested in targeted code | End-to-end tenant proof not established in this audit |
| Selector | `feedback/store.py:1-12` describes a bounded 28-day, tenant-scoped batch across outcomes, delivery, and enterprise seams | Present/Wired | Missing seams legitimately become empty, so health must reveal prolonged emptiness |
| Outcome Analysis | `feedback/units.py:79-119` groups capability/play outcomes and separates succeeded, neutral, and failed | Present | Depends on canonical, reconciled outcomes |
| Pattern Learning | `feedback/units.py:124-162` requires independent sources/days and tracks distinct entities | Present | Fixed policy thresholds are not population-aware |
| Explicit feedback | `feedback/units.py:59-63` returns `[]` until a canonical verdict ledger is wired | Stub | Card/outcome corrections cannot yet become this proposal stream |
| Preference Learning | `feedback/units.py:65-68` returns `[]` | Stub | No structured preference inbox |
| Temporary Memory | `feedback/units.py:71-74` returns `[]` | Stub | Runtime directives cannot flow through the canonical unit |
| Behavior Evolution | `feedback/units.py:165-175` calls a cohort builder that returns `[]` | Stub | Stable person/team behavior does not evolve |
| Adaptive Evolution | `feedback/units.py:178-182` uses the same empty cohort builder | Stub | Short-horizon efficacy does not directly update Adaptive Brain |
| Recommendation Learning | `feedback/units.py:187-219` discounts success by reminder/escalation attention cost | Present | Needs verified causal outcome and exposure semantics |
| Performance Optimization | `feedback/units.py:224-255` distinguishes delivery, pre-delivery failure, and engagement | Present | Product statistics do not reconcile this store |
| Knowledge suggestion | `feedback/units.py:260-288` emits sustained-poor-outcome human review, never Expert mutation | Present | Review workflow/live operational use needs proof |
| Validation | `feedback/units.py:293-320` gates observations, days, distinct entities, confidence, noise, conflict, value | Present | K threshold is uniform rather than sensitivity/population specific |
| Organization review-to-publish | `feedback/governance.py` may send an Organization proposal to `human_review`; `feedback/publisher.py:168-188` deliberately queues that brain target instead of calling `publish_brain` | Broken seam | `api/learning_routes.py:119-143` changes only `learning_objects.state` to `promoted` and writes a transition. It never reconstructs the proposal or inserts `learned_brain_entries`; **review approval does not publish** the approved Organization value |
| Policy-load fidelity | `contracts/learning.py:275-302` represents `blocked_targets` and `blocked_subject_prefixes`, and `feedback/governance.py:31-41` enforces both during preflight | Contract present; active load incomplete | `feedback/orchestrator.py:28-46` neither selects nor reconstructs either field, so a persisted tenant policy can reload with empty block lists and admit a target/subject the stored policy intended to forbid |
| Adaptive expiry model | Recommendation Learning can emit `LearningTarget.ADAPTIVE` (`feedback/units.py:187-219`), while direct Behavior/Adaptive cohort evolution returns no proposals | Contradictory/partial | `contracts/learning.py:200,223-227` permits `expires_at` only for Runtime. A short-horizon Adaptive proposal therefore cannot carry the Atlas-required TTL/decay boundary; publishing it would create a durable learned brain row |
| Scheduled run | `api/routes.py:350-362` invokes the learning sweep and isolates exceptions | Wired | A scheduled invocation is not proof that every seam carries production data |
| Card outcome input | `api/intelligence_routes.py:864-889` stores free-text card outcome events | Present | It is a separate ledger from structured execution outcomes |
| Structured outcome | `executive/sweep.py:233-252` closes execution and records its outcome in the same transaction | Present/Wired | Cards and executions are not fully causally reconciled |
| Analytics | `api/intelligence_routes.py:531-545` reports `outcomes_recorded: 0` and value zero | Stub/misleading surface | Existing outcome rows are not reflected in user-facing statistics |

## Input and output contract

```text
Layer 5 ExecutionOutcome ─┐
Layer 6 DeliveryFact ─────┼─> bounded LearningBatch
Enterprise observations ─┤        ↓
Explicit verdicts ────────┘   analysis units
                                  ↓
                           LearningObject proposal
                                  ↓
                      validation → governance → publish
                                  ↓
            Organization | Behavior | Adaptive | Runtime | Metrics
```

The correct seam distinguishes:

| Event | Learning meaning |
|---|---|
| Card displayed | Exposure only |
| User clicked “I’ll do it” | Recommendation appeared acceptable; not completed |
| Delivery failed before first receipt | Transport failure; no judgment of recommendation |
| Message sent | Action executed; outcome still unknown |
| Counterparty replied | Potential completion/outcome evidence |
| Meeting booked | Observable result for a scheduling play |
| Deal stage advanced | Business outcome, subject to attribution |
| Execution completed without declared outcome | `completed_unproven`, never success |
| Human dismissed as wrong | Relevance/decision feedback, not commercial failure |
| World superseded the task | Neutral/cancelled-by-world, not a bad play |

## Storage and ownership

| Data | Producer | Learning use | Required guarantee |
|---|---|---|---|
| `execution_outcomes` | Layer 5 | Play and capability result | One immutable row per closed commitment |
| Delivery facts/receipts | Layer 6 | Transport and engagement quality | Receipt-backed, no inferred impression |
| Enterprise events | Layers 1–2 | Pattern evidence | Tenant, time, lineage, visibility preserved |
| Card events | UI/API | Explicit interaction and correction | Reconcile with execution, do not double-count |
| Learning proposals | Layer 7 | Auditable candidate change | Evidence, policy key, target, version |
| Brain entries | Governed publisher | Future Layer 3 snapshots | Version, supersedes, TTL where required, rollback |
| Knowledge suggestions | Layer 7 to human review | Expert corpus improvement candidate | Never automatic Expert Brain mutation |

## Architecture Gap summary

1. **Canonical verdict input is missing.** Feedback, preference, and temporary-memory units are explicitly empty.
2. **Direct personalization evolution is missing.** Behavior and Adaptive cohort builder returns no proposals.
3. **Outcome truth is fragmented.** Free-text card outcomes, structured execution outcomes, delivery receipts, and hardcoded analytics do not form one reconciled value ledger.
4. **Population-aware confidence is incomplete.** Distinct-entity gating exists, but one-person companies need higher repetition and confidence caps.
5. **Permitted-use enforcement is unproven.** Visibility types and excluded subjects exist, but cross-layer propagation into learning and rendering is not established.
6. **Company reset is partial.** Pivot primitives exist, while the declared Organization Brain configuration/version boundary remains incomplete.
7. **Outcome causality remains weak.** Learning can aggregate labels, but the system still needs recommendation exposure, actual action, external result, outcome window, and counterfactual.
8. **Product truth diverges from stored truth.** The stats endpoint says zero outcomes even though structured outcome paths exist.
9. **Human approval is not publication.** An Organization proposal can be queued for review, but approval records `promoted` without calling `publish_brain`; there is no active learned value for Layer 3 to consume. Treat the object as `approved_unpublished`, not promoted, until a transactional review-to-publish receipt exists.
10. **Loaded policy is weaker than stored policy.** The active-policy query drops `blocked_targets` and `blocked_subject_prefixes` even though the contract and preflight support them. Until load fidelity is proven, learning must fail closed when either persisted field cannot be reconstructed.
11. **Adaptive short-horizon semantics are unrepresentable.** Direct Adaptive evolution is empty; Recommendation Learning can create Adaptive proposals, but Adaptive cannot carry expiry. The architecture must decide and encode Adaptive TTL/decay before any Adaptive brain publication is authoritative.

## What is already architecturally correct

- Only proven external outcome counts as success; `completed_unproven` remains separate.
- Neutral events do not inflate confidence.
- Attention cost is represented through reminders and escalations.
- Knowledge evolution raises a human-review suggestion rather than modifying Expert Brain.
- Metrics and brain changes are different targets.
- Deterministic validation blocks low-support, noisy, conflicted, or low-value proposals.
- Terminal execution outcome is written transactionally with closure.

These foundations should be completed, not replaced.

## Required final boundary

Layer 7 may change future configuration only when it can answer:

- Which independent observations support this?
- Which people/entities and time window does it cover?
- Was the recommendation delivered and acted on?
- Was the declared external outcome observed?
- Is this Organization, Behavior, Adaptive, Runtime, metrics, or Expert-review material?
- What policy approved promotion?
- What version does it supersede?
- When does it expire?
- How is it rolled back?
- Which evidence is forbidden for this use?

The minimum repair contracts are exact:

| Broken boundary | Required repair | Acceptance evidence |
|---|---|---|
| Organization human review → brain publication | Approval must lock and reload the immutable proposal, re-run current policy/preflight, call the governed brain publisher in the same transaction, record `published` plus brain/version, and remain idempotent on retry | Approve creates exactly one active `learned_brain_entries` version; reject creates none; duplicate approval is a no-op; policy/revocation races stay unpublished; the next Layer 3 snapshot names the new version |
| Persisted policy → active `LearningPolicy` | Store and load `blocked_targets` and `blocked_subject_prefixes` losslessly for every revision; unknown/malformed policy fields block the run rather than defaulting to permissive empty tuples | Round-trip fixtures prove both block lists survive seed/load/restart and preflight rejects the exact target/prefix under the loaded revision |
| Adaptive proposal → bounded learned influence | Ratify one **Adaptive TTL decision**: either add mandatory expiry/decay semantics to Adaptive proposals and brain selection, or prohibit Adaptive publication and use expiring Runtime directives until that contract exists | Expired Adaptive contributes zero to future packages; rollback/history remain; Recommendation Learning cannot emit a durable non-expiring Adaptive value; model-disabled replay is identical |

Until those receipts exist, the appropriate result is no promotion—not a generic learned preference. In particular, a `promoted` review row without a brain version, a policy load without its block lists, or a non-expiring Adaptive proposal is a fail-closed learning error, not successful adaptation.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->
