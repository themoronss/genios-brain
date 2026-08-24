# Evaluation, ROI, Trust, and System-Health Scorecard

## Current verdict

At `harsh/mvp@b739bd5`, architecture and bounded tests can be scored; customer intelligence value cannot. No supplied evidence connects a recommendation to one accountable action, verified Outcome, declared Counterfactual and attributable customer value. The correct baseline is therefore **Outcome-proven: No; ROI: Unknown**, not zero value and not implied value from card volume.

The scorecard is conjunctive. A privacy leak, wrong recipient, unsupported prescription, duplicate send, stale completed loop or fabricated outcome is a release failure even if average quality is high. Weighted averages may prioritize work after hard gates pass; they cannot compensate for a critical False-action.

## Current evidence snapshot

| Dimension | Highest defensible current state | Evidence | Missing proof |
|---|---|---|---|
| Local architecture | Present/Wired varies by layer | Typed contracts and substantial deterministic implementations across L1–L7 | One authoritative typed vertical chain |
| Bounded tests | Tested in many units | L1 69 focused passed; L2 214 passed; Delivery 192 passed/11 skipped; declared documentation units green | Full baseline is red: 9 failed, 1314 passed, 39 skipped |
| Live surface | Surface symptoms observed | Supplied cards show generic reply/recap/reset, aggregation and scalar confidence | Runtime commit/config/tenant trace for every screenshot |
| Deep expertise | Present, materially partial; **zero reviewed or accepted** | Sales **46 total / 43 Stub / 3 non-stub draft-unreviewed / 0 reviewed-or-accepted**. Support **49 / 40 / 9 / 0**, with **14 authored situations / 5 routed L2 types**. Admin **57 / 57 / 0 / 0** and no executable route. Compiler remains shadow/default-off. | Named-reviewer accepted immutable closure for one scoped authoritative lane, correct abstention elsewhere, and labelled evidence that it beats legacy |
| Execution/delivery | Native execution and legacy Slack delivery are real frameworks | ExecutionObject/lifecycle/outcomes; composed legacy outbox/gate | Card claim weld, canonical v2 delivery/result and live receipt |
| Learning | Governed infrastructure, partial units with authority breaks | Validation/versioning/rollback primitives exist; direct Behavior/Adaptive cohorts are empty. Organization approval can stop without publication; stored block lists can disappear on reload; recommendation learning can emit Adaptive although Adaptive cannot carry expiry. | Review→publish→consume receipt, stored-versus-loaded policy equality, no non-expiring Adaptive authority, policy-valid safe rollback, and one-brain semantic decision delta |
| Customer Outcome | Unknown | No attributable real result supplied | Action, completion, window, external result, counterfactual and attribution |
| ROI | Unknown; current stats surface hardcodes zero | Customer target and cost model exist | Canonical ledger, real costs, baseline/control and attributable value |

## Hard release gates

| Gate | Numerator / denominator | Required threshold for promoted lane | Current state | Failure action |
|---|---|---:|---|---|
| Wrong business subject/recipient | Prescriptive outputs with wrong subject/target / all prescriptive outputs | **0** | Screenshot risk; runtime rate Unknown | Stop authority, review source/role model |
| Restricted/cross-client use escape | Forbidden evidence reaching unauthorized context/package/card/delivery/learning / attempted forbidden cases | **0** | End-to-end Unknown | Suppress, quarantine, invalidate descendants |
| Unsupported expertise prescription | Actionable outputs with Stub, draft/unreviewed, unaccepted, unreachable or uncovered capability / inputs failing any expertise-admission gate | **0** | Legacy fallback and missing review-state admission risk | Make Observation only authoritative; accepted hash/reviewer/dependency closure is required |
| Stale/completed/superseded resurfacing | Closed loops rendered/actioned / closed-loop replay cases | **0** | Surface failures observed | Cancel/suppress and repair BSO lifecycle |
| Duplicate logical execution/send/outcome | Extra executions/messages/outcomes / logical commands | **0** | Vertical proof absent | Block, reconcile, enforce idempotency/fence |
| Missing mandatory gold field | Actionable items missing subject, what-remains, evidence, expertise, stakes, alternative/stop, owner, completion or outcome window / actionable items | **0** | Current projection permits missing fields | Render non-action; fix upstream |
| Model-added authority | Model outputs changing fact/role/route/score/action/permission/lifecycle/brain / model-assisted cases | **0** | Bounded controls exist, full replay pending | Reject output; deterministic fallback |
| Unreconciled efficacy update | Positive/negative learning updates without action+external outcome / efficacy updates | **0** | Fragmented seam | Retract/quarantine proposal |
| Organization approved without publication | Approved Organization proposals lacking exactly one active brain version and later compiler-consumption receipt / approved Organization proposals | **0** | Approval API can report promoted without calling the brain publisher | Keep `approved_unpublished`; resume governed publish idempotently under current policy |
| Stored-versus-loaded policy mismatch | Learning runs whose loaded revision/hash/authority fields differ from persisted policy, including either block list / attempted runs | **0** | Loader omits `blocked_targets` and `blocked_subject_prefixes` | Abort as `policy_incomplete`; repair lossless reload before unit execution |
| Non-expiring Adaptive authority | Published, active or selected Adaptive entries without a ratified TTL/decay/supersession law / Adaptive proposals | **0** | Recommendation learning may emit Adaptive but Adaptive cannot carry expiry | `adaptive_ttl_unresolved`; publish/select nothing or use a semantically correct expiring Runtime lease |
| Unsafe rollback | Rollbacks reviving expired, prohibited, visibility-invalid or policy-invalid predecessors / rollback attempts | **0** | Exact predecessor existence alone is not current safety | Block/review rollback; select a currently valid predecessor or empty state |
| Hash-only brain influence | Selected Expert/Organization/Behavior/Adaptive mutations changing only package/snapshot/hash appearance, not the intended typed decision field or explicit no-effect / brain mutation replays | **0** | Current adapter hashes three runtime brains without consuming their values in judgment | Abstain from influence claim; require per-brain semantic decision delta or scoped no-effect receipt |
| Unexplained input loss | Inputs − explicit dispositions / inputs seen | **0** | Cross-layer accounting absent | Incident; repair no-silent-drop receipt |
| Declared golden replay skips | Skipped required cases / declared cases | **0** | Not yet executed as product replays | No release; a skip is not a pass |

