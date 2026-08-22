# Layer 5 Executive — Improvements, Acceptance, and Metrics

## Target

Layer 5 is successful when one still-valid decision becomes one accountable, governed lifecycle that the card, human, agent, scheduler and outcome ledger all observe. The Improvement program below preserves the real ExecutionObject/sweep/store strengths and closes vertical joins. It does not propose rewriting Layer 5 around an LLM.

## Prioritised improvement register

| Priority | Improvement | Current evidence/problem | Delivery slice | Acceptance | Metric | Exit gate |
|---:|---|---|---|---|---|---|
| P0 | Weld card action to Executive | `do_it_myself` mutates card+signal to `acted` but not execution/action/outcome | Idempotent command takes card id, execution id, action id, claimant and command id; transaction/event updates claim without closing source authority | Duplicate, retry, crash and concurrent actor replays converge | Unlinked actionable cards; duplicate claims; card/execution state divergence | 0 divergence on golden suite; production rollout blocked otherwise |
| P0 | Enforce semantic execution target | Structurally valid person/node/connector can reach `subject_ref` without exact requester/target/thread | Typed precondition from Layer 2 with requester, connector, target, relationship, thread, unresolved action and missing-context codes | Boardy multi-intro produces separate work or review; never connector target | Target ambiguity abstention; wrong-target correction rate | 100% HKS target replays correct; no prescriptive fallback |
| P0 | Strengthen current authority | Baseline tests identify missing latest graph-version predicate; no-signal execution can be treated authoritative | Require current lineage or explicit review-only orphan policy; fence sweep on current graph/decision version | Superseded/orphan/revoked fixtures never remind or execute | Stale-authority send rate; orphan prescriptive executions | Named authority cluster green; both metrics zero |
| P0 | Scope completion evidence | Current monitoring is real but depends on supplied subject/success semantics | Match requester, target, relationship, thread, action kind and post-creation time; preserve conflict review | Cross-channel completion closes exact work; parallel role does not | False completion; unresolved-after-real-completion | Zero false closure on adversarial suite; >95% scoped reconciliation on pilot-labelled set |
| P0 | Govern agent handoff | Intended route returns HTTP 501; no single-executor approval protocol | Approval token, one fenced executor lease, scoped tool/action payload, idempotency key, cancellation and signed result | Concurrent approvals create one lease; duplicate results are harmless; expiry revokes work | Duplicate execution; unapproved attempt; result correlation | Keep 501 until security, idempotency and result suites are green |
| P1 | Add business cadence | Generic reminder ladder cannot express Theresa-style periodic/material update | Cadence object: invitation/consent evidence, eligibility event, minimum interval, last sent, next due, stop condition and version | Two prior updates plus no material progress defers; new milestone triggers one eligible update | Eligible-send precision; cadence spam; missed eligible update | Theresa and opt-out HKS replays green; manual correction under agreed threshold |
| P1 | Ratify Executive/Delivery ownership | Atlas: semantic audience in Executive, concrete recipient/channel/time in Delivery; current code freezes concrete plan in Executive | Architecture decision records authority, migration and validation rule; replay both designs before selection | Exactly one layer owns each routing decision; other layer only validates/executes | Dual-policy disagreement; stale-route corrections | ADR approved; all route fixtures deterministic; no silent ownership shift |
| P1 | Reconcile reassignment representation | Store row can change while immutable payload contains original communication plan | Either create new execution/replan version or make routing an explicit mutable projection referenced by version | Reassign during sweep never validates/sends/escalates old owner | Owner mismatch incidents; reassignment latency | Concurrency/fencing suite green; audit shows one routing version |
| P1 | Add approval lifecycle semantics | Atlas names AwaitingApproval/Failed; current state set lacks them | Ratified explicit states or lossless mapping with reason codes and API presentation | Approval timeout/rejection/provider failure remain distinguishable | State ambiguity; manual forensic time | Transition/migration/API contract tests green |
| P1 | Join operational and business outcomes | Native outcome rows exist; visible path and counterfactual value are incomplete | Link decision, execution, delivery, action receipt, completion, business result, attribution window and alternative causes | Every value claim drills to receipts; unproven remains unproven | Outcome coverage; attributed useful outcomes; false ROI claim | No influenced-revenue claim without counterfactual receipt |
| P2 | Add optional grounded drafting | Current Executive has no model calls; Atlas permits human prose only | Draft after deterministic plan using allowlisted facts, cache, validator and template fallback | Model-off replay leaves execution identical; unsupported claims discarded | Unsupported-claim rate; edits; tokens per accepted draft | Zero unsupported facts in HKS set; budget degradation replay green |
| P2 | Operational observability | Scheduler is bounded after `a90ff66`, but live tenant proof is outside code inspection | Trace sweep duration, backlog, validation/cancel reasons, reminder effectiveness and stale version | Operators can explain every skipped/sent/closed execution | Sweep p95; backlog age; unexplained transition count | Alerts and runbook validated; unexplained transitions zero |

## Build order

| Phase | Units | Why this order | Completion condition |
|---|---|---|---|
| A — one truth | Card weld, semantic target, latest authority, scoped completion | Prevents wrong or phantom work before adding reach | HKS Boardy/card/cross-channel tests green |
| B — safe execution | Agent lease, approval states, reassignment versioning | Enables delegation without duplicate authority | 501 remains until whole phase green |
| C — expert supervision | Cadence and owner/channel ADR | Adds Theresa-level judgment and removes policy ambiguity | Cadence and routing golden suites green |
| D — value proof | Outcome/counterfactual ledger and observability | Measures business change, not internal activity | Pilot trace completeness and attribution gates green |
| E — prose quality | Optional grounded drafting | Improves usability after meaning is correct | Model-off equivalence and grounding gate green |

