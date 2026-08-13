# Update 2 — GeniOS Must Store Bounded Context Without Becoming the Memory Layer

**Status:** Open — architecture decision and product specification only

**Severity:** Critical — without this boundary GeniOS either lacks enough context to produce
intelligence or expands into an unbounded memory product

**Observed surfaces:** GeniOS Mac intelligence card and Dashboard → Intelligence → Context

**Example:** `Deliver the commitment to nitesh.pant@devdashlabs.com today`

---

## 1. Executive decision

GeniOS will sit above connected business tools and may also read from a dedicated memory layer.
GeniOS will nevertheless persist its own limited state because a completely stateless system cannot
resolve identities, join evidence across tools, detect changes, deduplicate recommendations, explain
decisions, enforce freshness, or measure outcomes.

That persistence does **not** make GeniOS the memory layer.

The architectural boundary is:

> Source tools and dedicated memory systems own durable source history and general recall. GeniOS
> owns the minimum evidence-linked context and decision state required to understand the current
> business situation, decide safely, explain the decision, deliver it once, and measure the outcome.

In short:

- memory answers **what has happened and what can be recalled**;
- the GeniOS Context Graph answers **what is currently true, related, relevant, and sufficiently
  evidenced**; and
- GeniOS intelligence answers **what should happen next, why, under which conditions, and with what
  authority**.

The product goal is not `remember everything`. It is:

> Know enough, prove enough, and retain enough to decide correctly.

---

## 2. What happened

### 2.1 The intelligence card asserted an action without reconstructing the situation

The Mac card displayed an apparently specific recommendation:

> `Deliver the commitment to nitesh.pant@devdashlabs.com today`

It also showed details such as:

- Nitesh Pant;
- DevDash Labs;
- source: Gmail;
- due date: 5 August;
- company, role, phone number, focus, and a proposed meeting slot;
- labels including open questions, meeting proposed, intro thread, and next step agreed;
- confidence, urgency, and an overall score.

This looks rich, but the action-critical meaning remains unclear:

- Who exactly is Nitesh Pant in relation to the user and GeniOS?
- Which Gmail thread or meeting produced this conclusion?
- What exactly was promised?
- Who made the promise?
- What did Nitesh say, and what did the user say?
- Was 5 August an explicit deadline, a proposed date, or an inferred date?
- What artifact or response must be delivered?
- Why does it matter now?
- What happens if the user does nothing?
- What is the next safe action?

The card therefore surfaced a conclusion before making its underlying situation understandable.

### 2.2 Context search did not answer the user's questions

The user searched `devdash` in the Context surface to understand the card. The result showed one
company/primary record for `nitesh.pant@devdashlabs.com` and a detail panel containing approximately:

- active relationship;
- current lifecycle;
- one context fact that repeats the email address;
- evidence confidence and freshness percentages;
- evidence count and source labels such as Gmail and Google Calendar;
- last update time.

This did not explain the person, relationship, conversation, commitment, evidence, or recommended
action. The Context surface exposed record-management metadata rather than decision-ready context.

Repeating an email address as a `Context Fact` is not useful context. An evidence count of nine is
also not an explanation if the user cannot see which claims those nine pieces of evidence support.

### 2.3 The resulting user journey is backwards

The current journey is effectively:

```text
GeniOS gives a confident action
    ↓
User does not understand the action
    ↓
User searches GeniOS Context
    ↓
Context still does not explain the situation
    ↓
User must reopen Gmail/Calendar and reconstruct everything manually
    ↓
User must perform the understanding and decision work themselves
```

That defeats the purpose of a company intelligence layer. A user may open the source to verify a
high-impact claim, but they should not have to reconstruct the basic situation because GeniOS failed
to carry the relevant context into the intelligence object.

---

## 3. The architecture question this exposed

Fixing the card requires more than a better sentence. GeniOS must know enough about the person,
company, conversation, commitment, timeline, and evidence to create an intelligible recommendation.

That raises a legitimate question:

> If GeniOS reads tools and memory systems, periodically synchronises their data, and stores richer
> facts and relationships, does GeniOS itself become the memory layer?

