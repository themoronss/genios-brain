# Layer 6 Delivery (Atlas 5.2) — LLM Use Cases and Cost

## Current truth

Current Delivery is not entirely model-free. `deliver.pipeline.build_cards_for_org` passes the configured LLM into `render_copy`; one call (output cap 600 tokens) may generate the headline, situation and usable artifact together. `render.py` then applies Deterministic length and invention checks and falls back to slot copy on model/provider/validation failure. Cost tokens are sent to `graph.record_cost` with purpose `l5_render`—a historical label even though this report numbers Delivery as Layer 6.

Routing, audience rules, timing, quiet hours, gate verdicts, retry, rate limiting, priority and lifecycle remain deterministic. Executive reminders and Slack formatting are deterministic and grounded. Atlas agrees: LLM use in Delivery is **very minimal**, limited to rewriting copy, drafting emails/Slack, summarising a fixed execution plan and tone adaptation. It is never allowed to choose route, recipient, timing, policy, retry, priority or rate limit.

The quality warning is important: the Current `V-02` validator rejects unsupported digit runs and proper nouns. It does not prove every causal claim, intent, promise, adjective, relationship role or recommended action is entailed. “No invented name/number/date” is a useful guard, not full grounded intelligence.

## Current, Atlas and Proposed placement

| Task | Current path | Atlas policy | Proposed eligible rate | Deterministic pre-gate | Deterministic post-gate | LLM forbidden authority | Cost control |
|---|---|---|---:|---|---|---|---|
| Select recipient | Legacy stored assignee; v2 rules | Never | 0% | Current semantic target, visibility, directory | ACL and active recipient | Recipient/CC | No call |
| Choose channel/destination | Executive frozen plan plus gate; v2 route rules | Never | 0% | Operational capability, ratified owner | Route law and adapter health | Channel/fallback | No call |
| Decide timing/interrupt | Gate/presence/quiet-hour rules | Never | 0% | Current clocks/preferences/presence | SEND/DEFER/SUPPRESS | When or whether to notify | No call |
| Priority/rate/retry | Pure contract and SQL rules | Never | 0% | Valid object/attempt/window | Range, budget, lifecycle | Priority, quota, retry | No call |
| Card headline/situation | One model call can create both; V-01/V-02 fallback | Rewriting/summary allowed | Reduce to 0–20% of bounded cards; default deterministic situation copy | Correct situation, target, exact remaining action, fact allowlist, authority; never call on review-only input | Statement-level evidence map, length, role/tense/negation/conflict validators | Situation meaning, action, urgency, confidence | Cache per execution/state/audience/prompt; small output cap |
| Action artifact/draft | Same model call can generate body and set `artifact_ready` | Drafting allowed | 0% automatically; 20–60% only after explicit draft request/approved action | Valid linked execution/action, recipient role, channel, policy, source excerpts, allowed claims | Every claim cited; promises/amounts/deadlines unchanged; human/agent approval | Send permission, commercial/legal promise, tool call | Separate on-demand call; cap; no generation for unused cards |
| Reminder copy | Grounded deterministic bridge/adapter | Rewriting allowed | 0–15% only when template usability fails measured review | Valid reminder intent and cadence, exact fact corpus | No new fact/action/consequence; template fallback | Reminder eligibility, escalation, recipient | One cached variant per reminder state |
| Tone adaptation | Tone instruction exists; live formatter mostly deterministic | Allowed | 10–30% of approved human copy across supported languages/roles | Same semantic draft and audience policy | Semantic equivalence and forbidden-claim check | Audience/visibility or factual content | Adapt base copy, not regenerate facts |
| Executive/digest summary | Deterministic current summary | Summarisation allowed | 0–25% for narrative compression on demand | Fixed item IDs/numbers and current authority | Count equality, item coverage, source links | Inclusion, rank, numbers, ROI | Batch once per brief/hash |
| Agent envelope | v2 format shape exists; intended handoff is 501 | May phrase instructions, never scope/permission | 0% until governed handoff; then 0–10% prose field only | Approval, one lease, exact machine schema and constraints | Strict schema/signature; model text non-authoritative | Agent/tool/scope/approval/idempotency | No call before operational route |
| Delivery analytics narrative | Structured arithmetic only | Report prose allowed, not numbers | 0–10% on explicit report request | Fixed measured transport/engagement/outcome tables | Recompute every number; preserve unknown/unproven | Metrics, attribution, conclusion of causality | One cached report per data window |

## Problems in the Current render call

