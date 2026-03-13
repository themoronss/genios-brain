## The Complete V1 Graph Engineering Deep-Dive

Let me go layer by layer, starting with the foundational architecture, then into the visual and UX specifics.

---

### 1. Graph Taxonomy — What Types of Nodes and Edges Exist

Before you render anything, you need a clean ontology. This is what most builders get wrong — they mix entity types and relationship types without a schema, and the graph becomes unreadable noise.

**Node types (V1):**

Your org (center node, always fixed), People (individual contacts), Companies (organizational entities — inferred from email domains). That's it for V1. Every node has a `type`, a `stage`, and an `interaction_count`.

**Edge types (V1):**

Email thread (directional — who initiated), Commitment made (special edge subtype — you promised something to them, or they promised something to you). Every edge has `sentiment_score`, `timestamp`, `topic[]`, `direction`.

**Relationship stage (the visual signal):**

This is the most important visual encoding in the entire graph. Every node color must map to a stage without the user needing to read a label.

```
ACTIVE  → Green    (last contact < 7 days, positive sentiment)
WARM    → Teal/Blue  (last contact 7-30 days)
DORMANT → Amber    (last contact 30-90 days)
COLD    → Gray     (last contact > 90 days)
AT_RISK → Red      (negative sentiment trend, regardless of recency)
```

Here's the critical architecture of the categorization logic:---

### 2. Ingestion Filter — What Gets Excluded Before Graph Construction

This is where most builders are sloppy. If you let everything in, the graph is useless noise.

**Hard exclusions at ingestion time:**

Anything from a `noreply@`, `donotreply@`, `notifications@`, `alerts@` prefix. Any domain on the promotional sender list (Mailchimp, SendGrid, Klaviyo headers). Any email thread where the contact sent to a BCC list of 50+ people (mass outreach). Any domain that matches known newsletter/marketing domains (substack.com, beehiiv.com etc.). Auto-generated calendar invites with no human reply chain.

**The detection logic:**

```python
def is_human_interaction(email_thread) -> bool:
    if has_list_unsubscribe_header(email_thread):
        return False  # marketing email
    if sender_domain in KNOWN_PROMOTIONAL_DOMAINS:
        return False
    if recipient_count > 10 and sender != org_domain:
        return False  # mass outreach, not a relationship
    if is_automated_sender_pattern(email_thread.sender):
        return False  # noreply@, notifications@, etc.
    return True
```

Only human-to-human threads go into the graph. Everything else is discarded before entity extraction.

---

### 3. Auto-Categorization — How Clusters Are Decided

When a founder connects Gmail, GeniOS needs to automatically assign contacts to categories without manual input. Here's the exact logic:

**Category detection hierarchy (in order of priority):**

1. Domain match against a curated VC/investor domain list (~500 known firms). If match → `INVESTOR`
2. Email signature parsing — if role contains "CEO/Founder/Partner/MD/GP/LP" → cross-reference with known VC firms
3. Thread topic analysis — if thread contains terms like "term sheet / valuation / due diligence / cap table / round" → likely `INVESTOR`
4. Same org domain → `TEAM`
5. Thread contains "invoice / payment / contract / proposal / vendor" → `VENDOR`
6. Thread contains "onboarding / support / feature request / pricing / trial" → `CUSTOMER`
7. All others → `OTHER`

**The critical insight here:** Categories are probabilistic, not binary. Every entity gets a `category_confidence` score. Low confidence nodes get flagged for manual review in the dashboard. You never want to silently miscategorize an investor as a vendor.

---

### 4. The Visual Graph — Exact Rendering Spec

Here's how the graph actually renders:

**Node sizing:** Node radius scales with `interaction_count`. Min radius: 12px. Max: 36px. Formula: `radius = 12 + Math.sqrt(interaction_count) * 3`. This means highly engaged contacts are visually prominent without drowning the graph.

**Node shape:** Circles for people. Rounded squares for companies. Your org node is always a larger circle in the center with a distinct ring.

