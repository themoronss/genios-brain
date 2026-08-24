# Golden Replay 03 — Counterparty Availability and Reschedule Actor Ownership

## Evidence boundary

**[SCREENSHOT]** Supplied cards show quoted scheduling language such as “could we push the call…” and “I am available to meet…,” transformed into overdue `Deliver` actions and sometimes labelled “You promised.” They also display past-scheduled calendar items with occurrence unverified or calendar disconnected. This proves that the rendered intelligence can confuse a scheduling utterance with an owned deliverable; the image alone does not prove who authored the underlying message, which event is authoritative, or which code branch produced the card.

**[CODE]** proves relevant risk, not screenshot causation. Layer 1 retains transport headers but has no mandatory typed business-role contract. Layer 2's BSO path can emit one anchor, reconstructed/synthetic membership and an org-visible slice with `missing_fields=()` in `genios_engine/context/situation_bso.py:69-166`. Current-state reduction and request identity are not yet a proven authoritative cross-channel boundary. This replay therefore mutates author, proposal, acceptance, supersession, time zone and event state explicitly.

## Scenario contract

| Field | Required value | Blocking condition |
|---|---|---|
| **Business subject** | The scoped counterparty and meeting/reschedule decision, not the quoted sentence itself | Counterparty or meeting identity ambiguous ⇒ Review source |
| Actor roles | Speaker/proposer, recipient, scheduling owner, organizer and approver are distinct typed roles | Direction inferred from content/From alone ⇒ Review source |
| Exact open loop | Whether a current proposal awaits Rohit's response, awaits the counterparty, is confirmed, was superseded, cancelled, completed or expired | No current-state winner ⇒ Observation only |
| Why now | Evidence-linked response deadline, conflict, approaching valid proposal, or authoritative schedule change | Age of an old quote alone ⇒ no urgency |
| Expertise | Accepted scheduling/open-question capability with occurrence and current-calendar requirements | Unsupported/incomplete ⇒ Observation only/Defer |
| Completion | Proposal accepted/declined and authoritative event updated, or explicit cancellation/stop | “I'll do it,” reply draft, or old past-scheduled invite is not Completion |
| **Outcome** | Meeting confirmed, rescheduled, declined, cancelled, occurred/no-show, or remains unresolved inside a declared window | Delivery/open is not meeting outcome |

## Current failure versus expected behavior

**Current failure:** the card copies availability language into `Deliver <quote>`, calls the utterance overdue, and can assign it to the wrong owner. It conflates speech act (proposal), actor direction (who offered), state (accepted/superseded), and action (who must respond). The founder must reopen the thread and calendar to discover whether anything remains.

**Expected behavior:** GeniOS first states the current meeting state and actor ownership. If the counterparty proposed a still-valid time and Rohit has not answered, the action is “Rohit: accept or decline the counterparty's proposal,” with conflict evidence and an alternative. If Rohit proposed the time, the ball is with the counterparty; GeniOS waits unless a separate agreed follow-up trigger exists. Any later confirmation, cancellation, reschedule or completion suppresses the old proposal.

## Layer 1 through Layer 7 replay

| Layer | Deterministic input | Required output | Fail-closed behavior | Acceptance evidence |
|---|---|---|---|---|
| **Layer 1 — Knowledge** | Email/chat messages with From/To/Cc and exact quoted spans; calendar create/update/cancel status, organizer/attendees/time zone/recurrence; source versions and readiness | Immutable directional receipts for each proposal/reply/event revision; no promise/attendance inference | Park/Review source when author, quoted boundary, event revision, time zone or source window is incomplete | Provider/event/version, speaker/recipient headers, calendar revision and sync-health receipts |
| **Layer 2 — Context Intelligence** | Qualified directional receipts plus identity, meeting/request keys and graph/policy versions | One scoped meeting lifecycle; typed proposer/responder/organizer/owner; ordered proposals, acceptance, supersession, cancellation and occurrence certainty; conflicts/missing fields | Review source on actor/event conflict; Suppress superseded/closed proposal; `split_required` for merged meetings | BSO with exact request ID, roles, lifecycle, evidence membership and version fence |
| **Layer 3 — Domain Expertise** | Valid meeting BSO and four-brain snapshot | Accepted scheduling/open-question capability requiring current proposal, responder, feasibility/calendar readiness and expiry | Observation only/Defer when capability or calendar/actor dependency is incomplete; generic commitment rule cannot override | Capability/package/snapshot, accepted closure, coverage and exclusion receipt |
| **Layer 4 — Reasoning** | Current BSO plus authoritative expertise package | Compare accept, decline, counter-propose, clarify and wait/stop; eliminate infeasible/stale moves; name correct actor, target, timing, stakes and Completion | No imperative/action button if responder/current proposal cannot be proved | Decision trace, eliminated candidates, Alternative, stop/expiry and confidence vector |
| **Layer 5 — Executive Function** | Accepted decision, owner/approver, target, calendar dependency and success predicate | One execution for exact current response/update; claim is distinct from response, event update and confirmation | Block/cancel when proposal superseded, authority changed or current calendar conflicts | Decision/execution/action IDs, approval, dependency versions and completion predicate |
| **Layer 6 — Delivery** | Approved response with exact thread/recipient plus approved calendar mutation and send-time authority | Send once and reconcile calendar/provider result; update only intended event | Suppress stale/revoked response; reconcile unknown provider result before retry | Canonical DeliveryResult and calendar mutation receipt tied to execution/action |
| **Layer 7 — Learning** | Decision, actual response, authoritative meeting state and counterfactual | Learn bounded scheduling preference only from sufficient verified outcomes; keep actor correction separate | No preference from one availability quote, click/send, or inferred attendance | Outcome/window, correction lineage, support/TTL and future package consumption |

