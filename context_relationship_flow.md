# Context & Relationship Building Architecture - Complete Technical Reference

This document outlines the complete architecture of the GeniOS context engine with code-level accuracy. It details every step from Gmail OAuth connection through to relationship graph generation and context bundle creation for LLM agents.

---

## 1. Gmail OAuth Connection & Token Management

### OAuth Token Storage
- Tokens stored in `oauth_tokens` table with fields:
  - `access_token` (encrypted)
  - `refresh_token` (encrypted)
  - `account_email` (specific Gmail account, supports multiple accounts per org)
  - `org_id` (organization UUID)
  - Sync progress fields: `sync_status`, `sync_total`, `sync_processed`, `sync_error`, `sync_started_at`, `last_synced_at`

### Multi-Account Support (Update 4)
- Each organization can have multiple connected Gmail accounts
- `sync.py` endpoints support:
  - `POST /api/org/{org_id}/sync` - Syncs ALL connected accounts
  - `POST /api/org/{org_id}/gmail/accounts/{email}/sync` - Syncs specific account
  - `GET /api/org/{org_id}/gmail/accounts` - Lists all connected accounts
  - `DELETE /api/org/{org_id}/gmail/accounts/{email}` - Disconnects specific account

### Sync Status Progression
1. `idle` - No sync running
2. `running` - Sync in progress (set synchronously before background task starts)
3. `completed` - Sync finished successfully
4. `error` - Sync failed with error message

---

## 2. Email Fetching & Filtering (`app/tasks/gmail_sync.py`)

### Step 2.1: Collect Valid Email IDs (Incremental Filter Loop)
**Function**: `collect_valid_email_ids(service, user_email, target=100)`

Process:
1. Fetches emails incrementally in pages of 50 using Gmail API with q-filter:
   ```
   (in:inbox OR in:sent) -label:promotions -label:social
   ```
   This removes promotions/social labels **before** any full download (Gmail-side filtering only).

2. For each ID, fetches ONLY headers (lightweight) via `fetch_message_headers()`

3. **Validation check** (MINIMAL):
   - Extracts From/To headers
   - Determines which side is the contact (From if outbound, To if inbound)
   - **ONLY checks if contact_email is NOT empty**
   - ⚠️ **NO automated or internal email filtering happens here in main flow!**

4. Continues until `target` (default 100) valid emails collected or Gmail runs dry

5. Safety: Max 40 pages (~2000 candidates) before stopping

**Note**: The `is_automated_email()` and `is_internal_email()` functions exist in code but are **NOT used** in this main collection flow. They are only applied later to **CC participants** (see Step 6.3).

### Step 2.2: Deduplicate Against Database
- Checks `interactions` table for existing `gmail_message_id`
- Only new emails passed to LLM extraction

### Step 2.3: Fetch Full Messages & Parse
For each new email:
1. Downloads full message via `fetch_full_message(service, msg_id)`
2. Extracts headers: From, To, Cc, Subject, Date via `parse_headers()`
3. Extracts email body via `extract_email_body()` (text/plain priority, HTML fallback)
4. Determines direction:
   - If `from_email == user_email` → `direction = "outbound"`, contact is To
   - Else → `direction = "inbound"`, contact is From
5. Groups messages by `threadId` for context building

---

## 3. Thread Context Building (`build_thread_context()`)

**Purpose**: Give LLM awareness of full conversation to catch commitments buried in earlier messages.

**Implementation**:
- Takes last 3 processed messages in thread (chronological order)
- For each message, formats:
  ```
  [Message N - {THEM|YOU} on {date}]:
  {body snippet (max 800 chars)}
  ```
- Joined with `\n\n` separator
- Total context max ~6000 chars across 3 messages

**Threading Flow**:
1. All messages grouped by `threadId` and sorted by date (ascending)
2. As each message is processed, added to `thread_processed[thread_id]` list
3. Next message in same thread gets full context of previous messages
4. Context reused for CC participants (same email, same extraction intelligence)

---

## 4. Prompt Injection Sanitization (`sanitize_email_body()`)

**Security**: Before passing to LLM, strips injection patterns and replaces with `[REDACTED]`

**Patterns Blocked** (case-insensitive regex):
- `(?i)system\s*:` → SYSTEM:
- `(?i)ignore\s+(previous|above|all)` → Ignore previous instructions
- `(?i)disregard\s+(previous|above|all)` → Disregard
- `(?i)forget\s+(previous|above|all)` → Forget
- `(?i)you\s+are\s+now` → You are now a different AI
- `(?i)act\s+as\s+(if|a|an)` → Act as if/a/an
- `<\|system\|>` → LLaMA system tag
- `<\|im_start\|>`, `<\|im_end\|>` → ChatML tags
- `\[INST\]`, `\[/INST\]` → Mistral tags
- `(?i)prompt\s*injection` → Prompt injection
- `(?i)jailbreak` → Jailbreak
- `(?i)new\s+instructions?` → New instructions

---

## 5. LLM Extraction & Intelligence (`app/ingestion/entity_extractor.py`)

### Step 5.1: Models & Fallback Strategy
**Primary**: `llama-3.3-70b-versatile` via Groq
- Temperature: 0.1 (deterministic)
- Max tokens: 700
- Rate limit: 30 requests/minute (2s delay between requests)

**Fallback Triggers**:
1. If Groq returns 429 (rate limit) → Retry up to 3 times with exponential backoff (2s, 4s, 6s)
2. If max retries exceeded → Switch to Gemini `gemini-2.5-flash`
3. If Gemini not configured → Use hardcoded fallback with sentiment=0.0

### Step 5.2: Extraction Prompt & JSON Output
**Input to LLM**:
```
Subject: {email_subject}
From: {sender_name}
Body: {safe_body (first 3000 chars, sanitized)}

[Optional thread context if previous messages exist]
```

