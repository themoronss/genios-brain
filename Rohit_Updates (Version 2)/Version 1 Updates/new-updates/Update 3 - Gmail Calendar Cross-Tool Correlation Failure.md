# Update 3 — Gmail and Google Calendar Are Not Being Presented as One Business Reality

**Status:** Open — root-cause analysis and implementation specification only

**Severity:** Critical / P0 product-trust issue

**Observed surfaces:** GeniOS Mac intelligence cards and Dashboard → Intelligence → Context

**Affected source path:** Gmail → Google Calendar / Google Meet → Context Graph → Situation →
Intelligence Card

**Observed examples:** Meetings with Rohit and Aditya happened on Google Meet, but their meeting
history is absent from the context shown by GeniOS

---

## 1. Executive verdict

This is a major cross-tool intelligence failure.

The Correlation Engine exists and both Gmail and Google Calendar have ingestion paths. That does
not mean the complete product path is correlated. The current implementation can ingest an email
and a calendar event, place them in separate correlation groups, and then render a Context record
that reads neither group. The user therefore sees two source systems as separate realities even
though both describe the same relationship or interaction.

The correct diagnosis is not simply `Google Calendar is missing`, and it is not yet possible to
claim from the screenshots alone that Calendar ingestion failed. There are three different
questions:

1. **Was the Calendar event captured and processed?** This requires a live tenant-scoped event
   audit for the Rohit and Aditya meetings.
2. **If captured, did the Gmail and Calendar events enter the same correlation/situation?** The
   current code contains several deterministic ways for them to be split.
3. **If correctly correlated in the graph, did the Context API, read model, and card actually
   consume that correlation?** The answer in the current implementation is no. The active Context
   and card projections mostly read direct facts on one node, not the connected meeting or its
   correlation members.

The third failure is confirmed from the code. The exact live-row answer to the first two must be
established through an audit before selecting the necessary recovery path.

The core correction is:

> A source being connected is not correlation. An event having any correlation ID is not
> cross-tool correlation. Correlation is complete only when evidence from different tools that
> describes the same real-world situation is joined, available in the bounded situation view,
> consumed by the intelligence/card projection, and shown with claim-level provenance.

---

## 2. What happened

### 2.1 Rohit meeting

The user held a meeting with Rohit on Google Meet. That interaction is not visible where GeniOS is
supposed to explain the current relationship and the reason behind an intelligence card.

The missing meeting means the user cannot tell:

- that a meeting was scheduled;
- whether it remained only scheduled, was cancelled, or actually happened;
- when the meeting happened;
- who attended;
- which prior Gmail conversation led to it;
- what open question, commitment, or next step it affected;
- what the correct action is after the meeting.

### 2.2 Aditya meeting

The Mac card for `adityad@iima.ac.in` shows Gmail-derived information including:

- `Deliver the commitment to adityad@iima.ac.in today`;
- `23d overdue — you promised this`;
- `Meeting proposed ×2`;
- a date/time, duration, role, and IIMA Ventures context;
- `Grounded in Gmail`.

However, the user confirms that a Google Meet meeting with Aditya already happened. The card still
looks as if Gmail's proposed-meeting state is the complete reality. It does not show the Calendar
interaction or explain how that meeting changed the open loop.

This can produce a materially wrong recommendation. If a meeting was proposed and later scheduled,
the state should no longer be only `Meeting proposed`. If the meeting occurred, the next action may
be to follow up on its outcome, deliver an agreed artifact, or wait for the other party. It should
not blindly continue acting as if scheduling is still the unresolved task.

### 2.3 Context search confirms the product symptom

The Context surface shows records such as an email address, an active/current label, a fact count,
confidence/freshness, and `gcal` / `gmail` badges. It does not show the meeting, timeline, connected
email, decision impact, or next step.

More importantly, the `gcal` and `gmail` badges in this screen are not proof that the selected
record was corroborated by both tools. For non-demo records, the dashboard currently fills source
badges from the workspace's globally connected tools. A person can therefore display both badges
even when neither source has been joined to that specific record.

That is a trust defect: the UI visually implies record-level evidence that the data contract does
not provide.

---

## 3. Why this is more serious than one missing meeting

GeniOS is intended to understand one business reality across fragmented tools. Gmail may contain
the proposal and promise, Calendar may contain the accepted time, Google Meet may contain evidence
that the meeting occurred, a transcript/notes tool may contain the discussion, and a CRM may contain
the deal state. None of those sources alone is the situation.

If the product reads every tool but renders them independently, it is still a collection of source
views. It has not become an intelligence layer.

This failure affects:

- identity: whether records from two tools refer to the same person;
- interaction state: proposed versus scheduled versus cancelled versus held;
- open-loop state: whether an old request is still unresolved;
- commitment state: whether a promise was changed, fulfilled, or superseded;
- recommendation correctness: what the user should do now;
- confidence: whether multiple sources support a claim;
- provenance: which source supports which statement;
- trust: whether the badges, counts, and explanations mean what they say.

A recommendation generated from Gmail while ignoring a related meeting can be confidently wrong.
That is worse than showing no recommendation.

---

## 4. What should have happened

For a Gmail conversation that results in a Google Calendar/Meet interaction, the intended flow is:

1. Gmail captures the conversation, participant identity, thread continuity, proposed time, open
   questions, commitments, and explicit meeting references.
2. Google Calendar captures the calendar event, organizer, attendees, time, status, title,
   description, stable event identifiers, and conference reference.
3. Identity resolution determines which participant nodes are the same humans across tools.
4. Correlation determines whether the email and calendar event describe the same situation. It
   records why they were joined or why they were left separate.
5. The situation model reconciles their lifecycle:
   `proposed → scheduled → past scheduled / verified held / cancelled / no-show unknown`.
6. The Context projection assembles a bounded relationship view containing the recent meeting and
   its relevant source evidence.
7. Intelligence recomputes the open loop using the new state.
8. The card explains what changed, why the new action follows, and which source supports each claim.

For Aditya, a correct output might look like:

> **Aditya — IIMA Ventures**
>
> Gmail: meeting proposed on 18 July.
>
> Google Calendar: meeting scheduled for 20 July, 1:00–1:30 PM IST.
>
> Meeting occurrence: not independently verified / verified by Meet attendance, depending on the
> available evidence.
>
> Open item after the meeting: `<specific deliverable or question>`.
>
> Recommended next step: `<specific action>`, because `<grounded reason>`.

The system must not infer that the meeting was definitely held merely because a past Calendar event
exists. Calendar proves that an event was scheduled. `Held` needs stronger evidence such as Meet
attendance, transcript/notes, explicit follow-up, or user confirmation. If that evidence is not
available, the honest state is `Past scheduled meeting — occurrence unverified`.

---

## 5. The Correlation Engine does exist

The failure is not caused by a total absence of correlation code.

The current backend already contains:

- a Google Calendar connector;
- a structured `gcal.calendar_event` mapping;
- meeting nodes and `person → attended → meeting` graph edges for small meetings;
- exact-email normalization for attendee identities;
- a Correlation Engine that groups events by thread or `(anchor entity, domain)`;
- `context_correlations` and `context_correlation_members` tables;
- situation refresh logic;
- a graph-node endpoint that can read a node's relationships live;
- tests that assert the structured lane invokes correlation.

The architecture therefore has several required pieces. The vertical path is incomplete, and some
of those pieces make incompatible assumptions. The existence of the engine only proves that a
function can be called. It does not prove that the correct records are joined or that downstream
surfaces read the result.

---

## 6. Why correlation can fail even though the engine is present

### 6.1 Correlation is narrower than its name suggests

The implemented Correlation Engine is deliberately deterministic and conservative. It does not
perform unrestricted semantic matching across all source data. Its main grouping rules are:

1. inherit an existing correlation from the same email thread; otherwise
2. group by the strongest available anchor entity plus one domain; otherwise
3. correlate to nothing.

This is a good safety posture against false merges, but it creates predictable false splits when
the cross-tool bridge is incomplete.

Calendar events do not share Gmail's thread ID. Therefore Calendar cannot use the strongest
continuity rule. It must survive identity resolution and then produce the same anchor and domain as
the Gmail event.

### 6.2 Gmail and Calendar can receive different domains

This is one of the strongest code-level explanations for a split.

The domain classifier has source priors for CRM, support, and billing sources. It has no source
prior for Gmail or Google Calendar. Gmail is processed as unstructured text, so its subject/body can
trigger keywords such as `deal`, `pricing`, `proposal`, `demo`, `budget`, or `contract` and receive
the `sales` domain.

Google Calendar is processed through the structured lane. The capture pipeline intentionally does
not preprocess structured event text. It passes no text into the domain-hint function, so a GCal
event normally receives no domain hint and falls back to `general` during correlation.

The Correlation Engine includes domain in the stable correlation key. Therefore the same person or
company can produce:

- Gmail → `(Aditya, sales)`;
- Google Calendar → `(Aditya, general)`.

Those are two valid but separate correlation groups. Both events can be marked `correlated`, the
health metric can look healthy, and the user still gets two realities.