## Intelligence quality and Trust scorecard

| Metric | Definition | Why it matters | Pilot target/hypothesis | Anti-gaming rule |
|---|---|---|---|---|
| Gold-contract completeness | Actionable outputs with every mandatory field / actionable outputs | Measures whether founder still has to reconstruct decision | 100% in promoted scope | Observation-only cannot be counted as actionable pass |
| Exact-open-loop accuracy | Outputs whose `what remains` matches labelled current truth / evaluated outputs | Separates intelligence from activity summaries | ≥95% after hard zero wrong-target gate | Reviewer sees full thread/current-state fixture |
| Domain/capability accuracy | Correct accepted domain/capability or correct abstention / evaluated situations | Prevents fundraising/Admin laundering into Sales | 100% on golden set | Nearest generic route counts wrong |
| Alternative quality | Decisions with materially distinct fallback/wait/stop or justified sole safe move / actionable decisions | Tests real consultation rather than template | ≥95% | Reworded same action is duplicate |
| Evidence auditability | Decisive claims reopened to exact authorized receipt/version / audited claims | Builds explainable Trust | 100% | Node dump or generic “Gmail” tag is not evidence |
| Confidence calibration | Observed correctness versus declared probability/vector bin | Prevents 94% confidence on weak expertise | Pre-register acceptable calibration error | Missing hard dimension blocks action instead of lowering average |
| Founder correction burden | Critical role/state/domain/action corrections / evaluated recommendations | Measures whether GeniOS reduces founder-as-brain work | Falling weekly; zero critical corrections before authority | Dismissals need structured reason; silence is not approval |
| Trusted-and-acted-on rate | Recommendations explicitly trusted and executed / evaluated actionable recommendations | Customer adoption signal | Baseline then sustained lift; not a standalone success metric | Must join actual execution, not button click |
| Decision-quality lift | Blinded expert/customer preference for GeniOS vs baseline action on same fixture | Measures judgment improvement | Visible within 2–4 weeks | Randomized ordering and adjudication; exclude unanswerable cases |
| Per-brain semantic decision delta | One-brain mutations producing exactly the declared change in goal, constraint, policy, candidate eligibility/rank—or an explicit justified no-effect / valid one-brain mutation replays | Proves Expert/Organization/Behavior/Adaptive knowledge shaped judgment rather than package/hash appearance | 100% typed expected delta or explicit no-effect in promoted lane | New `brain_snapshot_id`, package ID, manifest version or knowledge hash alone scores zero |

## False-action and attention scorecard

A **False-action** is an action surfaced, claimed, executed or delivered that should have been suppressed, stopped, deferred, reviewed, or targeted elsewhere under current truth. It is more damaging than a missed low-value observation because it spends customer attention and can harm a relationship.

