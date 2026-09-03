# Layer 5 Executive — Loopholes, Edge Cases, and Fail-Closed Rules

## Definitions

A Loophole passes the current shape/check while violating the intended guarantee. An Edge case is a legitimate business shape that must be handled. A demonstrated mismatch is a failure; a code-path consequence not replayed here is a risk. “Fail closed” means return a named non-authoritative state—review, waiting, blocked, defer, cancel, expire, or no execution—while preserving evidence. It never means silently dropping work.

## Loophole register

| ID | Loophole | How the current check can pass | Consequence | Fail closed now | Structural fix | Golden acceptance |
|---|---|---|---|---|---|---|
| L5-LP-01 | Card acceptance without execution claim | `do_it_myself` marks card and signal `acted` successfully | UI implies ownership while planned action/execution remains unchanged; later authority revocation may cancel it | Do not mutate source authority unless linked execution claim commits | One idempotent command writes card receipt and execution claim/progress | Retry/crash/concurrent click yields one claimant and open execution |
| L5-LP-02 | Card state mistaken for completion | Card reaches terminal-looking `acted` state | Business outcome and success event are absent | Display “claimed,” never “done,” until scoped receipt arrives | Separate presentation states: offered, claimed, executing, completed, outcome verified | Click alone cannot close action/execution/outcome |
| L5-LP-03 | Orphan execution authority | Store authority path can accept an execution without a signal link, bounded only by other validity checks | Prescriptive work can outlive missing source lineage | Review-only orphan state; no reminder/send | Require explicit authority reference plus latest-version predicate | Orphan fixture cannot produce interrupting delivery |
| L5-LP-04 | Reassignment split-brain | Mutable store columns change assignee while immutable payload still embeds original communication owner | Sweep validation, detail view and reminder routing can disagree | Pause work on version mismatch | Versioned replan or one canonical routing projection | Mid-sweep reassignment never validates/sends to old owner |
| L5-LP-05 | Node-level success overreach | A post-creation event matches broad subject/node criteria | One relationship’s event can complete another parallel execution | Waiting/review when role/thread/action scope is absent | Typed success matcher keyed by requester, target, relationship, thread, action and time | Parallel investor/customer fixture closes one only |
| L5-LP-06 | Generic cadence dressed as strategy | Reminder ladder and elapsed time are valid | Repeated nag replaces a consented monthly/material-progress strategy | Defer when cadence prerequisites are missing | Cadence object with consent, eligible event, last sent, minimum interval and stop rule | Theresa fixture sends zero/one at exact eligibility |
| L5-LP-07 | Confidence bypasses approval | Action has high confidence/priority but approval semantics are incomplete | Restricted outreach or destructive action can execute | Await approval regardless of confidence | Approval state/token and scope enforcement | High-confidence unapproved action never claims executor |
| L5-LP-08 | Self-escalation satisfies “target exists” | Owner, approver and escalation target identifiers are all non-empty but identical | Infinite noise without an accountable escalation path | Block/review the cycle | Distinct-role/cycle validator and terminal escalation policy | Founder-only org produces one governance review, not repeated reminders |
| L5-LP-09 | Connector accepted as target | Structurally valid `subject_ref`/owner facts exist | Boardy or shared connector gets the action instead of introduced human | No execution when semantic target role is unresolved | Required requester/connector/target/thread fields from Layer 2 | Multi-intro replay creates target-specific work |
| L5-LP-10 | Execution event counted as value | Outcome/activity row exists | Internal progress is reported as revenue influence | Label operational outcome and attribution separately | Counterfactual/value ledger with business window and competing causes | No ROI claim without action, result and attribution receipt |
| L5-LP-11 | “Agent available” inferred from generic webhook | An agent endpoint/registration exists elsewhere | Unsafe handoff bypasses explicit HTTP 501 approval boundary | Keep handoff unavailable | Single-executor lease, signed payload, idempotent result, revocation | Duplicate approvals yield one active lease |
| L5-LP-12 | Expired-card rebuild treated as semantic refresh | `b739bd5` allows rebuilding after card expiry | Same wrong recommendation can be regenerated from unchanged unresolved signal | Re-evaluate authoritative situation; review on unchanged conflict | Versioned situation hash and supersession/completion rules | Expiry replay rebuilds only genuinely open current state |

## Edge case matrix