The fix must not simply delete domain from the correlation key. A person can legitimately have a
sales situation and a support situation at the same time. Instead, structured Calendar content
must receive deterministic domain evidence, and hard meeting bridges must be allowed to reconcile a
domain mismatch when they prove the events describe the same interaction.

### 6.3 Identity matching is exact and can under-correlate aliases

Calendar attendees become person nodes using normalized email addresses. Exact email identity is a
safe hard join, but the same human may appear as:

- a work address in Gmail and another work/alias address in Calendar;
- a personal Gmail address on the invite and a company address in the email;
- organizer-only rather than attendee;
- an older address that has not been linked to the current identity;
- a forwarded invite where the actual participant is not represented as expected.

Names are not safely auto-merged, which is correct. However, there must be an explicit alias and
identity-evidence path. Without it, Rohit in one tool and Rohit under another address in a second
tool remain different nodes.

Internal/external classification currently depends on active `org_seats` email addresses. If the
user's Calendar account or alias is missing from `org_seats`, the engine can treat an internal seat
as an external counterparty or fail to choose the intended participant anchor.

### 6.4 Person-to-company lifting is conditional

The engine tries to prevent Gmail and Calendar from anchoring the same human differently. It lifts
a person to a company only when a live company node already exists whose canonical key exactly
matches the person's email domain.

If the company node does not exist, the domain is personal, or the company canonical key differs
from the email domain, the Calendar event stays person-anchored. Meanwhile Gmail extraction may
have produced a company anchor. The two events then land in separate situations.

This is another intentional fail-closed behavior, not random nondeterminism. It still requires a
reconciliation path and observability so a split does not remain invisible.

### 6.5 Calendar capture and mapping lose useful bridge evidence

The connector currently captures:

- event ID;
- organizer email as the actor;
- attendee emails;
- title, start, end, status, description, and location;
- `hangoutLink` in the encrypted raw event.

The structured graph mapping persists the title, time, status, description, and location. It does
not map the captured `hangoutLink`, and the connector/mapping do not preserve several high-value
cross-tool identifiers and states such as:

- iCalendar UID;
- Google Meet conference/meeting code;
- recurring-event identity;
- creator versus organizer;
- attendee response state;
- attendee display name;
- cancellation/deletion semantics beyond the basic status;
- structured conference data.

The connector also flattens attendees to email strings before mapping, so display names and
response states are discarded. The organizer is stored as event actor metadata but is not created
as a graph relationship unless that address is also present in attendees.

These omissions remove deterministic cross-source bridge keys. The engine is then forced to rely on
the weaker entity-plus-domain rule.

### 6.6 Some meetings intentionally receive no attendee edges

For more than ten attendees, the structured commit path stores one attendee-list fact on the
meeting and intentionally does not create per-person nodes, edges, or correlations. This protects
the graph from webinars and large events, but a real meeting with eleven relevant participants
cannot appear through a person's `attended` relationship under the current rule.

The safety guard is useful, but the threshold cannot silently convert a real interaction into an
unlinked event. Large events need a bounded relation strategy, such as linking only the organizer,
internal attendees, explicitly tracked counterparties, and already-known high-confidence people.

### 6.7 First-connect Calendar history is bounded to 120 days

On first connection, Google Calendar fetches the most recent 120 days plus future events. Any older
meeting will not be captured by the normal initial snapshot. This may or may not explain the Rohit
or Aditya examples, depending on their actual dates and the connection watermark. It is a live-data
diagnostic, not a confirmed cause from the screenshots.

### 6.8 The strongest confirmed defect: Context does not consume the correlated graph

Even when Calendar ingestion, identity, graph edges, and correlation all succeed, the active Context
page can still hide the meeting.

The backend `/context/facts` endpoint returns a per-node count and direct fact summary. It does not
join graph edges, meeting-node facts, correlation members, situations, or claim-level source
evidence. A person therefore appears as an email/person record with their own direct facts. Their
connected meeting exists on another node and is omitted.

The separate entity deep-dive endpoint reads adjacent node display names, but it does not load the
neighbor meeting's title, time, status, source references, or correlation evidence. It returns
`recent_interactions: []` unconditionally.

The dashboard Context page does not call that deep-dive endpoint when a row is selected. It builds
the side panel entirely from the shallow facts list, so a meeting edge in the graph has no route to
the screen.

This is not a probabilistic root cause. It is a confirmed projection defect in the current code.

### 6.9 The card projection also ignores correlation and meeting neighbors

The card helper resolves the signal's subject node and loads only direct active facts and direct
observations on that node. It does not traverse:

- graph edges;
- connected meeting nodes;
- `context_correlation_members`;
- the current situation;
- source-event provenance.