**Output JSON Structure**:
```json
{
  "summary": "one sentence max 150 chars",
  "sentiment": 0.0 to 1.0 (float),
  "intent": "follow_up|request|commitment|introduction|negotiation|update|question|other",
  "interaction_type": "email_reply|email_one_way|commitment|other",
  "commitments": [
    {
      "text": "what was promised",
      "owner": "them|us",
      "due_signal": "natural language date or null",
      "confidence": 0.0 to 1.0
    }
  ],
  "topics": ["topic1", "topic2", ...max 5],
  "engagement_level": "high|medium|low",
  "contact_role": "investor|customer|vendor|partner|candidate|team|lead|advisor|media|other",
  "is_human_email": true|false
}
```

### Step 5.3: Commitment Processing
**Confidence Scoring**:
- Firm commitments: `confidence >= 0.7` (clear explicit promises)
- Soft commitments: `confidence < 0.7` (maybe, try, should, sometime)

**Processing in code**:
```python
for commitment in all_commitments[:15]:  # Max 15 per email
    conf = float(c.get("confidence", 0.5))
    cleaned = {
        "text": str(c.get("text", ""))[:200],
        "owner": str(c.get("owner", "them")),
        "due_signal": c.get("due_signal"),
        "confidence": round(max(0.0, min(1.0, conf)), 2),
        "is_soft": conf < 0.7  # Tag for downstream processing
    }
```

### Step 5.4: Contact Role Validation
**Valid Roles**:
```python
VALID_CONTACT_ROLES = {
    "investor", "customer", "vendor", "partner", "candidate",
    "team", "lead", "advisor", "media", "other"
}
```
Raw LLM output normalized to lowercase and validated. Invalid roles → `"other"`

### Step 5.5: Fallback Behavior
If LLM fails (all retries exhausted):
```python
return {
    "summary": body[:200] OR subject[:200] OR "No content available",
    "sentiment": 0.0,
    "intent": "other",
    "interaction_type": "email_one_way" if not is_reply else "email_reply",
    "engagement_level": "low",
    "commitments": [],
    "topics": [],
    "contact_role": "other",
    "is_human_email": True  # Assume human on fallback
}
```

---

## 6. Graph Building & Data Persistence (`app/ingestion/graph_builder.py`)

### Step 6.1: Contact Upsert with Fuzzy Deduplication

**Function**: `upsert_contact(db, org_id, email, name, entity_type=None)`

**Dedup Process** (`find_existing_contact_by_domain_and_name()`):
1. Extract domain from email (e.g., `priya@sequoia.com` → `sequoia.com`)
2. Skip if domain is personal: `gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `icloud.com`, `protonmail.com`, `aol.com`
3. Query contacts with same `company_domain` and `org_id`:
   ```sql
   SELECT id, name, email FROM contacts
   WHERE org_id = :org_id AND company_domain = :domain
   LIMIT 50
   ```
4. Extract first name from new contact: `"Priya Sharma"` → `"priya"`
5. Compare against existing contacts at same domain
6. If first name matches AND same domain → **MERGE**: return existing `contact_id`
7. Example: `priya@sequoia.com` + `priya.sharma@sequoia.com` both map to same node

**Contact Creation**:
If no match found:
```sql
INSERT INTO contacts (
    id, org_id, email, name, company, company_domain, entity_type
)
VALUES (:id, :org_id, :email, :name, :company, :domain, :entity_type)
ON CONFLICT (org_id, email)
DO UPDATE SET
    name = EXCLUDED.name,
    company = COALESCE(EXCLUDED.company, contacts.company),
    company_domain = COALESCE(EXCLUDED.company_domain, contacts.company_domain),
    entity_type = COALESCE(EXCLUDED.entity_type, contacts.entity_type)
```

**COALESCE Logic**: If syncing multiple times, existing `entity_type` is preserved. New sync won't overwrite with NULL.

**Company Extraction** (`extract_company_from_email()`):
- Skips personal domains
- Extracts domain name: `priya@sequoiacap.com` → `Sequoiacap`
- Converts: `"my-company"` → `"My Company"` (capitalize each word)

### Step 6.2: Interaction Creation

**Function**: `create_interaction(db, org_id, contact_id, gmail_id, subject, summary, date, direction, ...)`

**Interaction Weight Calculation** (`_calculate_interaction_weight()`):
```python
type_weights = {
    "email_reply": 0.7,
    "email_one_way": 0.1,
    "commitment": 0.95,
    "meeting": 0.9,
    "other": 0.3
}

base_weight = type_weights[interaction_type]
engagement_mult = {"high": 1.2, "medium": 1.0, "low": 0.6}[engagement_level]
direction_mult = 1.1 if direction == "INBOUND" else 0.9
sentiment_mult = 0.4 if (interaction_type == "commitment" and sentiment < -0.3) else 1.0

