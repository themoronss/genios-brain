# Admin Intelligence: Layer 2 to Layer 5 Failure Analysis

**Document type:** Structured conversion of the architecture discussion  
**Scope:** Why GeniOS currently surfaces facts instead of actionable intelligence, what Layer 2 through Layer 5 must own, and how an Admin-only intelligence MVP should be structured  
**Numbering used in this document:** Layer 1 Capture, Layer 2 Context, Layer 3 Domain Expertise, Layer 4 Reasoning, Layer 5 Delivery

---

## 1. The Core Question

The product is capturing emails, meetings, people, companies, commitments, and other business records. But the visible output often reads like:

- An email was sent.
- A meeting happened.
- A commitment exists.
- A deal is in a particular stage.
- A contact has not interacted recently.

The expected intelligence is materially different:

- This investor has not replied six days after a warm introduction; follow up today with a meaningful company update rather than a generic reminder.
- This meeting finished three days ago, but the promised deck and next step were never sent; Rohit owns the follow-up.
- Thirteen people associated with 314 Capital and Far Network have not replied; four are high-value warm contacts and should be prioritised.
- This opportunity has remained in the same state longer than comparable opportunities and the economic buyer has stopped engaging.

The central problem is therefore not a lack of facts. It is a failure to carry evidence through the complete intelligence chain:

```text
Evidence
  -> Business context
  -> Bounded situation
  -> Domain interpretation
  -> Candidate decisions
  -> Selected action
  -> Accountable delivery
  -> Measured outcome
```

The system currently breaks at multiple boundaries in this chain.

---

## 2. Direct Verdict

The failure is not caused by only one layer.

| Layer | Primary question | Current failure mode | Customer-visible symptom |
|---|---|---|---|
| Layer 1: Capture | What evidence entered the system? | Source coverage or freshness may be incomplete | The relevant email, meeting, or record is missing entirely |
| Layer 2: Context | What is happening now, how did it change, and what is missing? | Facts are not consistently assembled into temporal, roleful, objective-aware situations | The product repeats facts instead of recognising an actionable situation |
| Layer 3: Domain Expertise | What does this situation mean in this business domain? | Expertise is not always routed, admitted, activated, or specific enough | Advice is generic, irrelevant, or absent |
| Layer 4: Reasoning | What should be done now, among the valid alternatives? | Company knowledge and competing actions do not sufficiently change selection | Every case produces the same shallow recommendation |
| Layer 5: Delivery | How should the decision be surfaced and acted upon? | Rich decisions are bypassed, flattened, stale, or shown through fact-oriented APIs | A fact card is presented as intelligence |

For unanswered emails, post-meeting follow-ups, and investor-outreach cases, the biggest semantic failure begins in Layer 2. The biggest expertise and runtime failures are in Layer 3. The final quality and personalisation failure is in Layer 4. The immediate facts-only presentation problem is in Layer 5.

---

## 3. The Correct Layer Boundaries

### Layer 1: Capture

Layer 1 should answer:

> What evidence entered the system, from which source, with what provenance and authority?

It should capture and preserve:

- Email envelopes and bodies
- Sent and received direction
- Calendar events and changes
- Documents
- CRM records
- Database records
- Source timestamps and identifiers
- Evidence lineage

Layer 1 should not decide whether an unanswered email deserves a follow-up. Silence is not an event sent by Gmail. It has to be derived later by evaluating captured evidence against time.

### Layer 2: Context and Business Situations

Layer 2 should answer:

> What is true now, who is involved, what was the objective, what changed, what did not happen, whose turn is it, and what decisive context is missing?

Layer 2 owns business-state understanding. It must not decide the best action.

### Layer 3: Domain Expertise

Layer 3 should answer:

> According to the relevant domain, what does this situation mean, which playbooks apply, what information is required, and which actions are eligible or prohibited?

Layer 3 should not select the final action merely because one rule matched.

### Layer 4: Reasoning

Layer 4 should answer:

> Given the situation, applicable expertise, company objectives, user preferences, uncertainty, and competing alternatives, what should be done now?

It must compare candidates, rank them, reject unsafe or low-value choices, and abstain when context is insufficient.

### Layer 5: Delivery

Layer 5 should answer:

> Who needs to know, when, through which surface, with what explanation and action affordance?

It must preserve the decision rather than reducing it back to a fact.

---

## 4. Why an Unanswered Email Is Not a Simple Fact

Suppose Rohit sends an investor an email on 25 August.

Layer 1 can directly capture:

```yaml
sender: Rohit
recipient: person@fund.com
sent_at: 2026-08-25
subject: Company update
```

But no source sends the following event:

```yaml
event: recipient_did_not_reply_for_six_days
```

That state must be derived:

```yaml
last_outbound_at: 2026-08-25
last_inbound_after_outbound: null
evaluation_time: 2026-08-31
elapsed_days: 6
response_expected: true
follow_up_count: 0
ball_in_court: external
```

This requires identity resolution, thread reconstruction, objective detection, elapsed-time computation, response expectation, and scheduled reevaluation. These are Layer 2 responsibilities.

Layer 3 must then interpret the state:

- Is this sales, fundraising, investor relations, hiring, or a vendor conversation?
- Is six days too early, appropriate, or too late?
- Is a progress update better than a reminder?
- Has the recipient already declined?
- Is a warm reintroduction preferable?
- When should the system recommend waiting or stopping?

Layer 4 then chooses the best action for this specific company and person.

Layer 5 finally presents a usable recommendation, draft, owner, timing, evidence, and expected result.

---

## 5. Layer 2: Exact Required Architecture

Layer 2 should be a pipeline of business-state components rather than a single extraction call or graph query.

```text
Layer 1 evidence
    -> Identity and entity resolution
    -> Roles and relationships
    -> Interaction reconstruction
    -> Intent and objective
    -> Timeline and state transitions
    -> Temporal and absence detection
    -> Commitments and open loops
    -> Cross-source correlation
    -> Cohort construction
    -> Situation assembly
    -> Context quality
    -> Situation refresh and lifecycle
    -> Layer 3-ready context slice
```

### 5.1 Identity and Entity Engine

This component must determine:

- Whether two names or email addresses refer to the same person
- Whether a person belongs to 314 Capital, Far Network, or another organisation
- Whether differently formatted organisation names refer to the same entity
- Whether the actor is the user, a teammate, an external contact, or an automated system
- Which person, organisation, thread, meeting, deal, or ticket should anchor the situation

It must preserve ambiguity instead of merging identities without evidence.

### 5.2 Role and Relationship Engine

Layer 2 should model roles such as:

- Founder
- Investor
- VC partner
- Prospect
- Customer
- Champion
- Decision-maker
- Economic buyer
- Candidate
- Employee
- Vendor
- Internal owner

It should also model relationship state:

- Cold outreach
- Warm introduction
- Active sales discussion
- Existing investor relationship
- Fundraising prospect
- Partnership discussion
- Customer relationship
- Internal dependency

Layer 2 establishes the role and relationship with evidence. Layer 3 decides what those roles mean for domain policy.

### 5.3 Interaction Reconstruction Engine

Individual emails and meetings must become one continuous interaction history:

```text
Initial outreach
  -> No response
  -> Reminder 1
  -> No response
  -> Meeting scheduled
  -> Meeting completed
  -> Deck promised
  -> Deck sent
  -> Investor response pending
```

Required state includes:

- Initial and latest outbound messages
- Initial and latest inbound messages
- Follow-up count
- Response latency
- Thread participants
- Channel transitions
- Current interaction state
- Related meeting and business object

Without this engine, the system cannot distinguish an initial email from a second or third reminder.

### 5.4 Intent and Objective Engine

The same words can appear in very different business contexts. Layer 2 should infer the objective with evidence and confidence:

- Fundraising outreach
- Investor update
- Sales outreach
- Partnership
- Hiring
- Customer support
- Vendor management
- Internal approval
- General business operations

Example:

```yaml
objective:
  type: fundraising_outreach
  target: investor_response
  confidence: 0.86
  evidence:
    - email subject
    - thread content
    - recipient role
    - attached pitch deck
```

### 5.5 Temporal State and Absence Engine

This is one of the most important missing capabilities.

It should derive:

- Time since last outbound
- Time since last inbound
- Time since meeting completion
- Time in business-object state
- Whether an expected event did not occur
- Whether a due date was crossed
- Whether an interaction has become dormant
- When the situation must be evaluated again

