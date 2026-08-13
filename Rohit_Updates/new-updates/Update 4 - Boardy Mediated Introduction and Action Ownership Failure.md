# Update 4 — Boardy Introductions Collapse into the Bot Instead of the Human Who Needs a Response

**Status:** Open — root-cause analysis and implementation specification only

**Severity:** Critical / P0 product-trust and operational-continuity issue

**Observed surfaces:** GeniOS Mac intelligence cards, Dashboard → Intelligence → Context, and
Gmail threads introduced through Boardy/Bodi

**Affected path:** Gmail headers and thread → Context Graph → Cross-event correlation → Domain
Expertise → Reasoning → Decision/Card projection → Reply or delegation action

**Terminology note:** The user described the networking bot as `Bodi`; the screenshots and email
address show `Boardy` / `boardy@boardy.ai`. This update uses **Boardy** for the observed system and
**mediated introduction** for the general situation class.

---

## 1. Executive verdict

This is not merely a missing-card issue and it is not simply “Boardy’s fault.” Boardy may fail to
remind the user, but GeniOS independently has the Gmail evidence required to recognise that a
human contact is waiting for a response, a calendar link, material, or a scheduling decision.
GeniOS currently fails to turn that evidence into the correct person-specific open loop.

The central semantic error is:

> The current pipeline frequently treats the transport sender as the business subject.

When Boardy sends an introduction email, Boardy is the **connector/intermediary**. The other human
is the **introduced contact**, and the user or a delegated operator owns the next action. Those are
different roles. The current graph has email participants and generic `corresponded_with` edges,
but it does not have the roleful interaction needed to represent this distinction.

As a result, multiple unrelated introduction threads can be compressed into one
`boardy@boardy.ai` record. The Mac card then shows aggregated labels such as:

- `Meeting proposed ×11`;
- `Intro thread ×6`;
- `Timeline slipping ×3`;
- `Open question ×2`;
- details from different people, companies, dates, and conversations.

That is not one business situation. It is one connector being used as an accidental aggregation
bucket for many separate relationships.

The failure is distributed, but ownership is not ambiguous:

1. **Primary root cause — Context modelling:** Layer 2 stores ordinary email content and thread
   state on the sender node and lacks first-class mediated-introduction, participant-role, request,
   and action-owner objects.
2. **Primary contributing cause — Correlation semantics:** the Correlation Engine groups evidence,
   but its graph inputs do not state who is the connector, introduced contact, requester, action
   target, or observer. Grouping events is not the same as resolving action ownership.
3. **Primary capability gap — Domain Expertise:** the relevant Admin capabilities exist only as
   names and descriptions. The repository currently reports 57 Admin capability stubs, zero
   complete capabilities, zero routed capabilities, and zero Admin situations.
4. **Runtime activation gap — Domain Compiler:** the compiler is off by default and, when enabled,
   runs only as a shadow measurement pass. It persists nothing and changes no decision. It cannot
   explain the current live card.
5. **Downstream reasoning gap — active legacy path:** the live path scans one graph node at a time
   and runs a generic `intro_followup` / `unanswered_email` rule over a narrow node-local snapshot.
   It therefore reasons about Boardy when Boardy was made the subject upstream.
6. **Projection gap:** briefs and cards join the decision back to the signal’s subject node, so the
   upstream sender error becomes a Boardy-labelled card and the actual human email/action remains
   hidden.

The Reasoning Orchestrator itself is **not** the component that should discover the missing human.
Its explicit contract is to schedule reasoning units; it does not analyse the situation, query the
database, or select the business entity. If the capability and context snapshot say “Boardy,” the
orchestrator deterministically schedules reasoning about Boardy.

The fix must therefore start before card rendering. GeniOS needs a first-class, thread-scoped
`MediatedIntroduction` / `Interaction` with roleful participants and a separate `OpenLoop` that
states exactly:

- who introduced whom;
- which human is the actual counterparty;
- what that human asked for;
- who currently owns the response;
- what response channel and address should be used;
- whether the task is reply, calendar link, schedule, materials, update, decline, wait, or close;
- whether the task can be delegated and to whom;
- what evidence and thread support the conclusion.

Only then can Domain Expertise and Layer 4 produce useful intelligence.

---

## 2. What happened

### 2.1 The real user workflow

Boardy continually introduces the user to people for networking. A typical flow is:

1. Boardy sends an introduction email and includes the user and another person.
2. The other person replies, often keeping Boardy in CC.
3. The person may ask for an update, availability, calendar link, material, or a direct meeting.
4. The user forgets to reply or schedule.
5. The user expects GeniOS to identify the open loop and say what to do.
6. The user may act personally or delegate the operational handling to HR/admin.

For this workflow, the most valuable object is not `boardy@boardy.ai`. It is the separate open loop
with each introduced human.

### 2.2 Evidence visible in Gmail

The Gmail screenshot shows multiple distinct threads, including examples such as:

- `Boardy Intro: Lalitha + Rohit`, including a cancelled intro and a request to send material or
  reschedule;
