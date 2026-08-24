# Update 1 — Intelligence Cards Have Zero Decision Clarity Across Situations

**Status:** Open — analysis and implementation specification only

**Severity:** Critical — the user repeatedly cannot understand what the situation is or what to do

**Observed surface:** GeniOS browser/Mac side-panel intelligence cards

**Observed examples:** `Reply to invite@thegenios.com now`, `Deliver the commitment to
nitesh.pant@devdashlabs.com today`, and `Deliver the commitment to nelieo.shorya@gmail.com today`

---

## 1. Executive summary

This is not one bad unanswered-email card. It is a system-wide clarity failure across the current
intelligence-card model. Different cards can show contacts, dates, tags, profile attributes, scores,
confidence, urgency, and an action-like headline, yet still fail to answer the questions a person
needs before acting:

- Who is this person or team?
- What situation or source interaction is this about?
- What exactly are they waiting for, and what did we promise?
- Why does this matter now?
- What happens if we do nothing?
- What exactly should the user do?
- What evidence supports the recommendation?

As a result, the card creates the impression of intelligence while leaving the user with zero
decision clarity. The user has to open Gmail, Calendar, CRM, or another source, locate the relevant
record, reconstruct the situation, determine what matters, and decide what to do. That is the
cognitive work GeniOS is supposed to remove.

This is not only a UI-copy problem and it cannot be fixed by adding more profile fields. The system
currently surfaces available metadata around the situation without guaranteeing that the decisive
context is present. The correction must cover the upstream facts, entity and situation assembly,
Decision Brief, card projection, API contract, UI rendering, action semantics, persistence, tests,
and migration/backfill behavior for every actionable card type.

---

## 2. What the user currently sees

### 2.1 Observed example A — unanswered email

The original card contains approximately:

- `Reply to invite@thegenios.com now`;
- `8d since they wrote — still waiting on you`;
- source: Gmail;
- observation: `Positive reply`;
- `Ball in court: on you`;
- `Last heard from them: 4 Aug`;
- score, confidence, and urgency numbers;
- actions: `I'll do it`, `Snooze`, and `Not relevant`.

These fields prove only that an unanswered thread was detected. They do not prove what reply is
required or why replying is the correct business action.

### 2.2 Observed example B — DevDash commitment

Another card says:

> `Deliver the commitment to nitesh.pant@devdashlabs.com today`

It includes company, role, phone, focus, proposed slot, due date, tags, score, confidence, urgency,
and Gmail grounding. However, it does not show the promised deliverable, the exact statement that
created the commitment, the relevant source thread, completion criteria, or the next concrete step.

The user searched the Context surface for `devdash` and found a primary record, one fact repeating
the email address, relationship/lifecycle labels, evidence count, freshness, and source badges. The
Context view still did not answer who this person is in the current situation, what was said, what
was promised, or what the user should do.

### 2.3 Observed example C — Nelieo commitment

The latest card says:

> `Deliver the commitment to nelieo.shorya@gmail.com today`

It shows:

- `14d overdue — you promised this`;
- `Nelieo Shorya · gmail.com`;
- Gmail and a due date of 29 July;
- labels including `Positive reply`, `Open question`, `Meeting proposed ×3`, `Intro thread`, and
  `Next step agreed ×2`;
- availability, phone number, date, product capability, scheduled time, and time;
- score 47, confidence 73%, and urgency 100%.

Despite the larger amount of metadata, the user still cannot tell:

- what commitment was made;
- which of the multiple proposed meetings or next steps is relevant;
- what `runtime execution layer` means in this commitment;
- whether the user must send something, prepare something, attend a meeting, make an introduction,
  or confirm a decision;
- what successful completion looks like;
- why the action must happen today rather than simply being old.

This proves that adding attributes does not create clarity. The card contains more data, but not the
specific decision context.

### 2.4 Repeating failure pattern

