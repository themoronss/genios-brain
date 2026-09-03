# Golden Replay 06 — Filled, Closed, Rejected, or Deferred Relationship

**Scenario:** an opportunity has reached a terminal or waiting state, but the underlying human relationship continues. GeniOS must keep **opportunity lifecycle** separate from **relationship lifecycle** and distinguish filled, closed-won, closed-lost/rejected, and explicitly deferred. Later email or calendar activity does not automatically reopen an opportunity.

## Evidence boundary

**[SCREENSHOT] Observed symptom:** one supplied product screenshot shows a card whose displayed stage is `filled` while the same surface recommends “Reply now” and “Confirm or decline the proposed meeting.” This proves that rendered contradiction for that captured card. It does not prove the underlying CRM state was authoritative/fresh, which internal branch produced the card, that a real opportunity should reopen, or that every filled/closed case behaves identically.

**[MODELLED] Designed replay:** the filled, won, rejected, deferred, relationship-only and authoritative-reopen fixtures below are acceptance probes. Their expected behavior, prohibited behavior and Layer 1–Layer 7 receipts define what must be tested; they are not production observations and are not `[TEST]` results. The modelled replay deliberately varies opportunity lifecycle independently from relationship activity so the observed screenshot is not generalized beyond its evidence.

## Business subject and fixture

The **Business subject** is the scoped opportunity plus its relationship role, not the person’s entire inbox history. The base fixture contains a Sales opportunity marked `filled/closed`, an old proposal/intro thread and later generic relationship activity. A variant contains an investor partner who explicitly says “send meaningful updates and I may reconsider,” which is a conditional deferral—not an active deal and not proof of permanent rejection.

The system must preserve two linked but independent objects:

| Object | Allowed lifecycle | Reopen authority |
|---|---|---|
| Opportunity | active → won/filled, lost/rejected, deferred/waiting, expired | Authoritative new decision, explicit reconsideration trigger, new opportunity or approved stage change |
| Relationship | active, dormant, nurture-permitted, restricted, ended | New permitted interaction/consent; never inferred solely from opportunity closure |

## Current failure

**[SCREENSHOT]** The supplied `filled` card still says “Reply now” and asks to confirm a proposed meeting; that is the observed failure symptom. The screenshot alone cannot establish whether stale source state, context reduction, legacy pack selection, reasoning or projection caused it. **[MODELLED]** The replay tests the suspected failure boundary by requiring terminal opportunity state to hard-eliminate pursuit while preserving the separate relationship. It also probes the opposite error: a blunt terminal-state filter deleting the continuing relationship and losing a future lawful nurture or explicit reopen. The Theresa-like mutation must keep conditional deferral distinct from rejection and prohibit fabricated “one last chance” urgency.

## Expected behavior

- **Filled/closed-won:** suppress pursuit and stale proposal/meeting work; create customer-success or handoff intelligence only if a separate verified obligation exists.
- **Closed-lost/rejected:** no Sales pursuit. Preserve relationship state and an evidence-based reopen condition; use No action/stop unless a permitted distinct nurture decision is supported.
- **Deferred:** wait until the explicit date, milestone, material-update or counterparty trigger. Do not turn elapsed silence into rejection or repeated follow-up.
- **Relationship activity after closure:** attach to the relationship; do not reopen the old opportunity unless the event contains authoritative reopen semantics.

## Prohibited behavior

- Do not call `filled` unresolved simply because old tags remain.
- Do not ask to confirm a past/proposed meeting after the opportunity is terminal.
- Do not turn rejection into “last chance,” or deferral into rejection.
- Do not permanently erase the relationship when an opportunity closes.
- Do not let any new email/calendar event reopen the old opportunity.
- Do not learn “closed means keep following up” from clicks, sends or later unrelated replies.

## Exact Layer 1–Layer 7 contract