The engine must run when time passes, not only when a new event arrives.

```text
Day 0: Email sent
Day 3: Situation re-evaluated
Day 5: Follow-up threshold may be crossed
Day 7: Repeated silence state
```

Layer 2 should compute elapsed state. Layer 3 supplies domain thresholds and interpretation.

### 5.6 Commitment and Open-Loop Engine

Layer 2 should represent both explicit and inferred open loops.

Explicit:

> I will send the deck tomorrow.

```yaml
owner: Rohit
action: send_deck
due_at: tomorrow
status: open
```

Implicit:

> An important external meeting completed, a next step was discussed, but no follow-up evidence exists.

```yaml
type: post_meeting_follow_up
expected_owner: Rohit
due_at: inferred
inference_confidence: 0.72
requires_domain_policy: true
```

Layer 2 detects the open loop. Layer 3 and Layer 4 determine whether and how to act.

### 5.7 Business Object Lifecycle Engine

Layer 2 must preserve state history, not just current state:

- Deal-stage history
- Relationship-interaction history
- Meeting lifecycle
- Outreach lifecycle
- Support-ticket lifecycle
- Commitment lifecycle
- Customer lifecycle
- Approval and operational workflow lifecycle

This makes it possible to state:

> The deal has remained in Proposal for eighteen days and its close date moved twice.

instead of only:

> The deal is in Proposal.

### 5.8 Cross-Correlation Engine

This engine should connect related evidence across sources:

```text
Gmail: Proposal sent
Calendar: Follow-up meeting completed
Notion: Updated deck exists
CRM: Opportunity still marked Contacted
Gmail: No inbound response after the meeting
```

The output should be a coherent, evidence-backed situation. Correlation must not be misrepresented as causation.

### 5.9 Cohort and Pattern Context Engine

This component is necessary for network-level questions such as:

> Which founders, investors, and VCs associated with 314 Capital and Far Network have not replied?

Example output:

```yaml
cohort:
  type: investor_outreach
  organisations:
    - 314 Capital
    - Far Network
  contacted_people: 18
  replied: 5
  awaiting_response: 13
  waiting_more_than_five_days: 7
  already_followed_up: 4
  never_followed_up: 3
```

Layer 2 describes the cohort. Layer 3 and Layer 4 decide which contacts matter and what should be done.

### 5.10 Business Situation Engine

Situation types should describe what is happening rather than prematurely embedding domain judgment.

Recommended situation families:

#### Communication

- `communication.outbound_awaiting_response`
- `communication.inbound_awaiting_internal_reply`
- `communication.repeated_follow_up_without_response`
- `communication.thread_reactivated`

#### Meetings

- `meeting.upcoming_with_missing_preparation`
- `meeting.completed_without_follow_up`
- `meeting.promised_material_pending`
- `meeting.next_step_not_scheduled`
- `meeting.cancelled_or_rescheduled`

#### Commitments

- `commitment.approaching_due`
- `commitment.overdue`
- `commitment.owner_ambiguous`
- `commitment.fulfilment_unverified`

#### Relationships

- `relationship.no_recent_interaction`
- `relationship.stakeholder_changed`
- `relationship.single_threaded`
- `relationship.engagement_changed`

#### Business objects

- `business_object.state_unchanged`
- `business_object.state_changed`
- `business_object.source_state_conflict`
- `business_object.required_actor_missing`

#### Cohorts

- `cohort.outreach_response_gap`
- `cohort.follow_up_coverage_gap`
- `cohort.interaction_pattern_changed`

#### Epistemic and quality situations

- `context.identity_ambiguous`
- `context.decisive_evidence_missing`
- `context.sources_contradict`
- `context.evidence_stale`

### 5.11 Context Quality Engine

Layer 2 must separately report:

- Completeness
- Freshness
- Confidence
- Source authority
- Contradictions
- Identity ambiguity
- Temporal coverage
- Missing decisive fields

Example:

```yaml
quality:
  completeness: 0.68
  freshness: 0.94
  confidence: 0.81

missing_fields:
  - recipient_role
  - outreach_objective
  - expected_response_window

contradictions:
  - crm_says_open
  - email_indicates_not_interested
```

