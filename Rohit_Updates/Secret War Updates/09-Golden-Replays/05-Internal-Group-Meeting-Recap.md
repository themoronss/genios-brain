# Golden Replay 05 — Internal or Group Meeting Recap Eligibility

**Scenario:** a calendar event is in the past, often with many attendees and a generic Zoom description. GeniOS must determine whether a meeting actually occurred, whether an external business subject exists, and whether anyone promised or reasonably owes a recap. A past event is evidence of scheduling—not attendance, discussion, obligation or recap value.

## Evidence boundary

**[SCREENSHOT] Observed symptom:** the supplied product screenshots show cards recommending “Send a recap of the meeting” at 93–94% displayed confidence while exposing calendar event data and a generic Zoom invitation description. The screenshots prove that rendered symptom only. They do not prove attendance, discussion, an external obligation, the precise producing code branch, or that every similar event receives the same card.

**[MODELLED] Designed replay:** the base fixture, mutations, expected states, prohibited behavior and Layer 1–Layer 7 assertions below are an acceptance design derived from the customer requirement and architecture contract. They are not claims that this replay has run against a production tenant or that the current runtime passes it. A future test result must be labelled `[TEST]`; a verified external result must be labelled outcome evidence.

## Business subject and test fixture

The **Business subject** is the bounded meeting relationship or exact post-meeting commitment, not the organizer, attendee list, calendar title or every person in a cohort. The base fixture contains:

- a past calendar event titled `[Session] Building Your MVP | Launchpad 30`;
- Rohit plus a large group of attendees;
- a boilerplate Zoom join description but no transcript, notes, attendance receipt or explicit recap promise;
- no verified external decision-maker, unresolved question, deliverable, owner or completion predicate.

The **[MODELLED]** fixture is deliberately insufficient for an outbound recap. Its shape targets the **[SCREENSHOT]** symptom without upgrading the screenshot into proof of the upstream meeting state.

## Current failure

**[SCREENSHOT]** The observed current surface presents “Met N days ago,” invitation detail and a recap recommendation together. The displayed result collapses four truths from the customer’s perspective—scheduled, occurred, attended and produced an external obligation—without showing evidence for the latter three. The screenshot does not establish whether the cause is source capture, context reduction, reasoning or projection. **[MODELLED]** The replay therefore mutates each truth independently and requires every unproved state to fail closed; for an internal workshop, self-owned event, cancelled/no-show call or cohort session with no promised follow-up, an outbound recap would manufacture work and may expose attendee information.

## Expected behavior

The base fixture yields **Observation only** or suppression: “Past group session found; occurrence, attendance and external recap obligation are unverified.” The card has no send/recap action button. It may offer a permission-safe “Review calendar/source” route that asks exactly whether the event occurred and whether an external deliverable was agreed.

An actionable recap/follow-up appears only after evidence proves all required gates: occurrence, relevant attendance, a permitted external recipient or bounded group, exact unresolved follow-up, owner/approval, appropriate content/source, and observable Completion. When the real obligation is a promised deck or answer, the recommendation must name that deliverable rather than say “send recap.”

## Prohibited behavior

- Do not infer attendance or discussion from a past scheduled event.
- Do not recap to the organizer, self, internal team or whole cohort merely because addresses exist.
- Do not copy boilerplate invitation/Zoom text as meeting intelligence.
- Do not invent key points, next steps, recipient, owner or outcome.
- Do not label a calendar-derived priority score as decision confidence.
- Do not learn that every past meeting should trigger outreach from clicks or sends.

## Exact Layer 1–Layer 7 contract

