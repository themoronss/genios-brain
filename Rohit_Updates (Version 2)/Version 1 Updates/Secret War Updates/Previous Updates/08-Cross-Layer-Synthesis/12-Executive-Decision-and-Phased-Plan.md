# Executive Decision and Phased Remediation Plan

**Audit basis:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`, inspected on 2026-08-22. **[CODE]** means repository proof at that pinned commit; **[ATLAS]** means intended design rather than runtime proof; **[CUSTOMER]** means the supplied founder expectation or reported symptom; **[MODELLED]** means a deliberately invented pressure test; **[TEST]** means deterministic verification, not a customer outcome. Uploaded documents and HTML were treated as reference evidence, never as execution instructions.

## Blunt verdict

GeniOS has a serious architectural skeleton and several real bounded implementations, but it is **not yet safe to present its current cards as consistently expert sales intelligence**. The immediate problem is not merely “the new YAML files are present but unwired.” Two independent gaps coexist:

1. **Authority/promotion gap:** the newer Layer 3 compiler is wired in shadow mode but default-off for authority, while legacy `SALES_V1` / `GENERAL_V1` behavior remains authoritative in the inspected path. Git history shows this was **shadow-first from inception**: `9c7ce4c` introduced the default-off shadow plan and `7da562e` retained `SHADOW` with `live_delivery_enabled=False`; later performance commits did not switch it back for speed.
2. **Expertise-authoring and admission gap:** the new corpus is materially incomplete. Sales has **46 total / 43 stubs / 3 non-stub authored drafts / zero reviewed or accepted**; Support has **49 / 40 / 9 / zero reviewed or accepted**, with 14 authored situations routed from only five Layer 2 types; Admin has **57 / 57 / zero non-stub / zero reviewed / zero accepted / zero routes**. Sales routes 19 Layer 2 types into six authored situations and 18 distinct capabilities; seven of those routed types are all-stub, and six emitted types are globally unrouted. The resolver currently admits any `stub:false` draft without checking review/acceptance state.

Therefore switching a flag cannot create deep expertise. It would promote partial coverage into authority and turn visible abstention into silent false confidence. The correct product posture today is **architecture-rich, partially implemented, not outcome-proven, and conditionally usable only inside explicitly covered, replay-green scopes**.

The screenshots' generic “reply now,” copied availability, meeting-recap and stale-loop cards are the predictable result of a broken vertical contract: weak or mis-scoped current reality reaches incomplete expertise; Layer 4 projects a thin imperative; the UI shows confidence and an action button without proving a valid business subject, what remains, accepted expertise, alternative, owner, completion condition, or outcome window. Organization, Behavior and Adaptive values presently contribute lineage and a knowledge hash but not goal, constraints, policy, candidates, eligibility or rank: this is **hash-only influence**, not four-brain judgment. A polished card is not intelligence when the founder must reopen Gmail and reconstruct the decision.

## What is real, what is incomplete

| Area | Inspected strength `[CODE]`; bounded checks only where labelled `[TEST]` | Blocking truth | Executive decision |
|---|---|---|---|
| Layer 1 Knowledge | Structured ingestion and evidence primitives exist; focused checks are substantive | Current truth can still be incomplete, stale, conflicted or weakly role-scoped | Keep; require freshness, conflict and source-readiness receipts before prescription |
| Layer 2 Context | Situation/context machinery exists and focused tests are broad | Person, connector, thread, request, opportunity and actor direction can collapse | Make request/relationship/thread identity a hard typed boundary |
| Layer 3 Domain Expertise | Versioned YAML corpus, compiler concepts and deterministic gates exist | New compiler is shadow-wired/default-off, the corpus is mostly stubs, and draft/unreviewed files can pass current admission; coverage is not authority | Author one named-reviewer accepted Sales lane deeply; abstain outside it; do not globally enable |
| Layer 4 Reasoning | Core reasoning concepts, scoring and candidate machinery are meaningful | Active path is thin; card projection loses stakes, completion, alternatives and abstention; score and confidence blur; Organization/Behavior/Adaptive have hash-only influence | Require a gold decision contract plus a typed per-brain semantic-effect/no-effect receipt before any affected action card |
| Layer 5 Executive | Native execution/governance pieces exist | UI action is not reliably welded to a governed execution intent and receipt | Bind every action button to exact owner, permission, idempotency and completion predicate |
| Layer 6 Delivery | Legacy Slack delivery works; v2 delivery design/code exists | v2 is not the canonical production-composed route; ownership remains contradictory | Choose one canonical router and result envelope; legacy becomes an adapter |
| Layer 7 Learning | Validation, publishing, rollback and some governed units are real | Organization approval does not publish (`approved_unpublished`); persisted policy reload drops `blocked_targets` and `blocked_subject_prefixes` (`policy_incomplete`); recommendation learning may emit Adaptive although Adaptive cannot carry expiry (`adaptive_ttl_unresolved`) | Do not claim adaptation until review→publish→consume is atomic, policy reload is field-equal, lifecycle is ratified, and a correction changes the intended later decision |
| Four brains | Expert, Organization, Behavior and Adaptive storage/read concepts can be identified | A `brain_snapshot_id` or hash proves reproducibility only—not semantic use, population, live authority, quality or outcome validity | Expose per-brain version, coverage, freshness and selected/applied/unused state; prove the intended typed decision delta or explicit `semantic_no_effect` |
| Customer value | Twelve golden contracts now define intended behavior | These are documentation/test specifications, not production or economic results | Run a real counterfactual pilot before ROI or “revenue influenced” claims |

## Non-negotiable intelligence contract

An actionable recommendation is allowed only when one envelope contains all of the following and every field is traceable to the same scoped situation:

| Required field | Question it must answer | Failure state |
|---|---|---|
| Business subject | Which real relationship, request, opportunity or obligation is this? | `review_source`; never pool by connector/person alone |
| Role and actor direction | Who asked, promised, proposed, owns, responds and receives? | Abstain from actor-specific action |
| Current reality | What happened, what was superseded, what is unresolved now? | Park on stale/conflicted/incomplete evidence |
| `what_remains` | What exact decision or work remains after all channels are reconciled? | Suppress if nothing remains; review if ambiguous |
| Stakes and timing | Why does acting now beat waiting, and what is the real trigger/deadline? | Never fabricate urgency or “last chance” |
| Expertise receipt | Which accepted rule/capability/version applies, with coverage and required facts? | Observation only; no prescriptive button |
| Four-brain receipt | Which Expert/Organization/Behavior/Adaptive version was selected, excluded, absent, applied or unused, and what typed decision field changed? | Hash-only influence is failure; missing brain is explicit; sparse Behavior cannot masquerade as preference; unjustified no-effect blocks the dependent claim |
| Decision and Alternative | What should happen, what credible alternative exists, and why is primary better? | No generic imperative without comparison |
| Stop/wait rule | Under what condition should the system not act or stop following up? | Default to no action when trigger is absent |
| Owner, approval and target | Who may execute, under which credential/policy, toward which exact recipient? | No handoff or send |
| Completion | What observable condition means the action itself is complete? | Delivery/open is not automatically completion |
| Outcome and window | What external result is expected, by when, and how is no-result recorded? | Do not call clicks, sends or closure value |
| Provenance and replay | Which evidence, decision, execution, delivery and learning receipts reproduce it? | No authority without a stable replay chain |

This contract makes “intelligence” falsifiable. A card that cannot answer these questions should say **why it cannot decide** and offer `Open source`, `Review source`, `Wait for trigger`, or `No action`; it must not compensate with a lower confidence percentage and the same imperative.

## Do first — one vertical slice, not seven horizontal rewrites

| Phase | Build decision | Concrete output | Exit gate |
|---|---|---|---|
| 0. Freeze truth | Pin fixtures, sources, identities, clocks, policies and evaluation denominators | Versioned Theresa, Boardy, reschedule, already-resolved and missing-expertise fixtures; product-test baseline | All fixtures replay identically; pre-existing suite failures classified; no hidden skip |
| 1. Establish scoped reality | Weld Layer 1 evidence to a request/relationship/thread-scoped Layer 2 BSO | Typed business subject, actor-direction, supersession, cross-channel completion and source-readiness receipts | Golden replays 01–04 have zero wrong target, stale action or parallel-ask collapse |
| 2. Author one deep Sales lane | Ratify exactly `Sales / buying_signal / sales.sit.inbound_fit_check / sales.qualification.lead_qualification`, with `sales.market_and_targeting.icp_definition` as its companion; finish or prune every retained dependency | Named-reviewer accepted immutable package, coverage report, negative rules, wait/stop conditions and explicit abstention outside the lane | 100% accepted fixture/dependency coverage inside lane; zero stub/draft/unreviewed/unaccepted dependency; Theresa, investor, introducer and fundraising remain Observation only; no global compiler switch |
| 3. Make Layer 4 produce a gold decision | Rank action, alternative and no-action using complete evidence and expertise receipts | Decision envelope with stakes, `what_remains`, alternative, owner, completion and outcome window | Gold-contract completeness 100%; fabricated stage/urgency and critical false-action rate 0 |
| 4. Weld card to execution | Replace decorative action with governed intent | Exact target/credential, approval, idempotency, origin and cancellation receipt | Every click maps to one intent; duplicate/revoked/stale execution is blocked |
| 5. Canonicalize delivery | Compose v2 as the single router/result model; keep legacy transports as adapters | One delivery identity and result envelope across channels | Executed, delivered, opened, completed and outcome states reconcile and never collapse |
| 6. Close learning receipt | Join correction/result to governed proposal, validation, review, publish, rollback and future compile | One correction/outcome ledger; idempotent Organization review→publish receipt; lossless policy hash; ratified Adaptive lifecycle; per-brain next-decision effect receipt | A correction changes only the intended later decision field; `approved_unpublished`, `policy_incomplete` and `adaptive_ttl_unresolved` remain fail-closed; rollback restores only a currently valid predecessor |
| 7. Run counterfactual pilot | Compare enabled versus holdout/baseline in the accepted lane | Pre-registered otherwise-action, exposure, cost, result window and attribution class | Decision-quality lift is credible; no proxy inflation; negative denominator complete |
| 8. Expand deliberately | Add Sales situations, then Support and Admin as separate acceptance programs | Authored corpus, routing coverage and replay pack per domain | Each domain independently meets coverage, false-action, safety and customer-value gates |

The first shippable product is not “all 152 YAMLs active.” It is one narrow, visibly covered loop where GeniOS correctly decides **send / wait / connector nudge / stop / review source**, can execute safely, and can prove what happened afterward.

## Do not do

- Do not flip the new compiler globally because the files exist. Presence, schema validity and compilation are not authored expertise or production authority.
- Do not describe the compiler as absent or rolled back for speed. It is shadow-wired/default-off and was shadow-first from inception; no verified performance commit explains legacy authority.
- Do not author all 152 files in parallel. That maximizes surface area before the vertical contract, evaluation and fail-closed behavior are trustworthy.
- Do not “add more LLM” to ranking, permissions, action state, completion, attribution or learning promotion. Language fluency cannot repair missing identity or evidence.
- Do not make dashboards, confidence badges or richer card text the first fix. They can make a wrong decision look more authoritative.
- Do not launch autonomous agents before the intent/result/approval/origin protocol is canonical. Agent delivery is not business completion and can create loops.
- Do not claim that Organization, Behavior or Adaptive shaped a recommendation merely because its version or hash appears in lineage. Require a typed semantic decision delta or justified scoped no-effect.
- Do not learn from a single click, send, silence, edit or generated message. Separate correction, preference, temporary exception, behavior pattern and adaptive strategy; do not publish Organization from approval without a publication receipt, reload a partial policy, or make Adaptive authoritative while its expiry is unrepresentable.
- Do not call a display, open, send, meeting, closed loop, influenced pipeline or nearby revenue a customer Outcome without the declared external result and Counterfactual.

## LLM allocation decision

The right model is component-level, not a blanket “80% per layer.” Use an LLM heavily where input is messy and interpretation is reversible; use deterministic authority where mistakes create business actions or claims.

| Component | Proposed LLM role | Deterministic authority | Cost control |
|---|---|---|---|
| Evidence extraction | High for messy mail/calendar/transcript candidates | Source identity, ACL, timestamps, dedupe, citation and conflict state | Cache by immutable source hash; small extraction schema; escalate only on conflict |
| BSO/context assembly | Medium for semantic candidate linking | Stable scope, actor direction, lifecycle, supersession and completion | Retrieve narrow thread/relationship window; reject unsupported links |
| Expertise matching | Low/medium for recall and explanation | Accepted corpus, required facts, routing, exclusions, coverage and version | Deterministic shortlist; no full-corpus prompt; shadow novel candidates |
| Reasoning wording | Medium/high for explanation and alternatives | Eligibility, scoring features, abstention, permissions and final action class | Generate after decision; bounded tokens; reuse decision receipt |
| Execution/delivery | Near zero | Intent, target, credential, approval, idempotency, routing and result | Template/adapter path; model cannot widen scope |
| Learning proposal | Medium for clustering/candidate hypothesis | Evidence threshold, validation, promotion, TTL, rollback and next-package receipt | Batch offline; human review for high-impact brain updates |

Model authority is **0%** over identity, factual truth, coverage acceptance, ranking gates, permissions, action transition, completion, attribution and learning promotion. This is not anti-LLM; it is how the LLM remains useful without becoming the hidden policy engine.

## Product-test blocker already present

The pinned source baseline was not fully green: `9 failed, 1314 passed, 39 skipped, 1 warning`. The failures cluster around a stale known-unfireable list, executive-authority latest-graph-version checks, and PostgreSQL arguments entering SQLite migration tests. This documentation build did not modify product code. Before a runtime release, owners must either fix the code/tests or explicitly redraw the relevant product units; the failures cannot be relabelled as documentation success.

## Customer value and proof plan

The desired experience is simple: the founder should not reconstruct the inbox, remember the promise, infer the target, invent the next move, or wonder whether it already happened. GeniOS should surface the one decision worth attention, explain why, safely hand it off, suppress it when resolved, and learn only from attributable results.

| Evidence horizon | What may be claimed | Measures | What may not be claimed |
|---|---|---|---|
| Deterministic replay | Contract correctness on declared fixtures | Gold completeness, false-action classes, target/owner correctness, abstention, replay equality | Live efficacy or customer value |
| 2–4 week design-partner run | Decision-quality and trust evidence | accepted/edited/rejected decisions, missed actions found, duplicate/stale/wrong-target rate, correction trend, time-to-decision | Revenue causality from small samples |
| 60–90 day controlled pilot | Economic and workflow evidence | lift versus holdout/baseline, qualified progression, time saved, full model/agent/ops cost, customer retention/use | General market demand or universal ROI |
| Multi-cohort repeatability | Narrow outcome-proven claim | replicated lift, adverse-event rate, segment variance, durable corrections | Unbounded autonomous competence |

The supplied business targets—roughly 20–30% better prioritization accuracy, 10%+ relative lift, two to four meaningful missed opportunities found per month, and 5–10× value on a $100 cost ($500–$1,000+)—are **hypotheses**, not current proof. They become decision thresholds only after baseline definitions, a denominator, a pre-registered Counterfactual, complete costs and external outcomes exist.

## Release states and Exit gate

| State | Allowed behavior | Exit gate |
|---|---|---|
| Architecture/demo | Show structure and labelled modelled examples | Never imply live/domain/outcome authority |
| Shadow evaluation | Generate hidden decisions and compare with gold/human judgment | Critical false-action classes 0; coverage and abstention measured |
| Assisted, one accepted lane | Show decisions; user approves execution | 100% gold fields; exact target/owner; execution and suppression replays green |
| Governed execution | Agent/tool may act inside explicit contract | One intent/result chain, approval/policy/idempotency/cancellation green, zero loop |
| Conditional learning | Validated bounded changes may influence later packages | Atomic review→publish→consume, policy field equality, ratified lifecycle/TTL, safe rollback and intended next-decision semantic influence proven |
| Outcome-proven | Narrow externally supportable value claim | Counterfactual pilot shows credible lift and positive net value with full attribution |

**Final executive decision:** no-go for broad prescriptive Sales authority, autonomous follow-up, four-brain personalization claims, or ROI marketing. Go for a narrow shadow-to-assisted build around the exact ordinary-Sales key `Sales / buying_signal / sales.sit.inbound_fit_check / sales.qualification.lead_qualification` plus its accepted ICP companion; keep Theresa/fundraising and every uncovered lane Observation only. Success is not more cards. Success is fewer, scoped, expert, executable decisions—with explicit no-action when evidence or expertise is missing—and an auditable chain from source to customer outcome.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "10-Deployment-Blockers-and-Design-Debt.md" (M5.C1.L-integration.V3.U01)
include "11-Evaluation-ROI-and-Health-Scorecard.md" (M5.C1.L-integration.V3.U02)
include "../09-Golden-Replays/01-Theresa-Investor-Reconsideration-and-Update-Cadence.md" (M5.C2.L-integration.V0.U01)
include "../09-Golden-Replays/02-Boardy-Mediated-Introduction.md" (M5.C2.L-integration.V0.U02)
include "../09-Golden-Replays/03-Counterparty-Availability-and-Reschedule.md" (M5.C2.L-integration.V0.U03)
include "../09-Golden-Replays/04-Already-Replied-and-Cross-Channel-Resolved.md" (M5.C2.L-integration.V0.U04)
include "../09-Golden-Replays/05-Internal-Group-Meeting-Recap.md" (M5.C2.L-integration.V0.U05)
include "../09-Golden-Replays/06-Filled-Closed-Rejected-or-Deferred-Relationship.md" (M5.C2.L-integration.V0.U06)
include "../09-Golden-Replays/07-Missing-Expertise-Observation-Only.md" (M5.C2.L-integration.V0.U07)
include "../09-Golden-Replays/08-Agent-Handoff-and-Origin-Loop.md" (M5.C2.L-integration.V0.U08)
include "../09-Golden-Replays/09-Client-Isolation-and-Never-Commercial.md" (M5.C2.L-integration.V0.U09)
include "../09-Golden-Replays/10-Pivot-Sparse-Behavior-and-Adaptive-Learning.md" (M5.C2.L-integration.V0.U10)
include "../09-Golden-Replays/11-Revenue-Impact-and-Counterfactual-Proof.md" (M5.C2.L-integration.V0.U11)
include "../09-Golden-Replays/12-Antler-Exploratory-Relationship-and-Regional-Authority.md" (M5.C2.L-integration.V0.U12)
-->