The engine must fail closed:

- Sufficient context: pass the situation to Layer 3
- Decisive fields missing: produce a clarification-required situation
- Conflicting evidence: produce a contradiction situation
- Stale evidence: request revalidation
- Identity unresolved: abstain from person-specific conclusions

### 5.12 Situation Refresh and Lifecycle Engine

Every situation should move through an explicit lifecycle:

```text
Detected
  -> Active
  -> Changed
  -> Escalated
  -> Resolved
  -> Expired
```

It must be reevaluated when:

- New evidence arrives
- A time threshold is crossed
- A CRM or business-object state changes
- A commitment becomes overdue
- A user corrects context
- Missing evidence becomes available
- The applicable domain policy changes

The same underlying situation should evolve rather than creating duplicate cards.

### 5.13 Required Layer 2 Output Contract

```yaml
situation_id:
situation_type:
evaluation_time:

anchors:
  person:
  organisation:
  thread:
  meeting:
  business_object:

actors:
  self:
  counterparty:
  roles:

objective:
current_state:
previous_state:
state_changes:

timeline:
  last_inbound:
  last_outbound:
  elapsed_time:

open_loops:
commitments:
ball_in_court:

evidence:
contradictions:
missing_fields:

quality:
  completeness:
  freshness:
  confidence:

next_evaluation_at:
```

Layer 2's definition of done is:

> For any person, company, meeting, thread, deal, or operational object, Layer 2 can explain who is involved, their roles, the objective, what happened, what did not happen, how long it has been, whose turn it is, what remains open, what evidence supports the state, what context is missing, and when the situation must be evaluated again.

Layer 2 must not choose the final action, rank business value, draft a message, or decide who should be interrupted.

---

## 6. Layer 3: Exact Required Architecture

Layer 3 turns a domain-neutral situation into domain-specific interpretation.

### 6.1 Universal Domain Router

Domain detection should not belong to the paid Admin pack. It should be an always-on universal routing capability.

Layer 2 supplies observed concepts:

```yaml
situation_type: communication.outbound_awaiting_response
objective: fundraising_outreach
recipient_role: investor
relationship: warm_introduction
```

The universal router produces multi-label domain candidates:

```yaml
domain_candidates:
  - domain: admin.investor_operations
    confidence: 0.93
  - domain: sales
    confidence: 0.18
```

The router should:

- Support primary and secondary domains
- Preserve uncertainty
- Accept human correction
- Avoid forcing every situation into one domain
- Remain independent of product entitlements

### 6.2 Domain Expertise Packages

Each capability should be executable rather than merely descriptive.

Required structure:

```yaml
capability:
trigger:
required_context:
eligibility_conditions:
negative_conditions:
timing_policy:
domain_thresholds:
candidate_actions:
abstention_conditions:
evidence_requirements:
expected_outcomes:
measurement_contract:
```

Example:

```yaml
capability: investor_first_follow_up

trigger:
  situation: communication.outbound_awaiting_response

required_context:
  - objective
  - recipient_role
  - relationship_type
  - elapsed_days
  - follow_up_count

eligibility:
  objective: fundraising_outreach
  recipient_role:
    - investor
    - vc_partner

negative_conditions:
  - recipient_explicitly_declined
  - do_not_contact
  - response_window_not_crossed
  - recent_follow_up_already_sent

candidate_actions:
  - send_progress_update
  - send_specific_question
  - seek_warm_reintroduction
  - wait
  - stop_outreach

abstain_when:
  - recipient_identity_uncertain
  - objective_unknown
  - thread_history_incomplete
```

### 6.3 Positive, Negative, and Abstention Expertise

Good expertise must know:

- When to act
- When to wait
- When not to act
- When a generic reminder is inappropriate
- When another channel is preferable
- When repeated follow-up creates relationship risk
- When evidence is insufficient
- When a human clarification is required

Without negative and abstention rules, the product becomes a reminder generator rather than an intelligence system.

### 6.4 Admission and Routing

Authored files are not production proof. Every live capability and situation definition needs:

- Review status
- Accepted admission state
- Reachable route from emitted Layer 2 situations
- Required-context validation
- Positive replay
- Negative replay
- Abstention replay
- Versioned receipts

Current audited corpus totals were:

- Sales: 47 complete, 47 routed
- Admin: 57 complete, 36 routed
- Customer Support: 49 complete, 42 routed
- Total: 153 complete, 125 routed

This means 28 authored capabilities were not reachable from current situation routes. Separately, the stricter admission check reported 28 blocked situation documents. These are distinct gaps even though the counts happen to match.

### 6.5 Activation

The Domain Expertise compiler is currently off by default in repository configuration:

```python
use_domain_compiler: bool = False
```

Therefore, expertise existing in the repository does not prove that it is the authoritative scheduled decision path for a deployed tenant.

### 6.6 Company-Specific Knowledge

Layer 3 must package four forms of knowledge:

1. Universal domain expertise
2. Organisation-specific rules and objectives
3. Behavioural patterns
4. Adaptive preferences and outcome learning

Packaging these values into metadata or a hash is insufficient. Layer 4 must demonstrably use them so that changing a company rule can change the selected action.

---

## 7. Layer 4: Exact Required Architecture

Layer 4 should not convert the first matched rule into a recommendation. It should compare valid candidates.

For one investor situation, candidates may include:

```text
A. Send a generic reminder
B. Send a meaningful progress update
C. Ask the warm introducer to reconnect
D. Wait three days
E. Stop following up
```

Layer 4 should rank them using:

- Current objective
- Urgency
- Expected business value
- Relationship strength
- Evidence quality
- Risk
- Follow-up count
- Recipient seniority
- User preference
- Previous outcomes
- Cost of interruption
- Reversibility
- Explicit organisational constraints

### 7.1 Required Reasoning Stages

```text
Applicable expertise
  -> Generate candidate actions
  -> Apply eligibility constraints
  -> Apply negative and safety constraints
  -> Score impact, urgency, confidence, and cost
  -> Apply organisation rules
  -> Apply behavioural and adaptive knowledge
  -> Compare alternatives
  -> Select, wait, clarify, or abstain
  -> Produce a decision receipt
```

### 7.2 Required Decision Output

```yaml
decision:
  recommended_action:
  owner:
  timing:
  expected_result:

why_now:
why_this_action:

alternatives:
rejected_candidates:
uncertainties:
missing_context:

evidence:
confidence:
priority:

completion_condition:
outcome_measurement:
```

### 7.3 Definition of Real Personalisation

The following replay must produce a meaningful difference:

```text
Same evidence
+ Organisation rule A
= Decision A

Same evidence
+ Organisation rule B
= Decision B
```

If company knowledge changes only a manifest hash or metadata field while the selected action remains identical, the system is not thinking for the company.

---

## 8. Layer 5: Exact Required Architecture

Layer 5 must preserve the decision contract.

### 8.1 Full Intelligence Card

```text
What happened
An investor meeting completed three days ago.

Why it matters
No follow-up or promised deck is visible, and this is a high-value warm relationship.

Recommended action
Send a concise follow-up today with the deck and one explicit next step.

Why this action
No previous reminder has been sent, and an update is more appropriate than a generic check-in.

Owner
Rohit

Evidence
Meeting record, email thread, and extracted commitment

Confidence
84%

Alternative
Wait one day if the deck is not ready.
```

### 8.2 Delivery Failure Modes

Layer 5 fails when:

- It uses a fact-oriented Context endpoint as the intelligence surface
- It omits why-now, alternatives, uncertainty, owner, and expected outcome
- It shows an empty Morning Brief
- It renders stale cards after upstream reasoning changes
- It creates duplicate reminders for the same evolving situation
- It surfaces low-value items while hiding higher-value ones
- It selects the wrong channel or owner
- It exposes locked intelligence through client-side data

Context and Intelligence must remain separate:

- Context: What is known?
- Intelligence: What matters, why, and what should be done?

---

## 9. Admin-Only Intelligence MVP

An Admin-only commercial launch is a valid strategy. However, the product bundle and semantic domains should remain separate concepts.

### 9.1 Recommended Product Bundle

```text
Admin Intelligence Plan
├── Executive Administration
├── Meeting and Follow-through
├── Business Operations
├── People/HR Operations
├── Finance and Compliance Administration
├── Vendor and Contract Administration
└── Fundraising and Investor Operations
```