| Layer | Required input and responsibility | Required receipt/output | Fail-closed result |
|---|---|---|---|
| **Layer 1 — Knowledge** | Capture event id/version, organizer, invitees, response/status transitions, cancellations, recurrence, start/end, title/description and source readiness; never create attendance | Immutable calendar receipts with current provider state, visibility/use and explicit absence of transcript/attendance evidence | Park/Review source if version/status/source is stale; publish “scheduled” only |
| **Layer 2 — Context Intelligence** | Bound one meeting occurrence; classify internal/external/mixed only from grounded identities; separate scheduled, occurred, attended and outcome states | BusinessSituationObject with meeting subject, roleful participants, verified state, exact evidence membership, missing `attendance`, `external_counterparty`, `outcome` and `open_loop` | Observation only/Suppress; no person-wide attendee aggregation |
| **Layer 3 — Domain Expertise** | Select recap/follow-up capability only when its required occurrence, audience, purpose and obligation objects are complete | ExpertisePackage with accepted capability/version, four-brain snapshot, visibility and coverage; otherwise unsupported/incomplete | No action-authorizing playbook; generic Sales fallback forbidden |
| **Layer 4 — Reasoning** | Compare exact deliverable, clarification, internal documentation, wait/stop and no-action; require stakes and Completion | Decision trace with candidates/rejections, why now, owner, expiry, confidence vector and explicit no-action when gates fail | `INSUFFICIENT_CONTEXT`, `NO_ACTION` or Review source; no generic “Send recap” |
| **Layer 5 — Executive** | Create work only for a named recipient/deliverable and accountable owner after authority/approval | ExecutionObject with scoped action, dependencies, content/asset version, approval and success predicate | No execution for base fixture; cancel if event state is later cancelled/no-show |
| **Layer 6 — Delivery** | Revalidate audience, permission, event/decision authority and payload immediately before send | Canonical DeliveryResult linked to execution/action and provider receipt | Suppress stale, internal-only, wrong-audience or unverified recap materialization |
| **Layer 7 — Learning** | Join decision exposure, actual action, delivery, external acceptance/result and permitted use | No proposal from calendar age/click alone; bounded efficacy only after repeated verified follow-up outcomes | No promotion; cancelled/no-show/internal cases are neutral/suppressed, not failed Sales plays |

## Mutation matrix

| Mutation | Expected behavior | Prohibited behavior | Outcome / pass evidence |
|---|---|---|---|
| Internal-only team workshop, verified occurred | Suppress outbound recap; create internal note/action only if an exact internal commitment exists | Email everyone because meeting occurred | No external delivery; internal completion separately receipted |
| Self-only focus block | Suppress | “Send recap to yourself” | Zero card/action |
| Event cancelled before start | Suppress; preserve cancellation receipt | “Met N days ago” | No ExecutionObject/DeliveryObject |
| External invitee declined; no attendance evidence | Observation only/Review source | Assume meeting happened | Missing attendance remains visible |
| External meeting verified attended, no open obligation | No action/stop | Generic courtesy recap by default | Explicit no-action trace |
| External meeting with promised deck | Recommend exact deck delivery, named recipient/date and clarify/renegotiate Alternative | Replace deliverable with generic recap | Completion is delivery/acceptance of exact deck |
| Group cohort where organizer explicitly promised shared notes | Governed group follow-up to eligible attendees only, with approved content and privacy-safe audience | Expose full attendee list or send to declined/nonparticipants | One deduped delivery per lawful recipient; receipt reconciliation |
| Mixed internal/external event, one confidential segment | Narrow content/audience or require approval | Send common recap containing restricted facts | Visibility intersection enforced |
| Recurring event, only one occurrence happened | Scope evidence/action to occurrence id | One card containing all recurrences | Exactly one current occurrence decision |
| Transcript says no next steps | No action/stop even though attendance is proven | Recap because transcript exists | Decision cites explicit absence of obligation, not source absence |
| Meeting outcome recorded in another tool | Suppress duplicate follow-up if completion predicate is met | Resurface calendar task | Cross-channel completion receipt closes loop |
| Source disconnected after invitation | Observation only; freshness unknown | Treat lack of cancellation/update as confirmation | Source-readiness hard gate fails |

## Replay assertions

1. Identical fixture and version set produce identical non-action decision and trace hash.
2. No action text, action button, ExecutionObject or DeliveryObject exists for the base fixture.
3. `scheduled`, `occurred`, `attended`, `external_counterparty` and `open_loop` are independent fields; no rule aliases them.
4. Every actionable mutation names exact recipient, follow-up object, stakes, owner/approval, expiry, Alternative and Completion.
5. Removing attendance or obligation evidence from an actionable fixture deterministically returns to Observation only.
6. Private/group audience constraints survive source → BSO → package → decision → delivery → learning.

## Outcome

The base replay passes when the past group event produces no recap CTA and clearly states the missing occurrence/attendance/external-obligation evidence. The promised-deck mutation passes only when the exact asset reaches the correct external counterparty and acceptance is reconciled separately from delivery. Success is **zero fabricated recap work, zero wrong/group-wide recipients, and one evidence-grounded follow-up only when a real unresolved obligation exists**.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../01-Layer-1-Knowledge/06-Improvements-Acceptance-and-Metrics/README.md" (M2.C1.L-interface.V0.U01)
-->