| False-action class | Example | Rate denominator | Release target | Cost recorded |
|---|---|---|---:|---|
| Wrong target/role | Reply to Boardy instead of introduced contact | Actionable decisions | 0 | Human correction + relationship harm review |
| Already resolved | Reminder after reply in another channel | Open-loop decisions | 0 | Attention minutes + duplicate outreach |
| Unsupported prescription | Investor/Admin advice from generic Sales | Uncovered inputs | 0 | Review/recovery time |
| False completion | “I’ll do it” or provider accepted treated as done | Claims/executions | 0 | Hidden unfinished work |
| Duplicate send | Retry after ambiguous provider acceptance | Logical deliveries | 0 | Provider cost + recipient interruption |
| Low-value interruption | Generic recap/follow-up with no stakes | Displayed/actionable items | Threshold only after critical zeros; compare net benefit | View/dismiss/act time |
| Agent loop | Agent-origin webhook triggers another agent run | Agent executions | 0 | Tokens/tools/side effects |

Track `net_attention_value = attributable_or_conservatively_assisted_value - founder/team correction time - reminder/escalation time - false-action recovery - model/provider/agent cost`. A higher card count is not a positive metric.

## Execution, Delivery, and Learning health

| Metric | Correct calculation | Healthy gate | Current limitation |
|---|---|---|---|
| Acceptance→execution weld | Commands producing exactly one valid ExecutionObject / accepted commands | 100% or explicit `accepted_unclaimed` | Parallel card/native paths |
| Execution completion integrity | Completions with scoped post-creation success receipt / completed executions | 100% | `completed_unproven` must stay neutral |
| Delivery reconciliation | Terminal/unknown canonical results / materialized actions | 100%; unknown has owner/SLO | Legacy/v2 result split |
| Send-time authority freshness | Sends revalidated against current graph/decision/policy / sends | 100% | Reminder path weaker than card path |
| Duplicate external impression | Extra provider messages / logical deliveries | 0 | Ambiguous timeout proof incomplete |
| Canonical outcome completeness | Eligible outcomes with recommendation, action, delivery, external result, window and identity / outcomes | 100% for efficacy cohort | Ledgers fragmented |
| Feedback ingestion | Supported verdict revisions with learning disposition / verdict revisions | 100% | Direct feedback unit empty |
| Learning support validity | Promoted proposals passing independent source/day/entity/use gates / promotions | 100% | Population/sensitivity policy incomplete |
| Organization approval→publish | Approved Organization proposals with exactly one active brain version and publisher transition / approved Organization proposals | 100%, or durable `approved_unpublished` with owner/SLO | Approval route updates learning state but does not call `publish_brain` |
| Policy reload equality | Runs where stored and loaded revision, canonical hash and every authority field—including both block lists—match / attempted runs | 100%; mismatch aborts before units | Stored restrictions can reload as empty defaults |
| Adaptive lifecycle validity | Adaptive proposals with ratified expiry/decay, pivot invalidation, supersession and selector enforcement / Adaptive proposals | 100%; otherwise zero publication | Adaptive cannot carry expiry under current `LearningObject`; no non-expiring Adaptive may become authoritative |
| Publish→compile consumption | Active learned versions appearing in intended future package / active versions | 100% | Consumption proof absent |
| Per-brain intended decision change | Consumed versions changing only the expected typed decision dimension, or recording justified scoped no-effect / tested consumed versions | 100%; package/hash-only change is failure | No vertical semantic replay yet |
| Safe rollback | Rollbacks restoring a predecessor valid under current expiry, policy, visibility/use and evidence / rollback attempts | 100%; otherwise empty/disabled state | Existing primitive may find predecessor without full current-law proof |
| Correction-to-clean latency | Time until all affected descendants suspended/recomputed | Defined SLO by severity | Retraction chain incomplete |
| Empty-seam/run health | Runs exposing coverage/freshness/empty reason / runs | 100% | Green no-op sweep possible |

## Counterfactual and attribution contract

Every value evaluation row must be created before or at decision time where possible:

| Counterfactual field | Required value |
|---|---|
| Situation/opportunity ID | One bounded current business object |
| GeniOS recommendation/version | Exact decision, package/brain/config versions and timestamp |
| Otherwise-action | What human/agent would have done without GeniOS: action, wait, unknown, or baseline policy |
| Acceptance state | Accepted, modified, rejected, unseen; button click is only intent |
| Actual action | What was performed, by whom, when, under which execution |
| Delivery/exposure | Whether target actually received/was exposed; ambiguous remains unknown |
| Declared Outcome/window | Reply, meeting, stage change, retention, time saved, etc., and measurement deadline |
| Alternative causes | Other campaigns, product changes, market events, founder action and world changes |
| Attribution class | `caused`, `assisted`, `associated`, or `unknown`, with confidence/evidence |
| Value/cost | Conservative realized value plus labor/model/provider/agent/attention cost |

Only `caused` and an explicitly weighted portion of `assisted` may enter attributable value. `Associated` and `unknown` stay visible but do not inflate ROI.

## Customer and economic Outcome scorecard

These are **customer hypotheses from the supplied requirement**, not current achievements.