weight_score = base_weight * engagement_mult * direction_mult * sentiment_mult
weight_score = round(max(0.0, min(1.0, weight_score)), 3)  # Clamp to 0-1
```

**Stored in `interactions` table**:
```sql
INSERT INTO interactions (
    id, org_id, contact_id, gmail_message_id, direction, subject, summary,
    interaction_at, sentiment, intent, interaction_type, reply_time_hours,
    weight_score, topics, account_email
)
```

Fields:
- `direction`: `"inbound"`, `"outbound"`, or `"cc"` (for CC participants)
- `weight_score`: 0.0-1.0 (used to rank interactions by importance)
- `topics`: Array of extracted topics
- `account_email`: Gmail account that received/sent the email

### Step 6.3: CC Participant Handling (Update 3)

**Loop**: For each person in CC list:
1. Extract: `cc_email`, `cc_name`
2. Skip own email: `cc_email != user_email`
3. Skip if automated: `is_automated_email(cc_email, cc_name)`
4. Skip if internal: `is_internal_email(cc_email, user_email)`
5. Create contact: `upsert_contact(db, org_id, cc_email, cc_name, entity_type=None)`
   - No LLM role extraction for CC (doesn't affect tag)
6. Create separate interaction:
   ```python
   create_interaction(
       ...,
       direction="cc",  # Distinct from inbound/outbound
       sentiment=intelligence["sentiment"],  # Reuse from primary
       intent=intelligence["intent"],
       commitments=[],  # CC doesn't inherit commitments
       topics=intelligence.get("topics", []),  # But shares topics
       ...
   )
   ```
7. Logged: `🔗 CC edge: {cc_email} ↔ gmail:{msg_id[:8]}...`

**Result**: CC participants become graph nodes with "cc" directed edges to the same email.

### Step 6.4: Commitment Storage with Due Date Parsing

**Function**: `_store_commitments(db, org_id, contact_id, interaction_id, commitments, direction)`

**Due Date Parsing** (`parse_due_signal(due_signal, reference_date=None)`):

Handles natural language patterns:

1. **Absolute Month+Day**: `"March 20"`, `"20 March"`, `"20th of March"`
   - Regex: `march\s+(\d{1,2})(?:st|nd|rd|th)?` or `(\d{1,2})(?:st|nd|rd|th)?\s+march`
   - Creates datetime for that date in current year
   - If date already passed, moves to next year

2. **Relative Weekdays**: `"Friday"`, `"next Friday"`
   - Weekday map: Monday=0, Tuesday=1, ..., Sunday=6
   - `days_ahead = (target_weekday - current_weekday) % 7`
   - If `days_ahead == 0`, set to 7 (means next occurrence)
   - If "next" in signal, add 7 days

3. **Relative Phrases**:
   - `"today"` → today 23:59
   - `"tomorrow"` → +1 day 23:59
   - `"EOD"` / `"end of day"` → today 23:59
   - `"EOW"` / `"this week"` → Friday 23:59
   - `"next week"` → Friday next week 23:59
   - `"EOM"` / `"end of month"` → Last day of current month 23:59
   - `"next month"` → Last day of next month 23:59

4. **Relative Numbers**:
   - `"in N days"` or `"N days"` → ref_date + N days
   - `"in N hours"` → ref_date + N hours
   - `"in N weeks"` → ref_date + N weeks
   - `"within N days"` → ref_date + N days

5. **If unparseable**: Returns `None`

**Commitment Status Assignment**:
```python
is_soft = commitment.get("is_soft", False)
status = "SOFT" if is_soft else "OPEN"
```

**Stored in `commitments` table**:
```sql
INSERT INTO commitments (
    id, org_id, contact_id, commit_text, owner, due_date,
    status, source_interaction_id, created_at
)
VALUES (
    :id, :org_id, :contact_id, :commit_text, :owner, :due_date,
    :status, :source_interaction_id, NOW()
)
ON CONFLICT DO NOTHING
```

**Status Lifecycle**:
- `OPEN`: Firm commitment (confidence >= 0.7), due_date may be NULL
- `SOFT`: Tentative commitment (confidence < 0.7), should be confirmed
- `OVERDUE`: Set by relationship calculator when `due_date < NOW()`

---

## 7. Relationship Health Scoring (`app/graph/relationship_calculator.py`)

### Step 7.1: Called After Every Sync
After all emails processed, `recalculate_all_relationships(db, org_id)` runs automatically.

### Step 7.2: EWMA Sentiment Calculation

**Algorithm**: Exponential Weighted Moving Average

```python
EWMA_ALPHA = 0.3  # Recent interactions: 30% weight, history: 70% weight

ewma = 0.0
for interaction in sorted_interactions (oldest to newest):
    sentiment = interaction.get("sentiment", 0.0)
    ewma = EWMA_ALPHA * sentiment + (1 - EWMA_ALPHA) * ewma
```

**Effect**: Recent emails heavily influence score, but smooth out spikes. `ewma` ranges -1.0 to 1.0.

### Step 7.3: Sentiment Trend Detection

**Algorithm**: Compare recent vs older interactions

```python
if interaction_count < window * 2 (default window=5):
    return "STABLE"  # Not enough data