**Edge thickness:** Scales with `sentiment_avg`. Positive sentiment → thicker, more visible edge. Negative → thin dashed line. No interaction in 60+ days → very faint edge.

**Edge color:** Most recent edge color reflects the last interaction sentiment. Green tint = positive, gray = neutral, red = negative or at-risk.

**Layout algorithm:** Force-directed (react-force-graph). The physics here actually matters — nodes with more interactions will be pulled closer to your org node because they have more edges. This creates a natural clustering where your most engaged relationships visually cluster around the center. This is not accidental — it's the graph telling you who your real network actually is.---

### 5. What Clicking a Node Shows — The Full Detail Panel

This is where most dashboards fail. They show you a contact card with name, email, and last interaction date. That's not a context graph — that's a CRM. The detail panel has to answer the real question: **what do I need to know right now to act on this relationship correctly?**

The panel opens as a right-side drawer (not a modal — modals break graph exploration). Here's the complete content spec:---

### 6. Clicking an Edge — What It Shows

Clicking an edge (the line between two nodes) reveals interaction-level detail, not entity-level. This is a different context entirely.

When you click an edge between your org and a person:

- A list of all email threads in that relationship, sorted by date
- Sentiment trajectory — was this relationship trending up or down over time?
- Topic clustering — what subjects kept appearing across threads?
- Response time analysis — are they fast to reply (high interest) or slow (low engagement)?
- The full text summary of the last 3 threads

When you click a company node edge (between a person and their company):

- Who else at that company is in your graph
- What's the aggregate sentiment across all contacts at that company
- Whether you have multiple open commitments with the same org

---

### 7. Graph Summary View — The Overview Intelligence Panel

Above or beside the graph, a persistent summary panel shows org-level intelligence. This is not per-contact — it's the meta-view:

```
YOUR NETWORK HEALTH
───────────────────
Total contacts: 247
Active right now: 18
Need follow-up (overdue): 6
At risk: 2
Open commitments: 4 (2 overdue)

ATTENTION REQUIRED:
→ Ananya Rajan — 67 days since last contact (was warm)
→ Series A term sheet follow-up — 15 days, no response
→ Commitment overdue: Kapil Sharma (retention data, Mar 10)
```

This panel updates nightly. It's the "daily briefing" view — not individual deep-dives.

---

### 8. Multi-Source Graph Update Architecture

This is the most architecturally interesting part. When you add HubSpot or Notion tomorrow, you're not rebuilding the graph — you're enriching existing nodes with new signal.

**The merge architecture:**

Every entity in the graph has a `canonical_id`. When a new source comes in, the system runs entity resolution before writing:

```
New source entity arrives:
  → Exact email match? → merge into existing node, add source tag
  → Name + company match (fuzzy)? → flag for review, suggest merge
  → No match? → create new node with source = "hubspot"
```

Every node then carries a `sources[]` array. A node enriched from Gmail + HubSpot + Calendar shows all three. The context bundle compiler knows to pull from all sources when building context.

**Source priority hierarchy (when signals conflict):**

1. Direct email (Gmail) — highest trust. Human wrote it.
2. Calendar (scheduled interactions) — high trust, structured
3. CRM (HubSpot) — medium trust (often manually entered, can be stale)
4. Notion/docs — low trust for relationship data (context enrichment only)
5. LinkedIn/web enrichment — lowest trust (public, not behavioral)

When sources conflict (HubSpot says "warm", Gmail says last contact was 6 months ago), Gmail wins because behavioral data beats manually-entered CRM data.---

### 9. Graph Enrichment Ceiling — How Rich Can a Node Become?

This is what separates a shallow CRM from a genuine context graph. Here's the full enrichment stack per node, layered by what's available at each stage:

**V1 enrichment (Gmail only):**
Name, email, company, role (from signature), interaction count, sentiment trend, communication style, topics, open commitments, relationship stage, last interaction summary.