## Acceptance scenarios

| Scenario | Required trace | Forbidden result | Acceptance receipt | Exit gate |
|---|---|---|---|---|
| Theresa update | Invitation → sent-history → materiality → cadence eligibility → execution → send/action → response/window | Rejection narrative, daily age reminder, duplicate update | Cadence version, evidence IDs, command ID, delivery/action/outcome | Exact expected zero/one execution over simulated timeline |
| Boardy connector | Source threads → connector/target edges → bounded situations → separate executions | Boardy as reply target; one card with all introductions | Target/thread IDs and abstention reason for unresolved intro | Zero connector-target errors in adversarial corpus |
| Meeting state change | Proposal → newer reschedule/cancel/attendance evidence → authority revalidation | Old “confirm meeting” execution remains active | Supersession/cancel receipt | No stale execution after latest event |
| “I’ll do it” | Card → linked execution/action → idempotent claim → owner-visible running/waiting → completion evidence | Card/signal `acted` with execution untouched or completed | Command, claimant, action transition, completion/outcome IDs | Crash/retry/concurrency test converges exactly once |
| Agent execution | Approval → lease → scoped payload → tool receipt → result → completion/outcome | Two agents, implicit approval, generic webhook as success | Approval/lease/signature/idempotency/result IDs | Security and duplicate-delivery suites green before endpoint enabled |
| Self-escalation | Same owner/approver/target detected → blocked governance review | Repeat reminder to same founder | Cycle reason and review owner | Zero repeated self-escalations |
| Cross-channel resolution | Email execution → verified same relationship/action completion elsewhere | Unrelated channel event closes work or duplicate follow-up sends | Identity/thread/action match trace | Precision 100% on golden; uncertain cases abstain |
| Expired projection rebuild | Card expires → still-current signal/situation revalidated → one fresh projection | Expiry alone claims semantic refresh or creates duplicate | Old/new card link and situation version | `b739bd5` behavior retained plus semantic freshness gate |

## Metric hierarchy

| Level | Metric | Definition | Anti-gaming rule | Target type |
|---|---|---|---|---|
| Correctness | Wrong-target execution rate | Executions whose requester/target/thread was corrected by reviewer | Count before suppression too | Release: zero in golden; pilot threshold agreed |
| Correctness | Card/execution divergence | Actionable card state disagrees with linked execution/action state | No unlinked card excluded from denominator | Release: zero |
| Correctness | False completion rate | Completed/succeeded without scoped external evidence | Click/send never counts | Release: zero in golden |
| Safety | Unauthorized/duplicate executor rate | Agent/human action outside approval or more than one lease | Retry duplicates included | Release: zero |
| Judgment | Useful execution precision | Proposed executions judged correct and timely by labelled review | Abstentions and corrections visible | Pilot trend, not vanity confidence |
| Cadence | Eligible-send precision/recall | Correct sends among eligible / captured eligible events | Consent and stop rules required | HKS 100%; pilot measured |
| Operations | Time to accountable owner | Valid decision to claimed execution | Do not stop timer at card render | Improve versus baseline |
| Operations | Reminder efficiency | Useful progress events per reminder | Repeated reminder inflates denominator | Increase while reminder volume decreases |
| Completion | Reconciliation latency | External success event to exact execution close | Unproven stays separate | p50/p95 reported |
| Outcome | Outcome receipt coverage | Executions with completed/unproven/failed result and evidence window | Internal event alone insufficient | Near-total for pilot cohort |
| Value | Attributed useful outcome | Outcome with stated counterfactual and plausible attribution | Card existence never counts | 2–4 meaningful advances/month is a hypothesis to validate |
| Cost | Human correction burden | Minutes/corrections required to fix target, owner, plan or completion | Dismissals analysed separately | Visible reduction within 2–4 weeks |
| LLM | Cost per accepted grounded draft | Configured token cost divided by accepted/useful drafts | Rejected drafts remain in spend | Budget-specific ceiling |

## Release gates

1. All P0 deterministic suites pass with zero skips; the current baseline authority failures are fixed rather than reclassified.
2. Every actionable card carries an execution/action link or is explicitly observation-only.
3. Unknown semantic target, missing approval and uncertain completion fail closed with evidence and no interrupting delivery.
4. The agent handoff endpoint continues returning 501 until its complete contract is green.
5. The Atlas/current owner-channel contradiction has an approved architecture decision and migration/replay plan.
6. Latest expiry/rebuild behavior remains: expired projection does not suppress valid work, but rebuild requires a current unresolved situation.
7. Model-disabled operation preserves all numbers, routes, permissions, lifecycle and outcomes.
8. A design-partner pilot produces end-to-end receipts before any Outcome-proven claim.

## Decision

Do not increase card volume or model creativity first. Complete Phase A, then safe delegation and cadence. The decisive Exit gate is not a prettier recommendation: it is a replayable chain in which the right remaining action reaches the right accountable owner once, stays supervised, closes only on evidence, and produces a measurable outcome without founder reconstruction.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M4.C1.L-logic.V0.U01)
include "../05-LLM-Use-Cases-and-Cost/README.md" (M4.C1.L-logic.V1.U01)
-->