recent_avg = average(last 5 interactions' sentiment)
previous_avg = average(interactions 5-10)
delta = recent_avg - previous_avg

if delta > 0.15:
    return "IMPROVING"
elif delta < -0.15:
    return "DECLINING"
else:
    return "STABLE"
```

### Step 7.4: Relationship Stage Calculation

**Function**: `calculate_relationship_stage(last_interaction_at, sentiment_ewma, now=None)`

```python
# Rule 1: AT_RISK overrides everything
if sentiment_ewma < -0.3:
    return "AT_RISK"

# Rule 2: Days since last interaction
days_since = (now - last_interaction_at).days

# Rule 3: Stage classification
if days_since < 7 and sentiment_ewma > 0:
    return "ACTIVE"
elif days_since < 30:
    return "WARM"
elif days_since < 60:
    return "DORMANT"
else:
    return "COLD"
```

**Stage Meanings**:
- `ACTIVE`: Recent (< 7d) + positive sentiment → Engaged relationship
- `WARM`: Recent (< 30d) → Ongoing but not immediate
- `DORMANT`: Older (30-60d) → Needs re-engagement
- `COLD`: Very old (> 60d) → Stale relationship
- `AT_RISK`: Negative sentiment (ewma < -0.3) → Urgent attention needed

### Step 7.5: Confidence Score Calculation

**Function**: `calculate_confidence_score(interaction_count, days_since_last, sources=["gmail"])`

```python
SOURCE_WEIGHTS = {"gmail": 0.35}
CONFIDENCE_HALFLIFE_DAYS = 30

# Base score from sources
base_score = sum(SOURCE_WEIGHTS.get(source, 0.1) for source in sources)  # 0.35 for Gmail

# Recency decay (exponential halflife)
recency_factor = 0.5 ** (days_since_last / CONFIDENCE_HALFLIFE_DAYS)

# Volume multiplier
if interaction_count >= 20:
    volume_mult = 1.15
elif interaction_count >= 10:
    volume_mult = 1.05
elif interaction_count >= 5:
    volume_mult = 1.00
elif interaction_count >= 2:
    volume_mult = 0.80
else:
    volume_mult = 0.55

# Recency bucket multiplier
if days_since_last > 90:
    recency_mult = 0.75
elif days_since_last > 30:
    recency_mult = 0.90
else:
    recency_mult = 1.00

final_score = base_score * recency_factor * volume_mult * recency_mult
return round(min(1.0, final_score), 2)  # 0.0 to 1.0
```

**Effect**: High confidence = recent data with volume. Low confidence = old or sparse data.

### Step 7.6: Human Score Calculation

**Purpose**: Indicates likelihood contact is real human (vs marketing/automated)

```python
human_score = 0.0

# Check signals from interactions
has_outbound = any(direction == "outbound" for i in interactions)
any_unsubscribe = any(has_unsubscribe == True for i in interactions)
total_interactions = count(interactions)

if not any_unsubscribe:  # No unsubscribe headers found
    human_score += 0.3
if has_outbound:  # You replied to them (two-way)
    human_score += 0.2
if total_interactions >= 2:  # Multiple interactions
    human_score += 0.2

human_score += 0.3  # Base benefit of doubt

return round(min(1.0, human_score), 2)  # 0.0 to 1.0
```

### Step 7.7: Topics Aggregation

```sql
SELECT DISTINCT topic
FROM interactions i2, unnest(i2.topics) as topic
WHERE i2.contact_id = :contact_id AND i2.topics IS NOT NULL
LIMIT 10
```

Collects all unique topics discussed with contact (flattens array across interactions).

### Step 7.8: Sentiment History Storage

Keeps last 10 interactions as JSON array:
```json
[
  {"timestamp": "2025-03-18T10:30:00+00:00", "sentiment": 0.8},
  {"timestamp": "2025-03-17T14:20:00+00:00", "sentiment": 0.5},
  ...
]
```

### Step 7.9: Update Contact Record

```sql
UPDATE contacts
SET relationship_stage = :stage,
    sentiment_avg = :sentiment_avg,
    sentiment_ewma = :sentiment_ewma,
    sentiment_trend = :sentiment_trend,
    confidence_score = :confidence,
    first_interaction_at = :first_interaction,
    last_interaction_at = :last_interaction,
    interaction_count = :interaction_count,
    topics_aggregate = :topics,
    sentiment_history = :sentiment_history,
    human_score = :human_score,
    metadata = jsonb_set(
        COALESCE(metadata, '{}'::jsonb),
        '{last_recalc_at}',
        to_jsonb(NOW())
    )
WHERE id = :contact_id
```

---

## 8. Context Bundle Generation (`app/context/bundle_builder.py`)

### Step 8.1: Contact Fuzzy Lookup

**Function**: `get_contact_by_name(db, org_id, entity_name)`

1. **Exact Match First** (case-insensitive):
   ```sql
   SELECT * FROM contacts
   WHERE org_id = :org_id
   AND (TRIM(LOWER(name)) = TRIM(LOWER(:name)) OR LOWER(email) LIKE LOWER(:email_pattern))
   LIMIT 1
   ```
   Returns immediately if found (confidence = 1.0)

2. **Fuzzy Match** (if exact fails):
   - Use `rapidfuzz.process.extractOne()` with `fuzz.WRatio` scorer
   - Score cutoff: 70.0 (minimum match quality)
   - Tries both name and email fields
   - Picks best match
   - Confidence = `match_score / 100.0`

### Step 8.2: Fetch Recent Interactions

**Query**:
```sql
SELECT * FROM interactions
WHERE contact_id = :contact_id
ORDER BY weight_score DESC NULLS LAST, interaction_at DESC
LIMIT 10
```

**Sorting**: By weight_score first (important interactions surface), then by recency.

### Step 8.3: Fetch Open Commitments with Lifecycle

**Query**:
```sql
SELECT
    commit_text, owner, due_date, status,
    EXTRACT(DAY FROM (due_date - NOW())) as days_until_due,
    created_at
FROM commitments
WHERE contact_id = :contact_id
AND status IN ('OPEN', 'OVERDUE', 'SOFT')
ORDER BY
    CASE status WHEN 'OVERDUE' THEN 0 WHEN 'OPEN' THEN 1 ELSE 2 END,
    due_date ASC NULLS LAST,
    created_at DESC
LIMIT 10
```

**Sorting**: OVERDUE first, then OPEN, then SOFT. Within each, sorted by due_date.

**Computed**: `is_overdue = days_until_due < 0`

### Step 8.4: Action Recommendation Logic

**Function**: `determine_action_recommendation(contact, entity)`

**Rules** (checked in order):

1. **BLOCK** (hard fail):
   - Relationship stage = `AT_RISK` OR
   - `sentiment_ewma < -0.5`
   - Action: "DO NOT contact. Escalate to human."

2. **ESCALATE** (human review required):
   - (`entity_type` = INVESTOR/BOARD) AND (stage = ACTIVE or WARM) AND (topics contain sensitive keywords) OR
   - Any sensitive topic detected
   - Sensitive topics: `investor`, `board`, `performance`, `legal`, `compliance`, `acquisition`, `term sheet`, `due diligence`, `equity`, `fundraising`, `series a`, `series b`, `investment`
   - Action: "Draft with extreme care. Must be reviewed by human."

3. **WARN** (proceed cautiously):
   - Any OVERDUE commitments OR
   - (Stage = DORMANT AND sentiment_trend = DECLINING)
   - Action: "Relationship needs attention. Use cautious tone."

4. **PROCEED** (normal):
   - Default for healthy relationships
   - Action: "Clear to execute workflows auto-responsively."

### Step 8.5: Context Paragraph Generation

**Function**: `generate_context_paragraph(contact, interactions, entity, open_commitments)`

**Output Structure** (meant to be prepended to agent's system prompt):

```
Line 1: Identity and role
"{name} from {company} ({entity_type})."

Line 2: Relationship context with confidence
"Relationship: {stage}. {N} exchanges. Last contact {time_ago}. (Confidence: {HIGH|MEDIUM|LOW}, {0.X})"

Line 3: Sentiment with trend
"{Positive|Negative|Neutral} dynamics ({📈 improving|📉 declining|stable})."

Line 4: Topics
"Primary topics: {topic1}, {topic2}, {topic3}."

Line 5: CRITICAL - Open commitments
"⏳ {N} open commitment(s).
  - {commitment_text} (due {date})"

Or if overdue:
"⚠️ OVERDUE: {N} commitment(s) not fulfilled.
  - {commitment_text} (due {date})"

Line 6: Soft commitments
"~ {N} tentative promise(s) (follow up to confirm):
  - {commitment_text}"

Line 7: Communication style
"Prefers: {communication_style}."

Line 8: Last interaction
"Last from {them|you}: {summary}"

Line 9: Engagement frequency
"Engaged: {N} replies."

Line 10: Health alerts
"🚨 ALERT: Relationship at risk. Action required." (if AT_RISK)
"⚠️ Dormant + declining. Consider warm re-engagement." (if DORMANT + DECLINING)
```

**Output Example**:
```
Priya Sharma from Sequoia Capital (INVESTOR). Relationship: WARM. 8 exchanges. Last contact 5 days ago. (Confidence: HIGH, 0.87) Positive dynamics (📈 sentiment improving). Primary topics: Series A, cap table, product roadmap. ⏳ 2 open commitment(s). - Send cap table before March 25 (due 2025-03-25) - Intro to LP network (due null) Engaged: 3 replies. Last from them: Excited about your progress.
```

### Step 8.6: Return Bundle

```python
return {
    "entity": {
        "name": contact["name"],
        "email": contact["email"],
        "company": contact["company"],
        "relationship_stage": stage,
        "confidence": 0.87,
        "sentiment_avg": 0.45,
        "sentiment_ewma": 0.62,
        "sentiment_trend": "IMPROVING",
        "last_interaction": "5 days ago",
        "communication_style": "Direct",
        "topics_of_interest": ["Series A", "cap table", ...],
        "open_commitments": 2,
        "open_commitments_detail": [
            {
                "text": "Send cap table",
                "owner": "us",
                "due_date": "2025-03-25",
                "status": "OPEN",
                "is_overdue": false,
                "is_soft": false,
                "days_until_due": 7
            },
            ...
        ],
        "overdue_commitments": 0,
        "interaction_count": 8,
        "interaction_types": {
            "email_reply": 3,
            "email_one_way": 4,
            "commitment": 1,
            "meeting": 0
        }
    },
    "match_confidence": 1.0,
    "matched_from": "Priya Sharma",
    "recent_interactions": [
        {
            "subject": "Series A planning",
            "summary": "Discussed cap table and investor intro timeline",
            "sentiment": 0.8,
            "intent": "commitment",
            "topics": ["Series A", "cap table"],
            "interaction_at": "2025-03-18T10:30:00+00:00",
            "direction": "inbound",
            "interaction_type": "email_reply",
            "weight_score": 0.95,
            "reply_time_hours": 2.5
        },
        ...
    ],
    "context_for_agent": "Priya Sharma from Sequoia Capital (INVESTOR). ...",
    "confidence": 0.87,

    # ── ACTION SIGNALS (checked first by agents) ──
    "action_recommendation": "proceed",  # or block|escalate|warn
    "escalation_recommended": false,
    "action_reason": "Relationship is healthy. Agent can draft and send.",

    # ── DATA QUALITY ──
    "data_quality": {
        "confidence_score": 0.87,
        "last_recalc": "2025-03-18T14:22:00+00:00",
        "sources": ["gmail"]
    }
}
```

---

## 9. Complete Data Flow Diagram (ACTUAL IMPLEMENTATION)

```
Gmail Inbox
    ↓
OAuth Token (refresh as needed)
    ↓
collect_valid_email_ids() [Gmail-side filter ONLY]
    ├─ Gmail API: -label:promotions -label:social
    └─ Lightweight header validation: contact_email not empty
       ⚠️ NO automated/internal filtering in main flow
    ↓
Fetch Full Messages (batch)
    ├─ parse_headers()
    ├─ extract_email_body()
    └─ Group by threadId
    ↓
build_thread_context() [Last 3 processed messages in thread]
    ↓
sanitize_email_body() [Remove prompt injection patterns]
    ↓
extract_email_intelligence() [LLM extraction]
    ├─ Primary: Groq llama-3.3-70b-versatile
    ├─ Rate limit handling: 2s delay, 3 retries, exponential backoff
    ├─ Fallback: Gemini 2.5-flash (on 429)
    └─ Returns: summary, sentiment, intent, commitments[], topics[], contact_role, is_human_email
    ↓
upsert_contact() [Primary contact, with fuzzy dedup]
    ├─ find_existing_contact_by_domain_and_name()
    │   └─ Match: first_name + company_domain (same-person dedup)
    ├─ extract_company_from_email()
    └─ Apply entity_type via COALESCE (preserve existing)
    ↓
create_interaction() [Primary contact]
    ├─ Calculate weight_score (type × engagement × direction × sentiment)
    ├─ Store direction="inbound" or "outbound"
    ├─ Store sentiment, intent, topics, weight
    └─ Call _store_commitments()
    ↓
Process CC Participants [filtering HAPPENS HERE]
    For each CC person:
    ├─ is_automated_email() check ← filters blocked senders
    ├─ is_internal_email() check ← filters same domain
    ├─ upsert_contact() [no entity_type override]
    └─ create_interaction() with direction="cc"
    ↓
_store_commitments() [For all commitments]
    ├─ parse_due_signal() [Natural language → ISO datetime]
    │   └─ 13 patterns: "March 20", "next Friday", "EOM", "in 3 days", etc.
    ├─ Determine status: "SOFT" if confidence < 0.7 else "OPEN"
    └─ Store in commitments table
    ↓
Update sync_status → "completed"
    ↓
recalculate_all_relationships() [For all org contacts]
    ├─ Fetch all interactions with sentiment
    ├─ Calculate sentiment_ewma (EWMA_ALPHA=0.3: recent 30%, history 70%)
    ├─ Calculate sentiment_trend (5-interaction window, delta threshold 0.15)
    ├─ Calculate confidence_score (30-day halflife decay)
    ├─ Calculate human_score (unsubscribe headers, outbound replies, volume)
    ├─ Calculate relationship_stage (ACTIVE|WARM|DORMANT|COLD|AT_RISK)
    │   └─ AT_RISK overrides all if sentiment_ewma < -0.3
    ├─ Aggregate topics
    ├─ Store sentiment_history JSON (last 10 interactions)
    └─ Update contact record with all metrics
    ↓
Agent requests context → build_context_bundle()
    ├─ get_contact_by_name() [exact match → fuzzy match (70 cutoff)]
    ├─ get_recent_interactions() [sorted by weight_score DESC]
    ├─ get_open_commitments_detailed() [OPEN|OVERDUE|SOFT]
    ├─ determine_action_recommendation() [block|escalate|warn|proceed]
    ├─ generate_context_paragraph() [10-line rich formatted string]
    └─ Return bundle with action signals & reason
    ↓
Agent checks action_recommendation FIRST
    ├─ block → Do not contact, escalate to human
    │   └─ When: AT_RISK or sentiment_ewma < -0.5
    ├─ escalate → Draft with extreme care, human review required
    │   └─ When: Investor/Board + sensitive topics (acquisition, term sheet, etc.)
    ├─ warn → Proceed with cautious tone
    │   └─ When: Overdue commitments or DORMANT + DECLINING
    └─ proceed → Normal workflow
    ↓
Agent prepends context_for_agent to system prompt
    ↓
Agent drafts email with full relationship awareness
```

---

## 10. Key Constants & Configuration

```python
# Email Filtering
AUTOMATED_EMAIL_PATTERNS = [
    "noreply", "no-reply", "donotreply", "do-not-reply", "newsletter",
    "digest", "alert", "notification", "automated", "bounce",
    "mailer-daemon", "postmaster", "jobnotification", "jobalert"
]
AUTOMATED_DOMAINS = [
    "@linkedin.com", "@substack.com", "@medium.com", "@facebookmail.com",
    "@notifications.*", "@alert.*"
]
PERSONAL_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "protonmail.com", "aol.com", "mail.com"
]