- `Boardy Intro: Maria + Rohit`;
- `Boardy Intro: Rohit + Silas`, followed by a check on whether they connected;
- `Boardy Intro: Nitesh + Rohit`;
- `Boardy Intro: Rohit + Sal`, including a booking-link instruction;
- `Boardy Intro: Rohit + Ori`, including an availability link;
- `Boardy Intro: Rohit + Marco`, including a request for an update on how the conversation went.

These are different people, different threads, different requests, and different lifecycle states.
They must not become one operational record just because Boardy participates in all of them.

### 2.3 What GeniOS currently shows

The Context search for Boardy shows one primary company/person-style record for
`boardy@boardy.ai`. The record exposes generic quality/freshness metadata and a source badge, but
does not answer:

- who the introduced people are;
- which of them replied;
- which of them still needs a response;
- each person’s direct email address;
- what each person asked for;
- whether a link, reply, meeting, material, or update is due;
- whether the user or another operator owns the next action;
- whether a related calendar event was created, cancelled, rescheduled, or completed.

The Mac card makes the underlying collapse more visible: unrelated states and details are shown
under one `Boardy · boardy.ai` heading. The card knows that many intro-like events happened, but it
does not know which real-world loop the user should act on.

### 2.4 The dangerous operational consequence

The user cannot reliably reply or delegate from the intelligence GeniOS provides. An HR/admin
operator receiving “handle Boardy” would still need to reopen Gmail, search all Boardy threads,
identify the actual human, infer the request, determine the right action, and reconstruct the
history.

That is not delegation. It transfers confusion rather than transferring an owned task with enough
context to execute safely.

---

## 3. What should have happened

For every Boardy thread, GeniOS should create a separate mediated-introduction interaction.

At minimum, it should distinguish these roles:

| Role | Meaning | Example |
|---|---|---|
| Principal | The user whose networking workflow is being managed | Rohit |
| Connector | The intermediary who created the introduction | Boardy |
| Introduced contact | The external human the user may need to contact | Sal, Ori, Lalitha, etc. |
| Requester | The person who made the current ask | The human asking for a link/update/material |
| Action owner | The person currently responsible for the next move | Rohit or delegated HR/admin |
| Action target | The external person who should receive the response | The requester/contact, not automatically Boardy |
| Observer/CC | A participant retained for context but not necessarily the response target | Boardy after the intro |
| Scheduler/delegate | An internal operator authorised to arrange the meeting | HR/admin, if policy allows |

The expected intelligence should then be person-specific, for example:

> Reply to Sal at `sal@…` — Boardy introduced you. Sal asked you to use the booking link on 6 Aug.
> No reply or booking is visible. Reply personally or delegate scheduling to HR.

This sentence is illustrative; production text must use the actual thread evidence and must never
invent the name, address, request, date, or absence of action.

The Context view should also allow a Boardy-level summary, but only as a source/workflow roll-up:

> 6 introductions: 2 awaiting your reply, 1 awaiting their reply, 1 scheduled, 1 cancelled, 1
> closed.

Every count must be derived from the state of separate interaction/open-loop records. It must not
be a count of raw observation labels attached to the Boardy node.

---

## 4. The correct conceptual model

### 4.1 Transport roles are not business roles

Email provides transport metadata:

- From;
- To;
- CC;
- Reply-To;
- thread/message identifiers;
- In-Reply-To / References;
- subject and body.

Business reasoning needs additional roles:

- connector;
- introduced contact;
- requester;
- principal;
- action owner;
- action target;
- observer;
- delegate.

`From = Boardy` does not imply `business subject = Boardy`.

`CC = Boardy` does not imply `reply target = Boardy`.

`To = multiple recipients` does not imply that every recipient owns or receives the same action.

### 4.2 A person is not a thread, and a thread is not an open loop

GeniOS needs three distinct identities:

1. **Person:** stable human or system identity, potentially with multiple verified addresses.
2. **Interaction/thread:** the bounded conversation or introduction instance.
3. **Open loop:** the current outstanding obligation or expected next move arising from that
   interaction.

One person can participate in many threads. One thread can create several open loops. One connector
can introduce hundreds of unrelated people. None of these should overwrite the others.

### 4.3 The mediated-introduction lifecycle

A useful state machine is:

`introduced → awaiting acceptance → accepted / declined / no response → scheduling requested →`
`calendar link sent → meeting scheduled → rescheduled / cancelled / held → follow-up due → closed`

Not every interaction visits every state. The state must be event-derived, time-aware, and
thread-scoped. New evidence should supersede obsolete state; it should not leave “meeting proposed”
active after the meeting was scheduled or held.

---

## 5. Confirmed current implementation path

### 5.1 Gmail capture preserves basic addresses but strips important semantics

`genios_engine/capture/connectors/composio.py:303-340` extracts:

- sender email;
- flattened To email addresses;
- flattened CC email addresses;
- subject;
- thread ID;
- labels;
- body/snippet.

This means the other person’s address may already exist in the raw event or as a graph person node.
The screenshots alone do not prove raw capture loss. A tenant-scoped audit is required before
claiming that a specific person’s address was never ingested.