Internally, each area should retain a separate namespace so it can later become an independent pack without rewriting historical situations, capabilities, or outcomes.

### 9.2 Executive Administration

- Important unanswered email
- Upcoming meeting preparation incomplete
- Post-meeting follow-up missing
- Promised document not sent
- Commitment approaching its due date
- Commitment overdue
- Scheduling conflict
- Repeated rescheduling
- Approval pending

### 9.3 Business Operations

- Cross-team dependency blocked
- Repeated operational delay
- Missing task owner
- Recurring task missed
- Process handoff incomplete
- Operational exception unresolved
- Required document missing
- Business deadline approaching

### 9.4 People and HR Operations

- Employee onboarding incomplete
- Offboarding or access revocation pending
- Candidate follow-up missing
- Interview feedback overdue
- Leave or payroll input pending
- Employee document expiring
- Policy acknowledgement pending
- Probation or review deadline

### 9.5 Finance and Compliance Administration

- Invoice follow-up
- Payment overdue
- Renewal upcoming
- Contract expiry
- Purchase approval pending
- Expense or reimbursement pending
- Compliance filing deadline
- Budget variance evidence

### 9.6 Vendor and Contract Administration

- Vendor response pending
- Contract renewal
- SLA issue
- Purchase order missing
- Vendor onboarding incomplete
- Documentation gap
- Service interruption follow-up

### 9.7 Fundraising and Investor Operations

- Investor outreach awaiting response
- Warm introduction not followed up
- Investor meeting preparation
- Post-meeting follow-up missing
- Promised deck or data-room item pending
- Investor update due
- Investor questions unanswered
- Fundraising commitment or open loop
- Network-level outreach coverage
- Repeated investor silence
- Next investor step not scheduled

### 9.8 Fundraising Boundary

The Admin plan may include operational fundraising work:

- Follow-up
- Coordination
- Meeting operations
- Commitment tracking
- Documentation
- Investor updates

Strategic investment expertise should remain separate or locked for a later product:

- Investor-fit evaluation
- Valuation advice
- Term-sheet analysis
- Negotiation strategy
- Allocation strategy
- Financial or investment recommendations

The commercial bundle can be called Admin Intelligence while internal capabilities use a namespace such as `admin.investor_operations` or `investor_relations`.

---

## 10. Detecting Other Domains and Showing Locked Intelligence

The system should detect unlicensed domains, such as Sales, without exposing their full intelligence.

### 10.1 Correct Flow

```text
Layer 2 situation
    -> Universal Domain Router
    -> Entitlement Gate
        -> Licensed Admin: compile and reason fully
        -> Unlicensed Sales: create locked detection receipt
```

### 10.2 Why Frontend Blur Alone Is Unsafe

The wrong implementation is:

1. Send the complete Sales intelligence payload to the browser.
2. Hide it using CSS blur.
3. Remove the blur after upgrade.

The content would remain visible through API responses, browser tools, logs, or client state.

### 10.3 Safe Locked-Domain Receipt

The backend should send only a redacted receipt:

```yaml
artifact_type: locked_domain_receipt
domain: sales
detected: true
count: 3
category: sales_follow_up
freshness: today
locked: true
required_plan: sales_intelligence
```

Possible UI:

> **3 Sales opportunities detected**  
> GeniOS identified follow-up opportunities in recent customer conversations.  
> Upgrade to Sales Intelligence to view the recommendations.

The backend must not send the contact names, detailed evidence, recommendation, score, or draft until entitlement exists.

### 10.4 Trust Requirements

A locked card should appear only when:

- A real eligible situation was detected
- Routing confidence crossed an accepted threshold
- Evidence is current
- The receipt is deduplicated
- The category is truthful
- Upgrading will reveal a real, already-reproducible decision path

Locked intelligence must never be fabricated as an upgrade prompt.

---

## 11. Three Priority Vertical Slices

The product should not attempt to perfect every Layer 2 component or author hundreds of additional capabilities before proving value. Three end-to-end slices should be completed first.

### 11.1 Outbound Email With No Reply

Layer 2 must establish:

- Sender and recipient
- Role and organisation
- Objective
- Relationship type
- Initial and latest outbound
- Latest inbound
- Elapsed time
- Follow-up count
- Ball in court
- Missing context