# LLM Configuration
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.5-flash"
GROQ_RATE_LIMIT_DELAY = 2  # seconds between requests
LLM_TEMPERATURE = 0.1  # Deterministic
LLM_MAX_TOKENS = 700

# Relationship Scoring
EWMA_ALPHA = 0.3  # Recent 30%, history 70%
CONFIDENCE_HALFLIFE_DAYS = 30
SOURCE_WEIGHTS = {"gmail": 0.35}

# Stage Rules
ACTIVE: days_since < 7 AND sentiment_ewma > 0
WARM: days_since < 30
DORMANT: days_since < 60
COLD: days_since >= 60
AT_RISK: sentiment_ewma < -0.3 (overrides all)

# Escalation Topics
ESCALATION_TOPICS = {
    "investor", "board", "performance", "legal", "compliance",
    "acquisition", "term sheet", "due diligence", "equity",
    "fundraising", "series a", "series b", "investment"
}
```

---

## 11. Graph Structure & Relationships (MANY-TO-MANY)

### How Relationships Are Built:

**Nodes** (Vertices):
- Each contact is ONE node in the graph
- `id`: UUID (unique identifier)
- `org_id`: Organization UUID (multi-tenant isolation)
- `email`: Unique within org (used for lookup)

**Edges** (Relationships):
- Each email interaction creates an EDGE
- Edge connects: **Org** ↔ **Contact** (via interactions table)
- Edges carry metadata (sentiment, topics, weight, etc.)

### Many-to-Many Implementation:

**Example**: Priya (investor) CC'd on email from Yash (customer)

```
Email 1: Yash → User
├─ Create interaction: Yash ↔ Email₁ (direction="inbound")
└─ Process CC:
   └─ Create interaction: Priya ↔ Email₁ (direction="cc")

