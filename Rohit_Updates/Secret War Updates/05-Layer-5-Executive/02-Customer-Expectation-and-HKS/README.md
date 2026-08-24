# Layer 5 Executive — Customer Expectation and HKS

## Customer outcome

The Customer should experience Layer 5 as an accountable chief of staff, not as a task generator. Once intelligence says what remains unresolved, Layer 5 must preserve that exact meaning, identify who can act, turn it into bounded work, watch for real completion, and stop or escalate for a business reason. The founder should not need to reconstruct the thread, remember a cadence, decide whether an agent can act, or manually reconcile the result.

Expected behavior is observable:

| Customer question | Expected Layer 5 answer | Failure substitute |
|---|---|---|
| What exactly remains? | One scoped commitment/action with evidence and success event | A copied email sentence or “reply now” |
| Who owns it? | Accountable human/agent plus approver and escalation target | Transport sender, connector, or company node treated as owner |
| What happens after I accept? | Claimed execution, dependency-aware steps, supervision and completion receipt | Card disappears because its state became `acted` |
| Can my agent do it? | Governed handoff with scope, approval, idempotency and one executor | HTTP 501 hidden behind a button or ambiguous multi-agent dispatch |
| When should it recur? | Business cadence using last sent, material progress, consent and stop rule | Fixed “N days since last email” reminder |
| Is it really done? | Post-creation evidence matches the exact action/thread/outcome | Click, send attempt, or unrelated later event counted as success |
| What if context is unsafe? | Review, waiting, defer, blocked or no execution | Confident assignment based on a person-wide dump |

## HKS register

“HKS” is preserved as the supplied label for high-consequence scenarios; no expansion is invented.

| HKS | Business situation | Harm if wrong | Required layers | Prohibited output | Fail-closed result | Golden replay | Exit gate |
|---|---|---|---|---|---|---|---|
| HKS-L5-01 Antler update cadence | Theresa invited periodic updates and reconsideration; two or three updates were sent without reply | Founder misses a legitimate re-engagement window or spams a partner | Roleful L2 state; Sales expertise; L4 strategy; L5 cadence/execution; L6 delivery; L7 outcome | “You were rejected; one last chance” or generic reply-now | Waiting/review until recipient, permission, update history, material progress and next eligibility are known | Replays invite, sent history, silence, material milestone and stop condition | Exact next eligible update, owner, draft boundary, no duplicate, response/outcome receipt |
| HKS-L5-02 Boardy introduction | Connector introduced Rohit to a separate human; separate threads represent connector and counterparty roles | Reply sent to Boardy, many intros collapsed, or unrelated facts merged | L1 thread fidelity; L2 requester/connector/target; L5 owner/target | “Reply to boardy@…” or one commitment for all introductions | Review source and separate each introduced human/thread | Multi-intro fixture with connector plus three counterparties | One ExecutionObject per unresolved target, zero connector-as-target |
| HKS-L5-03 Meeting proposal already resolved | A date was proposed, later rescheduled/completed/cancelled in calendar or another channel | Obsolete meeting confirmation embarrasses founder and destroys trust | Temporal L2 state; L5 success matcher | “Confirm the proposed meeting” after a newer outcome | Cancel/suppress and preserve conflict receipt | Email proposal followed by calendar completion and later mail | No open execution when newer authoritative state resolves it |
| HKS-L5-04 Card acceptance | User selects “I’ll do it” on a card backed by an execution | UI says accepted while Executive later cancels/expires, or double ownership occurs | L5 command/lifecycle; L6 receipt | Mark card and signal `acted` without claiming or progressing execution | Keep card actionable with explicit integration error | Duplicate click, retry, browser refresh and concurrent agent claim | One idempotent claim; linked action state visible; no completion before evidence |
| HKS-L5-05 Agent delegation | User approves an agent to execute a revenue-sensitive follow-up | Two agents send, agent exceeds scope, or no result is attributable | Approval, permissions, L5 executor lease, L6 handoff | Fire-and-forget webhook or pretend delegation succeeded | 501/not available is safer until protocol exists | Approval replay with duplicate requests and stale lease | Exactly one scoped executor, signed command, idempotent result and revocation |
| HKS-L5-06 Founder self-escalation | Founder is computed owner, approver and escalation target | Repeated self-notifications create noise without removing bottleneck | Org-role graph plus L5 escalation | Escalate Rohit to Rohit indefinitely | Block/review and propose a distinct delegate or governance decision | Same identity in all three roles | Cycle detector proves distinct accountable route or suppresses escalation |
| HKS-L5-07 Cross-channel completion | Counterparty replies in Slack/WhatsApp after the email-derived execution was created | Duplicate follow-up or false overdue state | Identity/thread correlation plus L5 observation | Continue reminders because Gmail alone is quiet | Waiting/review if correlation is uncertain; complete only on scoped match | Same person, two channels, one action, unrelated parallel deal | Correct action closes; unrelated relationship remains open |
| HKS-L5-08 Upstream person dump | Input contains many facts about one person/company but no exact requester, target or remaining action | Layer 5 makes arbitrary work look accountable | L2 situation contract and L5 precondition | Long “deliver” title copied from random fact | No execution; review source | Boardy-style node dump with mixed meetings and facts | Missing semantic target deterministically blocks planning |
| HKS-L5-09 Reassignment race | Commitment is reassigned while immutable payload still names original assignee | Wrong owner validation, reminder, or escalation | L5 store/versioning | Show new owner in list but validate old owner during sweep | Pause and require replan/version reconciliation | Reassign between two sweep phases | Payload/projection version agrees throughout one fenced sweep |
| HKS-L5-10 Restricted action | Action requires approval or permitted-use constraint | Private/support data drives commercial outreach | Governance plus L5 approval | Auto-execute because confidence is high | Await approval or suppress | Private support signal combined with sales opportunity | Approval and allowed-use receipt precede execution |