The answer is:

> **No, not if ownership, purpose, scope, provenance, retention, and deletion boundaries remain
> explicit. Yes, if GeniOS starts retaining unbounded source history for generic recall and becomes
> the canonical replacement for Gmail, Calendar, CRM, documents, or a dedicated memory service.**

Storage is an implementation capability. `Memory layer` is an architectural responsibility. A
system does not become the memory layer merely because it has a database.

---

## 4. Required conceptual separation

### 4.1 Source systems

Examples include Gmail, Calendar, Slack, CRM, project-management systems, databases, and documents.

They own:

- original messages, meetings, records, and files;
- native history and versions;
- source permissions and deletion;
- the authoritative representation of what happened in that tool.

GeniOS must not silently replace these systems as the source of truth.

### 4.2 Dedicated memory layer

A dedicated memory layer may own broader, durable recall such as:

- conversation history;
- episodic history;
- semantic/user memory;
- preferences and recurring patterns;
- consolidation, retrieval, forgetting, and memory lifecycle;
- recall across sessions and applications.

GeniOS can consume this layer through a scoped connector like any other governed source. GeniOS
should not duplicate its full corpus merely to perform intelligence.

### 4.3 GeniOS Context Graph

The Context Graph is a GeniOS-owned operational model. It should contain bounded, typed, current,
evidence-linked state such as:

- resolved entities;
- current relationships;
- typed facts;
- commitments and obligations;
- situation-relevant events;
- source references and provenance;
- freshness, validity, conflict, and supersession state.

Its purpose is not general recall. Its purpose is to assemble a trustworthy business situation for
expertise and reasoning.

### 4.4 GeniOS intelligence and decision state

GeniOS must also retain enough decision state to prove:

- what situation was evaluated;
- what evidence was available;
- what was missing or conflicting;
- which policy, capability, and rules were applied;
- what recommendation was selected or suppressed;
- what was delivered;
- what the user/agent did;
- what outcome followed.

This is decision provenance and auditability, not general-purpose memory.

---

## 5. Target architecture

```text
Gmail / Calendar / CRM / Slack / Documents / Databases
                         +
             Optional dedicated Memory Layer
                         ↓
          Scoped connectors and periodic capture
                         ↓
       Normalised events + source references/cursors
                         ↓
       GeniOS Context Graph / bounded working state
                         ↓
        Domain Expertise + deterministic reasoning
                         ↓
       Intelligence Object + Decision/Why Trace
                         ↓
         Human or approval-bound agent handoff
                         ↓
              Outcome + bounded learning
```

Important ownership rule:

- the external memory layer is an upstream governed source;
- the Context Graph is GeniOS's internal current-state and relationship substrate;
- a bounded decision snapshot is the immutable input to one reasoning decision;
- none of these authorises GeniOS to become an unlimited archive of source content.

---

## 6. Exactly what GeniOS should store

### 6.1 Connector and synchronisation state

GeniOS must retain enough operational metadata to synchronise safely and incrementally:

- tenant/workspace ID;
- connector/source ID;
- provider record/thread/event ID;
- sync cursor or watermark;
- source version, etag, or content hash where available;
- last successful sync time;
- last attempted sync time and status;
- permission/visibility scope used during capture;
- deletion/tombstone state;
- retry and idempotency keys.

Why this is required:

- without cursors, every cron run must reread everything;
- without source IDs and hashes, duplicate facts and cards are unavoidable;
- without tombstones, deleted or revoked information remains falsely current;
- without scope lineage, GeniOS cannot prove that the data was visible to the current consumer.

### 6.2 Resolved identity and entity index

GeniOS should store a tenant-scoped entity index containing only grounded identity mappings:

- canonical internal entity ID;
- entity type: person, company, team, deal, project, commitment, document, and similar types;
- provider-specific IDs;
- verified names and aliases;
- verified email addresses/domains;
- company/team association;
- resolution status such as `verified`, `probable`, `address_only`, `conflicted`, or `unknown`;
- evidence supporting each identity claim;
- confidence per claim, not one confidence for the entire person;
- merge/split/supersession history.