| Outcome metric | Baseline/control | Proposed customer target | Minimum evidence window | Current proof |
|---|---|---|---|---|
| High-value lead prioritization accuracy | Prior manual/agent ranking on same eligible set | +20–30% better | Labelled rolling set, blinded adjudication | Unknown |
| Conversion/resolution lift on recommended actions | Comparable control/baseline | 10%+ relative lift | Approximately 60 days with sufficient sample | Unknown |
| Would-have-missed opportunities | Pre-registered otherwise-action was no action/lower priority | 2–4 meaningful advances/closes per month | Monthly, each with receipts | Unknown |
| Decision/agent quality | Blinded before/after or control rating | Visible improvement | 2–4 week design-partner window | Unknown |
| Time saved | Measured coordination/context/correction time baseline | Positive net hours after management burden | Weekly | Unknown |
| Churn/expansion result | Comparable eligible cohort | Directional improvement; target pre-registered by pilot | 60–90+ days depending outcome | Unknown |
| Revenue/cost ROI | `(attributable incremental value + verified saved cost - fully loaded GeniOS cost) / fully loaded GeniOS cost` | Customer minimum 5–10× versus $100/month ($500–$1,000+ value) | 60–90 days | Unknown; value API hardcodes zero |

## System-health and Cost metrics

| Family | Metric | Required segmentation |
|---|---|---|
| Source | Coverage, freshness, cursor lag, poison/retry, revision/deletion reconciliation | Tenant, source, capability, visibility/use |
| Context | BSO validity, role conflict, synthetic fallback, completeness, correction rebuild lag | Domain, situation, relationship/thread |
| Expertise | Total/Stub/non-stub-draft/reviewed-or-accepted counts; authored situations/routed types; all-stub/unrouted routes; review age; accepted hash/dependency closure; authoritative/shadow/legacy packages; unsupported and draft/unreviewed abstention | Domain, situation, capability/version, reviewer, tenant/cohort, authority mode |
| Reasoning | Abstention, candidates, elimination reason, gold completeness, generic-imperative rate | Manifest/version, scenario, authority mode |
| Executive | Accepted-unclaimed, approval wait, dependency block, completion-unproven, expiry/cancel | Owner/agent, action type, capability |
| Delivery | Materialization, defer/suppress, attempts, unknown provider, duplicates, dead letters | Adapter, route, policy/config, worker version |
| Learning | Input seam health; proposal disposition; support failure; `approved_unpublished` count/age and approval→publish latency; stored-loaded policy hash/field equality and lost-block-list count; Adaptive-without-lifecycle and post-expiry selection; publish→consume latency; per-brain semantic delta/no-effect; safe/blocked rollback; correction/retraction latency | Unit, brain target/entry/version, policy revision/hash, population/use class, decision/package version, failure reason |
| LLM | Eligible events, physical calls/attempts, tokens, cache, repair, latency, validation failure, configured/provider Cost | Component, model/prompt/schema/policy, tenant/use |

## Pilot evaluation design

1. Pin the first Sales pilot key exactly as **`Sales / buying_signal / sales.sit.inbound_fit_check / sales.qualification.lead_qualification`**, with **`sales.market_and_targeting.icp_definition`** as the required companion and every retained dependency named-reviewer accepted at its immutable hash. Keep Theresa, investor, introducer and all fundraising scenarios **Observation only**, alongside Admin/investing, and outside the promotion denominator.
2. Record baseline decision and otherwise-action before revealing GeniOS output.
3. Blind-adjudicate subject, current loop, domain, action, alternatives, evidence and completion.
4. Weld accepted actions to execution/delivery and collect external outcomes through the declared window.
5. Include negative, ignored, never-delivered, modified, stopped and world-cancelled cases.
6. Report confidence intervals and sample size; do not market a percentage from a tiny cohort.
7. Run hard-gate replays continuously. One critical privacy/wrong-target/duplicate breach pauses authority.
8. Publish both numerator and denominator for every claim; preserve Unknown instead of coercing it to zero or success.

## Exit decision

The system becomes **conditionally trustworthy** for one named scope only when all hard gates are green with zero skips, gold-contract completeness is 100%, False-action critical classes are zero, execution/delivery/outcome accounting reconciles, restricted evidence never escapes, and customer corrections trend down. It becomes **Outcome-proven** only after the real Counterfactual pilot shows a credible improvement and ROI with full costs and attribution. Until then, Trust must come from honest coverage, visible abstention and reproducible receipts—not from a high scalar confidence or polished card.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "09-Root-Cause-Dependency-and-Remediation-Order.md" (M5.C1.L-integration.V2.U01)
include "07-Customer-Application-Expectation-Mapping.md" (M5.C1.L-integration.V0.U01)
-->