**V2 enrichment (+ Calendar + HubSpot):**
Meeting history, deal stage, pipeline value, meeting frequency, response time pattern, who introduced them (referral chain).

**V3 enrichment (+ Notion + Slack + LinkedIn scraping):**
Shared documents, internal discussion about this contact, public posts/articles they've written, mutual connections, company funding stage, headcount changes.

**The compounding effect:** Each additional source doesn't just add fields — it increases confidence in existing fields. A sentiment score derived from 3 email threads has low confidence. The same sentiment score, corroborated by Calendar meeting acceptance/rejection patterns AND HubSpot deal stage movement, becomes high confidence. That confidence delta is what makes the context bundle trustworthy enough to act on.

---

### 10. The Searchability & Cross-Check Architecture

Your question about being able to cross-check tomorrow via chatbot or dashboard is the right architectural instinct. This needs to be a first-class feature, not an afterthought.

**Dashboard search:** A global search bar at the top of the graph view. Type a name → jump to that node and open the detail panel. Type a topic → filter graph to show only nodes where that topic appeared in thread history. Type "overdue commitments" → filter to show only at-risk nodes with open commitments.

**Chatbot query layer (the GeniOS context tester):** This is screen 3 in your V1 dashboard. It's not just a search — it's a natural language query interface over your own graph data:

```
"What did I last discuss with Sequoia investors?"
→ Pulls all nodes with category=INVESTOR and company=Sequoia
→ Returns: last 3 interactions, sentiment, open commitments

"Who have I not contacted in 30 days?"
→ Graph query: stage=DORMANT or COLD, last_interaction < 30d
→ Returns: prioritized list with recommended actions

"What commitments do I have outstanding?"
→ Query: open_commitments > 0, ordered by due_date
→ Returns: ranked list with context on each
```

The chatbot is just a natural language wrapper over deterministic graph queries for V1. No hallucination risk because the answers come from your structured PostgreSQL graph, not from an LLM generating from memory. The LLM only formats the response — the data comes from the graph directly.

---

### The Engineering Reality Check

Here's what will actually be hard that most tutorials don't tell you:

**Entity resolution will break constantly.** Same person, different email signatures ("Sarah Chen", "S. Chen", "Sarah C."). You need a human review queue in your dashboard for low-confidence merges. Don't automate this blindly or you'll silently merge the wrong people.

**Sentiment scoring on short emails is unreliable.** A 3-word reply ("Sounds good, thanks") gets confused with a dismissive brush-off. Train your extraction prompt specifically on short email patterns. Add "email length" as a calibration signal — weight short replies differently.

**The graph will be slow at first.** PostgreSQL with graph-like queries on 6 months of email history for 300+ contacts will get slow fast without the right indexes. Index on `(org_id, last_interaction)`, `(org_id, entity_type, stage)`, and `(org_id, from_entity_id, to_entity_id)` from day one.

**V1's biggest risk is not technical — it's the cold start problem.** Founders with < 3 months of Gmail history will have an empty graph. You need a minimum of 50 meaningful interactions before the context bundle is interesting enough to impress anyone. Screen pilot customers for this before onboarding them.

<aside>
➡️

This is a full technical architecture deep-dive. Let me go section by section — engineering-level, no fluff.

---

## 1. How Graph Data Gets Updated With New Data and New Sources

There are three distinct update triggers, not one:

**Trigger A — Scheduled ingestion (nightly batch)**
Every night at 2am, a Celery job runs per org. It pulls the last 24h of new emails, calendar events, and CRM updates. Runs entity extraction, sentiment scoring, and stage recalculation. Writes delta updates to the graph — not full rewrites. Only nodes that changed get touched.

**Trigger B — Real-time webhook (within seconds)**
When HubSpot deal stage changes, or a Slack message is sent, a webhook fires immediately. This hits a lightweight ingestion endpoint that updates only the affected node. No full graph rebuild. This is how "last contact: 2h ago" stays accurate without waiting for the nightly job.