Layer 3 must provide:

- Domain-specific cadence
- Eligibility
- Negative conditions
- Reminder versus update strategy
- Wait and stop rules

Layer 4 must choose:

- Send now
- Wait
- Send an update
- Seek reintroduction
- Stop

Layer 5 must surface:

- Why now
- Exact action
- Owner
- Evidence
- Draft or action affordance
- Expected result

### 11.2 Meeting Completed Without Follow-up

Layer 2 must establish:

- Meeting status
- Participants and roles
- Objective
- Discussion context
- Commitments
- Owner and due date
- Follow-up evidence
- Elapsed time

Layer 3 must supply:

- Meeting-type-specific follow-up policy
- Required artefacts
- Negative conditions
- Timing guidance

Layer 4 must select the next action.

Layer 5 must deliver the recommendation and draft without reducing it to “meeting happened”.

### 11.3 Investor and Network Outreach Cohort

Layer 2 must establish:

- People associated with 314 Capital and Far Network
- Roles
- Outreach objective
- Warm versus cold relationship
- Response and follow-up history
- Cohort counts and time windows

Layer 3 must supply:

- Investor-relations expertise
- Update versus reminder strategy
- Warm-introduction policy
- Stop and escalation rules

Layer 4 must prioritise people and actions.

Layer 5 must show a ranked, accountable follow-up plan.

---

## 12. Current Verified Failure Points

The discussion identified the following current-checkout facts:

1. Layer 1 has buildable Gmail, Google Calendar, Notion, Google Drive, HubSpot, and database sources, but several operational and enterprise sources are catalogued without buildable implementations.
2. The Layer 2 situation context slice currently sets `missing_fields=()` unconditionally and marks metadata as shadow.
3. Unknown or weakly modelled domains can appear complete because no expected fields are declared.
4. Rich temporal histories such as stage history and time in stage are not broadly available.
5. The current authored expertise corpus contains 153 complete capabilities, of which 125 are routed.
6. Admin contains 57 complete capabilities, of which 36 are routed.
7. A strict admission check reported 28 blocked situation documents.
8. The Domain Expertise compiler is off by default.
9. Organisation, behaviour, and adaptive values are transported in expertise metadata, but their semantic influence on final reasoning is not sufficiently demonstrated.
10. The Context API returns facts, relationships, commitments, and a generic recommendation rather than invoking the complete intelligence path.
11. The Morning Brief currently returns no intelligence headline or priorities.
12. Existing cards may not rebuild when upstream reasoning or rendering improves because the build claim rejects any signal that already has a card.

Targeted current-checkout tests had 264 passing tests, 6 skips, and 2 expected failures. The corpus validator reported zero schema errors and 283 warnings. These results establish code consistency, not deployed activation or customer value. The current deployment flags, tenant source freshness, production database state, and the exact trace of the 314 Capital/Far Network emails were not verified.

Evidence locations:

- `genios_engine/capture/source_registry.py`
- `genios_engine/context/situation_bso.py`
- `genios_engine/context/domain_spec.py`
- `genios_engine/platform/config.py`
- `genios_engine/reason/adapters/expertise.py`
- `genios_engine/api/workspace_routes.py`
- `genios_engine/api/intelligence_routes.py`
- `genios_engine/deliver/store.py`
- `Domain Expertise/Admin Expertise/registry/situation-capability-map.yaml`
- `Domain Expertise/Sales Expertise/registry/situation-capability-map.yaml`
- `Domain Expertise/Customer Support Expertise/registry/situation-capability-map.yaml`

---

## 13. Exact Build Order

### Phase 1: Layer 2 situation foundation

1. Implement a stable Layer 2 situation contract.
2. Implement temporal and absence-derived observations.
3. Reconstruct conversation and outreach lifecycles.
4. Resolve people, organisations, roles, and network membership.
5. Add objective and intent evidence.
6. Add commitments, open loops, and ball-in-court state.
7. Add timer-driven reevaluation.
8. Add honest missing, stale, ambiguous, and contradictory context.

### Phase 2: Universal domain routing

1. Detect primary and secondary domains.
2. Preserve confidence and ambiguity.
3. Support human corrections.
4. Keep domain routing independent of entitlements.

### Phase 3: Admin expertise