| Current field/pattern | Why it does not create clarity |
|---|---|
| Email address or guessed display name | Identity label without an explained relationship or role in this situation. |
| `Reply now` / `Deliver the commitment` | Generic verb without the required outcome, artifact, recipient need, or completion criteria. |
| `Positive reply`, `Open question`, `Meeting proposed`, `Next step agreed` | Classification labels; they do not summarise what was said or which event controls the decision. |
| Profile attributes and phone number | Potentially useful background, but not proof of the current commitment or required action. |
| Availability/scheduled time | A date field without explaining whether it is the commitment, meeting, deadline, or historical proposal. |
| `Ball in court: on you` | Workflow state, not business context or consequence. |
| `14d overdue` / `Last heard 4 Aug` | Explains age, but not why the age matters or what is overdue. |
| Score | The user cannot tell what it means or how it affected the recommendation. |
| Confidence | It is unclear whether this is identity, extraction, evidence, situation, or recommendation confidence. |
| Urgency 99–100% | There is no grounded consequence or deadline basis explaining maximum urgency. |
| `I'll do it` | The resulting transition is unclear: claim, acknowledge, open source, execute, or complete. |

### 2.5 Product failure

The cards currently say:

> A pattern or open loop was detected, and here is surrounding metadata.

Every actionable card instead needs to say:

> Here is the verified situation, what specifically is expected, why it matters now, exactly what
> should happen next, what completion means, and the evidence behind that recommendation.

If GeniOS cannot answer those questions, it must say that context is incomplete instead of
presenting a confident action headline.

---

## 3. What the repository currently does

### 3.1 One visible example: the unanswered-email rule detects only a minimal condition

`genios_engine/packs/general_v1.py` fires `unanswered_email` when:

- `thread.ball_in_court == "us"`; and
- at least two days have passed since `thread.last_inbound`.

The selected play is `reply`. The fallback template is intentionally short:

- Headline: `Reply to {entity} now`
- Situation: `{days}d since they wrote — still waiting on you`

This is sufficient to detect an overdue response. It is not sufficient to explain what the sender
needs or why a reply is valuable. The same conceptual failure applies to commitment cards: detecting
that a due date passed is not the same as knowing the promised outcome, completion criteria,
business consequence, or correct next action.

### 3.2 The card builder persists a presentation shell, not the complete decision context

`genios_engine/deliver/card_builder.py` currently builds:

- headline/situation inputs;
- score and score inputs;
- assignee;
- a short evidence list;
- context tags;
- generic actions such as `run_play`, `do_it_myself`, `snooze`, and `wrong`.

It does not attach a complete Decision Brief containing the request, business stakes, recommendation
objective, steps, risk, consequence of inaction, and alternatives.

### 3.3 A partial Decision Brief already exists, but it is not connected to cards

`genios_engine/executive/brief.py` already composes `brief.v1` with fields such as:

- situation;
- why it matters;
- recommendation;
- evidence;
- risks;
- confidence;
- cost of inaction;
- provenance.

However:

1. `genios_engine/deliver/pipeline.py` does not compose or attach this brief when building cards.
2. The `cards` table has no persisted brief or authoritative brief reference.
3. The existing `why_it_matters` often renders scoring language such as `score 73, confidence 77`
   instead of a user-facing business reason.
4. The brief documentation mentions alternatives, but the emitted `brief.v1` object does not contain
   an `alternatives` field.
5. The recommendation identifies a verb/play but does not provide sufficiently specific user steps
   for the actual situation.

The right architectural concept exists, but its shape is incomplete and it is not integrated into
the card-delivery path.

### 3.4 The proactive insights API removes most of the remaining context

`GET /v1/insights` in `genios_engine/api/intelligence_routes.py` projects a card into approximately:

- title;
- one-line detail;
- contact name;
- generic action label;
- normalized score;
- source tools/domains.

It does not reliably return the subject's verified identity/relationship, source-object title,
specific request or promised outcome, stakes, consequence of inaction, evidence summary,
recommendation steps, completion criteria, or CTA semantics.

It also converts the overall card score into `confidence_score`. Overall utility/priority is not the
same quantity as evidence or recommendation confidence. This makes the displayed metric easy to
misinterpret.

### 3.5 The detail endpoint adds generic context too late

`GET /cards/{card_id}` in `genios_engine/api/routes.py` enriches the full card with profile facts and
relationship observations. This is useful, but:

- the side-panel feed is populated by `/v1/insights`, so this context is not available in the initial
  card payload;
- generic profile facts do not identify the exact request, commitment, or governing source event;
- observations such as `positive_reply` remain labels rather than decision-ready summaries;
- the enrichment is not joined to one authoritative, versioned Decision Brief.

### 3.6 The card contract has no universal clarity gate

The repeated examples show that the pipeline can produce an actionable-looking card when it has
detected a pattern and accumulated surrounding attributes, even if the decisive context is absent.
There is no universal cross-card contract that requires every actionable card to prove:

- the exact situation;
- the expected outcome or obligation;
- the evidence creating that expectation;
- the accountable owner and recipient;
- the why-now reason and consequence;
- the concrete next step and completion criteria.

Without this gate, individual card types can keep adding fields while remaining unusable. The
correction must therefore be enforced at the shared Intelligence Object/Decision Brief/card boundary,
not implemented as a one-off fix for `unanswered_email`.

---

## 4. Root cause

This is an integration and contract gap across layers, not a missing sentence.

```text
Source evidence from Gmail/Calendar/CRM/etc.
    ↓
Rule/pattern detects an open loop, due date, tag, or changed state
    ↓
Available attributes are gathered without proving the decisive context
    ↓
Decision Brief is incomplete or not attached
    ↓
/v1/insights reduces the card again
    ↓
UI receives an actionable-looking reminder, not an explained decision
```

The surface cannot display information the API does not return, and the API cannot return decision
context that was never assembled and attached to the card read model. More importantly, no surface
should be allowed to render an action-specific headline merely because the system has a contact,
date, and high score.

---

## 5. Required behavior

Every actionable intelligence card must answer five questions without requiring the user to open the
source first.

### 5.0 Universal zero-clarity gate

Before a card may display an action-specific imperative such as `Reply`, `Deliver`, `Escalate`,
`Review`, `Approve`, `Contact`, or `Schedule`, the authoritative decision context must make all of
the following clear:

1. **Situation:** What exactly happened or changed?
2. **Expectation:** What request, promise, obligation, risk, or decision now exists?
3. **Meaning:** Why does it matter to this user/workspace now?
4. **Action:** What exact outcome must the user or agent produce?
5. **Proof:** Which evidence supports every load-bearing claim?
6. **Completion:** How will GeniOS know the work is actually complete?

If any action-critical answer is unknown, the card must switch from an execution recommendation to
a context-recovery recommendation. Surrounding metadata, a high score, or a familiar contact cannot
bypass this gate.

### 5.1 Who is this?

Show only grounded subject information. The subject may be a person, team, company, deal, project,
customer, commitment, approval, document, incident, or another typed business object.

For a person/contact, show:

- verified display name, when known;
- verified organisation/team, when known;
- email address;
- relationship to the user/company;
- source system.

If resolution produced only an email address, say so. Do not turn a mailbox local-part or domain into
an invented person/team name.

### 5.2 What happened, and what are they waiting for?

Show:

- source-thread subject or source-object title;
- a grounded one- or two-sentence situation summary;
- the latest explicit question, request, commitment, obligation, risk, or required decision;
- the exact promised/requested outcome and who stated or accepted it;
- who currently owns the next move;
- when the source event occurred;
- the age of the open loop.

`Positive reply` can appear as supporting evidence. It cannot replace the actual request summary.

### 5.3 Why does this matter now?

The card must state a grounded business reason, for example:

- a verified deadline is approaching;
- a promised response is overdue;
- an opportunity, relationship, customer, approval, or commitment is at risk;
- another party cannot proceed until this response arrives.

Elapsed time alone is not a business consequence. `Score 51` is not a user-facing reason.

If no consequence or deadline is supported by evidence, the card must say that the impact is unknown
and must not display artificial near-maximum urgency.

### 5.4 What exactly should the user do?

The recommendation must include:

- one specific outcome-oriented action;
- what the response/action must accomplish;
- two or three grounded steps when the action is non-trivial;
- an `Avoid` guardrail when there is a meaningful risk;
- required artifact, recipient, channel, and deadline when applicable;
- observable completion criteria;
- the selected play and required approval boundary.

Bad:

> Reply now.

Good shape:

> Confirm or decline the requested invitation today. If confirming, provide the requested attendee
> details. If the request is no longer relevant, close the loop explicitly.

The example above is a shape, not a claim about the observed email. Actual text must be derived from
the real source evidence.

### 5.5 What proves this recommendation?

Show a concise evidence chain:

- source application;
- exact thread/source reference;
- relevant event timestamp;
- grounded excerpt or structured fact;
- fact/evidence confidence;
- decision and trace identifiers in the expandable technical view.

The default card should stay concise. Full evidence can open in a detail panel.

The evidence view must connect each claim to its supporting source. A flat list of evidence badges
or a numeric evidence count is not enough when the card depends on different evidence for identity,
commitment, due date, consequence, and recommended action.

