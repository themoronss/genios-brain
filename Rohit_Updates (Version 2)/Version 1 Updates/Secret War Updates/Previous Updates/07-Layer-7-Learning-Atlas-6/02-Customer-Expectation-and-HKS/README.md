# Layer 7 Learning — Customer Expectation and HKS

## Customer expectation

A founder does not want to maintain a learning system. They expect occasional correction plus observed business outcomes to make GeniOS measurably better without converting the founder into a full-time trainer.

At Layer 7 the customer’s test is:

> Does GeniOS learn the right lesson from what actually happened, apply it only where justified, explain the change, and improve future decisions without weakening policy or leaking evidence?

## Expected experience

| Customer moment | Expected Layer 7 behavior | Failure the customer notices |
|---|---|---|
| User marks a card wrong | Preserve the exact correction, subject, situation, reason, and scope | Same bad card returns because dismissal only changed UI state |
| User accepts a recommendation | Record acceptance separately from execution and outcome | Click is counted as success |
| Agent executes a play | Attribute the action to the execution and await external result | Agent webhook creates another recommendation loop |
| Counterparty replies | Reconcile reply to the open loop and declared success event | Loop remains open or outcome is credited twice |
| Recommendation works | Improve the relevant capability/play for the right cohort | Global preference changes after one event |
| Recommendation fails | Separate poor decision, poor execution, transport failure, and world change | System “learns” the wrong cause |
| Founder changes ICP | Expire current Runtime leases; separately supersede or retain Organization, Behavior, and durable Adaptive versions under governance; invalidate dependent snapshots before replaying open situations | A Runtime reset is reported as a full brain reset while old market physics remain active |
| User states a preference | Create bounded versioned preference with evidence and override rules | Preference silently overrides company policy |
| Data is sparse | Show low Adaptive/Behavior confidence and rely on universal expertise | Generic behavior is presented as personalized learning |
| Product claims value | Show recommendation → action → outcome → counterfactual → attribution | Dashboard counts cards and clicks as revenue |

## What a $100M company operator would demand

A larger or high-growth company raises the bar in five ways:

1. **Cohort scope:** learning must distinguish team, role, region, segment, client context, product, and time period.
2. **Causal discipline:** a deal closing after a card is not proof the card caused it.
3. **Governance:** company policy, consent, retention, visibility, and permitted use are hard constraints.
4. **Rollback:** every promoted change needs version, authorizing policy, evidence, expiry, supersession, and reversible deployment.
5. **Monitoring:** the company must see improvement, drift, bias, false learning, and attention cost—not only recommendation volume.

The customer should be able to ask, “Why did GeniOS change this play?” and receive the source outcomes, cohort definition, threshold, approval, before/after behavior, and rollback reference.

For the current implementation, the pivot receipt must say **Runtime reset complete, durable-brain reset incomplete**. `feedback/reset.py` changes `temporary_memories` only; it does not update `learned_brain_entries`, so Organization, Behavior, and durable Adaptive versions can remain active. Each durable version therefore needs a separate governed supersession, deactivation, or justified no-effect decision plus dependent-snapshot invalidation before an authoritative replay. A future Adaptive TTL/decay contract may add bounded expiry, but current Runtime reset cannot be used as proof that durable Adaptive expired.

## HKS register

“HKS” is preserved as the user’s literal label. These are high-consequence learning scenarios; no unverified expansion of the acronym is assumed.