However, the capture contract does not preserve enough structure for robust role resolution. It
does not currently expose a first-class structured participant list with display names and
business roles, and it does not explicitly retain Reply-To, In-Reply-To, or References as fields
used by this workflow.

Therefore the capture layer is **partially responsible**, but it is not enough to say “Gmail did
not provide the email.” The system commonly has the address and still fails to make it actionable.

### 5.2 Layer 2 creates generic people and correspondence edges

`genios_engine/context/pipeline.py:328-366` creates a sender node, creates To/CC recipient nodes for
small recipient sets, and writes generic `corresponded_with` edges.

That answers “which addresses appeared in correspondence?” It does not answer:

- who introduced whom;
- which recipient is the introduced contact;
- who made the ask;
- whom the user should reply to;
- which participant is merely copied;
- who owns the next task.

A repository search finds no active role model such as `introduced_by`, `introduced_contact`,
`mediator`, `participant_role`, `requester_node_id`, or `action_target_node_id` in the engine path.

### 5.3 Layer 2 attaches ordinary email content to the sender

The decisive implementation is in `genios_engine/context/pipeline.py`:

- ordinary email content uses `content_subject = sender_node` (`464-468`);
- observations are attached to that content subject (`488-501`);
- questions are explicitly written to the sender node (`503-516`);
- inbound thread state is written to the sender node (`532-552`);
- the pipeline returns `primary_node=sender_node` (`628-631`).

For a Boardy-originated introduction, this creates the following chain:

`Boardy sends intro`
→ `sender_node = boardy@boardy.ai`
→ `introduction/question/email state stored on Boardy`
→ `Boardy becomes the primary node`
→ `multiple Boardy threads accumulate on the same node`.

The introduced human may still have a generic person node due to To/CC parsing, but the
introduction and open-loop semantics are not attached to a roleful interaction involving that
human.

### 5.4 Outbound state can also be spread to the wrong participants

For outbound mail, Layer 2 writes `thread.last_outbound` and `thread.ball_in_court=them` on each
non-internal To/CC recipient in a small thread (`pipeline.py:367-388`).

In a reply-all flow, both the introduced person and Boardy may therefore receive similar state.
That is useful as low-level correspondence evidence, but it is not a correct statement of which
business loop moved to whose court.

### 5.5 Correlation receives untyped participant anchors

Correlation runs after these writes and receives the touched external nodes plus thread ID
(`pipeline.py:606-619`). The Correlation Engine can therefore keep messages with the same thread
together and can use shared anchors.

But its inputs still do not state the participant roles or the action object. A correlation group
can contain Boardy and the introduced person and remain unable to answer who needs a response.

This distinction is essential:

> Correlation answers “which evidence belongs together?” Action ownership answers “who must do
> what, for whom, through which channel, by when?”

The first does not automatically produce the second.

### 5.6 The active general rules are sender/node scoped and too weak

`genios_engine/packs/general_v1.py:41-46` defines `unanswered_email` using only:

- `thread.ball_in_court = us`;
- age of `thread.last_inbound`.

`general_v1.py:64-72` defines `intro_followup` using only:

- an `introduction` observation;
- absence of `followup_sent`;
- age of `thread.last_inbound`.

The `intro_followup` template says to follow up on the introduction to `{entity}`
(`general_v1.py:117-124`). If `{entity}` is the sender node, the rendered entity becomes Boardy.

These rules do not require:

- the introduced contact;
- the requester;
- the direct email address;
- the exact open ask;
- a thread-scoped state;
- a calendar correlation;
- an action owner or target;
- a delegation policy.

They can detect generic silence. They cannot manage mediated introductions correctly.

### 5.7 The live reasoning path uses narrow legacy snapshots

`genios_engine/reason/runner.py:560-589` compiles legacy pack rules into adapter capabilities and
then evaluates those rules over graph nodes. `legacy_context_snapshot` selects only the direct
fields named by the rule plus observations (`reason/adapters/legacy_context.py:39-52,94-163`).

For `intro_followup`, the direct evidence field is only `thread.last_inbound`. The snapshot does not
require a roleful thread, introduced person, request, or action target.

The adapter then wraps the rule in a generic play whose only step is effectively “prepare a draft
reply for human review” (`reason/adapters/legacy_pack.py:24-145`). The sophisticated Layer 4 kernel
is therefore executing an impoverished legacy capability over an impoverished context snapshot.

This is why having a Reasoning Engine does not guarantee useful reasoning. The quality ceiling is
set by the semantic context and capability contract supplied to it.

### 5.8 The card projection hardens the wrong subject

The brief composer uses the signal’s subject node and that node’s direct facts
(`genios_engine/executive/brief.py:45-148,198-224`). The insights API similarly joins the signal’s
subject to the graph node and exposes that node as `contact_name`
(`genios_engine/api/intelligence_routes.py:332-405`).

If Boardy was selected upstream, the delivery surface faithfully renders Boardy. The UI cannot
recover the missing introduced-contact role at this stage.

---

## 6. Why the Correlation Engine did not save this case

The Correlation Engine is present, but four separate conditions must hold before it can solve this
workflow:

1. the events must be captured;
2. the same real-world interaction must be recognised;
3. participant roles and state transitions must be represented;
4. the reasoner and UI must consume the correlated situation rather than one direct node.