## Deterministic mutations

| Mutation | Expected behavior | Prohibited behavior | Pass condition |
|---|---|---|---|
| Counterparty proposes a valid time; Rohit has not replied; calendar is fresh and free | Actionable: Rohit accept/decline, with counter-propose Alternative | “Deliver their sentence” or assign response to counterparty | Correct proposer/responder/target and exact proposal evidence |
| Rohit proposes availability; counterparty has not replied | Wait/stop until reply or explicit cadence; ball remains with counterparty | “You promised—overdue deliver availability” | No outbound action unless separate follow-up trigger is evidenced |
| Later message accepts and current calendar confirms | Suppress proposal-response loop; current state confirmed | Continue “confirm/decline” card | Matching completion closes exact request and cancels queued execution |
| Later counter-proposal supersedes original | Evaluate only newest authoritative proposal; preserve history | Act on old time | Old decision/action loses authority by version fence |
| Meeting cancelled after acceptance | Suppress confirmation; represent cancellation and any separate unresolved rebook ask | “Meeting confirmed” or recap | Cancellation wins by source authority/order; no recap without occurrence |
| Past scheduled event, occurrence/attendance unverified | Observation only/Review source | “Met N days ago” or send recap | No action button; missing occurrence/attendance code present |
| Calendar disconnected or sync window incomplete | Defer/Review source; do not claim feasibility or silence | High confidence/100% urgency | Source-readiness hard gate blocks prescriptive decision |
| Same people have two meetings in parallel | Two meeting/request IDs or `split_required` | One merged timeline/state | Zero cross-meeting proposal/status leakage |
| Time zone/DST parsing is ambiguous | Clarify/Review source with both interpretations | Select a time silently | No calendar mutation until normalized instant is verified |
| Assistant proposes on executive's behalf | Preserve assistant=delegate/proposer and executive/organization authority separately | Treat assistant as business target or infer unlimited authority | Delegation scope and approver are explicit before action |
| Reply send was accepted but provider timed out | Reconcile exact attempt | Blind duplicate reply/event update | One idempotency key gives at most one external response and one event mutation |
| Meeting occurred and a separate deliverable was agreed | Close scheduling loop; create a new deliverable request only with owner/evidence | Keep reschedule overdue or emit generic recap | Separate request ID, capability and Completion predicate |

## Prohibited behavior

- Do not convert a quoted availability statement or question into a deliverable without resolving its speaker, recipient and speech act.
- Do not label the counterparty's proposal as Rohit's promise, or Rohit's proposal as a task already owed to the counterparty.
- Do not use elapsed days, a past scheduled timestamp, invitation text, or scalar confidence as occurrence/attendance proof.
- Do not act on a superseded proposal, cancelled event, different meeting, stale calendar window or ambiguous time zone.
- Do not let an LLM or generic expertise rule choose actor ownership or current lifecycle.
- Do not treat claim, sent response, provider delivery or calendar update as meeting occurrence or business success.

## Outcome and exit gate

This replay passes only when every author-direction, supersession, cancellation, source-outage, time-zone and parallel-meeting mutation produces the declared decision class. Every actionable card states Business subject, proposer/responder/target, current proposal, exact `what remains`, why now, evidence/readiness/conflicts, accepted expertise, ranked action and Alternative, wait/stop rule, owner/approval, Completion and Outcome window.

Hard metrics are zero actor reversals, zero stale-proposal actions, zero cross-meeting leakage, zero “met” inference without occurrence evidence, 100% ambiguity abstention and at most one external response/event mutation per idempotency key. Value is later proven only if the correct scheduling decision reduced correction effort or prevented a missed meeting relative to the recorded counterfactual.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../02-Layer-2-Context-Intelligence/06-Improvements-Acceptance-and-Metrics/README.md" (M2.C2.L-interface.V0.U01)
-->