| HKS | Situation | Harm if wrong | Expected result | Prohibited result |
|---|---|---|---|---|
| HKS-L7-01 | User clicks “I’ll do it” but never performs the work | Bad play trains upward | Acceptance only; wait for execution and outcome | Count click as success |
| HKS-L7-02 | Message never delivered | Correct recommendation appears rejected | Mark transport failure; exclude from efficacy judgment | Learn negative user/counterparty preference |
| HKS-L7-03 | One founder dismisses one card during a bad week | Noise becomes company behavior | Store correction; require repeated scoped support | Global Behavior Brain rule |
| HKS-L7-04 | Same person is investor and customer | Role-specific response contaminates another domain | Learn on relationship-role/situation scope | Person-global preference |
| HKS-L7-05 | Agent and GeniOS observe the same reply | Outcome is double-counted | One canonical outcome ID and attribution record | Both systems independently increase confidence |
| HKS-L7-06 | Company pivots | Old ICP evidence produces confidently stale advice | Expire Runtime leases; inventory every active durable brain; govern each supersession/deactivation or explicit retention; invalidate dependent snapshots; then replay open loops | Treat Runtime reset or rerun as proof that Organization, Behavior, or durable Adaptive was invalidated; delete history; or keep old authority silently |
| HKS-L7-07 | Private community support message correlates with churn | Sensitive evidence becomes commercial targeting | `never_commercial` blocks promotion/use | “Successful” retention play trained on prohibited evidence |
| HKS-L7-08 | Three entities support a sensitive pattern | Minimum k passes but subjects remain inferable | Sensitivity-specific k and evidence redaction | Render subject evidence to commercial user |
| HKS-L7-09 | Returning applicant was rejected two years earlier | Stale judgment prejudices new evaluation | Context/version expiry and explicit reuse policy | Attach prior rejection reasoning silently |
| HKS-L7-10 | Outcome is completed but unproven | Process completion masquerades as business value | Neutral `completed_unproven` | Positive efficacy |
| HKS-L7-11 | Human corrects a mistaken identity | Wrong subject continues poisoning cohorts | Retract/supersede derived proposals and replay | Append correction while old derived learning stays active |
| HKS-L7-12 | External world closes opportunity during execution | Correct cancellation appears play failure | Cancelled-by-world/neutral attribution | Penalize recommendation |
| HKS-L7-13 | Low-volume enterprise has one high-value win | Monetary magnitude overwhelms support count | Separate business value from confidence | 100% confidence after one large deal |
| HKS-L7-14 | Client offboards from an agency | Their raw evidence must erase but permitted aggregate may remain | Client-level erasure with k-anonymous aggregate review | Cross-client trace survives or all company learning is destroyed |

## Required fail-closed behavior

| Missing or conflicted input | Expected Learning action |
|---|---|
| No canonical outcome | Do not update efficacy |
| No evidence lineage | Isolate row; do not fabricate org-visible evidence |
| Insufficient observations/days/entities | Retain as observation/candidate only |
| Identity or relationship role unresolved | Do not promote person or cohort preference |
| Delivery exposure unknown | Do not interpret silence as rejection |
| Privacy/use-class conflict | Suppress proposal or require governance review |
| Policy and preference conflict | Policy wins; record rejected preference application |
| Model parsing uncertainty | Preserve raw feedback for review; no promotion |
| Counterfactual absent | Do not claim attributable revenue |
| Existing version cannot be located | Block publish; never create an unlinked replacement |

## Sales, Customer, and Admin learning examples

### Sales

Learn that a specific play works for a defined stage/segment only after sufficient comparable outcomes. Do not learn “follow up after 3 days” from one positive reply, or transfer investor cadence into customer sales.

### Customer

Learn churn and expansion patterns from usage, support, billing, communication, and outcomes while enforcing use restrictions. “User complained privately” is not automatically a permitted upsell feature.

### Admin

Learn process bottlenecks from repeated handoff delay or approval friction. A one-time sick leave or connector outage is not company operating behavior.

## Customer acceptance questions

Layer 7 is valuable only if the customer can answer yes:

- Did the recommendation actually reach the intended human or agent?
- Did someone perform it?
- Did the external success event happen?
- Was the result attributed to the right capability, play, cohort, and brain?
- Can a reviewer inspect why a learning value changed?
- Can the change expire, be superseded, or roll back?
- Did the system avoid learning from forbidden or cross-tenant evidence?
- Are false actions, attention cost, and neutral outcomes visible?
- Does future decision quality measurably improve against a counterfactual?

If those answers are unavailable, the honest state is “learning infrastructure exists; customer learning effect unproven.”

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C3.L-contract.V0.U01)
include "../../00-Methodology/04-Customer-Intelligence-Contract.md" (M1.C2.L-contract.V0.U01)
-->