**Trigger C — Source addition (when founder connects a new tool)**
This is the most expensive operation. When HubSpot is connected after Gmail was already running, GeniOS runs a full historical backfill for that source, then entity resolution against existing nodes, then confidence score recalculation for every node that got enriched. This runs as a background job with a progress bar — never blocking the UI.

```
New source connected
→ OAuth granted
→ Historical backfill job queued (background)
→ For each entity in new source:
    → Entity resolution against existing graph
    → Exact email match? → merge, add source tag, boost confidence
    → Fuzzy name+company? → flag for review, tentative merge
    → No match? → create new node
→ Recalculate confidence score for all affected nodes
→ Recalculate relationship stages where new signal changes them
→ Regenerate context bundles for nodes that changed materially
→ Notify dashboard: "47 nodes enriched from HubSpot"
```

---

## 2. Data Decay, Improvement, Update, Compression — The Full Strategy

This is where most graph systems silently break. Data that never decays becomes noise. Data that decays too fast loses history. GeniOS uses five mechanisms:

**Time-decay scoring (not deletion)**
Every interaction edge has a `recency_weight` that decays on a half-life curve. An email from yesterday has weight 1.0. Same email from 6 months ago has weight ~0.15. The data is never deleted — it just has lower query weight. When building a context bundle, the compiler pulls interactions weighted by recency. Old interactions don't disappear — they just matter less unless they contain a commitment or a key topic marker.

```python
def recency_weight(days_ago):
    # Half-life of 30 days
    return 0.5 ** (days_ago / 30)

# Email from 3 days ago: weight = 0.93
# Email from 30 days ago: weight = 0.50
# Email from 90 days ago: weight = 0.12
# Commitment from 90 days ago: weight = 1.0 (override — commitments never decay)
```

**Relationship stage recalculation (nightly)**
Stage is not stored permanently — it's computed fresh every night from interaction history. ACTIVE → WARM → DORMANT → COLD is a function of recency + sentiment trend, recalculated as a cron job. No manual updates needed. If someone emails you today after 6 months of silence, they jump from COLD to ACTIVE automatically at next recalculation.

**Structured summarization (compression for deep relationships)**
A contact you've emailed 200+ times doesn't need 200 interaction records queried every time an agent asks for context. Once a relationship crosses 50 interactions, GeniOS runs a periodic summarization job:

```
LLM prompt: "Given these 50 interactions between [founder] and [contact],
write a 3-sentence relationship arc summary that captures:
- Overall trajectory (improving/declining/stable)
- Key recurring topics
- Most important commitments ever made
- Communication style inferred"
```

The summary becomes the working context. Raw interactions are archived but still queryable. This keeps context bundle generation under 200ms even for deep relationships.

**Active vs archive tiers**
Contacts not interacted with for 6+ months move to an archive partition. They still exist in the graph — you can search them, view them, their history is intact. But they don't get included in nightly stage calculations or context bundle pre-generation. They're reactivated instantly when a new interaction arrives.

**Confidence decay**
Confidence score decays when a source goes stale. If HubSpot hasn't synced in 48h (API issue), the confidence contribution from HubSpot decreases. The system marks those fields as "potentially stale" in the context bundle. Agents receive this signal and can caveat their outputs accordingly.

---

## 3. How GeniOS Context Graph Actually Updates Context Data

There are two layers — the raw graph update and the context bundle regeneration. They're separate jobs.

**Layer 1 — Raw graph update** happens on every ingestion event. Node fields updated, edge weights recalculated, stage computed. This is deterministic — no LLM involved.

**Layer 2 — Context bundle regeneration** happens when the raw graph changes materially for a node. "Materially" means: stage changed, new commitment detected, sentiment trend reversed, or it's been 24h since last bundle generation. The context bundle is an LLM-generated paragraph — it's pre-computed and cached, not generated on-demand at agent query time. This is the key latency insight: when an agent calls `genios.context()`, it gets a pre-built cached bundle in ~40ms, not a live LLM call.