| ID | Edge case | Correct behavior | Unsafe shortcut | Consequence | Fail-closed evidence |
|---|---|---|---|---|---|
| L5-EC-01 | One person is investor, prospect and partner in different threads | Separate executions by relationship and unresolved action | One person-wide work item | Wrong pitch, disclosure or completion | Relationship/thread ambiguity code and source links |
| L5-EC-02 | Connector sends many introductions from one mailbox | Connector remains evidence; each introduced person is a target candidate | One execution addressed to connector | Collapsed commitments and wrong recipient | Review until target/thread edge is resolved |
| L5-EC-03 | Proposed meeting is later rescheduled, cancelled or completed | Newer authoritative state supersedes proposal | “Confirm” based on older mail | Embarrassing stale outreach | Cancel/suppress with superseding-event receipt |
| L5-EC-04 | Counterparty completes via another channel | Correlate exact relationship/action and close once | Gmail silence means unresolved | Duplicate follow-up | Waiting if cross-channel identity confidence is insufficient |
| L5-EC-05 | All planned steps are checked but outcome is unknown | Waiting/completed-unproven | Call it successful | False learning and ROI | Preserve unproven outcome; no success promotion |
| L5-EC-06 | Owner becomes inactive after assignment | Re-resolve/reassign under policy, preserving history | Keep reminding inactive account | Work never advances | Block until a valid accountable owner is chosen |
| L5-EC-07 | Owner and approver are same person | Allowed only when policy permits; otherwise separate approval | Assume self-approval is valid | Governance bypass | Await distinct approver or explicit policy receipt |
| L5-EC-08 | Dependency completes after action deadline | Recompute feasibility or expire/replan | Run remaining step anyway | Out-of-window action | Expire or request revised decision |
| L5-EC-09 | Duplicate Layer 4 decision/replay | Idempotently return one live commitment per decision | Create duplicate reminders/executors | Double send and conflicting ownership | Existing execution receipt returned |
| L5-EC-10 | New decision supersedes old execution | Cancel/supersede old work before new authority acts | Let both proceed | Contradictory messages | Fenced supersession event and single-live assertion |
| L5-EC-11 | Long-running work survives housekeeping window | Remain valid only while decision/source/cadence authority remains current | 3,650-day card lifetime means relevant | Stale backlog | Revalidate semantics, not card age |
| L5-EC-12 | Required action has no safe executor | Surface blocked/review and why | Assign generic admin/agent blindly | Unauthorized or impossible work | No claim; missing-capability receipt |
| L5-EC-13 | External send succeeded but provider response timed out | Reconcile by idempotency/provider receipt before retry | Re-send immediately | Duplicate customer contact | Waiting/uncertain delivery, not action completion |
| L5-EC-14 | User dismisses a valuable recommendation | Cancel future prompts but retain dismissal reason and counterfactual | Delete history | Cannot learn preference or audit suppression | Dismissal event, no fabricated negative outcome |
| L5-EC-15 | Source visibility changes after planning | Revalidate permission before any execution/delivery | Frozen object assumed permanently allowed | Privacy breach | Cancel/suppress and retain policy-change receipt |

## Mandatory preconditions

| Gate | Required proof | Failure code/state | Prohibited fallback |
|---|---|---|---|
| Authority | Current decision, current source/signal or explicit authoritative orphan policy | `review_authority` / cancelled | “It was valid when created” |
| Semantic target | Requester, target, relationship/thread and exact unresolved action | `review_source` / no execution | Use sender, company or connector node |
| Ownership | Active accountable owner and non-cyclic escalation route | blocked/review | Assign founder/admin by default without explanation |
| Approval | Valid scoped approval for every restricted action | awaiting approval/blocked | Use confidence as permission |
| Dependencies | All declared prerequisites completed with receipts | pending/blocked | Mark step complete through UI shortcut |
| Freshness | Action window, decision expiry, cadence eligibility and supersession checked | defer/expire/cancel | Use card creation age alone |
| Completion | Scoped post-creation success event with provenance | waiting/unproven | Click, send attempt or silence equals success |
| Outcome | Business result and window separated from execution completion | completed-unproven | Internal event equals revenue outcome |

## State invariants

1. A card can be accepted without being completed; acceptance creates or claims work.
2. A sent message can be delivered without the underlying business action succeeding.
3. A completed action can remain outcome-unproven.
4. Revoked authority cancels future work but does not rewrite historical receipts.
5. Reassignment changes one versioned routing truth and never silently mutates decision meaning.
6. Expiry/rebuild fixes queue liveness only; every rebuilt projection is revalidated semantically.
7. Missing role/thread/cadence is not “low confidence”; it is a typed blocker.
8. The agent handoff remains 501 until governed approval and executor results exist.

## Consequence-ranked release blockers

| Priority | Blocker | Consequence if shipped | Required exit |
|---:|---|---|---|
| P0 | Card-to-execution split | Founder believes action is owned while system cancels/forgets it | Atomic idempotent weld replay green |
| P0 | Semantic target absent | Wrong person/action becomes authoritative work | Roleful target precondition and Boardy replay green |
| P0 | Completion overreach | False learning and duplicate/missed outreach | Scoped success matcher and cross-channel fixtures green |
| P0 | Unsafe agent delegation | Duplicate or unauthorized external action | Single-executor approval protocol green; remove 501 only then |
| P1 | Missing business cadence | Spam or missed relationship opportunity | Theresa cadence fixture green |
| P1 | Unratified routing owner | Executive and Delivery enforce conflicting policy | Recorded architecture decision plus migration/replay |
| P1 | Weak latest-authority predicate | Stale graph truth remains actionable | Baseline authority cluster green |
| P2 | Operational outcome sold as ROI | Misleading customer value claims | Counterfactual and attribution receipts |

## Verdict

The implementation contains meaningful safeguards, but the Loopholes above make the end-to-end path unsafe for prescriptive output outside bounded native replays. Fail closed at semantic target, authority, approval, dependency and completion boundaries; do not compensate with more reminders or a stronger model. Layer 5 becomes conditionally trustworthy only when P0 joins and golden edge cases prove one accountable lifecycle.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../02-Customer-Expectation-and-HKS/README.md" (M4.C1.L-contract.V1.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M4.C1.L-data.V0.U01)
-->