Email 2: Priya + Yash → User (CC)
├─ Create interaction: Priya ↔ Email₂ (direction="inbound")
└─ Process CC:
   └─ Create interaction: Yash ↔ Email₂ (direction="cc")
```

**Result**: Both are connected to each other through shared emails (many-to-many)

**Key Details**:
- Same email can create MULTIPLE interaction edges (one per participant)
- CC participants: `direction="cc"` (distinct from inbound/outbound)
- Commitments: Tracked only on PRIMARY contact, NOT on CC participants
- Topics: Shared across all participants in same email
- Sentiment: Shared across all participants in same email

---

## 11.1 Node Properties (What's Stored Per Contact)

### Identity Fields:
- `id`: UUID
- `email`: Contact email address
- `name`: Display name
- `company`: Extracted from domain (or NULL for personal emails)
- `company_domain`: Domain extracted (e.g., sequoia.com)
- `entity_type`: Role classification (investor, customer, vendor, partner, candidate, team, lead, advisor, media, other)

### Relationship Health Metrics:
- `relationship_stage`: ACTIVE | WARM | DORMANT | COLD | AT_RISK
- `sentiment_avg`: Average sentiment across all interactions (float -1.0 to 1.0)
- `sentiment_ewma`: Exponential weighted moving average (recent 30%, history 70%)
- `sentiment_trend`: IMPROVING | STABLE | DECLINING
- `confidence_score`: 0.0-1.0 (how much to trust the data)
- `human_score`: 0.0-1.0 (likelihood contact is real human vs automated)

### Interaction Data:
- `interaction_count`: Total interactions with this contact
- `first_interaction_at`: Timestamp of earliest interaction
- `last_interaction_at`: Timestamp of most recent interaction
- `topics_aggregate`: Array of all unique topics discussed
- `communication_style`: Preferred communication mode (inferred)
- `sentiment_history`: JSON array of last 10 interactions [{"timestamp": "...", "sentiment": 0.8}, ...]

### Metadata:
- `metadata`: JSONB for extensibility
  - `last_recalc_at`: When relationship metrics were last calculated

---

## 11.2 Edge Properties (What's Stored Per Interaction)

### Email Metadata:
- `id`: UUID
- `gmail_message_id`: Gmail message ID (unique per contact per org)
- `subject`: Email subject line
- `summary`: LLM-extracted one-liner
- `interaction_at`: Email timestamp

### Direction & Type:
- `direction`: "inbound" (from them) | "outbound" (from us) | "cc" (CC'd)
- `interaction_type`: "email_reply" | "email_one_way" | "commitment" | "other"

### Engagement Signals:
- `sentiment`: -1.0 to 1.0 (extracted by LLM)
- `intent`: follow_up, request, commitment, introduction, negotiation, update, question, other
- `engagement_level`: high | medium | low
- `reply_time_hours`: How long until they replied (nullable)
- `weight_score`: 0.0-1.0 (importance: type × engagement × direction × sentiment)

### Content:
- `topics`: Array of business topics discussed
- `account_email`: Which Gmail account sent/received this email

---

## 11.3 What Gets Computed & Stored After Each Sync

When `recalculate_all_relationships()` runs (automatically after sync):

**For each contact node**:
1. **Fetch all edges** (interactions) for that contact
2. **Calculate sentiment_ewma**:
   ```
   ewma = 0.0
   for each interaction (oldest → newest):
       ewma = 0.3 * sentiment + 0.7 * ewma
   ```
3. **Calculate sentiment_trend** (5-interaction window):
   ```
   recent_avg = avg(last 5 sentiments)
   previous_avg = avg(before that 5)
   delta = recent_avg - previous_avg
   if delta > 0.15: "IMPROVING"
   elif delta < -0.15: "DECLINING"
   else: "STABLE"
   ```
4. **Calculate confidence_score**:
   ```
   base_score = 0.35 (Gmail source)
   recency_factor = 0.5 ^ (days_since_last / 30)
   volume_mult = based on interaction_count
   recency_mult = based on days_since_last
   score = base_score × recency_factor × volume_mult × recency_mult
   ```
5. **Calculate human_score**:
   ```
   0.3 if no unsubscribe headers
   + 0.2 if has outbound replies
   + 0.2 if >= 2 interactions
   + 0.3 base score
   = 0.0-1.0
   ```
6. **Calculate relationship_stage**:
   ```
   if sentiment_ewma < -0.3: "AT_RISK" (overrides all)
   elif days_since < 7 and sentiment_ewma > 0: "ACTIVE"
   elif days_since < 30: "WARM"
   elif days_since < 60: "DORMANT"
   else: "COLD"
   ```
7. **Aggregate topics**: Unique topics across all edges
8. **Store sentiment_history**: JSON array of last 10 interactions
9. **Update contact node** with all computed values

---

## 11.4 What Gets Shown for Graph Visualization

When displaying relationship graph (frontend):

**Node Properties Displayed**:
- `name`: Contact name (label)
- `email`: Contact email
- `entity_type`: Color coding (investor=#8b5cf6, customer=#10b981, vendor=#f59e0b, etc.)
- `interaction_count`: Node size (5pt base + min(count/8, 4))
- `relationship_stage`: Status indicator (ACTIVE=bright, COLD=faded, AT_RISK=red)
- `sentiment_ewma`: Visual indicator (positive=green, negative=red)

**Edge Properties Displayed**:
- `link_type`: "cc_shared" (dashed line) vs "primary" (solid line)
- `weight_score`: Line thickness (0.8 for cc, 1.2 for primary)
- `sentiment`: Color intensity (positive=brighter, negative=darker)

**Node Size Calculation**:
```javascript
baseSize = 10 if self else 5 + min(interaction_count / 8, 4)
// Example: 8 interactions = 5 + 1 = 6pt
// Example: 32+ interactions = 5 + 4 = 9pt (max)
```

**Link Styling**:
- Primary interactions: Solid line, width 1.2, solid stroke
- CC interactions: Dashed line `[4, 4]`, width 0.8, dashed stroke

---

## 11.5 Context Bundle for LLM Agent

When an agent requests context for a contact, the `build_context_bundle()` returns:

**Entity Block** (contact metrics):
```json
{
  "name": "Priya Sharma",
  "email": "priya@sequoia.com",
  "company": "Sequoia Capital",
  "relationship_stage": "WARM",
  "confidence": 0.87,
  "sentiment_avg": 0.45,
  "sentiment_ewma": 0.62,
  "sentiment_trend": "IMPROVING",
  "last_interaction": "5 days ago",
  "communication_style": "Direct",
  "topics_of_interest": ["Series A", "cap table", "investor intro"],
  "open_commitments": 2,
  "overdue_commitments": 0,
  "interaction_count": 8,
  "interaction_types": {
    "email_reply": 3,
    "email_one_way": 4,
    "commitment": 1
  }
}
```

**Recent Interactions Block** (sorted by weight_score DESC):
```json
[
  {
    "subject": "Series A planning",
    "summary": "Discussed cap table and investor intro",
    "sentiment": 0.8,
    "intent": "commitment",
    "interaction_type": "email_reply",
    "weight_score": 0.95,
    "direction": "inbound",
    "topics": ["Series A", "cap table"]
  },
  ...
]
```

**Open Commitments Block** (firm + overdue first):
```json
[
  {
    "text": "Send cap table before end of month",
    "owner": "us",
    "due_date": "2025-03-31",
    "status": "OPEN",
    "is_overdue": false,
    "is_soft": false,
    "days_until_due": 13
  },
  {
    "text": "Intro to LP network",
    "owner": "them",
    "due_date": null,
    "status": "SOFT",
    "is_soft": true
  }
]
```

**Context Paragraph** (prepended to agent's system prompt):
```
Priya Sharma from Sequoia Capital (INVESTOR). Relationship: WARM. 8 exchanges. Last contact 5 days ago. (Confidence: HIGH, 0.87) Positive dynamics (📈 sentiment improving). Primary topics: Series A, cap table, investor intro. ⏳ 2 open commitment(s). - Send cap table before end of month (due 2025-03-31) - Intro to LP network (due null). Engaged: 3 replies. Last from them: Very positive feedback on progress.
```

**Action Signals** (checked first by agent):
```json
{
  "action_recommendation": "proceed",  // or block|escalate|warn
  "escalation_recommended": false,
  "action_reason": "Relationship is healthy. Agent can draft and send."
}
```

---

## 11.6 Database Schema (Complete Reference)

### contacts (Node Table)
```sql
CREATE TABLE contacts (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  email TEXT NOT NULL,
  name TEXT,
  company TEXT,
  company_domain TEXT,
  entity_type TEXT,  -- investor|customer|vendor|partner|candidate|team|lead|advisor|media|other
  relationship_stage TEXT,  -- ACTIVE|WARM|DORMANT|COLD|AT_RISK
  sentiment_avg FLOAT,
  sentiment_ewma FLOAT,  -- Exponential weighted moving average
  sentiment_trend TEXT,  -- IMPROVING|STABLE|DECLINING
  confidence_score FLOAT,  -- 0.0-1.0
  interaction_count INTEGER,
  first_interaction_at TIMESTAMP,
  last_interaction_at TIMESTAMP,
  topics_aggregate TEXT[],  -- Array of topics
  sentiment_history JSONB,  -- [{timestamp, sentiment}, ...]
  human_score FLOAT,  -- 0.0-1.0
  communication_style TEXT,
  metadata JSONB,

  UNIQUE(org_id, email),
  FOREIGN KEY(org_id) REFERENCES organizations(id)
);
```

### interactions (Edge Table)
```sql
CREATE TABLE interactions (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  contact_id UUID NOT NULL,
  gmail_message_id TEXT NOT NULL,
  direction TEXT,  -- inbound|outbound|cc
  subject TEXT,
  summary TEXT,
  interaction_at TIMESTAMP,
  sentiment FLOAT,  -- -1.0 to 1.0
  intent TEXT,  -- follow_up|request|commitment|introduction|...
  interaction_type TEXT,  -- email_reply|email_one_way|commitment|other
  reply_time_hours FLOAT,
  weight_score FLOAT,  -- 0.0-1.0 (importance ranking)
  topics TEXT[],  -- Array of business topics
  account_email TEXT,  -- Which Gmail account

  UNIQUE(gmail_message_id, contact_id),
  FOREIGN KEY(org_id) REFERENCES organizations(id),
  FOREIGN KEY(contact_id) REFERENCES contacts(id)
);
```

### commitments (Lifecycle Table)
```sql
CREATE TABLE commitments (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  contact_id UUID NOT NULL,
  commit_text TEXT,  -- What was promised
  owner TEXT,  -- them|us
  due_date TIMESTAMP,  -- Parsed from natural language
  status TEXT,  -- OPEN|OVERDUE|SOFT|COMPLETED
  source_interaction_id UUID,  -- Which interaction created it
  created_at TIMESTAMP,

  FOREIGN KEY(org_id) REFERENCES organizations(id),
  FOREIGN KEY(contact_id) REFERENCES contacts(id),
  FOREIGN KEY(source_interaction_id) REFERENCES interactions(id)
);
```

### oauth_tokens (Auth Table)
```sql
CREATE TABLE oauth_tokens (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  access_token TEXT,  -- Encrypted
  refresh_token TEXT,  -- Encrypted
  account_email TEXT,  -- Specific Gmail account (multi-account support)
  sync_status TEXT,  -- idle|running|completed|error
  sync_total INTEGER,  -- Total emails to sync
  sync_processed INTEGER,  -- Processed so far
  sync_error TEXT,  -- Error message if failed
  sync_started_at TIMESTAMP,
  last_synced_at TIMESTAMP,
  created_at TIMESTAMP,

  FOREIGN KEY(org_id) REFERENCES organizations(id)
);
```

---

## Graph Query Examples

### Find all contacts for an organization:
```sql
SELECT id, name, email, entity_type, relationship_stage, sentiment_ewma
FROM contacts
WHERE org_id = :org_id
ORDER BY interaction_count DESC;
```

### Get interaction history with a specific contact:
```sql
SELECT subject, summary, sentiment, interaction_type, weight_score, interaction_at
FROM interactions
WHERE contact_id = :contact_id AND org_id = :org_id
ORDER BY weight_score DESC, interaction_at DESC;
```

### Find all open commitments:
```sql
SELECT commit_text, owner, due_date, status,
       EXTRACT(DAY FROM (due_date - NOW())) as days_until_due
