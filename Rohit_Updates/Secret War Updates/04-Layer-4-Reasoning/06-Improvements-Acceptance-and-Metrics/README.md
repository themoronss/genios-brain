# Layer 4 — Improvements, Acceptance, and Metrics

**Starting point:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. The core decision maker supports candidates, hard elimination, total-order ranking, confidence floors and typed abstention. The active legacy/default adapters commonly supply one play and six units; API/card projection uses generic imperatives, maps score to confidence, and allows `stakes: missing` plus `completion: missing`.

## Improvement strategy

Fix Layer 4 as a decision pipeline, not as a copywriting exercise. First make it impossible to emit a prescriptive card without a complete decision object. Then enrich candidate generation and schedule the reasoning units that compare, challenge and validate those candidates. Finally expose the decision faithfully and measure whether it changes correct actions and outcomes.

The unit registry does not need a ceremonial “enable all 17” switch. Each promoted domain/situation should declare a versioned manifest containing the units needed for that decision class. The trace must prove what executed. A unit is valuable only if its input is complete and its output changes a tested decision.

## Prioritized improvement backlog

| Priority | Improvement | Current defect | Concrete change | Metric | Acceptance |
|---:|---|---|---|---|---|
| P0 | Make abstention authoritative end to end | API/legacy fallback can render generic imperative after core defer | Propagate typed `NO_ACTION`/`DEFER`/`INSUFFICIENT_CONTEXT`/`BLOCKED`; prohibit action projection | Unsupported prescription rate | **0** |
| P0 | Require stakes and completion | `api/routes.py:2056-2098` carries both as missing while action survives | Decision/card schema gate blocks prescriptive result unless both are concrete | Prescriptive cards missing stakes/completion | **0** |
| P0 | Separate score vector | `api/intelligence_routes.py:503-527` maps card score to confidence | Independent priority, urgency, coverage and calibrated confidence fields; no aliases | Score-confidence semantic violations | **0** |
| P0 | Enforce exact unresolved object | Generic “reply” produced without request/commitment | Require typed remaining-loop id, subject, target and current state | Generic imperative rate | **0** in promoted scope |
| P0 | Preserve hard constraints | Empty/missing constraints look passed | Declare mandatory constraint classes per manifest; absent means defer | Winner with missing mandatory constraint | **0** |
| P0 | Make four-brain values semantically consumable | `reason/adapters/expertise.py:180-213` puts Organization, Behavior and Adaptive values in `knowledge_hash`/version but not goal, constraints, policies, candidate eligibility or ranking | Define typed, authority-bounded consumers: Company constrains permission/policy; Behavior may rank permitted working-style choices; Adaptive may tune bounded timing/priority; every selected entry emits effect or no-effect receipt | Selected brain entries with unexplained semantic effect | **0** |
| P1 | Generate candidate set from deep plays | Legacy adapter supplies one generic play | Layer 3 supplies accepted plays; builder creates primary, fallback and wait/stop candidates | Decisions with ≥2 materially distinct eligible options | Target by scenario; exceptions traced |
| P1 | Expand and disclose Expert artifact consumption | Adapter uses the first capability question and only `expert_rules.definition.steps`, caps plays at four, and otherwise falls back to generic review | Add typed mappings for accepted heuristics, mental models and failure patterns; define deterministic play ordering/truncation; keep generic fallback review-only | Accepted Expert artifacts consumed or explicitly rejected | 100% receipt coverage |
| P1 | Schedule comparison/challenge units | Default DAG omits alternative/trade-off/validation/recommendation | Versioned scenario manifests include required units and unit receipt | Manifest execution coverage | 100% expected units |
| P1 | Semantic alternative dedup | Rephrased actions can appear distinct | Canonical candidate semantic key: strategy, target, channel, timing, asset, trigger | Duplicate candidate rate | <1% golden suite |
| P1 | Candidate rejection receipts | User cannot see why other moves lost | Persist constraint/evidence/rejection per candidate | Selected decisions with auditable rejection | 100% |
| P1 | Lossless card projection | Rich decision fields disappear into templates | Build card only from DecisionObject; prohibit generic synthetic ask steps | Critical-field round-trip | 100% |
| P1 | Canonical open-loop dedup | Delivery idempotency does not consolidate semantic decisions | Key by tenant + relationship/opportunity + unresolved object + state version | Duplicate authoritative cards per loop | **0** |
| P2 | Bounded ambiguity consultation | Hard ambiguous cases either generic or deferred | Atlas-permitted LLM consultation proposes questions/hypotheses; deterministic rerun decides | Correctable defer recovery | Lift without false prescriptions |
| P2 | Calibrate confidence/outcome | Decorative percentage lacks empirical meaning | Reliability curves by decision class and evidence bucket | Expected calibration error | Threshold set from pilot |
| P2 | Portfolio prioritization | Each card can claim urgency independently | Rank accepted decisions across scarce owner/time/dependencies | Impossible simultaneous commitments | **0** critical conflicts |