---

## 6. Fail-closed behavior when context is missing

The observed examples may not contain enough structured evidence to know what
`invite@thegenios.com` wants or what was promised to Nitesh/Nelieo. In that state, GeniOS must not
pretend that `Reply now` or `Deliver the commitment today` is a complete recommendation.

The card should instead say:

> **Reply context is incomplete**
>
> We verified that `invite@thegenios.com` wrote on 4 Aug and the next move is yours, but we could not
> verify what response they need.

Recommended action:

> Review the source email before responding.

Allowed primary action:

- `Open email`

Disallowed until the request is grounded:

- `Reply now` as a confident recommendation;
- `Urgency 99%` without a supported deadline/consequence;
- an automatically generated response claiming unknown facts;
- any action that marks the loop complete merely because the card was opened or claimed.

For an incomplete commitment, the card should say:

> **Commitment details are incomplete**
>
> We found evidence of a possible commitment to Nelieo due on 29 July, but we could not verify the
> promised deliverable or completion criteria.

Recommended action:

> Open the source thread and verify what was promised before acting.

Allowed primary actions:

- `Open source`;
- `View evidence`;
- `Mark as incorrect` when the commitment detection itself is wrong.

Disallowed until the commitment is grounded:

- `Deliver the commitment` as an executable instruction;
- `Urgency 100%` without an evidenced why-now consequence;
- automatic drafting, sending, scheduling, assigning, or completion;
- treating profile attributes, tags, or a due-date field as proof of the promised outcome.

This distinction is essential:

- confidence that an open loop exists;
- confidence that an identity/relationship is correctly resolved;
- confidence about what the sender wants or what was promised;
- confidence that the deadline and consequence are correct; and
- confidence that a particular action is correct

are three different values and must not be collapsed into one number.

---

## 7. Proposed card read-model contract

The card is a presentation/read model of authoritative upstream objects. It must not become a new
decision maker. The contract must work for unanswered messages, commitments, approvals, risks,
incidents, opportunities, and future situation types—not only email. The exact field names can
change during implementation, but the following semantics must survive end to end.

```json
{
  "card_version": "card.v2",
  "card_id": "...",
  "decision_id": "...",
  "decision_hash": "...",
  "execution_id": "...",
  "trace_id": "...",
  "subject": {
    "entity_id": "...",
    "entity_type": "person",
    "display_label": null,
    "relationship_to_workspace": null,
    "resolution_status": "address_only"
  },
  "identity": {
    "display_name": null,
    "address": "invite@thegenios.com",
    "organization": null,
    "relationship": null,
    "resolution_status": "address_only"
  },
  "situation": {
    "type": "unanswered_email",
    "summary": null,
    "source_subject": null,
    "last_inbound_at": "...",
    "age_days": 8,
    "ball_in_court": "us"
  },
  "request": {
    "summary": null,
    "requested_outcome": null,
    "deadline_at": null,
    "grounding_status": "missing"
  },
  "obligation": {
    "kind": "reply_required",
    "owner": "user",
    "recipient": null,
    "promised_outcome": null,
    "completion_criteria": null,
    "grounding_status": "missing"
  },
  "stakes": {
    "why_it_matters": null,
    "cost_of_inaction": null,
    "grounding_status": "missing"
  },
  "recommendation": {
    "verdict": "review_source",
    "objective": "Verify what response is required",
    "steps": ["Open the source email", "Review the sender's explicit request"],
    "avoid": "Do not send or mark complete until the request is verified",
    "play_id": null,
    "confidence_bp": 0
  },
  "actionability": {
    "state": "context_incomplete",
    "missing_required_fields": ["requested_outcome", "completion_criteria"],
    "allowed_effect_level": "read_only_verification"
  },
  "priority": {
    "score": 51,
    "reason": "Open loop has remained unanswered for 8 days"
  },
  "evidence": [],
  "source": {
    "tool": "gmail",
    "thread_ref": "...",
    "open_url": "..."
  },
  "actions": [
    {"id": "open_source", "label": "Open email", "effect": "none"},
    {"id": "claim", "label": "I'll handle this", "effect": "claim_only"},
    {"id": "snooze", "label": "Snooze", "effect": "defer_surface"},
    {"id": "not_relevant", "label": "Not relevant", "effect": "feedback"}
  ]
}
```