FROM commitments
WHERE org_id = :org_id AND status IN ('OPEN', 'OVERDUE', 'SOFT')
ORDER BY status, due_date ASC;
```

### Get relationship neighbors (many-to-many):
```sql
-- Find all contacts this person interacted with
SELECT DISTINCT c.id, c.name, c.email, COUNT(i.id) as shared_interactions
FROM interactions i
JOIN contacts c ON i.contact_id = c.id
WHERE i.gmail_message_id IN (
  SELECT gmail_message_id FROM interactions
  WHERE contact_id = :target_contact_id
)
AND c.id != :target_contact_id
GROUP BY c.id, c.name, c.email
ORDER BY shared_interactions DESC;
```

---

---

## 12. Design Principles & Guardrails

1. **Defense-in-Depth Filtering**: Pre-filter at Gmail API (labels) → header check → body check. Never process low-confidence emails to LLM.

2. **No Trust in LLM Output**: All JSON validated, confidence clamped to [0, 1], entity_type normalized to valid set.

3. **Deduplication Before Graph**: Same-person fuzzy dedup prevents split history. Company domain + first name = identity key.

4. **Commitment Confidence Distinction**: Soft commitments (confidence < 0.7) flagged with status="SOFT" for downstream caution.

5. **EWMA for Stability**: Recent emails matter (30%), but history smooths spikes. Sentiment < -0.3 = AT_RISK override.

6. **Recency Decay for Confidence**: 30-day halflife ensures old data loses weight as new data arrives.

7. **Action Recommendations First**: Agents check block/escalate/warn/proceed before reading context. No silent failures.

8. **Commitment Lifecycle**: OPEN (firm) → OVERDUE (past due_date) → COMPLETED. SOFT (tentative) tracked separately.

9. **CC as Graph Edges**: CC participants become nodes, but commitments tracked only on primary contact.

10. **Injection Sanitization**: All email bodies scanned and `[REDACTED]` before LLM to prevent jailbreaks.

---

**Last Updated**: 2025-03-18
**Version**: 2.0 (Code-Accurate Complete Reference)
