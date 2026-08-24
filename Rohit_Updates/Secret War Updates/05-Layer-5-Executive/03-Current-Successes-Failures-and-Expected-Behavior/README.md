# Layer 5 Executive — Current Successes, Failures, and Expected Behavior

## Evidence scope

All Current proof below is code evidence from `harsh/mvp@b739bd5`, not a deployment claim. Atlas is the expected design, screenshots are customer-visible symptom evidence, and the customer/HTML artifacts are requirement evidence. The repository baseline was already red (`9 failed, 1314 passed, 39 skipped`), including an Executive authority cluster; no row promotes code existence to Live or Outcome-proven.

## Required comparison

| Component or scenario | Atlas expected | Current proof | State | Verified success | Current failure | Loophole | What should have happened | Improvement | Acceptance evidence |
|---|---|---|---|---|---|---|---|---|---|
| ExecutionObject | Immutable, durable, idempotent work boundary with lineage | `contracts/execution.py` stores decision/reasoning/context/config provenance, actions, communication, escalation, clocks, success events and subject reference; store persists it | Wired | Native decision can become replayable accountable work | Legacy card and agent action do not universally consume this boundary | Rich object can exist while visible card state follows another truth | Every accepted card/agent command references exactly one execution and action | Make execution id/action id mandatory on actionable surfaces | Replay proves one decision, one live execution, one action command |
| Lifecycle | Distinguish planning, approval, execution, waiting, failure, completion and expiry | Guarded state machine plus scheduled sweep and outcomes | Wired | Pending/running/waiting/blocked/completed/cancelled/expired are distinct | Atlas approval and failed states are not first-class | Failure can collapse into blocked/cancelled or transport-only status | Preserve approval and failed semantics without inventing completion | Add states or explicitly map and ratify them | Transition matrix and migration replay are green |
| Action dependencies | Steps execute only after dependencies and approvals | `PlannedAction`, dependency validation and completion endpoint exist | Wired | Out-of-order action completion is rejected | Card click does not call this endpoint | UI can say “acted” while dependency remains incomplete | Accept should claim; explicit action receipt should progress; external success should close | Unified idempotent command service | Duplicate/out-of-order/concurrent click replay yields one legal state |
| Authority validation | Revalidate current decision/source authority during supervision | Sweep/store checks authority, expiry, window and active owner | Wired, baseline tests failing | Stale work can be cancelled when linked authority is invalid | Baseline authority tests require a missing latest graph-version predicate | Execution with no signal link is treated authoritative until other bounds revoke it | Require explicit authority lineage or review-only orphan state | Latest-version predicate plus orphan policy | Named authority tests pass; zero orphan prescriptive executions |
| Assignment | Deterministic accountable owner plus escalation fallback | Owner facts → actor → admin queue; reassign endpoint and store columns | Wired | Assignment is auditable and does not need an LLM | Bad semantic target produces bad owner | Reassigned row can diverge from immutable embedded communication plan | Resolve roleful target upstream; use one canonical routing version | Replan/version routing or remove duplicated owner state | Reassign-during-sweep fixture never validates/sends to old owner |
| Monitoring | Complete only from scoped post-creation evidence | Monitor checks observed events after execution creation and preserves unproven state | Wired | All steps done without business evidence remains waiting/unproven | Matching scope depends on input signal/node semantics | Broad node-level success event can close the wrong parallel relationship | Match requester, target, relationship, thread, action and time | Typed success predicate with conflict review | Cross-channel and multi-role replays close only intended execution |
| Reminder/escalation sweep | Bounded recurring watch loop | Scheduler calls `run_executive`; sweep validates, transitions, observes, decides and speaks | Wired | Recent scheduler repair avoids silent three-day scan behavior | Generic ladder cannot model promised periodic updates | Same reminder policy can fire despite no material progress or consent window | Cadence determines eligibility and stop condition | Versioned cadence contract | Theresa replay sends only when eligible and suppresses after stop |
| Card acceptance | User acceptance becomes accountable work, not completion | `deliver/actions.py` marks card and signal `acted`; API describes self-action as claim-only | Wired to card, not execution | UI has an explicit user action receipt | No planned action, execution, or outcome transition occurs | On next sweep, acted signal can revoke authority and cancel work | Atomically claim linked execution while retaining evidence until completion | Card-execution weld with outbox/event transaction | Card, signal, execution and action converge after retry/crash |
| Agent handoff | Approved, one-executor, idempotent delegation with result | Intelligence handoff endpoint returns HTTP 501 by design | Stub/fail-closed | It does not falsely claim a safe handoff | Customer cannot delegate through intended route | Other generic webhooks could be mistaken for this governed protocol | Remain unavailable until approval/lease/result contract exists | Build executor lease and signed result receipt | Concurrent handoff replay produces one executor and one result |
| Outcome recording | Achieved, failed or unproven outcome tied to execution | Sweep/store write outcomes; collector labels succeeded, completed-unproven, expired-untouched and effort | Wired on native path | Completion is not automatically economic success | Visible card path may never write an Executive outcome | Operational event counts can be presented as value without counterfactual | Join action, completion, business outcome and attribution window | Outcome/value ledger | Pilot can trace card → execution → delivery → action → outcome → attribution |
| Owner/channel boundary | Executive emits semantic intent; Delivery resolves concrete routing | Current `communication.py` chooses assignee/channel/channel class/interrupt/tone; Delivery gates it | Present, unratified delta | Frozen routing is deterministic and auditable | Atlas and current ownership disagree | Future code may enforce policy twice or mutate one side only | Ratify one authority and validate at the other boundary | Architecture decision plus dual-path replay | Same input produces one explainable recipient/channel owner |
| Expired card rebuild | Valid unresolved work can surface after obsolete projection expires | `b739bd5` excludes expired cards when checking whether an open signal lacks a card | Wired | An expired card no longer permanently suppresses a fresh projection | Semantic staleness and already-resolved work are not fixed | 3,650-day housekeeping expiry can preserve irrelevant cards | Rebuild only after authoritative unresolved-state reduction | Freshness/completion reconciliation before projection | Expired/rebuilt/resolved fixtures yield zero duplicates and no stale card |
| Person/node dump | One bounded execution for exact unresolved business state | `subject_ref` and owner facts are accepted by Layer 5; screenshots show aggregated facts around connector/person cards | Risk at input boundary | Layer 5 preserves supplied provenance | It cannot discover omitted requester/action target/thread | Structurally valid node reference can pass while semantically wrong | No prescriptive execution without semantic target contract | Require roleful BSO fields and abstention code | Boardy replay creates separate target-scoped work or review only |