For the observed example, this layer should answer:

- whether `nitesh.pant@devdashlabs.com` is verified as Nitesh Pant;
- whether DevDash Labs is verified as the organisation;
- what the current relationship with the user's workspace is;
- which claims came from Gmail, Calendar, CRM, memory, or another source.

It must not infer a person's identity solely from the mailbox local-part or invent a role from a
domain name.

### 6.3 Typed current facts

GeniOS should persist normalized facts needed to establish the current situation. Each fact must
carry its own lifecycle and provenance.

Minimum fact semantics:

- subject/entity ID;
- typed fact path;
- value;
- source record/reference;
- evidence span or pointer;
- extraction method/version;
- observed time;
- source-updated time;
- synced time;
- valid-from and valid-to where known;
- confidence;
- authority/source quality;
- current, stale, disputed, superseded, deleted, or unknown state;
- visibility and tenant boundary.

Example facts may include:

- `person.current_company = DevDash Labs`;
- `person.role = Co-founder & CEO`;
- `relationship.status = active`;
- `thread.ball_in_court = us`;
- `commitment.owner = Rohit`;
- `commitment.recipient = Nitesh Pant`;
- `commitment.due_at = 5 August`;
- `commitment.state = overdue`.

The due date and state are not enough by themselves. The promised outcome must also be captured or
explicitly marked unknown.

### 6.4 Relationships and graph edges

GeniOS should persist relationships that are necessary to understand business situations:

- person → company;
- person → role;
- user/workspace → person;
- person → conversation/thread;
- conversation → commitment;
- commitment → owner;
- commitment → recipient;
- commitment → due date;
- commitment → source evidence;
- commitment → blocker/dependency;
- decision → evidence;
- decision → selected play;
- action → outcome.

Each edge requires provenance, temporal validity, visibility, and confidence. A relationship without
supporting evidence must not silently become permanent truth.

### 6.5 Commitments, obligations, and open loops

An actionable commitment record must contain more than an email address and date:

- commitment ID;
- explicit promised outcome/deliverable;
- owner;
- recipient;
- source conversation;
- statement/evidence that created the commitment;
- created/observed time;
- explicit or inferred due date, clearly distinguished;
- current state;
- completion criteria;
- blockers and dependencies;
- renegotiation history;
- completion/cancellation evidence;
- confidence and unresolved fields.

If the exact deliverable is missing, the commitment must be marked `incomplete_context` or
equivalent. The system may report a suspected open loop, but it must not confidently instruct the
user to deliver an unknown thing.

### 6.6 Evidence and provenance

GeniOS should prefer references over full duplication. It may store:

- provider and source type;
- message/thread/event/document ID;
- authenticated deep link;
- source timestamp and author/participants;
- minimal relevant excerpt/span when necessary for explanation and replay;
- content/span hash;
- claim-to-evidence mapping;
- parser/extractor/model version;
- access/visibility classification;
- retention and expiry metadata.

The evidence object must answer:

> Which exact source supports this exact claim?

An evidence count such as `9` is insufficient unless the user can inspect which claims those nine
items prove. Evidence confidence must also remain separate from identity confidence,
recommendation confidence, priority, and urgency.

### 6.7 Bounded situation snapshots

Every reasoning run should receive an immutable, bounded snapshot containing only the context
required for that situation:

- root entity and situation type;
- relevant people and organisations;
- relevant facts and relationships;
- commitment/open-loop state;
- bounded event timeline;
- evidence references;
- missing information and conflicts;
- freshness state;
- permissions/policies relevant to the decision;
- evaluation time and graph/source versions.

This snapshot is not a general memory dump. It is a reproducible case file for one decision.

Why it must be retained:

- live source data may change after the recommendation;
- the user must be able to understand why GeniOS acted at that time;
- replay and audit require the same bounded input;
- a later deletion or correction must not make the historical decision inexplicable.

Sensitive snapshot content should have a separate, configurable retention policy from non-content
audit metadata.