## Current strengths against the Customer bar

- The native Executive flow distinguishes pending, running, waiting, blocked, completed, cancelled, expired and archived work.
- Action dependencies and explicit completion endpoints are real; the sweep does not automatically call every completed step a successful outcome.
- Assignment, escalation, expiry, authority checks, reassignment, observations, terminal outcomes and attention-cost collection are implemented.
- The recent scheduler and expired-card rebuild fixes improve persistence: bounded work runs, and an expired card can be rebuilt for a still-valid signal.

These are engineering successes, not proof that the Customer receives high-quality intelligence. The visible path can still bypass them.

## Failure boundary and owner

| Failure | Layer 5 owns | Layer 5 does not own | Required response |
|---|---|---|---|
| Wrong requester/target/thread | Refuse to create work without semantic target | Reconstruct identity from raw source | Fail closed to source review |
| Weak Sales recommendation | Preserve/execute only a valid Layer 4 decision | Invent a better sales strategy | Reject invalid decision contract |
| Button-state drift | Unify claim/action/completion lifecycle | Treat UI state as evidence | Idempotent command boundary |
| Missing cadence | Represent and supervise approved cadence | Fabricate contact consent | Cadence contract plus upstream evidence |
| Unknown completion | Keep outcome unproven | Infer success from silence/click | Wait, reconcile, or expire |
| Unsafe delegation | Enforce approval and one executor | Assume agent authority | Continue explicit 501 until protocol is green |

## Acceptance standard

Layer 5 is Customer-ready only when every HKS golden replay produces one exact execution or a justified abstention, card acceptance is welded to the same lifecycle, agent delegation is governed, and completion is receipt-backed. Success means fewer founder decisions and higher outcome quality—not more reminders. Required pilot evidence includes correction burden, time-to-owner, claim-to-action latency, duplicate-action rate, unproven-completion rate, reminders per useful outcome, and attributed revenue/retention progress inside a defined window.

## Verdict

The native subsystem can support the Expected experience, but current integration cannot guarantee it. HKS-L5-04 and HKS-L5-05 are release-blocking: card acceptance and agent delegation do not yet share the implemented execution truth. HKS-L5-01 through HKS-L5-03 also show why age-based, person-wide activity cannot substitute for roleful cadence and real completion.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C1.L-contract.V0.U01)
include "../../00-Methodology/04-Customer-Intelligence-Contract.md" (M1.C2.L-contract.V0.U01)
-->