## Golden acceptance replays

| Golden scenario | Expected decision | Required alternatives/rejections | Completion and outcome | Exit gate |
|---|---|---|---|---|
| Theresa has a material milestone after requested updates | Send one milestone-specific update tied to reconsideration context | Wait if no new value; connector nudge only if permission/cadence supports it; reject “last chance” | Delivered to Theresa; reply/reconsideration window | Exact role/request/history, no fabricated rejection, expert-approved ranking |
| Theresa has no material new information | `NO_ACTION` until a material update/explicit cadence trigger | Repetitive follow-up rejected for low value/relationship cost | Observation trigger, not fake completion | No action card/button |
| Boardy introduces A and B | Separate decision for A and B; Boardy connector only | Direct contact vs permission-safe connector help vs close | Per-contact reply/meeting/outcome | No cross-intro evidence; zero Boardy-target mistakes |
| Calendar invite is cancelled/no-show | No recap; reschedule only if objective still valid | Recap rejected for no occurrence; wait/close considered | New accepted meeting or closed loop | 100 mutated calendar cases suppress false recap |
| External meeting occurred with promised deck | Deliver exact deck to named counterpart by agreed date | Clarify scope or renegotiate deadline; generic recap rejected | Receipt/acceptance of deck; opportunity movement window | Decision contains owner, approval, due time and external completion |
| User availability was superseded | `NO_ACTION` on old proposal | Current booked meeting retained; old deliver candidate rejected | Supersession itself closes proposal loop | No overdue card |
| High-value but ambiguous prospect identity | `DEFER` to role/entity review before contact | All recipient actions rejected | Identity resolved; then re-reason | Value cannot override identity gate |
| Restricted support complaint suggests expansion | Resolve support; commercial candidate blocked absent permission | Consent request only if policy allows; Sales outreach rejected | Support resolution and satisfaction window | Narrowest purpose/visibility preserved |
| Bank-details email | Verify out of band plus dual approval or block | Direct payment/update rejected | Verified approval and ledger acknowledgement | Zero unsafe action across spoof variants |
| One safe action exists | Select it with explicit elimination of every alternative | Trace shows legal/policy infeasibility, not fake alternatives | Action-specific completion | Sole-candidate exception mechanically justified |
| All candidates below floor | `DEFER`, selected candidate absent | Evidence-acquisition questions only | New evidence triggers fresh decision | No presentation fallback imperative |
| Same loop appears from Gmail and calendar | One authoritative decision with both receipts | Duplicate card rejected/merged by canonical key | Shared completion/outcome | Exactly one active decision |
| Four-brain semantic **brain mutation replay** | Hold BSO, corpus and three brains fixed; mutate exactly one selected brain entry | Company approval mutation must block/require approval; Behavior cadence may reorder only permitted candidates; Adaptive timing may alter only bounded timing/priority; inapplicable mutation must preserve decision with explicit no-effect | Trace records old/new snapshot, consumed entry, semantic field delta and unchanged protected fields | A hash/version change without intended semantic delta fails; unauthorized cross-axis delta fails |
| Expert consumption mutation matrix | Change capability question, a steps-bearing rule, a rule without steps, a failure pattern and add a fifth eligible play independently | Question may change goal; steps rule may change play; every other class must have typed effect or explicit rejection; four-play truncation must identify skipped IDs and policy | Decision trace links each effect/rejection to source artifact | No silent inert accepted artifact and no generic fallback with prescriptive authority |

## Decision quality metrics