```
Raw graph updated for node X
→ Check: did anything material change?
  → Stage change? YES → queue context bundle regeneration
  → New commitment detected? YES → queue
  → Sentiment flipped? YES → queue
  → Just recency update? NO → skip, use cached bundle
→ Bundle regeneration job runs (background, ~2s)
→ New bundle written to Redis cache (TTL: 24h)
→ Next agent call gets fresh bundle instantly
```

---

## 4. How an Agent Actually Fetches Data From GeniOS

Three integration patterns depending on the developer:

**Pattern A — Direct REST call (most common)**

```python
import requests

def get_context(entity_name, situation):
    response = requests.post(
        "https://api.genios.ai/v1/context",
        headers={"Authorization": f"Bearer {GENIOS_API_KEY}"},
        json={
            "org_id": "org_abc123",
            "entity_name": entity_name,
            "situation": situation  # optional — improves bundle relevance
        }
    )
    return response.json()

# Before any agent action involving a person:
context = get_context("Sarah Chen", "investor follow-up")
# Inject context.context_for_agent into the LLM prompt
```

**Pattern B — LangGraph entry node**

```python
from langgraph.graph import StateGraph

def fetch_context_node(state):
    # Runs FIRST before any other node
    entity = extract_entity_from_task(state["task"])
    ctx = genios_client.context(entity)
    return {**state, "org_context": ctx["context_for_agent"]}

graph = StateGraph(AgentState)
graph.add_node("fetch_context", fetch_context_node)  # always first
graph.add_node("draft_email", draft_email_node)
graph.add_node("send_email", send_email_node)
graph.add_edge("fetch_context", "draft_email")
```

**Pattern C — n8n no-code (for non-technical founders)**
HTTP Request node → POST to `/v1/context` → output goes into the prompt variable of the next AI node. Takes 10 minutes to set up, no code.

---

## 5. What Data Format Goes Into the Agent as Context

The API returns two things: a structured JSON object AND a pre-built `context_for_agent` paragraph. The paragraph is what gets injected into the prompt. The JSON is for developers who want to build custom logic on top.

```json
{
  "entity": {
    "name": "Sarah Chen",
    "company": "Sequoia Capital",
    "role": "Partner",
    "relationship_stage": "WARM",
    "stage_since_days": 12,
    "interaction_count": 14,
    "sentiment_trend": "positive",
    "sentiment_score": 0.74,
    "communication_style": "concise, data-forward, responds within 4h",
    "topics_of_interest": ["retention", "GTM", "India market"],
    "open_commitments": [
      {
        "text": "Send retention cohort data",
        "due": "2026-03-15",
        "source": "calendar",
        "detected_from": "Feb 18 call"
      }
    ],
    "what_works": "Short emails with specific metrics, no fluff",
    "what_to_avoid": "Long narrative emails, generic updates",
    "recommended_action": "Send brief update with retention numbers this week",
    "disclosure_rules": {
      "safe": ["revenue range", "user count", "retention rate"],
      "avoid": ["exact ARR", "cap table details"]
    }
  },
  "recent_interactions": [...],
  "sources_used": ["gmail", "calendar"],
  "context_for_agent": "Sarah Chen is a Partner at Sequoia Capital. Your relationship is WARM — last contact 12 days ago when you sent a traction update and she responded positively within 4 hours. On your Feb 18 call she specifically requested retention cohort data and you committed to send it by March 15 — this is overdue. She prefers short, data-forward emails. Do not share exact ARR — revenue range is safe. Recommended action: send a brief email with the retention numbers today, reference the Feb 18 commitment directly.",
  "confidence": 0.84,
  "confidence_breakdown": {
    "gmail": 0.91,
    "calendar": 0.88,
    "overall": 0.84
  },
  "generated_at": "2026-03-13T10:22:00Z",
  "cache_age_seconds": 1847
}
```