### 6.8 Intelligence and decision records

GeniOS should persist the authoritative output of its intelligence process:

- situation/decision ID;
- bounded context snapshot reference;
- capability, expertise, rule, and policy versions;
- evaluation time;
- findings and missing-context state;
- alternatives considered;
- selected recommendation or suppression reason;
- priority/utility inputs;
- separate evidence, identity, and recommendation confidence;
- why-now reason;
- consequence of inaction;
- evidence/why trace;
- approval requirements;
- expiry and revalidation conditions.

This prevents the card or Delivery layer from inventing business meaning after the decision.

### 6.9 Delivery, action, audit, and outcome state

GeniOS should persist enough state to deliver safely and learn from real outcomes:

- which surface received the intelligence;
- when and to whom it was delivered;
- delivery/deduplication key;
- viewed, snoozed, dismissed, claimed, approved, rejected, assigned, completed, or expired state;
- actor and authority for every transition;
- external handoff reference;
- verified completion evidence or explicit human confirmation;
- observed outcome;
- feedback and correction history;
- bounded aggregate learning derived from outcomes.

This is necessary to avoid repeatedly showing the same advice and to distinguish `opened`,
`claimed`, and `actually completed`.

---

## 7. What may be stored only temporarily

Some data may be required during extraction or verification but does not need indefinite retention:

- raw email bodies;
- full document text;
- temporary calendar/CRM payloads;
- parsed/OCR text;
- search-result payloads;
- embeddings and retrieval caches;
- LLM extraction intermediates;
- temporary source excerpts not used as decision evidence;
- transient join tables or candidate entity matches.

These should be encrypted, access-controlled, tenant-scoped, purpose-bound, and deleted or refreshed
under a short configurable TTL whenever persistent retention is not necessary.

If an excerpt becomes load-bearing evidence for a decision, only the minimum relevant span should be
retained under the evidence/snapshot policy. The full source should remain in the source system and
be fetched on demand when permissions and availability allow.

---

## 8. What GeniOS must not store by default

GeniOS must not become an uncontrolled second copy of the company's information estate. It should
not store by default:

- complete mailbox history;
- complete Slack or chat history;
- every meeting transcript indefinitely;
- full copies of all documents and drive folders;
- generic personal or autobiographical memory unrelated to a business decision;
- unlimited cross-session conversation recall;
- every source payload merely because the connector can access it;
- permanent ungrounded model summaries;
- an inferred identity, relationship, commitment, deadline, or consequence as established truth;
- source content after access was revoked or deletion policy requires removal;
- cross-tenant facts, embeddings, profiles, or learning.

GeniOS also must not advertise itself as the canonical owner of the original history. The source
record remains authoritative; the GeniOS fact is a typed, provenance-linked projection of that
record.

---

## 9. Retention classes

Exact durations must be configurable by tenant, data class, source policy, legal requirement, and
region. The architecture should define semantic classes before hard-coding day counts.

| Class | Examples | Retention principle |
|---|---|---|
| Ephemeral processing | Raw payloads, parsed text, temporary candidate matches | Delete after extraction/verification or a short TTL. |
| Refreshable context projection | Current facts, relationships, entity mappings, commitments | Keep while valid and necessary; supersede rather than silently overwrite; honour deletion and revocation. |
| Minimal evidence | Source IDs, deep links, hashes, load-bearing spans | Keep only as long as required to explain/replay the related decision and allowed by source policy. |
| Immutable decision record | Situation snapshot, policy/rule versions, recommendation, suppression reason | Retain for the configured decision/audit window; sensitive payload bytes may expire before metadata. |
| Delivery and outcome state | Claim, approval, handoff, completion, feedback | Retain for deduplication, accountability, outcome measurement, and dispute/audit requirements. |
| Aggregated learning | Bounded rates/counters with provenance | Retain only when privacy-safe, tenant-scoped, and linked to valid audited outcomes. |

Deletion must propagate. If a source record is removed or access is revoked:

- current context must no longer treat it as available evidence;
- active recommendations depending on it must be revalidated, suppressed, or expired;
- cached/raw content must be purged according to policy;
- any legally retained audit record must be reduced to the minimum permitted representation;
- the system must preserve an honest deletion/tombstone event rather than presenting stale data as
  current.

---

## 10. Cron synchronisation does not change the boundary

Whether data is read in real time, hourly, every two hours, or on demand changes freshness—not
architectural ownership.

Every source-derived record must distinguish:

- `source_updated_at`: when the provider says the source changed;
- `observed_at`: when the underlying business event occurred;
- `synced_at`: when GeniOS captured it;
- `valid_from` / `valid_to`: when the fact is considered true;
- `expires_at` or TTL: when it must be refreshed or withheld;
- `deleted_at` / tombstone: when the source was removed or became inaccessible.

An hourly cron can safely support many proactive use cases, but GeniOS must never describe the graph
as real-time when it is one or two hours behind. Before any time-sensitive delivery or external
handoff, critical facts and authority should be revalidated if their freshness window has elapsed.

---

## 11. Required DevDash context packet

For the observed case, the minimum actionable packet should have this semantic shape:

```json
{
  "identity": {
    "person": "Nitesh Pant",
    "email": "nitesh.pant@devdashlabs.com",
    "company": "DevDash Labs",
    "role": "Co-founder & CEO",
    "relationship_to_workspace": null,
    "resolution_status": "partially_verified"
  },
  "situation": {
    "type": "overdue_commitment",
    "summary": null,
    "last_relevant_event_at": null,
    "ball_in_court": "us"
  },
  "commitment": {
    "owner": "Rohit",
    "recipient": "Nitesh Pant",
    "promised_outcome": null,
    "due_at": "5 Aug",
    "due_date_basis": "unknown",
    "state": "suspected_overdue",
    "completion_criteria": null,
    "grounding_status": "incomplete"
  },
  "evidence": {
    "sources": ["gmail", "gcal"],
    "claim_links": [],
    "source_thread": null,
    "relevant_spans": []
  },
  "decision": {
    "verdict": "review_source",
    "why_now": "A possible commitment dated 5 Aug appears unresolved, but the deliverable is not verified.",
    "recommended_next_step": "Open the source thread and verify the promised outcome.",
    "avoid": "Do not mark complete, draft, send, or hand off an unknown commitment."
  }
}
```

The null and `incomplete` fields are deliberate. They show what must be resolved before a confident
`Deliver the commitment today` recommendation is allowed.

When the source evidence is complete, the same packet should replace those unknowns with:

- the exact promised deliverable;
- who stated/accepted it;
- the relevant quoted evidence span;
- explicit or inferred due-date basis;
- business consequence;
- concrete completion criteria;
- specific next steps;
- safe human or approval-bound agent handoff.

---

## 12. Required fail-closed behaviour

GeniOS must represent these as different states:

1. an email/contact was detected;
2. the person's identity was resolved;
3. a relationship was established;
4. a possible commitment was detected;
5. the exact promised outcome was grounded;
6. the deadline and its basis were grounded;
7. the consequence and recommended action were supported.

Confidence at one stage cannot substitute for missing information at another stage.

For example:

- 95% confidence that the email belongs to Nitesh does not prove what was promised;
- nine source items do not prove that 5 August was an explicit deadline;
- 77% recommendation confidence does not make an unknown deliverable actionable;
- 100% freshness does not mean the fact is complete or correct;
- 100% urgency cannot be justified by elapsed time alone.

If any action-critical field is missing or conflicted, the system must:

- name the missing context;
- downgrade or suppress the action-specific recommendation;
- offer a safe verification step such as `Open source` or `Review evidence`;
- avoid drafting, sending, assigning, or completing;
- preserve the unresolved state for later refresh.

---

## 13. Storage admission test

Before GeniOS persists a new data category, it must answer whether that data is necessary to do at
least one of the following:

1. resolve an entity or relationship;
2. establish the current business situation;
3. prove a load-bearing claim;
4. apply expertise, policy, or deterministic reasoning;
5. explain or replay a decision;
6. prevent duplicate/conflicting delivery;
7. verify completion or measure an outcome;
8. satisfy an explicit audit, security, or legal obligation.

If none applies, GeniOS should not persist the data.

Even when one applies, the system must still choose the minimum representation, narrowest
visibility, and shortest sufficient retention class.

---

## 14. Why this architecture is necessary

### 14.1 Intelligence requires continuity

A stateless request-time system cannot reliably compare yesterday with today, know whether a
commitment remains open, suppress a duplicate card, or learn whether prior advice worked.

### 14.2 Trust requires provenance

The user must be able to move from recommendation → claim → evidence → original source. Without
persisted provenance and bounded snapshots, GeniOS becomes an opaque summariser.

### 14.3 Safe action requires current context

A source may change after the original extraction. Freshness, supersession, conflicts, and
revalidation are necessary before delivery or execution.

### 14.4 Privacy requires minimisation

Copying every connected source into GeniOS would expand security, privacy, residency, deletion, and
breach scope. A minimum-context model reduces that exposure.

### 14.5 Product focus requires a memory boundary

If GeniOS becomes a general memory and search product, it drifts toward storing and retrieving
everything. Its differentiated responsibility is to transform governed context into evidence-backed
advice and accountable handoffs.

### 14.6 Audit requires some durable state

Refusing to store anything would also be unsafe. GeniOS could not prove what evidence, policy, or
decision produced a card. The correct answer is bounded persistence, not zero persistence.

---

## 15. Layer ownership

### Connected tools and optional memory provider

- Own original history and broad recall.
- Enforce native permissions, deletion, and retention.
- Expose scoped records and changes to GeniOS.

### Capture

- Synchronise incrementally using cursors/watermarks.
- Preserve source identity, timestamps, permissions, deletions, and hashes.
- Extract bounded structured claims without inventing meaning.

### Context

- Resolve tenant-scoped entities and relationships.
- Maintain typed current facts, conflicts, freshness, validity, and provenance.
- Assemble bounded situation candidates.
- Never become an unbounded content archive.

### Domain Expertise

- Declare which facts, relationships, evidence, and freshness are required for a situation.
- Declare when missing context must block or degrade a capability.

### Reasoning

- Evaluate an immutable bounded snapshot.
- Separate unknown, inferred, conflicted, stale, and verified inputs.
- Produce a recommendation, alternatives, missing context, and why-trace—or fail closed.

### Executive

- Convert the decision into an understandable brief: what happened, why it matters, what should
  happen, required conditions, consequence of inaction, and accountable owner.

### Delivery

- Render and route the authoritative decision.
- Revalidate freshness and authority where required.
- Never invent missing business context or become the source of a new decision.

### Feedback and learning

- Record verified outcomes and explicit corrections.
- Learn only from audited, tenant-scoped decision/outcome lineage.
- Prefer bounded aggregates over retaining unnecessary raw content.

---

## 16. Acceptance criteria

### Architecture boundary

- [ ] GeniOS is documented as an intelligence/decision layer, not the canonical memory/source layer.
- [ ] A dedicated memory provider can be connected as an upstream governed source.
- [ ] The Context Graph is explicitly owned by GeniOS as bounded operational state.
- [ ] Every persisted data class has a purpose, owner, visibility, retention class, and deletion
      behaviour.
- [ ] Raw-source replication is opt-in and justified, never the default connector behaviour.

### Context completeness

- [ ] A person search explains identity, organisation, relationship, supporting claims, and conflicts
      rather than repeating an email address as the only fact.
- [ ] A commitment contains the promised outcome, owner, recipient, source, due-date basis, state,
      completion criteria, and evidence—or explicitly marks each missing field.
- [ ] Evidence counts are inspectable as claim-to-source mappings.
- [ ] Current, stale, disputed, superseded, deleted, and unknown states are distinct.

### Intelligence safety

- [ ] A card cannot recommend delivering an unknown commitment.
- [ ] Missing action-critical context produces `review_source`, `request_context`, `defer`, or
      `no_action`, not confident generic advice.
