# Golden Replay 04 — Already Replied and Cross-Channel Resolved

## Evidence boundary

**[CUSTOMER]** reports that activity already completed or an email already handled can be resurfaced as “intelligence.” **[SCREENSHOT]** supplied cards show generic `Reply now` and overdue actions driven by old “last heard” dates, but the images do not prove that those exact asks were already answered in another channel. They establish the stale-loop surface pattern, not completion truth or runtime causation.

**[CODE]** establishes concrete exposure: Layer 2 has tested graph/lifecycle machinery but no proven authoritative request/action identity reducer spanning channels; person-global operational state and wrong-close risk are documented; the BSO boundary can reconstruct membership and omit missing-state truth; card acceptance and native execution are separate; the Layer 6 reminder bridge may use shallow open/expiry checks. This replay tests both false-open and false-close behavior. Cross-channel matching must close the exact request only—never every loop involving the person.

## Scenario contract

| Field | Required value | Blocking condition |
|---|---|---|
| **Business subject** | Exact person/company plus scoped relationship and request/commitment/opportunity | Person-only scope or ambiguous relationship ⇒ Review source |
| Exact open loop | Stable request/action identity, its requester/target/owner, created state and authoritative ordered transitions | No request identity or conflicting transitions ⇒ Observation only/Review source |
| Candidate completion | A same-thread reply, other-channel response, calendar change, delivered asset or external event mapped to the exact completion predicate | Semantic similarity/person match alone cannot close |
| Current state | Active, satisfied, superseded, expired, revoked or reopened, with source readiness and version fence | Incomplete provider window ⇒ no negative inference or automatic close |
| Completion | Verified event satisfies the exact request; closure is scoped and auditable | Card click, claim, send attempt, unrelated reply or generic meeting does not qualify |
| **Outcome** | Result following completion inside its declared window, recorded separately from closure and attribution | Closing a loop is not automatically business value |

## Current failure versus expected behavior

**Current failure:** a stale request can survive after the user answered or completed it elsewhere, producing duplicate outreach and destroying trust. The inverse failure is equally dangerous: a person-level reply can close multiple parallel asks even though only one was resolved. Both errors arise when “person had activity” substitutes for request-scoped current reality.

**Expected behavior:** GeniOS maintains a stable scoped request/action identity. New events are matched using strong thread, target, relationship, opportunity, content/object and completion-predicate evidence. An exact resolution suppresses the card, cancels queued work and records why. Ambiguous cross-channel evidence triggers Review source; it neither sends again nor silently closes unrelated work.

## Layer 1 through Layer 7 replay

| Layer | Deterministic input | Required output | Fail-closed behavior | Acceptance evidence |
|---|---|---|---|---|
| **Layer 1 — Knowledge** | Email/chat/CRM/calendar/provider events with message IDs, thread/channel IDs, direction, actors, timestamps, versions, visibility/use and source health | Immutable receipts preserving channel-specific identity, edits/deletions and ordering; no semantic completion inference | Park/mark source incomplete if cursor window, version, direction or permission is missing | Provider/event/version, parent/thread, actors, transformation and readiness receipts |
| **Layer 2 — Context Intelligence** | Qualified receipts plus stable request/commitment/action keys, identity/relationship and graph/policy versions | Ordered current-state reducer; exact completion matcher; lifecycle transition and matching reason; independent state for parallel asks | Review source on ambiguous match; Suppress only exact satisfied/superseded item; no person-wide close | BSO/request ID, evidence membership, completion event ID, match features, lifecycle and version fence |
| **Layer 3 — Domain Expertise** | Current-state BSO and four-brain snapshot | No package/play on satisfied/superseded request; accepted domain capability only for a genuinely active remainder | Observation only/unsupported if state or capability dependencies are incomplete | Package/coverage/snapshot plus current request lifecycle receipt |
| **Layer 4 — Reasoning** | Active or closed BSO plus authoritative expertise/unsupported status | Suppress closed candidate; for ambiguity choose Review source; for a new reopened ask create a new specific decision | Never preserve imperative merely because old score/age is high | Decision/suppression reason, candidate eliminations, exact Completion and validity |
| **Layer 5 — Executive Function** | Current decision/execution plus new completion/supersession mutation and authority versions | Atomically cancel/satisfy only matching pending execution; preserve audit; create new execution only for new request version | Block send during ambiguous race; “I'll do it” never competes with external completion | Request→decision→execution/action IDs and cancellation/completion mutation receipt |
| **Layer 6 — Delivery** | Materialized action plus immediate current-state/authority check | Suppress queued send if request closed; reconcile provider attempt if close/send race occurs | No delivery on stale version; ambiguous accepted-then-timeout must reconcile, not resend | Canonical DeliveryResult with suppression or attempt/idempotency/provider state |
| **Layer 7 — Learning** | Decision, suppression, actual completion, outcome, correction and counterfactual | Learn correction/duplicate-prevention separately; no negative outcome assigned to a safely suppressed stale action | No learning from person-wide correlation, click, send or unverified match | Scoped request/outcome lineage, matching correction, support/use gates and future consumption |