The current path only partially meets the first two.

### 6.1 Same thread is necessary but insufficient

All replies in one Gmail thread can correlate correctly and still produce a wrong card if the
thread has no roleful participant model. The system may know that Boardy, Rohit, and Sal appeared
together without knowing that Boardy introduced Sal and Sal is the action target.

### 6.2 A shared connector is a dangerous correlation anchor

Boardy appears across many independent introductions. If a shared participant is treated as the
main business anchor, unrelated interactions become neighbours of the same high-degree connector.

The system must never merge separate introduction situations merely because they share:

- Boardy’s email;
- a generic `introduction` observation;
- a company/domain label;
- a meeting-related keyword;
- the same user identity.

The stable boundary should be the source thread plus the resolved introduced-contact set and the
specific request/open-loop identity.

### 6.3 Correlation does not make decisions

Correlation should produce a bounded evidence group and relationship roles. It should not itself
decide whether to reply, schedule, delegate, wait, or decline. That choice belongs to Domain
Expertise plus reasoning.

The current problem is that the correlation output does not provide the typed situation required
for those later layers.

---

## 7. Why the Domain Compiler, Expert Brain, and Organizational Brain did not catch it

### 7.1 The Domain Compiler is not the live decision path

`genios_engine/platform/config.py:67-71` sets `use_domain_compiler=False` by default. When enabled,
`genios_engine/reason/runner.py:525-533` invokes it only as a shadow pass.

`genios_engine/reason/domain_shadow.py:57-138` explicitly states and implements that:

- nothing is persisted;
- no live decision is touched;
- packages are compiled and measured in shadow mode.

Therefore the current Boardy card was not rescued by the Domain Compiler because the compiler does
not currently control live decisions.

### 7.2 The Admin capability catalogue is not executable expertise yet

The generated Admin registry provides unambiguous evidence:

- `routed_l2_types: []`;
- `situations: 0`;
- `capabilities: 57`;
- `capabilities_stub: 57`;
- `capabilities_complete: 0`;
- `capabilities_routed: 0`.

Relevant capability files including Inbox & Correspondence, Calendar Management, Delegation & Task
Routing, Follow-up Coordination, Meeting Scheduling, and Request Intake are marked:

- `status: draft`;
- `stub: true`;
- experimental/unreviewed.

For example, Inbox & Correspondence correctly asks whether every message is answered once by the
right person, but its knowledge manifest has empty playbooks, heuristics, mental models, rules, and
decision frameworks.

The accurate conclusion is:

> GeniOS has 57 Admin capability names, not 57 live Admin reasoning capabilities.

The catalogue expresses intent. It does not yet provide runnable expertise for this case.

### 7.3 The Domain Compiler cannot reconstruct context Layer 2 never modelled

Even after activation, the compiler receives a Business Situation Object and context slice. The
current `build_business_situation` puts only the anchor node into `entities`, and the context slice
has one root entity (`genios_engine/context/situation_bso.py:105-166`).

If the anchor is Boardy and participant roles do not exist, the compiler cannot safely infer the
introduced contact or action target. A compiler packages available expertise around available
context; it does not make missing source truth appear.

### 7.4 The Expert Brain is a capability gap, not a magical fallback

The Expert Brain should supply a complete capability for a situation such as
`mediated_introduction_open_loop`. It should know the possible states, plays, failure modes,
constraints, handoffs, and success signals.

That capability is absent from the live route. The generic rules are being used instead.

### 7.5 The Organizational Brain has a different responsibility

The Organizational Brain should contribute tenant-specific operating policy, for example:

- Rohit’s verified identities;
- who is authorised to manage his calendar;
- the preferred booking link;
- response-time targets;
- working hours and time zone;
- VIP or do-not-engage relationships;
- whether HR/admin may draft, send, or only request approval;
- what context may be disclosed during delegation.

It should not invent that Sal is the introduced person when the interaction model only says that
Boardy, Sal, and Rohit exchanged email. Source-derived participant roles remain a Context Layer
responsibility.

### 7.6 Behavioral and Adaptive brains are not the root cause

Behavioral learning can learn the user’s normal response cadence, preferred tone, delegation
choices, or whether the user usually sends a calendar link. Adaptive reasoning can learn which
play succeeds and when to surface it.

Neither should guess the identity of the requester or action target. Learning can optimise a true
situation; it must not compensate for missing semantic truth.

---

## 8. Why the Reasoning Orchestrator did not catch it

The question “why did the Reasoning Orchestrator not see the human and calendar task?” assumes the
orchestrator is an analysing agent. In the implemented architecture it is not.

`genios_engine/reason/orchestrator.py:1-19` defines the orchestrator as only the scheduler. It:

- decides which declared reasoning units run;
- orders and parallelises those units;
- applies declared failure policies;
- records a deterministic trace.

It explicitly does not:

- analyse the situation;
- query Gmail or Calendar;
- discover entities;
- infer participant roles;
- choose the winning action.

Analysis belongs to reasoning units; synthesis belongs to the Decision Maker. Both are bounded by
the supplied capability and context snapshot.