It also explicitly filters out meeting title, start, end, and status fields from the card context.
Those fields usually live on the meeting node anyway, but the skip reinforces the missing-context
behavior.

The result is predictable: a Gmail-generated signal shows Gmail-derived labels even when a linked
Calendar meeting exists elsewhere in the graph.

### 6.10 Read-model invalidation is incomplete

After processing a structured Calendar event, the L2 runner returns only the meeting node as the
affected node. It rebuilds the meeting's read model, not every attendee person's read model.

Even if it rebuilt the person model, the current entity-360 builder only reads direct facts and
observations. It does not include graph edges or correlation/situation members despite its comment
describing an entity projection.

This creates two distinct problems:

- the person projection can remain stale after a new meeting edge is added;
- a fresh person projection still cannot contain the meeting because neighbor data is not read.

### 6.11 Situation refresh can fail without failing ingestion

Situation refresh runs after event processing. Exceptions are logged but treated as non-fatal so
source ingestion can continue. This is a reasonable resilience choice, but it means the system can
report an event as successfully processed while its derived situation view remains stale.

The status contract must distinguish:

- event captured;
- graph committed;
- correlation membership written;
- situation refreshed;
- projection rebuilt;
- intelligence invalidated/recomputed.

One green `processed` status is not proof that the end-user view is current.

### 6.12 The current source badges and evidence counts are misleading

For live records not covered by static demo metadata, the dashboard uses the first globally
connected tools as `sourceNames`. It does not receive record-level or claim-level source support.
This is why a record can show `gcal` and `gmail` even if the selected facts were not correlated
between those tools.

The backend calls a direct fact count `interaction_count`. The dashboard then sums that field into
an `EVIDENCE` number. As a result:

- fact count is presented as interaction count;
- interaction count is presented as evidence count;
- globally connected tools are presented as record sources.

These labels overstate what the system knows and make correlation failures harder to notice.

### 6.13 Tests verify invocation, not the real cross-tool outcome

Some correlation tests inspect the source code and assert that `commit_structured` contains a call
to `correlate_event`, that it occurs before commit, and that person-to-company lifting exists. Those
tests prove wiring syntax, not behavior across actual Gmail and Calendar events.

The real-Postgres L2 tests separately prove that:

- a structured HubSpot deal can reach a situation;
- an unstructured Gmail event can write facts and observations.

They do not run one Gmail meeting proposal and one GCal event for the same person through the full
pipeline and assert that:

- both events share the correct correlation/situation;
- domain differences are reconciled safely;
- the person Context bundle contains the meeting;
- the card consumes the updated situation;
- source evidence is claim-specific;
- the obsolete proposed-meeting state is retired.

The test suite therefore allows the exact user-visible failure reported here.

### 6.14 Health can be green while cross-tool reality is split

The current `correlation_reach` health metric asks whether a knowledge-bearing event belongs to any
correlation. It does not ask whether two likely-related events from different sources belong to the
same correlation.

If Gmail enters `(Aditya, sales)` and Calendar enters `(Aditya, general)`, both events are correlated
and neither is counted as uncorrelated. The metric can remain healthy while source fusion has
failed.

---

## 7. Root-cause classification

The evidence must be separated by certainty.

### 7.1 Confirmed from the current code

- Context's main facts endpoint is node-local and does not return meetings/correlations/situations.
- The Context UI does not fetch a record-specific deep-dive on selection.
- The available deep-dive returns no recent interactions and does not hydrate meeting facts.
- The card context helper is node-local and does not read correlation/situation membership.
- Source badges fall back to globally connected tools rather than record evidence.
- `interaction_count` is a direct fact count and is displayed as evidence.
- Calendar structured events normally lack text-derived domain hints.
- Calendar conference/link data is captured raw but not mapped into usable graph context.
- Read-model rebuilds do not propagate from meeting nodes to attendee-person projections.
- There is no full Gmail + GCal + Context/card end-to-end test.
- Health measures `correlated somewhere`, not `correctly fused across sources`.

### 7.2 Plausible but requiring live data verification

- The Rohit or Aditya calendar event was outside the first-connect window.
- The connector did not fetch the event or the event was dropped/parked/failed.
- The raw event contained an unexpected organizer/attendee shape.
- Gmail and Calendar used different email identities or aliases.
- The user/organizer address was missing or misclassified in `org_seats`.
- The two events received different anchor nodes.
- Gmail received `sales` while Calendar received `general`.
- The Calendar event belonged to a different 45-day correlation generation.
- Situation refresh failed after graph commit.
- The meeting exists correctly in the graph but the deployed API/UI version is stale.

These must not be converted into assertions without tenant-scoped row evidence.

