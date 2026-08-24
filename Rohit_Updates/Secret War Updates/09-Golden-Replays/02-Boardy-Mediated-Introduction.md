# Golden Replay 02 — Boardy-Mediated Introduction

## Evidence boundary

**[SCREENSHOT]** A supplied card addressed to `boardy@boardy.ai` explicitly warns that Boardy is an introduction connector and that many separate introductions were collapsed. The same surface shows aggregate tags such as dozens of meeting proposals and introductions, several unrelated calendar events, and a large fact dump. This proves a rendered wrong-scope symptom; it does not prove which commit, database rows, correlation route, or runtime flag produced it.

**[CODE]** independently establishes a credible risk boundary: transport actors survive Layer 1, but typed requester/connector/target roles are not mandatory; Layer 2 can use person/high-degree context, reconstruct membership, emit a single anchor and hardcode org visibility in `genios_engine/context/situation_bso.py:69-166`; first-claim alias behavior exists in `genios_engine/context/identity.py:134-145`. These facts do not by themselves prove the screenshot's cause. This replay makes connector, relationship, thread and action-target correctness deterministic.

## Scenario contract

| Field | Required value | Blocking condition |
|---|---|---|
| **Business subject** | Exactly one introduced contact and the scoped opportunity/request for that contact | Missing/ambiguous introduced identity or thread ⇒ Review source |
| Connector | Boardy, typed separately; never the default business subject or recipient | Connector/target collapse ⇒ split required, no action |
| Requester/owner/target | Requester is whoever made the bounded ask; Rohit/authorized agent is owner; introduced contact is target when outreach is actually unresolved | Role inferred solely from From/To ⇒ Review source |
| Exact open loop | The unresolved ask for this introduced contact only: reply, confirm meeting, deliver agreed next step, wait, or stop | Person-wide “ball in court” or aggregate intro history ⇒ not actionable |
| Evidence | Exact intro message, introduced address, parent/forwarded thread, replies, current meeting/outcome and source readiness | Synthetic/reconstructed-only membership ⇒ Observation only |
| Completion | Matching contact's exact request is externally resolved | A reply to Boardy or another introduced contact cannot close it |
| **Outcome** | Contact-specific response, meeting, accepted deliverable, explicit decline, or no response inside declared window | Delivery/card interaction is not contact outcome |

## Current failure versus expected behavior

**Current failure:** separate people and asks are collapsed into a connector-centred card. Boardy becomes the apparent entity to reply to; unrelated introductions, proposals, calendar events and facts are pooled; one generic “deliver” instruction cannot say which person, thread or unresolved request it belongs to. The product shifts reconstruction and target selection back to the founder.

**Expected behavior:** Boardy remains a relationship edge and provenance actor. Each introduced contact receives a distinct situation keyed by relationship/request/thread/opportunity. Resolved contacts are suppressed, unresolved contacts receive at most one current decision, and a Boardy escalation appears only as a separately justified candidate—not as a substitute recipient.

## Layer 1 through Layer 7 replay

| Layer | Deterministic input | Required output | Fail-closed behavior | Acceptance evidence |
|---|---|---|---|---|
| **Layer 1 — Knowledge** | Connector email with From/To/Cc, quoted/forwarded segments, introduced identities, message/thread IDs, attachments, source versions, visibility and freshness | Preserve every transport actor and exact span; emit no inferred business-role equality | Park/Review source if quoted boundary, introduced address, version or source window is missing | Provider/event/version, parent/forward chain, offsets, actors and readiness receipts |
| **Layer 2 — Context Intelligence** | Qualified intro receipts plus identity/graph/policy versions and contact-specific replies/calendar state | One Boardy connector node/edge plus one BSO per introduced relationship/open loop; exact membership, target, requester, owner, lifecycle, missing/conflicts and version fence | `split_required` for aggregate/chimera; Review source for ambiguous target; Suppress only the matching resolved request | Stable relationship/request IDs; zero shared commitments; bounded slices and exclusion reasons |
| **Layer 3 — Domain Expertise** | Contact-specific BSO and permission-resolved four-brain snapshot | Select the contact's accepted capability/domain, not a “Boardy” domain; explicit unsupported when closure is absent | Observation only; legacy generic pack cannot override target/coverage block | Capability/package/snapshot IDs, accepted closure, role-scope and authoritative mode |
| **Layer 4 — Reasoning** | One valid contact BSO and authoritative package | Contact-specific candidates: direct reply/action, wait/stop, or permission-safe connector escalation; hard-eliminate wrong recipients | No action CTA when target/request cannot be named; no single decision spans contacts | Decision/candidate/elimination trace, recipient intent, stakes, Alternative, Completion |
| **Layer 5 — Executive Function** | Current decision, contact target, owner/approver, dependencies and exact success predicate | One ExecutionObject per accepted contact action; claim/approval/completion remain independent | Block/cancel on ambiguous target, stale BSO, already-resolved request or missing approval | One decision→execution→action chain per relationship/request |
| **Layer 6 — Delivery** | Approved action with exact introduced recipient/thread, purpose, visibility and send-time fence | Materialize/send only to intended contact; connector nudge uses a separate approved action and payload | Suppress on recipient mismatch, lifecycle closure or stale authority; reconcile ambiguous attempt | Canonical DeliveryResult tied to contact execution/action and provider ID |
| **Layer 7 — Learning** | Per-contact decision, delivery, completion and outcome plus connector lineage | Learn contact outcome separately; connector-effectiveness pattern needs independent support and must not merge private contact facts | No learning from aggregate tags, one intro, click/send, or another contact's success | Contact/request outcome, counterfactual, support/population/use class and future package receipt |