The current chain is therefore deterministic but wrong:

`Boardy selected as sender/subject`
→ `node-local facts and observations selected`
→ `legacy intro rule compiled`
→ `Orchestrator schedules declared units`
→ `Decision Maker sees Boardy-rooted candidates`
→ `signal subject remains Boardy`
→ `card renders Boardy`.

The orchestrator cannot schedule a missing “resolve introduced contact” unit because the active
capability does not declare one and the context does not contain the required role contract.

---

## 9. Layer-by-layer fault ownership

| Layer/component | Responsibility in the correct design | Current failure | Ownership |
|---|---|---|---|
| L1 Gmail capture | Preserve full headers, participants, message/thread identity, body, labels | Basic addresses survive, but role-supporting header/participant structure is incomplete | Contributing |
| L2 extraction | Extract request, actor, target, dates, meeting/scheduling intent | Extracts generic observations/questions without a complete request/action contract | Primary |
| L2 Context Graph | Model people, interaction, roles, state, open loops, evidence | Sender becomes content subject; only generic correspondence edges exist | Primary root cause |
| L2 Correlation Engine | Join messages/events into a bounded real-world situation | Groups untyped anchors; cannot resolve connector versus counterparty or action ownership | Primary contributing cause |
| L2 cross-tool state | Join Gmail request to Calendar invite/change/outcome | No reliable thread/interaction state consumed in the Boardy card | Primary contributing cause |
| L3 Domain routing | Route mediated introduction to the correct capability slice | Gmail has no useful deterministic prior for this situation; Admin routes zero types | Primary capability gap |
| L3 Expert Brain | Provide executable inbox, scheduling, follow-up, delegation expertise | Relevant Admin capabilities are draft stubs with empty knowledge | Primary capability gap |
| L3 Domain Compiler | Package selected expertise for the situation | Off by default and shadow-only; current BSO is one-anchor and role-poor | Activation/design gap, not the originating error |
| Organization Brain | Supply ownership, permission, calendar, delegation, and disclosure policy | Cannot contribute enough policy to a non-existent roleful situation | Required enhancement, not root cause |
| L4 Orchestrator | Schedule declared reasoning units deterministically | Correctly schedules what it is given; it is not a semantic recovery engine | Not root cause |
| L4 reasoning units / selector | Analyse context and compare plays | Active path uses narrow legacy node snapshots and generic rules | Primary downstream cause |
| L4 Decision Maker | Select among valid grounded candidates | Candidate set lacks person-specific, scheduling, and delegation alternatives | Downstream consequence |
| L5 brief/card | Explain the decision and offer bounded action/handoff | Joins back to Boardy subject and renders aggregated, low-clarity context | Major product-surface cause |
| Context UI/read model | Show current state, evidence, relationships, history | Exposes shallow Boardy record instead of separate introduction loops | Major visibility cause |

No single patch to the card will fix this. Renaming the Boardy card or adding more email text would
leave the semantic and decision errors intact.

---

## 10. What GeniOS should store — bounded operational context, not an unbounded memory copy

GeniOS does not need to duplicate the entire Gmail mailbox into a new memory layer. Gmail remains
the source of truth for raw messages. GeniOS needs bounded derived records required to reason and
act.

### 10.1 Interaction record

Suggested minimum fields:

```text
interaction_id
interaction_type = mediated_introduction
source = gmail
source_thread_id
source_message_ids[]
connector_node_id
principal_node_id
introduced_contact_node_ids[]
participant_roles[]
first_seen_at
last_seen_at
current_state
confidence
evidence_refs[]
```

### 10.2 Request/open-loop record

```text
open_loop_id
interaction_id
request_kind = reply | calendar_link | schedule | materials | update | decline | other
requester_node_id
action_owner_node_id
action_target_node_id
reply_channel = email
reply_address
status = open | waiting_on_us | waiting_on_them | delegated | satisfied | cancelled | closed
due_at
delegable
delegation_constraints[]
supporting_event_ids[]
last_state_change_at
```

### 10.3 Calendar/meeting state

```text
meeting_id
interaction_id
calendar_event_id
meeting_url
attendee_node_ids[]
status = proposed | scheduled | rescheduled | cancelled | held | no_show | unknown
start_at
end_at
state_evidence_refs[]
```

The derived records should retain only the context required for intelligence, explanation,
deduplication, lifecycle, and delegation. Raw body access should remain through claim-level source
references and appropriate permissions.

---

## 11. Required extraction and role-resolution rules

### 11.1 Preserve the full header contract

Capture should preserve and normalise:

- structured From identity: display name plus email;
- structured To identities;
- structured CC identities;
- Reply-To;
- Message-ID;
- In-Reply-To;
- References;
- Gmail thread ID;
- sent/inbound direction;
- authenticated connected-account identities.

### 11.2 Resolve transport participants deterministically first

Use exact addresses and verified internal identities before any semantic inference. Do not merge
people solely by first name or display name.

### 11.3 Infer business roles with evidence and confidence

For a known Boardy-originated introduction:

- Boardy may be assigned `connector` only when the address/domain/integration identity is verified
  or the thread contains grounded introduction evidence;