---

## 8. Required live forensic audit for Rohit and Aditya

Before changing matching behavior or backfilling data, trace each meeting through every checkpoint.
The audit must be tenant-scoped and must avoid printing decrypted message bodies or sensitive tokens
into logs.

### Checkpoint A — source connection and sync

For Gmail and GCal separately, verify:

- active connection/account identity;
- last successful sync time;
- watermark/cursor;
- pagination completion;
- connector errors and retry/park status;
- whether the relevant calendar is `primary` or another calendar;
- whether the event date was within the configured backfill window.

### Checkpoint B — source event ledger

Locate the expected GCal event using tenant, participant email(s), approximate date, event ID,
iCalendar UID, or conference identifier where available. Record:

- `source_event.event_id`;
- source/object type and source object ID;
- occurred time and content version;
- emitted, parked, dropped, or failed outcome;
- domain hints;
- processing status and last error.

### Checkpoint C — structured payload and mapping

Within an authorized diagnostic context, verify that the encrypted/raw event contains:

- organizer;
- attendees;
- title/description;
- start/end/status;
- Meet/conference reference;
- event update/version fields.

Then verify which of those fields survived the structured mapping.

### Checkpoint D — graph write

Verify:

- one stable meeting node for the Calendar source object;
- current meeting title/start/end/status facts;
- attendee person nodes;
- `attended` edges;
- evidence references back to the Calendar event;
- idempotent behavior across event updates/reschedules.

### Checkpoint E — identity

For Rohit and Aditya, compare every relevant Gmail sender/recipient identity with Calendar organizer
and attendee identities. Verify:

- normalized canonical email;
- alias links and merge state;
- company relationship/domain;
- internal-seat classification;
- whether the same human resolved to the same `node_id`.

### Checkpoint F — correlation

For the relevant Gmail and GCal event IDs, compare:

- correlation IDs;
- anchor node IDs/types;
- domains;
- generations;
- `joined_via` reason;
- first/last event time;
- all source members in each group.

If the events have different IDs, identify the first differing key: identity, anchor, domain,
generation, or missing bridge.

### Checkpoint G — situation and projections

Verify whether:

- the correlation has an active situation;
- that situation contains both source events;
- situation refresh completed after the newest event;
- the meeting and attendee read models have current graph versions;
- the Context APIs return the meeting;
- the card's context snapshot includes the situation and source evidence;
- the old card was invalidated or recomputed after Calendar evidence arrived.

This produces an exact failure location for each example rather than one generic diagnosis.

---

## 9. What needs to change

### 9.1 Define a real cross-source interaction contract

Introduce a bounded `Interaction` or `SituationInteraction` projection. It is not a copy of Gmail
or Calendar history. It contains only the minimum decision-relevant state:

- stable interaction ID;
- interaction type;
- lifecycle state;
- start/end time and timezone;
- normalized participants and roles;
- subject/title and bounded decision-relevant summary;
- related situation/correlation ID;
- source references;
- claim-level provenance;
- verification state;
- effect on open questions, commitments, and next steps;
- last recomputed graph version.

This belongs to GeniOS's bounded context/decision state described in Update 2. Raw emails,
transcripts, complete calendar history, and generalized recall remain owned by source tools or a
dedicated memory layer.

### 9.2 Preserve deterministic Calendar bridge keys

The Calendar connector and mapping should preserve, subject to security policy:

- source calendar event ID;
- iCalendar UID;
- recurring-event ID and instance time;
- provider and conference ID / normalized Meet code;
- an access-controlled source pointer rather than an unrestricted raw link;
- organizer and creator identities;
- attendee identities, display names, and response states;
- event status, cancellation/deletion state, and updated version;
- title, description, location, start, end, and timezone.

These are correlation evidence, not unbounded memory. The source pointer allows deeper retrieval on
demand without copying the whole source payload into GeniOS.

### 9.3 Correlate through explicit bridge strength

Use deterministic evidence tiers.

#### Hard join — automatic

- same Gmail thread;
- same source calendar event ID or iCalendar UID;
- same normalized conference/Meet identifier;
- an email containing the exact calendar event/ICS/conference reference;
- an explicit source-system relation to the same business object.

Hard identity should override a superficial domain mismatch because it proves the interaction is
the same object.

#### Strong multi-signal join — automatic only above a tested threshold

Examples of combined evidence:

- at least one exact external participant identity;
- compatible organizer/attendee direction;
- proposed and scheduled times within a bounded window;
- meaningful title/topic overlap;
- email intent explicitly proposing or confirming the meeting;
- same company/deal/project anchor.