Important: this JSON is the unanswered-email variant of the shared contract. A commitment variant
must replace `request`/`obligation` semantics with the exact promised deliverable, owner, recipient,
due-date basis, and completion criteria while retaining the same clarity and grounding rules.

Null/unknown values above are intentional. Unknown facts must remain unknown. The UI must change its
headline, recommendation, actionability state, and CTA set based on grounding status instead of
filling the gaps with confident generic language.

---

## 8. Layer ownership

### Layer 1 — Knowledge

- Preserve source object/thread/message/event identifiers and evidence spans.
- Extract explicit questions, requests, commitments, obligations, response requirements, promised
  outcomes, completion criteria, and dates under a strict schema.
- Never invent an identity, request, promise, deadline, consequence, or completion condition.

### Layer 2 — Context

- Resolve each subject to a person/team/organisation or other typed business object only when
  evidence supports it.
- Assemble the relevant source events into the correct business situation and distinguish competing
  meetings, questions, commitments, and next steps.
- Keep identity confidence separate from evidence freshness and consistency.
- Expose missing, conflicting, stale, superseded, and verified context explicitly.

### Layer 3 — Domain Expertise

- Provide the relevant capability, constraints, play definitions, and missing-information policy.
- Define what evidence is required before an action-specific recommendation is allowed.
- Define the minimum clarity/completion contract for each situation type.

### Layer 4 — Reasoning

- Decide whether the correct result is an action such as `reply`/`deliver`, or a recovery state such
  as `review_source`, `request_more_context`, `defer`, or `no_action`.
- Produce the grounded recommendation, evidence references, confidence, alternatives, and why-trace.
- Never use elapsed time alone as proof of a business consequence.
- Block an action-specific imperative when its required outcome or completion criteria are unknown.

### Layer 5 — Executive

- Convert the decision into an understandable situation, expected outcome, concrete steps,
  guardrails, accountable owner, success/completion events, and cost of inaction.
- Produce the authoritative Decision Brief/Execution context the card projects.

### Layer 5.2 — Delivery

- Select the current surface/time/recipient under policy.
- Render the concise card from the authoritative decision/execution context.
- Never create a new recommendation merely because the required fields are absent.
- Render an explicit `Context incomplete` state when the shared clarity contract is not satisfied.

### API and UI

- Preserve the same semantic contract through `/v1/insights`, card detail, browser extension, and
  dashboard.
- Use progressive disclosure: concise decision card first, detailed evidence/technical trace on
  demand.
- Keep button labels and side effects explicit.
- Never let responsive/compact layouts remove the fields required to understand the decision.

---

## 9. Required implementation changes

### 9.1 Upgrade the Decision Brief

Create a backward-compatible new brief version or additive shape that includes:

- typed subject plus verified identity/relationship where applicable;
- exact source situation and governing event(s);
- explicit request, promised outcome, obligation, or required decision;
- accountable owner, recipient/stakeholder, and due-date basis;
- business-facing `why_it_matters`;
- specific recommendation objective and steps;
- required artifact/channel and observable completion criteria;
- alternatives;
- cost of inaction;
- actionability and missing-required-context status;
- separate evidence, identity, situation, deadline, and recommendation confidence;
- evidence and authority lineage.

Do not make `why_it_matters` a formatted score string. Scores may support the explanation, but they
are not the explanation.

### 9.2 Connect the brief to card construction

`genios_engine/deliver/pipeline.py` must obtain the authoritative brief/decision projection for the
same signal, reasoning run, candidate, decision hash, config snapshot, and evaluation time used to
build the card.

The card builder must not perform independent reasoning. It should only select and format fields from
the authoritative brief/execution object.

### 9.3 Persist the projection and lineage

Add an additive migration rather than rewriting migration history. Persist either:

- the immutable/versioned brief payload plus its semantic hash; or
- a stable brief/decision reference with a deterministic read projection.

Every card must remain traceable to the exact decision and execution authority that produced it.
Existing open cards require a defined backfill/rebuild policy; they must not silently keep the old
sparse semantics forever.

### 9.4 Expand `/v1/insights`

The list response must contain enough preview context to render the compact card without another
round trip:

- typed and grounded subject label;
- verified situation summary;
- explicit request/promise/obligation or `missing` state;
- accountable owner and expected outcome;
- business reason/why-now;
- recommendation objective;
- completion criteria or an explicit missing state;
- actionability state and missing required fields;
- correctly named priority and confidence fields;
- claim-linked source/evidence preview;
- typed actions.