The `context_for_agent` is literally prepended to the agent's system prompt before every action involving this person. The agent never operates blind.

---

## 6. Key Components of Each Graph — How They Work, Update, Forget, Hold

**Relationship Graph (PostgreSQL V1 → Neo4j V2)**

Stores: People nodes, Company nodes, Interaction edges, Commitment edges.

How it updates: Every new email ingested creates or updates an interaction edge. Sentiment score is recalculated as a rolling weighted average of the last 10 interactions. Stage is a computed field, recalculated nightly.

How it forgets: It doesn't delete — it decays. Interaction edges get lower `recency_weight` over time. Nodes with no interactions for 6 months move to archive partition. Commitments never decay — they stay at full weight until explicitly marked resolved.

How it holds: Every interaction is immutable once written. You can always go back and see what was discussed on a specific date. The graph is append-only for interaction edges.

What it answers: "Who is this person? What is our history? What was the last thing we discussed? What tone works? What did we promise?"

---

**Authority Graph (PostgreSQL — V2)**

Stores: Role nodes, Action type nodes, Permission edges (role → can do → action type up to threshold).

How it updates: Manual setup by admin at onboarding. Updates when roles change (person leaves, new hire). Does not update automatically from behavioral data — authority is set by humans, not inferred.

How it holds: Immutable by default. Every permission change is an append — old permissions are archived, not deleted. Full audit trail of who could do what and when.

What it answers: "Can this agent take this action? Who needs to approve it? What is the escalation chain?"

---

**State Graph (PostgreSQL + Redis)**

Stores: In-flight agent actions, active commitments, live budget states, open loops.

How it updates: Real-time. Every agent action writes to state immediately. Commitment fulfilled → state updated within seconds via webhook.

How it forgets: Completed state entries are moved to a `completed_actions` archive after 30 days. Redis cache TTL on live state: 5 minutes (refreshed on access). PostgreSQL holds the permanent record.

How it holds: Redis for sub-second live access. PostgreSQL for durable history. The two are kept in sync — Redis is purely a read cache.

What it answers: "What is happening right now? What commitments are open? What did agents do in the last hour?"

---

**Precedent Graph (Neo4j + Pinecone — V3)**

Stores: Past decisions and their outcomes. "In situation X, action Y was taken, outcome was Z."

How it updates: Every completed agent action that had a human approval or rejection gets written as a precedent node. Outcome is recorded 7 days later based on downstream signals.

How it improves: More precedents = better pattern matching. After 200+ precedents, the system can predict with reasonable confidence what a founder would approve for novel situations.

How it forgets: Precedents older than 12 months get a decay factor unless they were high-stakes decisions. Low-outcome-quality precedents (where the outcome was negative) are weighted down but never deleted — they're the failure cases the system learns from.

What it answers: "Have we been in a situation like this before? What did we do? What happened?"

---

## 7. Context Confidence — What It Is, Why It's Needed, How It's Decided

Confidence answers one question: **how much should the agent trust this context bundle?**

Without confidence, the agent has no way to know if it's working with rich, verified, multi-source data or a thin guess from two emails. A low-confidence context should make the agent more cautious — ask for clarification, escalate, add caveats.

**How it's calculated:**

```python
def calculate_confidence(node):
    score = 0.0
    weights = {
        'gmail':    {'weight': 0.35, 'decay_halflife': 30},
        'calendar': {'weight': 0.25, 'decay_halflife': 14},
        'hubspot':  {'weight': 0.20, 'decay_halflife': 60},
        'slack':    {'weight': 0.15, 'decay_halflife': 7},
        'notion':   {'weight': 0.05, 'decay_halflife': 90},
    }

    for source, cfg in weights.items():
        if source in node.sources:
            days_since_sync = get_days_since_sync(source)
            recency = 0.5 ** (days_since_sync / cfg['decay_halflife'])
            score += cfg['weight'] * recency

    # Boost for interaction volume
    if node.interaction_count > 20: score *= 1.1
    if node.interaction_count < 3:  score *= 0.6

    # Penalty for conflicting signals between sources
    if has_source_conflict(node): score *= 0.85

    return min(score, 1.0)
```