The matched features, rule version, and reason must be recorded so the join is explainable and
replayable.

#### Candidate only — human review or remain separate

- same display name only;
- same company domain only;
- same day/time only;
- generic title such as `Catch up`;
- fuzzy semantic similarity without stable participant evidence.

The system should continue to prefer a false split over a dangerous false merge, but false splits
must become visible candidates instead of silent permanent islands.

### 9.4 Reconcile domain without flattening all situations

Required changes:

- derive deterministic domain hints from Calendar title, description, location, and mapped business
  object references;
- preserve the exact evidence that generated the domain;
- if a hard meeting bridge exists, join the event even when one source is `general` and the other is
  `sales`/`support`/`admin`;
- if only weak entity evidence exists, keep domain separation;
- permit one event to support multiple situations only when explicit evidence warrants it;
- flag same-anchor, nearby-time, cross-source, different-domain groups as split candidates.

Domain should protect distinct business situations. It should not prevent two source records of the
same meeting from being recognized as the same interaction.

### 9.5 Make identity resolution cross-tool and explainable

Required behavior:

- exact normalized email remains a hard identity;
- provider/account aliases can be explicitly linked with evidence;
- organizer-only participants are represented;
- internal account aliases are included in org-seat identity;
- personal and work addresses are not auto-merged from name alone;
- ambiguous alias candidates remain unresolved and visible;
- every merge records evidence, method, confidence, and reversibility.

### 9.6 Model interaction lifecycle correctly

Do not treat all evidence as independent tags. Reconcile state transitions:

| Prior state | New evidence | Result |
|---|---|---|
| Meeting proposed in Gmail | Matching Calendar invite | Scheduled |
| Scheduled | Event moved | Rescheduled; old time superseded |
| Scheduled | Calendar cancelled | Cancelled; do not treat as held |
| Scheduled | Time passed, no attendance evidence | Past scheduled; occurrence unverified |
| Scheduled | Meet attendance/transcript/notes or user confirmation | Held / occurred |
| Held | Follow-up email contains next step | New post-meeting open loop |
| Proposed | Unrelated meeting with same person | Keep separate |

A meeting being held does not automatically fulfill every commitment in the Gmail thread. The
system must link the exact commitment or question affected. If that relation is unknown, say so.

### 9.7 Build a correlation-aware Context projection

The person/company Context bundle should be assembled from a bounded traversal:

- the resolved entity;
- direct current facts and observations;
- one-hop relevant interactions such as meetings;
- the active situations/correlations containing the entity's evidence;
- open questions, commitments, and next steps connected to those situations;
- claim-level source references;
- lifecycle and freshness per claim;
- explicit unknown/conflict states.

The projection should return real `recent_interactions`; it must not hardcode an empty array. A
neighbor name alone is insufficient: the meeting's title, time, state, relevant participants,
source, and decision impact are required.

### 9.8 Propagate read-model invalidation

When a meeting or relationship edge changes, rebuild/invalidate:

- the meeting projection;
- every affected attendee-person projection;
- relevant company/deal/project projections;
- affected correlation/situation projections;
- dependent signals, decision briefs, and active cards.

The invalidation record should carry graph version and cause event ID. A card must not claim current
context when its snapshot predates the meeting evidence.

### 9.9 Make cards situation-aware

The card builder must consume a bounded Decision Brief or situation projection, not only direct
facts on the signal's subject node.

Every actionable card must explain:

- who the person/company is in this situation;
- what happened across the relevant tools;
- the current interaction/open-loop state;
- what changed since the prior state;
- what remains unresolved;
- the exact recommended action;
- why that action follows;
- evidence per claim;
- uncertainty and safe fallback.

If required context cannot be assembled, the product must fail closed:

> `GeniOS found an open loop but cannot yet reconcile the related Gmail and Calendar evidence. Open
> sources to review; no action has been inferred.`

It must not continue showing a highly urgent generic instruction.

### 9.10 Make the UI evidence-honest

Replace current global/tool-derived badges and overloaded counts with:

- record sources: tools that produced evidence attached to this record;
- claim sources: tool/event references supporting each displayed statement;
- interaction count: actual distinct interactions;
- evidence count: actual evidence items supporting the selected claims;
- correlation state: joined, candidate, split, or unresolved;
- last successful correlation/projection time;
- `View evidence` links that open the authorized source record or evidence excerpt.

Never show Gmail or GCal as evidence for a record merely because the workspace connected those
tools.

### 9.11 Add cross-tool health and alerts

Add metrics that detect semantic incompleteness, not only orphan events:

- percentage of person-linked GCal meetings visible in person Context;
- percentage of meeting-proposal Gmail threads linked to a Calendar event;
- source-fusion ratio for active multi-source relationships;
- same-anchor/time-window groups split only by domain;
- same-identity events split across correlation generations;
- Calendar meetings without participant edges;
- organizer-only events without an external anchor;
- correlation memberships without a current situation;
- situation graph version versus Context/card projection version;
- active cards whose source evidence changed after card creation;
- record source badges without claim-level evidence — must always be zero.

Health should distinguish:

- `uncorrelated`;
- `correlated to the wrong/split group candidate`;
- `correlated but not projected`;
- `projected but stale`;
- `visible and evidence-complete`.

---

## 10. Historical recovery and backfill

Fixing only future events leaves the reported Rohit and Aditya cases broken. After the model and
projection are corrected, perform a tenant-safe rebuild in this order:

1. confirm source connection scope and desired history window;
2. fetch missing Calendar event metadata from the source of truth;
3. replay/recover parked or failed events;
4. remap Calendar fields and bridge identifiers;
5. resolve exact identities and create review candidates for ambiguous aliases;
6. rebuild meeting-person edges;
7. recompute cross-source correlations in deterministic event-time order;
8. rebuild situations;
9. rebuild affected entity/interaction read models;
10. invalidate and recompute affected signals and active cards;
11. verify Rohit and Aditya end to end;
12. compare pre/post grouping to detect accidental over-correlation.

The recovery must be replayable, idempotent, tenant-scoped, versioned, and auditable. It must not
require GeniOS to retain raw source history indefinitely. When raw payload TTL has expired, refetch
the allowed metadata from Gmail/Calendar using the stored source pointer and current authorization.

---

## 11. Required tests

### 11.1 Database end-to-end tests

Add a real-Postgres scenario that processes:

1. a Gmail email from `adityad@iima.ac.in` proposing a meeting and producing a `sales` hint;
2. a GCal event for the same external participant with no explicit domain hint;
3. a Calendar update/reschedule;
4. a post-meeting Gmail follow-up.

Assert:

- stable identity across sources;
- one correct interaction;
- correct correlation/situation membership;
- explainable join reason;
- domain mismatch is reconciled only because strong evidence exists;
- proposed state is superseded by scheduled state;
- occurrence remains unverified without attendance evidence;
- person Context contains the meeting;
- record sources are Gmail and GCal because both support the record;
- the card is recomputed and no longer presents stale scheduling context.

### 11.2 Negative correlation tests

Verify that the engine does not merge:

- two unrelated meetings with the same person;
- two generic `Catch up` meetings at different times;
- people with the same display name;
- a webinar and an individual sales meeting;
- separate sales and support situations without a hard interaction bridge;
- cancelled and replacement meetings unless a source identifier links them.

### 11.3 Identity and Calendar edge cases

Cover:

- work email versus personal Calendar alias;
- organizer not repeated in attendees;
- internal user with multiple authorized account aliases;
- more than ten attendees;
- recurring events and individual instances;
- all-day events;
- cancelled/deleted events;
- timezone changes;
- out-of-order connector recovery;
- events older than the default backfill window;
- duplicate connector delivery and replay.

### 11.4 Projection and UI contract tests

Assert that:

- Context selection fetches record-specific detail;
- `recent_interactions` is populated from real interaction data;
- meeting facts are hydrated, not only neighbor names;
- source badges come only from attached evidence;
- fact count, interaction count, and evidence count are distinct;
- the card reads the same situation version as Context;
- stale projections are labeled and not used for high-confidence action;
- an unresolved correlation shows an honest review state.

### 11.5 Health tests

Create two events that each belong to different valid correlations but should be a split candidate.
The new health metrics must detect that condition even though the old `correlation_reach` metric is
100%.

---

## 12. Acceptance criteria

This issue is complete only when all of the following are proven:

### Rohit and Aditya examples

- The exact GCal events are located or their absence is explained by connector evidence.
- Their correct identities are resolved across Gmail and Calendar.
- The related Gmail and GCal events share the intended interaction/situation, or the UI clearly
  explains why they remain separate.
- Context shows the meeting title, time, lifecycle, participants, and source evidence.
- The card reflects the latest cross-tool state and no longer relies only on Gmail.
- `Held` is shown only when occurrence evidence supports it.

### Data correctness

- Every displayed source badge is backed by record/claim evidence.
- Interaction count is not a fact count.
- Evidence count is not a connected-tool count.
- Correlation joins are reasoned, versioned, and replayable.
- Domain protection remains for genuinely separate situations.
- Ambiguous identity and correlation candidates do not auto-merge.

### Operational correctness

- Source capture, graph commit, correlation, situation refresh, projection, and card recomputation
  have separate observable status.