## Deterministic mutations

| Mutation | Expected behavior | Prohibited behavior | Pass condition |
|---|---|---|---|
| Boardy introduces three contacts in separate threads; all unresolved | Three BSOs and at most three contact-specific decisions | One Boardy person dump/card | Target precision 100%; no shared commitment/evidence outside explicit connector edge |
| Three contacts appear in one forwarded/quoted thread | Parser preserves spans; Layer 2 splits by introduced identity/request or returns `split_required` | Treat whole quoted body as one ask | Each membership has exact evidence span and reason; uncertainty blocks action |
| One contact replied, two remain silent | Suppress only replied contact's resolved request; independently evaluate the other two | Close all three or keep replied contact overdue | Wrong-close rate zero and distinct lifecycle receipts |
| One contact has a confirmed meeting; another merely proposed a time | Separate meeting states and expertise inputs | Copy meeting/status to all contacts | No cross-contact calendar fact in bounded slices |
| Boardy explicitly asks Rohit for a connector update | Create a separate Boardy-as-target request with its own evidence and decision | Reuse an introduced-contact action/Completion | Boardy request ID differs from every introduction ID |
| Introduced address is missing or ambiguous | Review source with exact question | Guess from company/domain/name | No BSO ready for expertise and no action button |
| Same display name maps to two anchored people | Return ambiguity/candidate set until anchored/reviewed | First claimant silently wins | No graph attachment/action before discriminator |
| One introduction is declined or relationship closed | Stop/suppress that opportunity while retaining connector/relationship history | “Last chance” or reopen from old activity | Closed opportunity cannot become actionable without authoritative new state |
| Connector thread contains private facts about another contact | Exclude facts from unrelated BSO and preserve narrowest visibility/use | Let high-degree neighbor context leak | Selected-context leakage is zero; exclusion receipt present |
| Direct contact send already occurred but provider result is unknown | Reconcile exact attempt before retry | Ask Boardy or resend blindly | Idempotency/provider receipt yields at most one direct external impression |

## Prohibited behavior

- Do not render Boardy as the person to pursue merely because Boardy is the transport sender.
- Do not aggregate every introduction, meeting, fact or commitment connected to Boardy into one operational situation.
- Do not close or reopen multiple requests through a person-wide state transition.
- Do not infer the target from display name, company, calendar title, high-degree graph proximity or an LLM guess.
- Do not let generic expertise/reasoning bypass a `split_required`, missing-role or unsupported result.
- Do not treat connector reply, card click, send receipt or another contact's outcome as this contact's Completion or value.

## Outcome and exit gate

The replay passes when Boardy plus three introductions deterministically yields three relationship/request-scoped BSOs, no shared commitment facts, no connector-as-target action, and correct independent lifecycle transitions under every mutation. Every actionable contact card must state Business subject, Boardy connector role, exact `what remains`, evidence/freshness/conflicts, accepted expertise/coverage, specific recipient/action, Alternative and stop rule, owner/approval, Completion and Outcome window.

Operational metrics are hard gates: zero wrong targets, zero cross-contact/context leakage, zero unrelated closes, 100% ambiguity abstention, and 100% traceable membership/recipient lineage. Customer value is not “three cards created”; it is reduced founder reconstruction and a verified contact-specific advance the system would otherwise have missed, reconciled with counterfactual and attribution.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../02-Layer-2-Context-Intelligence/06-Improvements-Acceptance-and-Metrics/README.md" (M2.C2.L-interface.V0.U01)
-->