## Deterministic mutations

| Mutation | Expected behavior | Prohibited behavior | Pass condition |
|---|---|---|---|
| User replies in the original email thread and satisfies the ask | Exact request becomes satisfied; pending card/execution suppressed | Continue “reply now” | Matching completion ID and suppression/cancellation receipt are present |
| User answers exact ask in Slack/chat with explicit request or asset reference | Cross-channel matcher closes only that request | Ignore strong completion or close every ask with person | One exact close; wrong-close and stale-loop rates zero |
| Same person has two parallel asks; Slack reply resolves one | One satisfied, one remains independently active | Person-wide ball-in-court/close | Distinct request IDs and lifecycle states survive |
| Cross-channel message is vague: “done” without object/thread/relationship evidence | Review source; no duplicate send while ambiguous | Guess completion or leave imperative actionable | Exact review question, candidates and no action button |
| Calendar booking resolves a scheduling request but a promised deck remains | Close scheduling only; retain deck request | Close both or keep scheduling overdue | Predicate-specific matching and two independent states |
| Asset was sent but acceptance is required for Completion | Record executed/delivered; keep completion pending until acceptance/declared rule | Call send Completion or success | Action, delivery, Completion and Outcome states remain separate |
| Source sync is partial during expected reply window | Mark source incomplete; do not infer silence or resolution | Fresh overdue decision from missing interval | Readiness code blocks negative inference/action authority |
| Completion event is later corrected/deleted/revoked | Rebuild lifecycle from new authoritative version; re-evaluate safely | Keep stale closed/open card | Version-fenced retraction and dependent rebuild receipt |
| Authorized agent replied on user's behalf with origin execution ID | Map to exact execution/request once; mark agent actor | Treat as independent human corroboration or trigger loop | Idempotent origin prevents duplicate decision/learning |
| Contact replies with a new, materially distinct ask after closure | Original remains closed; create a new request ID/version and decision | Reopen old request blindly or suppress new ask | New evidence membership and exact `what remains` are separate |
| Queued message races with newly observed completion | Revalidate before send; suppress if unsent, otherwise reconcile attempt and avoid retry | Duplicate outreach | At most one external impression; race outcome auditable |
| Similar text appears from another same-name person | Identity ambiguity/review; do not match | First claimant closes request | No lifecycle mutation until anchored/reviewed identity |

## Prohibited behavior

- Do not resurface a satisfied, superseded, expired, revoked or duplicate request as new intelligence.
- Do not close multiple asks because the same person replied somewhere; match the exact relationship/request/completion predicate.
- Do not use semantic similarity, display name or person-wide `ball_in_court` as sufficient completion authority.
- Do not infer “still waiting” while a required provider/channel window is incomplete.
- Do not let a stale card score, cached decision, generic pack or LLM prose override a newer completion mutation.
- Do not call claim, sent, delivered, opened, suppressed or closed a business Outcome without the declared external result and counterfactual.

## Outcome and exit gate

The replay passes only when all same-channel, cross-channel, parallel-ask, ambiguity, source-outage, correction, agent-origin and send-race mutations yield the declared state. An active card must still include Business subject, exact `what remains`, evidence/readiness/conflicts, accepted expertise, action and Alternative, owner/approval, Completion and Outcome window. A closed request must have no action button and must expose an auditable suppression reason to authorized reviewers.

Hard gates are zero stale-loop resurfacing, zero wrong closes, zero person-wide contamination, 100% ambiguity abstention, 100% version-fenced retraction and at most one external impression per action. Customer value is reduced duplicate work and correction burden plus any verified opportunity progression; card suppression itself is safety evidence, not ROI.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../02-Layer-2-Context-Intelligence/06-Improvements-Acceptance-and-Metrics/README.md" (M2.C2.L-interface.V0.U01)
-->