| Metric | Definition | Why it matters | Promotion target |
|---|---|---|---|
| Unsupported prescription rate | Prescriptive decisions where domain/role/evidence/constraints are incomplete | Direct trust/safety failure | **0%** |
| Decision completeness | Decisions with remaining loop, stakes, expiry, owner/approval, completion and outcome window | Ensures action is usable | 100% prescriptive |
| Action specificity | Recipient + action + asset/content + channel + timing + completion populated | Measures “zero reconstruction” | 100% where applicable |
| Alternative distinctness | Candidate pairs materially different by strategy/trigger/channel/timing | Detects fake choice | ≥99% distinct in golden suite |
| Abstention precision | Abstentions that truly lacked safe decision | Avoids useless caution | Expert-labelled threshold per lane |
| Abstention recall | Unsafe/unsupported cases correctly abstained | Prevents false certainty | 100% critical HKS |
| Hard-gate escape rate | Winner violating permission/role/mandatory constraint | Core invariant | **0%** |
| Brain semantic-consumption coverage | Selected four-brain entries with a typed effect or explicit deterministic no-effect receipt / all selected entries | Separates actual judgment from hash-only provenance | 100% promoted decisions |
| Hash-only manifest mutation rate | Brain mutations that change manifest hash/version but yield neither intended semantic delta nor explicit no-effect reason | Detects fake adaptation | **0%** |
| Expert artifact consumption coverage | Accepted Expert artifacts mapped to goal/play/constraint/candidate/rejection or explicit unsupported reason | Prevents corpus presence from masquerading as judgment | 100% in promoted capability versions |
| Score semantic integrity | API/UI fields preserve priority, urgency, coverage, confidence meanings | Prevents metric laundering | 100% schema tests |
| Confidence calibration | Predicted confidence versus correctness by decision class | Makes percentage meaningful | Monitored reliability curve; bounded ECE |
| Generic imperative rate | Cards reducible to reply/follow-up/recap/reset without specifics | Measures current symptom | **0%** promoted scope |
| Semantic decision duplicate rate | Multiple active decisions for canonical open loop | Prevents clutter/conflict | **0%** |
| Founder correction burden | Role/state/action corrections per delivered decision | Measures actual cognitive relief | Declining; zero critical corrections |
| Decision acceptance quality | Accepted unchanged / modified / rejected with reason | Diagnoses fit, not vanity clicks | Cohort baseline then improvement |
| Completion verification | Accepted decisions with externally observed completion | Keeps intent separate from result | 100% before learning success |
| Outcome lift | Business result versus recorded counterfactual/window | Proves value | Pilot target pre-registered |

## Implementation sequence

1. Define the authoritative DecisionObject-to-card contract and delete/disable prescriptive fallback when required fields are absent.
2. Correct score/confidence/urgency/coverage semantics at API and UI boundaries.
3. Add canonical unresolved-loop and candidate semantic keys.
4. Create scenario-specific manifests with mandatory units and constraint classes.
5. Add typed four-brain semantic consumers and per-entry effect/no-effect receipts; a hash change alone is never acceptance.
6. Feed multiple accepted Layer 3 plays; disclose steps-only eligibility, deterministic ordering, the four-play cap, skipped IDs and generic fallback source.
7. Add golden/mutation tests for each brain, each Expert artifact class, HKS, abstention and lossless projection.
8. Shadow against legacy using expert-labelled expected decisions, not parity alone.
9. Promote a narrow cohort with decision/package/manifest receipts and kill switch.
10. Reconcile execution, completion, outcome and counterfactual before widening scope.

## Exit gate

Layer 4 is **conditionally trustworthy** only for a named promoted scenario when every prescriptive output has a valid accepted Layer 3 package, exact remaining loop, complete mandatory constraints, materially distinct candidates or a justified sole-candidate exception, rejection trace, separated score vector, stakes, expiry, owner/approval, observable completion and outcome window; abstention survives through the card; semantic duplicates are absent; the expected manifest actually executes; the four-brain mutation matrix proves each selected entry's intended semantic effect or explicit no-effect; Expert artifact consumption and four-play truncation are fully receipted; all critical HKS mutations pass; and scoped evaluation shows expert-correct decisions without increased false prescription. All other scenarios remain shadow or fail closed.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M3.C2.L-logic.V0.U01)
include "../05-LLM-Use-Cases-and-Cost/README.md" (M3.C2.L-logic.V1.U01)
-->