- [ ] Identity, fact/evidence, recommendation, priority, freshness, and urgency metrics remain
      separately named.
- [ ] The user can understand what happened, why it matters, and what to do without reconstructing
      the entire source history.

### Freshness and lifecycle

- [ ] Every source-derived fact carries source, observed, synced, validity, and expiry/deletion
      semantics.
- [ ] Cron lag is visible and never described as real-time.
- [ ] Deleted/revoked source data cannot remain active evidence.
- [ ] Time-sensitive delivery revalidates expired critical context.

### Privacy and governance

- [ ] Full source bodies are not retained indefinitely by default.
- [ ] Evidence retains only the minimum necessary span or a source pointer where possible.
- [ ] Tenant and source visibility propagate to facts, edges, snapshots, intelligence, and delivery.
- [ ] Sensitive snapshot content and non-content audit metadata have separate retention controls.
- [ ] Tenant erasure and source revocation have an end-to-end propagation path.

---

## 17. Non-goals and guardrails

- Do not interpret `bounded storage` as `store everything now and delete later`.
- Do not make the Context Graph a duplicate mailbox, data lake, document store, or vector-memory
  product.
- Do not depend on live source fetching for every decision; bounded snapshots are required for
  reliability and replay.
- Do not persist model-generated summaries as facts without evidence and lifecycle metadata.
- Do not overwrite facts silently; supersede them and preserve the permitted audit lineage.
- Do not retain private source content solely to improve future model prompts.
- Do not let a memory provider widen the permissions available to the current GeniOS consumer.
- Do not treat presence in memory as proof that a claim is current.
- Do not let Delivery or the UI fill missing context with confident prose.
- Do not equate freshness, confidence, urgency, evidence count, and overall score.

---

## 18. Decisions that must be frozen before implementation

1. The exact data-class and retention-policy matrix per tenant/region.
2. Whether load-bearing evidence stores a minimal encrypted span, a source pointer/hash, or both.
3. Which decisions require retained snapshot bytes versus a reproducible reference-only snapshot.
4. How source deletion affects historical decision explanation under legal/audit requirements.
5. The entity-resolution confidence states and human correction workflow.
6. The commitment schema, especially explicit-versus-inferred due-date semantics.
7. Freshness windows per source and situation type.
8. Which actions require just-in-time source revalidation.
9. The contract exposed by an external memory provider and how its visibility/expiry propagates.
10. The migration/backfill rule for current sparse Context records and already-open intelligence
    cards.

These decisions should be recorded as explicit architecture contracts rather than emerging
accidentally from database columns or UI requirements.

---

## 19. The 60-second CTO version

The DevDash card exposed two connected failures. First, GeniOS confidently said `Deliver the
commitment today` without showing what was promised, who said it, where it was said, why the date
matters, or what should actually be delivered. Second, searching Context showed an email address,
record metadata, evidence count, and freshness—but still did not reconstruct the situation.

Fixing this requires bounded persistence. GeniOS cannot be stateless: it needs sync cursors, resolved
entities, typed facts, temporal relationships, complete commitment objects, claim-level provenance,
minimal evidence, bounded situation snapshots, intelligence/decision lineage, delivery state, and
verified outcomes. Those records are necessary for continuity, grounding, deduplication, replay,
safe handoff, and learning.

This does not make GeniOS the memory layer. Gmail, Calendar, CRM, documents, and an optional
dedicated memory provider remain the owners of original history and broad recall. GeniOS stores the
minimum refreshable context and immutable decision state needed to determine what is true and what
should happen next. Raw source bodies, complete histories, generic personal memory, and unlimited
recall remain outside the default boundary.

The governing rule is simple: if a data item does not help resolve a situation, prove a claim,
apply a decision, prevent conflicting delivery, explain/replay the decision, verify an outcome, or
satisfy an explicit obligation, GeniOS should not persist it. If it does, GeniOS should retain the
smallest representation for the shortest sufficient period under the narrowest visibility.
