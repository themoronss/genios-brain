# Layer 5 Executive — Architecture and Atlas Delta

## Contract

Layer 5 converts one still-authoritative Layer 4 decision into accountable work. Its boundary object is an immutable, content-addressed `ExecutionObject`; its operational duties are to identify accountable ownership, define actions and dependencies, supervise a lifecycle, escalate without creating facts, and record a real outcome. It must not reinterpret a bad subject, turn a card click into business completion, or hide uncertainty behind a reminder.

The current implementation is substantial. `contracts/execution.py`, `executive/execution.py`, `assignment.py`, `communication.py`, `lifecycle.py`, `monitor.py`, `sweep.py`, `execution_store.py`, `collect.py`, the Executive API, and the maintenance scheduler form a real execution subsystem. The correct conclusion is therefore neither “Layer 5 is missing” nor “Layer 5 is complete.” The subsystem is **Present and Wired** on its native commitment path, while the customer-visible card and agent paths remain incompletely welded to it.

## Atlas expectation versus Current code

| Responsibility | Atlas expectation | Current code proof | State | Gap or consequence |
|---|---|---|---|---|
| Execution boundary | Durable, idempotent ExecutionObject with provenance and success semantics | Frozen `ExecutionObject` carries decision/reasoning/context/config lineage, actions, communication, escalation, clocks, confidence, success events and subject reference | Wired | Rich object is not the universal action boundary for legacy card buttons or agent approval |
| Action plan | Deterministic steps, dependencies and completion criteria | `PlannedAction` plus dependency checks and store-backed action completion | Wired | Legacy card action does not complete a planned action |
| Ownership | Work owner, assignee, delegation and escalation | Deterministic assignment from owner facts to actor to admin queue; reassignment and escalation APIs exist | Wired | Wrong upstream role/subject produces a confidently wrong owner; no semantic repair belongs here |
| Lifecycle | Created, pending, running, waiting, approval, blocked, completed, failed, cancelled and expired distinctions | Current enum has created, pending, running, waiting, blocked, completed, cancelled, expired, archived; guarded transitions and sweeps exist | Wired | Atlas `AwaitingApproval` and `Failed` are not first-class current states |
| Supervision | Watch until resolution; never equate plan progress with outcome | `monitor.py` requires observed success evidence; all steps done without outcome becomes waiting/unproven | Wired | Card `acted` can revoke the signal and cancel the execution instead of proving completion |
| Escalation | Escalate according to consequence and accountability | Escalation target and reminder ladder are persisted; sweep emits reminder/escalation events | Wired | Self-escalation and unavailable delegate cycles need explicit rejection |
| Outcome | Store achieved/not-achieved/unproven outcome and operating cost | Sweep writes outcome on terminal close; collector distinguishes succeeded, completed-unproven, expired-untouched and in-progress | Wired | Customer cards and the 501 agent handoff do not reliably reach this outcome chain |
| Scheduler | Bounded recurring supervision | Maintenance invokes Executive before distribution; recent scheduler work bounds the sweep | Wired | Live tenant enablement and customer outcome proof were not established by this document |
| Approval | Human or governed approval before restricted action | Actions carry `requires_approval`; route surfaces commitments | Present | No idempotent single-executor approval protocol; agent handoff route returns 501 |
| Communication intent | Semantic audience and tone handed to Delivery | Atlas keeps concrete recipient/channel/time in Atlas 5.2 | Present, contradictory | Current Layer 5 freezes concrete assignee, channel and interrupt policy instead |

## Open ownership contradiction

This is a design decision, not a naming issue:

| Question | Atlas | Current code | Risk if left implicit | Ratification needed |
|---|---|---|---|---|
| Who resolves the concrete recipient? | Delivery at send time from semantic `audience_intent` | Executive writes concrete `assignee` into `CommunicationPlan` | Stale identity/presence cannot be re-resolved consistently | Select semantic-late binding or explicit frozen routing |
| Who chooses channel and timing? | Atlas 5.2 evaluates channel, presence, quiet hours and timing | Executive chooses channel class/channel/interrupt; Delivery gates and executes it | Two layers can appear to own the same policy and produce divergent replays | Define one policy authority and make the other validate only |
| What is immutable? | Work semantics are stable; delivery particulars may change at send time | Routing is inside the frozen object’s semantic hash, though the execution id excludes it | Reassignment can diverge between immutable payload and mutable store row | Define versioning/replan semantics for routing changes |