- Cross-tool split and correlation-but-not-projected conditions alert visibly.
- Historical backfill is idempotent and does not duplicate meetings or evidence.
- End-to-end tests run against real Postgres and pass without skips before release.

### User clarity

For any meeting-related card, the user can answer without opening Gmail or Calendar:

- Who is this?
- What was proposed?
- What was scheduled?
- Did it definitely happen, or is occurrence unverified?
- What was discussed or agreed, if evidence exists?
- What remains open?
- What exactly should I do now?
- Why should I do it?
- Which source supports each statement?

---

## 13. Likely implementation surface

This update is a specification, not an implementation patch. The eventual fix is multi-layer and
will likely touch:

### Backend

- `genios_engine/capture/connectors/calendar.py` — richer source metadata and sync diagnostics;
- `genios_engine/capture/structured/registry.py` — Calendar bridge fields;
- `genios_engine/capture/structured/apply.py` — organizer/attendee identity and response data;
- `genios_engine/capture/domain/hints.py` and capture pipeline — deterministic structured-text
  domain hints;
- `genios_engine/context/correlation.py` — bridge-aware, explainable cross-source joins;
- `genios_engine/context/structured.py` — complete affected-node propagation;
- `genios_engine/context/runner.py` — projection invalidation and stage-level status;
- `genios_engine/context/read_models.py` — correlation-aware bounded entity/interaction views;
- `genios_engine/context/situations.py` — interaction reconciliation and source coverage;
- `genios_engine/context/health.py` — split/projection health;
- `genios_engine/api/routes.py` and `genios_engine/api/workspace_routes.py` — evidence-complete
  Context/card contracts;
- migrations for additional bridge/provenance/health state;
- full DB end-to-end tests.

### Dashboard and Mac app

- Dashboard Context data client/types and row-selection behavior;
- Context record rendering for real interactions and claim evidence;
- removal of global connected-tool badges from record evidence;
- Mac card projection and lifecycle rendering;
- stale/unresolved-context fallback.

This should be implemented as one verified vertical slice. Fixing only the dashboard will conceal
upstream splits. Fixing only correlation will leave the user-facing projection blind.

---

## 14. Product boundary: this does not make GeniOS the memory layer

Cross-tool correlation requires bounded persisted state, but not unlimited memory.

GeniOS should store:

- normalized entity and interaction identities;
- source pointers and hashes;
- decision-relevant meeting state;
- correlation/situation membership and join reasons;
- bounded evidence excerpts or derived claims where policy permits;
- lifecycle transitions;
- projection versions and decision dependencies;
- user corrections and outcomes.

GeniOS should not become the durable owner of:

- complete Gmail bodies and attachments;
- every Calendar field forever;
- full Meet recordings/transcripts by default;
- unrestricted historical recall;
- duplicate copies of source-system history.

The source systems or a dedicated memory layer remain the durable history owners. GeniOS retains
the minimum evidence-linked state required to understand the current situation, explain a decision,
recompute safely, and audit the result.

---

## 15. What must not be done

- Do not solve this by showing more raw Gmail and Calendar metadata without reconciling it.
- Do not label globally connected tools as sources for every record.
- Do not remove domain from every correlation key and merge all interactions with one person.
- Do not fuzzy-merge identities from names alone.
- Do not claim a meeting was held only because its scheduled time has passed.
- Do not mark a commitment fulfilled merely because a meeting occurred.
- Do not let ingestion success stand in for situation/projection success.
- Do not ship only unit/introspection tests and call the cross-tool path verified.
- Do not backfill without tenant scoping, idempotency, provenance, and over-correlation checks.
- Do not generate high-urgency action cards when required cross-tool context is unresolved.

---

## 16. Final product decision

The Correlation Engine is present, but the current product does not complete cross-tool correlation
as an end-to-end capability.

At least one confirmed failure is downstream: Context and cards are not consuming the correlated
graph/situation needed to show meetings. There are also credible upstream split paths, especially
Calendar's `general` domain versus Gmail's text-derived domain, exact-email identity, conditional
person-to-company lifting, missing Calendar bridge fields, and bounded capture behavior. The exact
combination affecting Rohit and Aditya must be established from live tenant-scoped evidence.

The required outcome is not merely `show Calendar events`. It is:

> Gmail, Calendar, Meet, CRM, documents, and other connected tools must contribute evidence to one
> bounded, explainable business situation. GeniOS must reconcile that situation before producing an
> action, and every displayed claim must reveal which source supports it.

Until that is true, GeniOS may have a Correlation Engine internally, but the user does not yet have
a correlated intelligence product.
