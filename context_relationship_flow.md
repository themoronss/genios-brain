# Context & Relationship Building Architectue

This document outlines the core architecture of the GeniOS context engine. It details the precise process from raw Gmail data ingestion all the way to context bundle generation for LLM agents, focusing on data extraction, relationship calculation, graph storage, and safety guardrails.

---

## 1. Gmail Connection and Sync Flow (`app/tasks/gmail_sync.py`)

### Connection & Filtering
- Authentication is handled via OAuth tokens stored in the `oauth_tokens` table (supporting multi-account sync per organization).
- The sync engine fetches a targeted limit (e.g., 100) of **valid, human-to-human** emails.
- **Pre-filtering Rule**: Ignores promotional, social, and automated emails (e.g., noreply, newsletters) directly via the Gmail query before downloading payloads.
- **Internal Filter**: Skips emails sent between users on the same organizational domain to prevent polluting the external relationship graph.

### Thread Aggregation
To give the extraction LLM proper context, the sync process groups downloaded messages by their `threadId`. 
Before analyzing a message, it builds a **Thread Context**—extracting the bodies of the 3 previously processed messages in the thread, ensuring commitments buried deeper in conversations aren't missed.

---

## 2. LLM Extraction & Ingestion (`app/ingestion/entity_extractor.py`)

Every synced email is processed through the LLM pipeline to transform unstructured text into structured graph intelligence.

### Models Used
- **Primary**: `llama-3.3-70b-versatile` (via Groq) for high accuracy and speed.
- **Fallback**: `gemini-2.5-flash` kicks in seamlessly if Groq hits 429 rate limits or network issues.

### The Extraction Prompt
The LLM is prompted to output strictly validated JSON containing:
1. **Summary**: A one-sentence distillation of the discussion.
2. **Sentiment**: Float `-1.0` (very negative) to `1.0` (very positive).
3. **Intent**: Classified as follow_up, request, commitment, intro, etc.
4. **Interaction Type**: email_reply, email_one_way, commitment.
5. **Commitments Array**:
    - **text**: What was promised.
    - **owner**: Who made the promise (us or them).
    - **due_signal**: Natural language timeframe ("next week", "EOD").
    - **confidence score**: Used to split commitments into "FIRM" (>0.7) and "SOFT" (<0.7).
6. **Topics**: 2-5 key business topics discussed.
7. **Engagement Level**: High, medium, low.
8. **Contact Role (Labels)**: Assigned based on conversation context (`investor`, `customer`, `vendor`, `partner`, `candidate`, `team`, `lead`, `advisor`, `media`, or `other`).

---

## 3. Graph Building & Saving (`app/ingestion/graph_builder.py`)

Once intelligence is extracted, it is ingested into the PostgreSQL graph (Contacts, Interactions, Commitments).

### Contact Upsert & Deduplication
- **Fuzzy Deduplication**: To prevent creating "split" nodes (e.g. `priya@sequoia.com` vs `priya.sharma@sequoia.com`), the engine verifies if a contact with the same FIRST NAME and SAME DOMAIN already exists before creating a new node.
- **Labeling Application**: The `contact_role` extracted by the LLM is assigned to the `entity_type` parameter of the node if it's currently empty, applying dynamic categorization without human tagging.

### Edges (Interactions)
- A **Primary Interaction** edge is established between the Organization and Contact, capturing the extracted JSON.
- **CC Loop**: The backend iterates over all CC'd participants. It verifies they are not internal or automated, creates a contact node for them, and assigns them a distinct interaction edge connected to the same source email but labelled directionally as `cc`.

### Due Date Parsing
Commitments trigger a function `parse_due_signal()` which converts raw natural language due signals (e.g., "by March 20", "next Friday", "EOM") into strict ISO `datetime` stamps for lifecycle tracking. The commitments are saved as either `OPEN` or `SOFT` in the database.

---

## 4. Relationship Health Scoring (`app/graph/relationship_calculator.py`)

Relationships are recalculated dynamically (or on a nightly cron job) to keep data fresh. 

**Relationship Stage Logic**:
- Calculates an **EWMA Sentiment Score** (Exponential Weighted Moving Average where recent interactions carry 30% weight, heavily influencing the score while smoothing spikes).
- Calculates the difference between sentiments in recent vs older interactions to output a **Sentiment Trend** (`IMPROVING`, `STABLE`, `DECLINING`).
- **ACTIVE**: Interaction < 7 days old + positive EWMA sentiment.
- **WARM**: Interaction < 30 days old.
- **DORMANT**: Interaction < 60 days old.
- **COLD**: Interaction > 60 days old.
- **AT_RISK**: Overrides all rules if the EWMA Sentiment is < -0.3.

**Confidence Core**: Measures how much the agent should trust the data based on interaction volume and a 30-day recency halflife decay.

---

## 5. Context Compilation & Guardrails (`app/context/bundle_builder.py`)

When an external LLM agent (like via workflow automation) requests context for drafting or processing, the engine calls `build_context_bundle()`.

**Fuzzy Lookup**: The engine uses `rapidfuzz` to look up the requested user by name or email safely, even if misspelled in the prompt.

**Context Generation**: Generates a tightly packed, readable string (`context_for_agent`) meant to be prepended directly to the agent's system prompt. It contains their identity, aggregate sentiment, exact topics of interest, and crucially, an array of all `OPEN` or `OVERDUE` specific commitments.

### Security Guardrails & Escalations
The API does not just return text; it enforces deterministic behavioural guardrails before an AI workflow responds.
It generates an `action_recommendation` token:
- **`block`**: If the relationship is `AT_RISK` or sentiment is wildly negative. AI should NOT auto-contact.
- **`escalate`**: If the `entity_type` is *Investor* / *Board* AND the topic contains sensitive keywords (like `acquisition`, `term sheet`, `due diligence`). Drafts must be sent to human review.
- **`warn`**: If there are `OVERDUE` commitments detected with this user or if the relationship is `DORMANT` and declining. Agents are warned to adjust their tone.
- **`proceed`**: Nominal status; clear to execute workflows auto-responsively.

### Prompt Injection Shield (`sanitize_email_body`)
Before emails go to the engine's extraction LLM, the `entity_extractor` runs regex patterns searching for injection terminology (`ignore all previous instructions`, `<|system|>`, `prompt injection`). It strips these and replaces them with `[REDACTED]` so the extraction runs safely without hallucinating.

---
This flow ensures that any downstream workflow has perfect, multi-dimensional relational context on *who* they are talking to, *what* is owed, and *how* to speak to them, drastically reducing hallucinations.