The detail endpoint should return the full brief, steps, evidence, alternatives, and technical trace.

Do not map the overall score into a field named `confidence_score`.

### 9.5 Replace generic CTA semantics

Every action must have a documented state transition:

| Action | Required meaning |
|---|---|
| `Open email` / `View source` | Read-only navigation; does not claim or complete the loop. |
| `View advice` | Opens grounded steps and guardrails; does not draft or execute. |
| `I'll handle this` | Claims/acknowledges ownership only; does not mark the work complete. |
| `Mark done` | Available only after explicit user confirmation or verified success evidence. |
| `Snooze` | Defers delivery until a visible selected time; does not change the decision. |
| `Not relevant` | Records structured feedback and closes/suppresses according to policy. |
| `Assign to agent` | Approval-bound handoff carrying the complete execution context and scope. |

### 9.6 Update the surfaces

The compact card should render, in order:

1. Situation and grounded subject/identity;
2. what is expected: request, promise, obligation, risk, or decision;
3. why it matters/why now;
4. recommended outcome and concrete next step;
5. owner and completion criteria;
6. evidence and scores, progressively disclosed;
7. explicit CTAs.

The implementation must update every consumer of the insights/card contract, not only the screenshot
surface.

---

## 10. Acceptance criteria

This update is complete only when all of the following are true.

### Content correctness

- [ ] Every actionable card passes the universal situation, expectation, meaning, action, proof, and
      completion clarity gate.
- [ ] No actionable card shows only a subject/contact plus a generic verb when richer grounded
      context exists.
- [ ] If richer context does not exist, the card explicitly says context is incomplete and changes
      the recommendation to `review_source` or another fail-closed outcome.
- [ ] `Why this matters` contains a grounded business reason, not only a score, date, or
      ball-in-court status.
- [ ] The recommendation states what outcome the action must achieve.
- [ ] `Deliver the commitment` cannot appear unless the promised outcome and completion criteria are
      grounded.
- [ ] Classification tags and profile attributes cannot substitute for the situation summary.
- [ ] Evidence displayed on the card is a subset of evidence that actually affected the decision.
- [ ] Unknown identity, request, promised outcome, deadline basis, consequence, and completion
      criteria remain unknown.

### Score correctness

- [ ] Priority/utility, evidence confidence, identity confidence, situation confidence, deadline
      confidence, and recommendation confidence are separately named and never silently substituted
      for one another.
- [ ] Every visible score has an expandable explanation of its inputs.
- [ ] Near-maximum urgency cannot appear without a grounded why-now reason.

### Action correctness

- [ ] Every CTA has one documented server-side effect and audit event.
- [ ] `I'll handle this` cannot mark the card completed.
- [ ] Opening the source cannot mark the card claimed or completed.
- [ ] External effects remain approval-bound and scope-bound.
- [ ] Success is closed by verified evidence or explicit confirmation, not by a button-label
      assumption.

### Contract and integration correctness

- [ ] The clarity gate is shared across all card types rather than embedded only in the
      `unanswered_email` implementation.
- [ ] The authoritative brief/decision lineage survives into the persisted card projection.
- [ ] `/v1/insights` returns the compact decision context.
- [ ] The card-detail endpoint returns the full brief/evidence context.
- [ ] Browser extension, dashboard, notifications, and any agent API consume compatible versioned
      semantics.
- [ ] Existing open cards are backfilled/rebuilt or explicitly version-gated.
- [ ] Older clients receive a supported compatibility shape during rollout.

### Privacy and grounding

- [ ] List responses contain only the minimum safe preview; sensitive source excerpts remain behind
      authenticated detail access.
- [ ] Tenant, visibility, and participant restrictions are preserved.
- [ ] No LLM-generated identity, date, number, request, or consequence bypasses the invention and
      grounding validators.

---

## 11. Tests the CTO must add

### Unit tests

- Decision Brief emits `request.grounding_status=missing` when the explicit ask is absent.
- Missing request produces `review_source`, never `reply_now`.
- Missing promised outcome produces `review_source`, never `deliver_commitment`.
- Missing completion criteria prevents an executable commitment action.
- Grounded request plus sufficient evidence produces a specific recommendation.
- A high score, old due date, many evidence items, tags, or rich profile attributes cannot bypass the
  universal clarity gate.