1. Split Admin into stable internal namespaces.
2. Route every intended capability from an emitted Layer 2 situation.
3. Require admission for both situation definitions and capabilities.
4. Add positive, negative, and abstention replays.
5. Implement explicit operational fundraising and investor-relations capabilities.
6. Turn on the compiler for a controlled design-partner tenant after required operational checks.

### Phase 4: Reasoning

1. Generate multiple candidate actions.
2. Apply eligibility and negative constraints.
3. Rank impact, urgency, confidence, and cost separately.
4. Make organisation and learned preferences materially affect the selection.
5. Support wait, clarify, and abstain outcomes.
6. Persist rejected alternatives and why-not receipts.

### Phase 5: Delivery and entitlements

1. Make the decision surface authoritative.
2. Keep Context and Intelligence separate.
3. Preserve why-now, action, owner, timing, alternatives, evidence, and outcome.
4. Rebuild stale cards when evidence, reasoning, authority, or rendering changes.
5. Add backend-enforced locked-domain receipts.
6. Prevent full unlicensed intelligence from reaching the client.
7. Deduplicate evolving situations and delivery events.

---

## 14. Acceptance Tests

### 14.1 Layer 2 acceptance

Given a sent email and no later inbound reply, Layer 2 must produce a time-aware `outbound_awaiting_response` situation with actors, roles, objective, timeline, follow-up count, ball in court, evidence, missing context, and next evaluation time.

### 14.2 Layer 3 acceptance

Given the same Layer 2 situation but different domain roles, Layer 3 must produce materially different eligible strategies:

- Sales prospect
- Investor
- Founder-network contact
- Vendor
- Candidate

### 14.3 Layer 4 acceptance

Changing an accepted organisation rule or learned preference must change the chosen action or its ranking when the rule is relevant.

Removing decisive evidence must produce clarification or abstention rather than a confident recommendation.

### 14.4 Layer 5 acceptance

The visible card must contain:

- The bounded situation
- Why it matters now
- Recommended action
- Owner
- Timing
- Evidence
- Confidence
- Uncertainty
- Alternative
- Completion condition
- Expected outcome

The card must update when the underlying situation changes.

### 14.5 Locked-domain acceptance

For an unlicensed Sales situation:

- The backend returns only a safe locked receipt.
- The client does not receive person-level evidence or recommendation content.
- The receipt is based on a real detected situation.
- Upgrading unlocks a reproducible intelligence path rather than fabricated content.

---

## 15. Final Product Principle

Admin Intelligence should be the commercial MVP, not a semantic dumping ground.

Internally, Executive Administration, Business Operations, People Operations, Finance Administration, Vendor Operations, and Investor Operations should remain distinct expertise namespaces. An always-on universal router should detect other domains. Licensed Admin situations should receive complete expertise and reasoning. Unlicensed domains should produce evidence-backed, backend-redacted locked receipts.

The central standard remains:

> Layer 2 must turn evidence into a truthful, temporal business situation. Layer 3 must apply executable domain judgment. Layer 4 must choose among real alternatives using company-specific knowledge. Layer 5 must deliver the decision without flattening it back into a fact.

Until that complete chain is proven on real unanswered emails, meetings, commitments, and investor cohorts, the product has structured awareness—but not dependable company intelligence.

---

## Appendix A: Questions Consolidated From the Discussion

The conversation addressed the following successive questions:

1. Where are Layer 1, Layer 2, and Layer 3 failing to produce real intelligence rather than existing facts?
2. Why do unanswered prospect emails, meetings without follow-ups, and investor outreach not generate proactive reminders?
3. What should Layer 2 own beyond business understanding, cross-correlation, business situations, and context quality?
4. Is the failure only in Layer 2, or is Layer 3 domain expertise also incomplete?
5. Where can the chain still fail in Layer 3, Layer 4, and Layer 5?
6. Can the current product focus only on Admin Intelligence while detecting other domains as locked upgrade opportunities?
7. What should Admin Intelligence include across administration, business operations, HR, fundraising, and investor follow-through?
8. How should the architecture preserve future Sales and other domain packs without rebuilding the system?

This document consolidates the answers into one architecture and implementation direction rather than preserving the repetitive turn-by-turn chat transcript.