- the connected user identity is the principal;
- the other external participant is a candidate introduced contact;
- a direct human reply is strong evidence that the human is the active requester/counterparty;
- Boardy remaining in CC is evidence of context/observation, not automatic action ownership;
- Reply-To, explicit body requests, and latest non-quoted content outrank subject-line heuristics.

The subject pattern `Intro: X + Y` can be a hint, but never the sole authority.

### 11.4 Fail closed on ambiguous multi-party introductions

If there are multiple external humans and no grounded action target, GeniOS should say:

> This introduction appears to need a response, but the intended recipient is ambiguous.

It should offer review, not fabricate a direct recipient or send action.

### 11.5 Separate source actor, requested actor, and action target

Every extracted request/commitment should have explicit slots:

- source author;
- person making the request;
- person expected to act;
- person who should receive the output;
- connector/observer participants;
- evidence span.

Falling back all unresolved slots to the sender recreates the current bug and must be disallowed for
actionable situations.

---

## 12. Required correlation behaviour

### 12.1 Thread-scoped interaction identity

Each Gmail thread should map to one bounded interaction unless evidence proves that the thread
contains multiple separable situations. Different Boardy thread IDs must not merge into one
actionable situation merely because Boardy participates in each.

### 12.2 Cross-tool join keys

Calendar correlation should use a ranked combination of:

- exact attendee emails;
- organiser email;
- explicit Calendar event/message linkage;
- Meet URL;
- time window;
- normalised event title and participant names;
- booking-link evidence;
- source thread references.

Email-only “meeting proposed” must be superseded when stronger Calendar evidence establishes
scheduled, cancelled, rescheduled, or held state.

### 12.3 Interaction-level state reducer

State should be reduced from ordered evidence, not accumulated as independent permanent labels.
For example:

- invite created after proposal → `scheduled`;
- cancellation after invite → `cancelled`;
- reschedule reply plus new invite → `rescheduled/scheduled`;
- meeting end time passing is not sufficient by itself to claim `held` unless the accepted evidence
  policy supports it;
- outbound reply satisfying an ask → close or move that open loop, while preserving history.

### 12.4 Keep provenance at the claim level

The card should be able to explain:

- contact email came from which header/message;
- request came from which message text;
- calendar state came from which event;
- action ownership came from which organization policy;
- due state came from which explicit date or SLA.

A global `gmail` / `gcal` badge is not enough.

---

## 13. Required Domain Expertise capability

### 13.1 Add a routed situation type

Layer 2 should emit a typed situation such as:

```text
mediated_introduction_open_loop
```

The name can change, but the contract must distinguish it from generic unanswered email and generic
sales follow-up.

### 13.2 Promote the required Admin slice from stub to complete

The minimum vertical slice includes:

- Request Intake;
- Inbox & Correspondence;
- Follow-up Coordination;
- Meeting Scheduling;
- Delegation & Task Routing;
- Calendar Management only when a request becomes a real calendar allocation decision;
- Commitment Tracking when the user or counterparty made an explicit promise.

These capabilities need complete outcomes, failure modes, playbooks, heuristics, decision
frameworks, rules, KPIs, handoffs, and object requirements. They must then be routed in the
situation-capability map.

### 13.3 Candidate plays

The capability should be able to generate and compare at least:

- reply to the introduced contact;
- send the user’s approved calendar link;
- schedule using the contact’s link;
- ask for availability;
- send requested material;
- acknowledge and wait;
- decline the introduction politely;
- follow up after no response;
- delegate scheduling to HR/admin;
- request user clarification;
- close as no action required.

Each play must identify the external target, internal owner, required evidence, permission boundary,
and success signal.

### 13.4 Cross-domain composition

The operational loop belongs primarily to Admin expertise, but the relationship goal may belong to
networking, recruiting, partnerships, investment, or sales. Domain compilation should compose the
relevant slice without allowing a generic sales rule to misclassify every introduced person as a
deal.

---

## 14. Required reasoning contract

### 14.1 Business Situation Object

The BSO should include all relevant entities with roles, not only one anchor:

```text
entities:
  - Boardy: connector
  - Rohit: principal / current action owner
  - Sal: introduced contact / requester / action target
  - HR operator: eligible delegate, if authorised
```

### 14.2 Situation Context Slice

The context selector should include:

- interaction state;
- participant roles;
- latest unquoted request;
- open-loop state;
- direct response address;
- last inbound and outbound messages for this thread;
- calendar correlation and current event state;
- organisation policy for delegation and calendar handling;
- evidence references and ambiguity markers.

It must not load all Boardy history into every Boardy situation.

### 14.3 Reasoning units

The capability should declare units that answer separate questions:

- **Context:** what happened in this specific interaction?
- **Identity/role:** who is connector, requester, counterparty, owner, and target?
- **Dependency:** is a calendar event, promised material, or user clarification required?
- **Constraint:** what may HR/admin do and what requires approval?
- **Lifecycle:** has newer evidence satisfied, cancelled, or superseded the ask?
- **Priority:** how urgent and important is this particular relationship?
- **Action:** which play best closes the loop?
- **Confidence:** is recipient/action evidence sufficient to recommend or execute?