Confidence below 0.5 → context bundle is flagged as "low confidence." The `context_for_agent` paragraph includes a caveat: "Note: limited interaction history — treat recommendations with caution." Agents receiving low-confidence bundles are configured to escalate rather than act autonomously.

---

## 8. What Each Tool Shows and How It Maps to the Graph

```
GMAIL
→ Relationship Graph: interaction edges, sentiment, topics,
  communication style, commitments
→ State Graph: open loops from threads (unanswered questions,
  promised follow-ups)
→ Precedent Graph: past email decisions and outcomes

CALENDAR
→ Relationship Graph: meeting edges (stronger signal than email),
  acceptance/rejection pattern, meeting frequency
→ State Graph: upcoming commitments, scheduled follow-ups
→ Confidence boost: calendar acceptance = confirmed active interest

HUBSPOT
→ Relationship Graph: role, company, phone, pipeline enrichment
→ State Graph: deal stage, days in stage, pipeline value
→ Authority Graph: deal approval thresholds per role
→ Confidence: medium — manually entered, can be stale

SLACK
→ Relationship Graph: internal discussion about external contacts
  (who internally knows them, what was said)
→ State Graph: live team actions, in-progress work
→ Special: reveals "real" relationships that don't show in email
  (daily Slack = active, even if email = cold)

NOTION / DOCS
→ Relationship Graph: shared documents as edges between people
  (two people co-authoring a doc = relationship signal)
→ State Graph: meeting notes with action items
→ Precedent Graph: past decisions documented in pages
→ Confidence: low — documents context, not behavioral signal
```

---

## 9. Smart Insights Per Graph Category — What Gets Shown and How

**From Relationship Graph:**

- "15 contacts in your investor cluster received no update this month" — graph query: category=investor, last_outbound > 30 days
- "Kavita Nair's reply window closing in 4 days" — stage=warm, days_since_last_contact approaching 15d threshold
- "4 warm contacts going cold this week" — stage=warm, projected to cross 30d threshold within 7 days
- "Mukesh Arora introduced 3 investors — no thank-you sent" — referral edges with no outbound thread to source node post-introduction

**From State Graph:**

- "9 open commitments — 3 overdue" — open_commitments where due_date < today
- "Stripe RBI docs blocking INR billing" — commitment tagged as blocker with revenue_impact flag
- "Acme expansion deal stalled 11 days in proposal stage" — HubSpot stage + time_in_stage > threshold

**From Authority Graph (V2):**

- "Agent attempted action outside approved threshold — escalated" — policy violation caught before execution
- "Your approval rate for agent actions this week: 94%" — learning signal for threshold calibration

**From Precedent Graph (V3):**

- "Similar investor follow-up situation in October — founder approved, deal progressed" — precedent match surfacing past outcome
- "Last 3 times a customer went 21 days silent post-onboarding, they churned" — pattern from precedent graph fed into churn risk insight

The insight engine runs a nightly job that queries each graph with ~40 pre-built signal detection queries. Each query has a threshold and a priority tier (P1 = act within 24h, P2 = act this week, P3 = FYI). Results are ranked by priority and displayed as the categorised insight panel. No LLM involved in detection — all deterministic graph queries. LLM only writes the human-readable insight sentence on top of the structured result. This is why insights are reliable and don't hallucinate — the data is real, only the prose is generated.

</aside>

![image.png](attachment:4b1dd1df-f60f-4563-bf38-bd8702897c8d:image.png)

![image.png](attachment:f9c098fe-1176-4923-8e03-40a5b8a8a44b:image.png)

![image.png](attachment:e81d0422-4405-4aef-bb3e-37c271078fe7:image.png)