- Overall utility is never returned as recommendation/evidence confidence.
- Generic fallback never invents identity, organisation, request, promised outcome, deadline,
  consequence, or completion criteria.
- `I'll handle this` transitions to claimed/running ownership only, not completed.

### API contract tests

- `/v1/insights` returns the complete compact preview contract.
- `/cards/{card_id}` returns the full authoritative brief and evidence lineage.
- Old and new card versions deserialize during the migration window.
- Unauthorized users cannot retrieve source excerpts or cross-tenant context.

### End-to-end fixtures

Create deterministic fixtures across multiple card types:

1. **Complete unanswered email:** verified sender, subject, explicit request, date, consequence, and
   evidence. The card must explain the situation and provide a specific action.
2. **Incomplete unanswered email:** only sender address, last inbound time, and ball-in-court are
   known. The card must say context is incomplete, show `Open email`, and withhold confident
   reply/urgency claims.
3. **Complete commitment:** verified owner, recipient, exact promised outcome, source statement,
   due-date basis, consequence, and completion criteria. The card may recommend a specific delivery
   action.
4. **Incomplete commitment:** contact, tags, profile fields, due date, and high score are present, but
   the promised outcome is missing. The card must show `Commitment details are incomplete`, offer
   source/evidence review, and withhold `Deliver the commitment`.
5. **Ambiguous competing events:** multiple meeting proposals and next-step labels exist. The card
   must not arbitrarily choose one as the governing commitment.

Add at least one non-email situation fixture to prove that the clarity gate is a shared card
contract rather than email-specific behaviour.

### Required verification after implementation

The final implementation should at minimum run:

```bash
.venv/bin/pytest -q tests/test_executive_brief.py tests/test_delivery.py \
  tests/test_intelligence_authority_routes.py \
  tests/test_card_decision_context.py tests/test_insights_card_contract.py
.venv/bin/python -m compileall -q genios_engine
.venv/bin/pytest -q
```

`tests/test_card_decision_context.py` and `tests/test_insights_card_contract.py` are proposed new test
files. These commands are a required future verification contract; they have not been run as part of
this analysis-only update because the implementation does not exist yet.

Database-backed verification must also apply all migrations to a clean test database and prove that
existing card rows remain readable or are migrated by the declared backfill path.

---

## 12. Non-goals and guardrails

- Do not solve this only by adding more frontend text.
- Do not solve this by showing every available attribute; more metadata is not decision clarity.
- Do not ask an LLM to invent the missing business reason at card-render time.
- Do not turn `positive_reply` or an email domain into an inferred identity.
- Do not treat `meeting_proposed`, `next_step_agreed`, an old date, or a product-capability field as a
  complete commitment.
- Do not expose raw private email content in list responses or notifications.
- Do not let Delivery make a new business decision.
- Do not auto-send, schedule, deliver, assign, or complete anything as part of this correction.
- Do not mark work complete because the user opened, claimed, or snoozed the card.
- Do not remove current authority, replay, grounding, visibility, and invention safeguards to make the
  richer card easier to render.

---

## 13. The 60-second CTO version

This is a system-wide zero-clarity defect, not one bad email card. Across the observed examples,
GeniOS can show a contact, company/profile fields, dates, tags, score, confidence, urgency, and a
headline such as `Reply now` or `Deliver the commitment today`. The user still cannot tell what was
said, what was promised, which source event matters, why action is required now, what exact outcome
to produce, or what completion means. The Nelieo card proves that adding more metadata does not fix
the issue: it contains many attributes and labels but still omits the commitment itself.

The repository already has part of the correct abstraction in `brief.v1`, but the card pipeline does
not attach it, the brief itself is incomplete, the cards schema stores a sparse shell, and
`/v1/insights` drops most context again. The fix must introduce a shared, versioned clarity gate and
grounded decision-card projection for every situation type. The projection must preserve the typed
subject, exact situation, request/promise/obligation, owner, expected outcome, due-date basis,
stakes, why-now reason, recommendation, steps, completion criteria, claim-linked evidence, separate
confidence meanings, source lineage, and typed action semantics through every UI consumer.

When any action-critical field is missing, the system must fail closed: explicitly say what context
is incomplete, offer `Open source`/`View evidence`, and withhold the action-specific imperative and
unexplained maximum urgency. No score, contact profile, evidence count, tag collection, or old date
may bypass that rule.