### 14.4 Decision Maker requirements

The Decision Maker must compare grounded alternatives. It should not receive only one generic
“reply” candidate. If the target email, ask, or current state is missing, the result should be
`INSUFFICIENT_CONTEXT` or a clarification/review recommendation rather than a confident Boardy
card.

---

## 15. Admin operations and delegation behaviour

The user’s HR/admin example is an important product requirement, not an optional convenience.

### 15.1 Correct handoff packet

A delegated task should include only the minimum actionable packet:

- contact name and verified direct email;
- Boardy as the introduction source;
- exact request and supporting source link;
- current calendar/meeting state;
- approved response or scheduling options;
- deadline/SLA;
- disclosure constraints;
- whether the delegate may send, draft for approval, or only coordinate internally;
- completion signal.

### 15.2 Accountability must survive reassignment

Delegation should change `action_owner_node_id` from Rohit to the authorised operator while
preserving:

- Rohit as principal;
- the external contact as action target;
- Boardy as connector;
- the source interaction;
- audit history;
- the required approval boundary.

### 15.3 No implied autonomous sending

Defining reply, scheduling, and delegation capabilities does not automatically authorise external
execution. Default behaviour should remain advice/draft/handoff with human approval unless the
workspace has granted a narrow action explicitly.

---

## 16. Required product/UI behaviour

### 16.1 Person-specific action card

Every actionable card should answer, without opening another screen:

1. Who is this person?
2. How did we connect?
3. What happened?
4. What exactly are they waiting for?
5. What changed since the original intro?
6. What should I do now?
7. Why is that the correct action?
8. Which email/address/channel will be used?
9. Can I delegate it, and what will the delegate receive?
10. Which source evidence supports each claim?

### 16.2 Actions

Depending on the grounded state, the card may offer:

- `Open Gmail thread`;
- `Reply to <person>`;
- `Draft reply`;
- `Send calendar link`;
- `Open their booking link`;
- `Delegate scheduling`;
- `Mark already handled`;
- `Not relevant`;
- `Needs review`.

The action target must be the actual contact/requester. Boardy may remain in CC when appropriate,
but it must not be selected merely because it sent the original intro.

### 16.3 Boardy summary surface

A Boardy-level record may show channel/workflow health:

- number of introductions;
- accepted/declined/no-response counts;
- awaiting-user counts;
- awaiting-counterparty counts;
- scheduled/cancelled/held counts;
- overdue operational loops.

It should link to person-specific interactions. It should not replace them.

---

## 17. Forensic audit required for the live tenant

Before backfilling or claiming data loss, inspect each observed Boardy thread end to end:

1. Gmail source thread and every message ID.
2. From, To, CC, Reply-To, Message-ID, In-Reply-To, References, labels, and direction.
3. Raw L1 event and gated event.
4. Extracted entities, observations, questions, requests, and commitments.
5. Graph nodes created for Boardy, Rohit, and every introduced contact.
6. Generic and roleful edges, if any.
7. Which node received `introduction`, `question`, `thread.last_inbound`, and
   `thread.ball_in_court`.
8. Correlation group(s), anchors, domain, and situation ID.
9. Matching Calendar events, attendees, organiser, Meet URL, status, and timestamps.
10. Reasoning rule/capability selected.
11. Exact ContextSnapshot / SituationContextSlice supplied to reasoning.
12. Decision candidates and selected subject.
13. Signal, brief, card, and Context read-model output.

This audit separates three cases:

- **capture loss:** the person or message never entered L1;
- **semantic loss:** the address exists, but the graph/open loop assigned it incorrectly;
- **projection loss:** the situation is correct in storage, but Context/card does not consume it.

The current code confirms semantic and projection risks. The audit is still required to classify
every live Boardy example accurately.

An existing repository audit dated 12 Aug reported that `intro_followup` had 14 apparently eligible
nodes and zero emitted signals, and that email↔calendar/person linking was weak. That is useful
historical evidence, but it must be rechecked against the current tenant/runtime before being
presented as the present count.

---

## 18. Recovery and backfill

Fixing future ingestion is insufficient because existing forgotten introductions are exactly the
valuable backlog the user wants GeniOS to recover.

The recovery job should:

1. identify Boardy/Bodi-mediated Gmail threads from retained source events or refetch scope;
2. reconstruct structured participants and message chronology;
3. resolve connector, principal, introduced contact, requester, action owner, and action target;
4. create thread-scoped interactions and open loops;
5. correlate matching Calendar/Meet events;
6. reduce each interaction to its current lifecycle state;
7. rerun the correct routed capability;
8. close/supersede stale Boardy-rooted signals and cards;
9. create person-specific cards only where the current loop is still open;
10. publish an audit report of recovered, ambiguous, skipped, and failed threads.

Ambiguous threads must go to review. They must not be silently assigned to the most likely person.

---

## 19. Required tests

### 19.1 Unit tests