| Layer | Required responsibility | Required output/receipt | Fail-closed state |
|---|---|---|---|
| **Layer 1 — Knowledge** | Capture authoritative stage/decision messages, CRM versions/tombstones, exact deferral language/date/condition and later events separately | Immutable source/version/thread receipts; signal atoms distinguish closure, rejection, deferral, reconsideration condition and generic activity | Park/Review source when CRM/message authority or freshness is unknown; never invent stage |
| **Layer 2 — Context Intelligence** | Build separate opportunity and relationship entities/edges; reduce timeline to one current opportunity state; scope later events by thread/role | BusinessSituationObject with terminal/waiting state, reason, effective time, relationship role, reopen condition, conflicts and exact evidence membership | Suppress terminal opportunity action; Review source on conflicting states; never person-wide reopen |
| **Layer 3 — Domain Expertise** | Apply lifecycle-specific Sales/customer-success/relationship capability only when accepted and complete; preserve Company/permission constraints | ExpertisePackage names accepted capability/version, stop/nurture/reopen rules, coverage and four-brain snapshot | Observation only/Defer for unsupported investing/fundraising or stub coverage; no generic legacy substitute |
| **Layer 4 — Reasoning** | Hard-eliminate pursuit on terminal state; compare wait/stop, relationship-safe nurture, handoff or explicit reopen; state trigger, stakes and Completion | Decision with rejected stale candidates, Alternative, no-action trigger, separated confidence/priority and current validity | `NO_ACTION`, Suppress or Review source; no age-based imperative |
| **Layer 5 — Executive** | Cancel stale opportunity executions; create new work only from a new authoritative decision with owner/approval and success predicate | Versioned ExecutionObject linked to the new opportunity/relationship object, not the closed one | No execution until reopen condition and authority pass |
| **Layer 6 — Delivery** | Revalidate terminal state, target, consent/purpose and decision version immediately before send | Suppression/DeliveryResult receipt for stale work; lawful new relationship touch has a fresh idempotency key | Suppress old proposal/meeting CTA and any revoked nurture |
| **Layer 7 — Learning** | Record terminal outcome separately from relationship response; learn cadence/reopen efficacy only from repeated reconciled cases | Joined decision→action→external result with outcome class and counterfactual; no click/send as success | No promotion from one closure/reply; deferral and rejection remain distinct labels |

## Mutation matrix

| Mutation | Expected behavior | Prohibited behavior | Outcome / pass evidence |
|---|---|---|---|
| Role/position is filled | Suppress all pursuit for that opportunity; relationship may remain dormant | Confirm old proposed meeting | No active Sales execution/card |
| Deal closed-won and onboarding task exists | New customer-success situation for exact handoff task | Continue prospect chase or merge onboarding into old Sales card | Handoff Completion separately observed |
| Explicit rejection, no reopen condition | No action/stop; retain historical relationship | “One final chance” | Zero outbound pursuit; state remains closed-lost |
| Explicit deferral until Q4 | Wait until Q4 trigger; observation schedule only | Follow up weekly because silence grows | No delivery before trigger |
| “Send material updates; I may reconsider” | Deferred conditional state; update only when verified material milestone exists and accepted expertise supports it | Label as fresh rejection or active opportunity | One milestone-specific decision or No action |
| Generic “great to hear from you” after rejection | Relationship activity only | Reopen deal automatically | Old opportunity remains closed |
| Counterparty explicitly says “let’s reconsider” | Create new version/reopened opportunity with receipt; re-reason from current evidence | Mutate old closed state without history | New opportunity/version parented to reopen event |
| Same person joins a new company | New relationship/opportunity scope | Transfer old company’s stage/permission/history as current | Separate company/opportunity identifiers |
| CRM says closed, email implies active negotiation | Review source/conflict; do not choose silently | Pick whichever event is newest regardless of authority | Conflict receipt and human/authoritative resolution |
| Nurture consent revoked | Suppress relationship touch and cancel queued execution | Use prior preference/cadence | Revocation visible through delivery gate |
| Rejection later deleted/corrected by authoritative source | Supersede with new version and rebuild, preserving history | Erase audit trail or keep stale rejection authoritative | Exact supersession chain |
| Two independent opportunities with same company | Close only the matching opportunity | Company-wide closure or reopen | Each opportunity retains independent state |

## State precedence and reopening rules

1. Terminal opportunity state is a hard action gate, not a negative score feature.
2. Relationship existence does not imply commercial permission or an active opportunity.
3. Reopen requires an explicit source-authoritative event mapped to the exact opportunity or creation of a new opportunity.
4. Deferral stores a trigger and stop/cadence rule; time before trigger is No action, not low-priority action.
5. New generic activity may update relationship freshness but cannot override opportunity state.
6. A new decision/execution/delivery receives fresh ids and provenance; the closed object is never silently reused.

## Replay assertions

- Every base terminal-state fixture produces no pursuit CTA, ExecutionObject or delivery.
- Removing terminal evidence forces Review source, not an assumed active stage.
- Changing `rejected` to `deferred_until:<trigger>` changes only the waiting/reopen semantics and preserves history.
- Relationship facts remain queryable after opportunity suppression without leaking into candidate eligibility.
- The same evidence/version set produces the same state and suppression trace.
- Layer 7 counts won/lost/deferred/nurture outcomes separately and never infers ROI from a card exposure.

## Outcome

The replay passes when the closed/filled/rejected opportunity stays closed, deferred work waits for its exact trigger, and the human relationship remains accurately represented without creating pursuit. An explicit authoritative reopen creates a new versioned decision chain. Success is **zero stale Sales actions, zero fabricated “last chance,” zero accidental permanent relationship deletion, and one auditable reopen only when new evidence actually authorizes it**.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../03-Layer-3-Domain-Expertise/06-Improvements-Acceptance-and-Metrics/README.md" (M3.C1.L-interface.V0.U01)
-->