No recommendation here silently resolves that contradiction. Until architecture owners ratify it, changes to recipient/channel ownership must fail closed behind replay comparison rather than shifting policy ad hoc.

## Current architecture flow

1. Layer 4 decision and authoritative signal/context enter `build_execution`.
2. Validation rejects expired or window-closed work; deterministic planners create actions, owner, communication, escalation and success semantics.
3. `execution_store` persists the object, actions and lifecycle state with one live commitment per decision.
4. The bounded Executive sweep validates current authority, transitions state, observes post-creation evidence, decides whether to remind/escalate/close, and writes events/outcomes.
5. `executive_bridge` later turns reminder events into Delivery outbox work and links the commitment to an existing card by signal where possible.

The customer-visible alternate flow is different: `deliver/actions.py` can move a card and source signal to `acted`, but it does not complete the matching execution action, execution, or outcome. That split is the most important integration Gap.

## Freshness and rebuild nuance

The latest pinned source includes two related but different repairs. Commit `a90ff66` bounded the scheduler that could otherwise look hung and changed housekeeping card expiry to 3,650 days, so open cards normally leave through user action or a real `decision_expires_at`. Commit `b739bd5` changed open-signal selection so an **expired card no longer permanently blocks rebuilding a fresh card for a still-open, still-valid signal**. This is real queue resilience. It is not semantic freshness: it does not decide that Theresa’s promised-update cadence changed, that a Boardy introduction was resolved in another thread, or that an obsolete action should close.

## Architectural gaps that block the intended intelligence

| Gap | Exact failure surface | Layer 5 response now | Required architecture |
|---|---|---|---|
| Card-to-execution weld | “I’ll do it”/self-action changes card and signal, not execution step/outcome | Parallel state machines drift | One idempotent action command updates card receipt and ExecutionObject lifecycle in a single governed flow |
| Agent approval/handoff | Handoff endpoint intentionally returns HTTP 501 | No false claim of delegation, which is correct fail-closed behavior | Approval token, one executor lease, idempotency key, scoped payload and result receipt |
| Business cadence | Generic reminder ladder cannot encode monthly/material-progress/update-history consent | May nag or miss the promised update | Versioned cadence object with eligibility, last-sent, next-due, materiality and stop conditions |
| Semantic target | Person/node or connector can arrive instead of requester/action target/thread | Assignment can only consume the supplied subject | Upstream roleful situation gate; Layer 5 abstains when action target is unresolved |
| Completion reconciliation | Cross-channel reply or meeting outcome may not map to success event | Execution waits, cancels, or expires | Thread/contact/action-scoped success matcher with provenance and conflict handling |
| Mutable routing versus frozen payload | Reassignment rows may no longer match embedded communication plan | Potential validation/reminder disagreement | Explicit replan/version or a canonical mutable routing projection |
| Outcome value proof | Operational outcomes exist, but customer value and counterfactual linkage are incomplete | Activity can be measured without proving benefit | Outcome receipt linked to decision, execution, delivery, business metric and comparison window |

## Non-goals and fail-closed boundary

Layer 5 must refuse prescriptive execution when the source decision is expired, authority is revoked, owner or target is ambiguous, required approval is absent, a dependency is incomplete, or success cannot be attributed to a scoped post-creation event. It may return observation, review, waiting, defer, cancelled, or unproven. A model, UI button, transport receipt, or elapsed time cannot supply authority.

## Verdict

**Framework-ready, not live-ready.** The native Executive path has real object, lifecycle, supervision, assignment, escalation and outcome machinery. It is not yet a single customer truth because legacy cards and agent handoff bypass or stop short of that machinery, semantic cadence/target failures arrive unresolved, and the Atlas-versus-current owner/channel split is unratified. The layer becomes conditionally trustworthy only after those vertical joins are deterministic, replayed, and receipt-backed.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->