| Risk | Current evidence | Consequence | Proposed control | Acceptance |
|---|---|---|---|---|
| Semantic garbage enters prompt | Renderer trusts supplied facts/slots/reason code | Fluent person dump or wrong target remains wrong | Refuse model and actionable card unless bounded target/action/current state pass | Boardy/meeting/Theresa failures abstain before render |
| Shallow invention check | `V-02` checks digits and non-initial proper nouns | Unsupported causality, intent, promises or qualitative claims may pass | Claim-level entailment/citation allowlist plus deterministic prohibited-claim rules | Adversarial unsupported-claim suite rejects every case |
| One call does card plus artifact | Headline/situation/draft body generated even if user never requests draft | Higher Cost and larger unsafe surface | Deterministic card; generate artifact only on accepted draft action | Calls per viewed/used draft materially fall |
| No renderer cache shown | Identical rebuild/state can call again | Duplicate cost and copy drift; `b739bd5` rebuild can rerender | Tenant-scoped semantic cache | Same state/model/prompt makes zero new calls |
| Cost sink failure swallowed | Recording exception never blocks delivery | Cost ledger can undercount without operational alert | Non-blocking durable telemetry/dead letter and reconciliation | Injected sink failure is visible and reconciled |
| Output cap only | 600-token output limit; prompt contains serialized facts | Large person fact set increases input cost/privacy exposure | Curated evidence envelope and input token ceiling | Prompt contains only cited target/thread/action facts |
| Fallback “always ships” | Model rejection returns slot-interpolated card | Honest fields can still be semantically incomplete or truncated | Separate copy failure from intelligence admission; no actionable fallback without required meaning | Missing target/action becomes review, not card |
| Artifact-ready from nonempty text | Any validated body marks `run_play` ready | Draft can look executable without governed agent/handoff | Add artifact policy/approval and action/execution link | Ready artifact cannot execute while handoff remains 501 |

## LLM call contract

| Dimension | Required rule |
|---|---|
| Trigger | Only after deterministic admission; drafts generated on explicit need, not every card |
| Input | Minimal visibility-filtered fact envelope with target, thread, action, evidence IDs and allowed claim types |
| Cache key | Tenant + execution hash + lifecycle/state version + target/audience + surface/language + prompt/model version |
| Output | Structured copy plus claim-to-evidence mapping; artifact separated from card summary |
| Validation | Schema, length, exact numbers/names/dates, role, tense, negation, modality/promise, conflict and citation completeness |
| Retry | One transient retry maximum; validator rejection never receives a creative “try again”; template/review fallback |
| Timeout | No impact on routing/lifecycle; deterministic copy or DEFER/review according to surface contract |
| Observability | Provider/model/prompt, token counts, latency, cache hit, validator/reject reason, fallback and user edits |
| Governance | Same tenant/visibility/retention as source; no secret or inaccessible fact in prompt/log |
| Authority | Model output can be edited/drafted, never routed/sent/executed without deterministic command and approval |

## Cost model

Vendor prices are configuration, not an architecture constant:

`call_cost = input_tokens × configured_input_rate + output_tokens × configured_output_rate`

`monthly_delivery_llm_cost = Σ accepted_and_rejected_call_cost + bounded_retry_cost`

| Cost lever | Current/unsafe pattern | Proposed control | Metric |
|---|---|---|---|
| Eligibility | Model can run during card build | Call only for admitted high-value prose need | Calls per built card |
| Draft timing | Artifact generated before user chooses it | On-demand draft after action acceptance | Draft calls per used artifact |
| Input size | Serialize full provided facts | Minimal cited envelope and token ceiling | Input tokens per call |
| Cache | No explicit render cache | Semantic cache by immutable versions | Cache-hit ratio |
| Batching | One call per card | Batched narrative only for digest/report, never mix target-specific drafts | Calls per brief |
| Output | Up to 600 tokens for combined copy/artifact | Surface-specific caps; separate short card and optional draft | Output tokens/useful artifact |
| Retry | Provider failure falls back today | Keep immediate deterministic fallback; at most one transient retry only when user waits for draft | Retry and fallback rate |
| Model tier | One configured model path | Small evaluated drafting model; escalation only for measured language need | Cost and edit burden by model |

## Budget degradation

| State | Behavior | Invariant |
|---|---|---|
| Healthy | Eligible prose adaptation/draft can run | Routing, policy and action meaning fixed |
| Near budget | Templates/cache first; drafts only explicit | No important delivery suppressed for copy cost |
| Exhausted | Deterministic grounded copy or review | Never alter recipient/timing/priority |
| Provider unavailable | Record fallback, no unbounded wait | Outbox/lifecycle continues safely |
| Validator rejects | Discard entire model output | No partial unsupported artifact survives |

## Acceptance gates

1. With the LLM disabled, identical input yields identical DeliveryObject, route, gate, priority, worker result and Executive lifecycle.
2. Unsupported claim rate is zero on Boardy, Theresa, stale-meeting, self-escalation and restricted-use fixtures.
3. Missing semantic target/action never reaches `render_copy`; it becomes review/suppression.
4. Identical cache key produces no new call and byte-stable approved copy.
5. Model budget exhaustion cannot change whether, whom, when or where Delivery sends.
6. A nonempty artifact cannot authorize run-play/agent execution; the 501 boundary remains until governed handoff is green.
7. Cost ledger reconciliation reports every call even when the primary sink temporarily fails.

## Verdict

The Current model call is bounded and has useful guards, but it is too early and too broad: one call writes the card’s situation and an executable-looking artifact before semantics and demand are fully separated. The Proposed LLM role is narrower—optional grounded copy and on-demand drafting after deterministic meaning/authority—while every delivery decision remains deterministic. Better intelligence comes from fixing target, state, cadence and lifecycle first, not increasing model percentage.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C2.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M4.C2.L-data.V0.U01)
-->