## Verified successes in the native path

1. The ExecutionObject is not a placeholder. It is immutable, content-addressed, round-trip validated, persisted with actions/escalations, and carries the provenance needed for audit.
2. `execution_store` enforces guarded transitions, one live commitment per decision, dependency-aware action completion, dismissal, reassignment and outcome rows.
3. `monitor.py` explicitly avoids the dangerous shortcut “all steps checked = customer outcome achieved.” It can hold a completed plan in waiting/unproven state.
4. The maintenance composition runs Executive before distribution, so reminder intent can be bridged into Layer 6 rather than being only a dormant library.
5. `collect.py` records operational labels and human attention/reminder/escalation cost, a necessary basis for later value measurement.

## Current failure chain visible to the founder

The screenshots’ low-quality cards are not caused by one missing prompt. A wrong or person-wide situation survives upstream; Layer 4 may select a generic age-driven action; the card surface uses the legacy action state; Layer 5’s richer execution can exist beside it; Delivery shows facts without fixing semantics; and no shared completion receipt closes the loop. The visible result can be a polished “reply now,” “confirm meeting,” or recap suggestion even when the real remaining action is an invited periodic update, a separate introduced counterparty, or nothing at all.

## Should have happened: three concrete replays

| Situation | What happened now | Should have happened | Evidence required before action |
|---|---|---|---|
| Theresa invited updates, later silence | Generic rejection/last-chance interpretation or age reminder is possible | Detect consented update cadence; check updates already sent and material progress; schedule next eligible update or wait | Exact invitation, recipient role, sent-history, material milestone, stop condition |
| Boardy introduced another person | Connector/node facts can collapse into one oversized commitment/card | Create work for the introduced human’s separate thread; Boardy remains connector evidence, not target | Introduction edge, introduced identity, target thread, open request, completion state |
| User presses “I’ll do it” | Card/signal become `acted` while execution truth does not progress | Idempotently claim the linked execution action, preserve open authority, show owner, and wait for actual completion | Execution/action link, claimant, command id, dependency/approval status |

## Evidence receipts and claim limits

| Evidence | Supports | Does not support |
|---|---|---|
| `contracts/execution.py` and Executive modules | Present/Wired native contract and machinery | Live tenant correctness or customer outcome |
| `api/routes.py` maintenance order | Composition reachability | Frequency, successful production runs or no backlog |
| `deliver/actions.py` | Exact legacy card/signal mutation | Execution completion or business success |
| Handoff HTTP 501 | Correct explicit absence/fail-closed state | Safe agent execution elsewhere |
| `a90ff66` and `b739bd5` | Bounded scheduler and expired-card rebuild behavior | Semantic resolution, cadence intelligence or stale-loop elimination |
| Screenshots | Live-looking visible symptom set | Full trace or root-cause proof by themselves |
| Baseline test ledger | Known red authority/portability/corpus clusters | Regression caused by these documents |

## Verdict

Layer 5 has Verified success as an execution subsystem, but the Current failure is a broken vertical contract: visible acceptance and agent delegation do not consistently enter that subsystem, and upstream semantic ambiguity is not rejected strongly enough. The correct Expected state is one receipt-backed lifecycle from decision through real outcome, with explicit abstention wherever requester, target, cadence, approval or completion evidence is unresolved.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C1.L-contract.V0.U01)
include "../../00-Methodology/03-Source-and-Commit-Manifest.md" (M1.C1.L-data.V0.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->