- Boardy sends an intro to Rohit and one external person.
- External person replies with Boardy in CC.
- External person replies directly without Boardy.
- Rohit replies-all.
- Rohit replies only to the introduced person.
- Contact asks for a calendar link.
- Contact supplies their own booking link.
- Contact asks for materials or an update.
- Contact declines.
- Boardy asks whether the parties connected.
- Multiple Boardy threads involve different people.
- Two people share the same display name but different emails.
- One person uses multiple unverified addresses.
- Multi-party intro has more than one external person.
- Thread exceeds the current bulk-recipient threshold.
- Reply-To differs from From.
- Quoted history contains an old request but latest message closes it.

### 19.2 Correlation tests

- Different Boardy thread IDs never merge into one actionable interaction solely through Boardy.
- Same thread messages remain one interaction.
- Calendar invite joins the correct introduction through attendees/time/linkage.
- Cancellation supersedes scheduled state.
- Reschedule creates a new current event without losing history.
- Unrelated meeting with the same person does not automatically satisfy the intro loop.

### 19.3 Reasoning tests

- Correct human is the signal/card subject or explicit action target.
- Boardy is connector provenance, not default recipient.
- Reply, schedule, calendar-link, materials, wait, decline, delegate, and review alternatives are
  generated only when their required context exists.
- Missing target email produces insufficient context/review, not a send-ready recommendation.
- Closed/cancelled/satisfied loops emit no open action.
- Delegation respects organization policy and approval scope.

### 19.4 End-to-end acceptance scenarios

For Lalitha, Maria, Silas, Nitesh, Sal, Ori, Marco, and any other observed Boardy contacts, the
tenant audit should be replayed from source event through card output. Each case must show whether
the exact contact, request, status, calendar evidence, and next action are correct.

No example should be declared fixed from synthetic tests alone.

---

## 20. Health metrics and alerts

Track at least:

- percentage of mediated-introduction threads with resolved participant roles;
- percentage with a verified introduced-contact email;
- percentage of open requests with requester, owner, target, and request kind;
- percentage correlated with Calendar when meeting intent exists;
- number of actionable cards whose target is a known connector/bot;
- number of distinct source threads collapsed under one person/card;
- intro-follow-up eligible versus emitted counts;
- ambiguous-recipient rate;
- stale `meeting proposed` states contradicted by Calendar;
- open loops closed by a later outbound reply, meeting, cancellation, or explicit resolution;
- delegation completion and re-open rates.

Alert when a connector node accumulates many intro/question/meeting observations but the system has
few or no person-specific open loops. That is a direct detector for the current Boardy failure.

---

## 21. Acceptance criteria

This update is complete only when all of the following are true:

1. Every observed Boardy thread is represented as a separate bounded interaction.
2. Connector, principal, introduced contact, requester, action owner, action target, and observers
   are explicit and evidence-backed.
3. The actual human’s direct email is visible when grounded in Gmail headers.
4. The card states the exact outstanding request or explicitly says it is unknown.
5. Gmail and Calendar evidence reduce to one current interaction state.
6. Different Boardy introductions do not merge into one action card.
7. Boardy appears as introduction source/provenance, not automatically as the person to reply to.
8. Reply/scheduling/material/delegation actions target the correct person and thread.
9. HR/admin handoff includes a bounded executable context packet and preserves accountability.
10. Ambiguous targets fail closed and request review.
11. Relevant Admin capabilities are complete and routed, not merely present as draft stubs.
12. The Domain Compiler path is either activated through a measured shadow-to-live cutover for this
    vertical slice or the temporary legacy path has an explicit removal/migration gate.
13. Reasoning consumes a roleful situation/context slice rather than only a sender node.
14. Existing incorrect Boardy-rooted cards are superseded or closed through an audited backfill.
15. Deterministic unit, correlation, reasoning, and end-to-end tests pass with no skipped critical
    case.
16. A live tenant replay proves the named examples, not only synthetic fixtures.

---

## 22. Final answer: exactly where is the fault?

The shortest accurate answer is:

> The first major fault is in the Context Layer: GeniOS models Boardy as the subject because it sent
> the email, but it does not model the mediated introduction, participant roles, or person-specific
> open loop. Correlation then groups evidence without enough semantics. The live Domain Expertise
> path cannot repair it because the Domain Compiler is shadow-only and the relevant Admin
> capabilities are all unrouted stubs. Layer 4 then runs generic node-local legacy rules, and the
> card faithfully renders the wrong Boardy-rooted subject.

Therefore:

- **Context Graph / semantic extraction:** primary root cause;
- **Cross-correlation:** major contributing cause, but not the only cause;
- **Admin Expert Brain and domain routing:** major missing capability;
- **Domain Compiler:** not responsible for inventing missing truth and not active in live decisions;
- **Reasoning Orchestrator:** not the root cause; it only schedules declared units;
- **Reasoning context/rules and Decision Maker inputs:** major downstream limitation;
- **Card/Context projection:** major reason the failure becomes visible as “zero clarity.”

The architecture does not need a magical model that reads everything again at the end. It needs a
clean contract across the layers:

`source evidence → roleful interaction → bounded open loop → correlated current state → routed`
`expert capability → grounded alternatives → accountable action or handoff → explainable card`.

That is the missing vertical slice.
