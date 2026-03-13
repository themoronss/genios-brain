This is the complete scoring architecture for GeniOS Brain. Every score, every algorithm, every update mechanism — section by section.

---

## Section 1 — Confidence Score

**What it is:** A measure of how much the agent should trust the context bundle for a given entity. Not a measure of relationship health — purely a measure of data quality and freshness.

**Why it exists:** An agent acting on a context bundle built from 2 emails should behave very differently from one built from 6 months of Gmail + Calendar + HubSpot. Confidence is the signal that controls agent assertiveness vs caution.

**The math:**

```python
def confidence_score(node):

    SOURCE_WEIGHTS = {
        'gmail':    0.35,
        'calendar': 0.25,
        'hubspot':  0.20,
        'slack':    0.15,
        'notion':   0.05,
    }

    DECAY_HALFLIFE_DAYS = {
        'gmail':    30,
        'calendar': 14,
        'hubspot':  60,
        'slack':    7,
        'notion':   90,
    }

    base_score = 0.0

    for source, weight in SOURCE_WEIGHTS.items():
        if source not in node.sources:
            continue
        days_stale = days_since_last_sync(source, node.org_id)
        recency_factor = 0.5 ** (days_stale / DECAY_HALFLIFE_DAYS[source])
        base_score += weight * recency_factor

    # Volume multiplier
    n = node.interaction_count
    if n >= 20:   volume_mult = 1.15
    elif n >= 10: volume_mult = 1.05
    elif n >= 5:  volume_mult = 1.00
    elif n >= 2:  volume_mult = 0.80
    else:         volume_mult = 0.55  # single interaction — very low trust

    # Conflict penalty — sources disagree on stage or role
    conflict_mult = 0.85 if has_source_conflict(node) else 1.0

    # Recency of last interaction
    days_since_last = node.days_since_last_interaction
    if days_since_last > 90:   recency_mult = 0.75
    elif days_since_last > 30: recency_mult = 0.90
    else:                      recency_mult = 1.00

    final = base_score * volume_mult * conflict_mult * recency_mult
    return round(min(final, 1.0), 2)
```

**How it updates:** Recalculated every time the node is touched by ingestion, every time a source syncs, and every night as a catch-all. It is never manually set — always computed.

**What agents do with it:**

```
confidence >= 0.80 → act autonomously
confidence 0.60–0.79 → act with caveat in output
confidence 0.40–0.59 → escalate for human confirmation
confidence < 0.40 → do not act, flag as insufficient data
```

---

## Section 2 — Sentiment Score

**What it is:** A per-interaction float between -1.0 and +1.0 representing the emotional tone of a communication. Aggregated into a per-relationship sentiment average and a trend direction.

**Three distinct layers:**

Layer 1 — Raw interaction sentiment (per email/message)
Layer 2 — Relationship sentiment average (rolling weighted mean)
Layer 3 — Sentiment trend (is the relationship getting better or worse?)

**Layer 1 — Per interaction:**

```python
def score_interaction_sentiment(email_body, subject, reply_time_hours):

    # LLM call — Claude Haiku (cheap, fast)
    prompt = f"""
    Score the sentiment of this email on a scale from -1.0 to +1.0.
    -1.0 = strongly negative (angry, disappointed, rejecting)
     0.0 = neutral (informational, transactional)
    +1.0 = strongly positive (excited, approving, committed)

    Also classify: positive / neutral / negative
    Also extract: is there a commitment made? (yes/no)
    Also extract: is there a concern raised? (yes/no)

    Email subject: {subject}
    Email body: {email_body}

    Return JSON only.
    """

    result = llm_call(prompt)
    raw_score = result['sentiment_score']

    # Reply time modifier — fast reply = higher engagement signal
    if reply_time_hours < 2:    reply_boost = 0.05
    elif reply_time_hours < 24: reply_boost = 0.02
    elif reply_time_hours > 72: reply_boost = -0.03
    else:                       reply_boost = 0.0

    # Direction modifier — inbound positive > outbound positive
    # (them liking you matters more than you liking them)
    direction = get_email_direction(email)  # INBOUND or OUTBOUND
    direction_mult = 1.2 if direction == 'INBOUND' else 0.9

    adjusted = (raw_score + reply_boost) * direction_mult
    return round(max(-1.0, min(1.0, adjusted)), 3)
```

**Layer 2 — Relationship sentiment average:**

Not a simple mean. Uses exponential weighted moving average so recent interactions matter more:

```python
def relationship_sentiment_avg(interactions):
    # Sort by date ascending
    interactions = sorted(interactions, key=lambda x: x.timestamp)

    ewma = 0.0
    alpha = 0.3  # smoothing factor — higher = more weight on recent

    for interaction in interactions:
        ewma = alpha * interaction.sentiment_score + (1 - alpha) * ewma

    return round(ewma, 3)

# Example trace:
# Interaction 1: score=0.2 → ewma = 0.2
# Interaction 2: score=0.6 → ewma = 0.3*0.6 + 0.7*0.2 = 0.32
# Interaction 3: score=-0.3 → ewma = 0.3*(-0.3) + 0.7*0.32 = 0.134
# Interaction 4: score=0.8 → ewma = 0.3*0.8 + 0.7*0.134 = 0.334
```

**Layer 3 — Sentiment trend:**

```python
def sentiment_trend(interactions, window=5):
    # Compare last N interactions against previous N
    recent = interactions[-window:]
    previous = interactions[-window*2:-window]

    if len(previous) < 2:
        return 'insufficient_data'

    recent_avg = sum(i.sentiment_score for i in recent) / len(recent)
    previous_avg = sum(i.sentiment_score for i in previous) / len(previous)

    delta = recent_avg - previous_avg

    if delta > 0.15:    return 'IMPROVING'
    elif delta < -0.15: return 'DECLINING'
    else:               return 'STABLE'
```

**How sentiment updates:** Every new interaction triggers a recalculation of EWMA and trend. Not batched — real-time on ingestion.

**AT_RISK override:**

```python
if relationship_sentiment_avg < -0.3:
    node.stage = 'AT_RISK'  # overrides all other stage logic
```

---

## Section 3 — Relationship Stage Score

**What it is:** A categorical label (ACTIVE / WARM / DORMANT / COLD / AT_RISK) computed from recency + sentiment + interaction frequency. Not stored as a fixed field — recomputed every night.

**The decision tree:**

```python
def compute_relationship_stage(node):

    days_since = node.days_since_last_interaction
    sentiment = node.sentiment_avg
    freq = node.interaction_frequency_per_month

    # AT_RISK overrides everything — check first
    if sentiment < -0.3:
        return 'AT_RISK'

    # Churn signal: was active/warm, now suddenly silent
    if node.previous_stage in ('ACTIVE', 'WARM') and days_since > 21:
        if sentiment < 0.0:
            return 'AT_RISK'  # sudden cold after positive = churn signal

    # Standard stage logic
    if days_since <= 7 and freq >= 2:
        return 'ACTIVE'
    elif days_since <= 7 and freq < 2:
        return 'WARM'         # recent but infrequent
    elif days_since <= 30:
        return 'WARM'
    elif days_since <= 90:
        return 'DORMANT'
    else:
        return 'COLD'
```

**The frequency score behind it:**

```python
def interaction_frequency_per_month(interactions, months=3):
    # Count interactions in last N months
    cutoff = today - timedelta(days=months*30)
    recent = [i for i in interactions if i.timestamp > cutoff]
    return len(recent) / months  # interactions per month average
```

**Stage transition rules (prevents flapping):**
A node cannot jump more than one stage in a single recalculation cycle. ACTIVE cannot become COLD overnight — it goes ACTIVE → WARM → DORMANT → COLD over successive nights. Exception: AT_RISK can be applied immediately regardless of current stage.

---

## Section 4 — Interaction Weight Score

**What it is:** Not all interactions are equal. A 45-minute call > a one-line reply > a newsletter forward. Every interaction edge has a weight that feeds into relationship scoring.

```python
INTERACTION_WEIGHTS = {
    'meeting_attended':        1.0,   # highest — both parties showed up
    'meeting_declined':       -0.3,   # they said no to your time
    'email_thread_reply':      0.7,   # they engaged
    'email_sent_no_reply':     0.1,   # you reached out, silence
    'slack_direct_message':    0.6,
    'slack_mention_response':  0.5,
    'hubspot_deal_progressed': 0.8,
    'hubspot_deal_stalled':   -0.2,
    'document_shared':         0.4,
    'document_viewed':         0.5,   # they opened it
    'commitment_fulfilled':    0.9,   # they did what they promised
    'commitment_missed':      -0.6,
}

def weighted_interaction_score(interactions):
    total = 0.0
    for i in interactions:
        base = INTERACTION_WEIGHTS.get(i.type, 0.3)
        recency = recency_weight(i.days_ago)
        total += base * recency
    return round(total, 2)
```

**How it updates:** Every new interaction appended, score recalculated as running total with recency decay applied.

---

## Section 5 — Recency Weight (Decay Function)

**What it is:** A multiplier applied to every interaction score to discount older data. The backbone of the decay system.

```python
def recency_weight(days_ago, halflife=30):
    """
    Exponential decay with configurable half-life.
    At t=0 (today): weight = 1.0
    At t=halflife: weight = 0.5
    At t=2*halflife: weight = 0.25
    """
    return 0.5 ** (days_ago / halflife)

# SPECIAL CASES — decay override:
# Commitments: halflife = 999 (never decay until resolved)
# First interaction: halflife = 180 (how you met someone matters long-term)
# Negative interactions: halflife = 45 (bad experiences fade faster)
# Calendar accepted meeting: halflife = 21 (fresh signal, decays fast)
```

**Different halflives per interaction type:**

```python
HALFLIFE_BY_TYPE = {
    'commitment':           999,  # never decays until resolved
    'first_interaction':    180,  # origin story matters
    'meeting_attended':      45,
    'email_thread_reply':    30,
    'slack_message':         14,  # fast decay — casual channel
    'hubspot_note':          60,  # CRM notes stay relevant longer
    'negative_interaction':  45,  # bad experiences fade
    'deal_progression':      30,
}
```

---

## Section 6 — Communication Style Score

**What it is:** An inferred profile of how a contact prefers to communicate — not a single number, but a structured object built from behavioral patterns.

```python
def build_communication_style(node):

    interactions = get_all_interactions(node)

    # Average email length they send (words)
    their_avg_length = mean([word_count(i.body)
                             for i in interactions
                             if i.direction == 'INBOUND'])

    # Average reply time (hours)
    reply_times = compute_reply_times(interactions)
    their_avg_reply = mean(reply_times['theirs'])
    your_avg_reply  = mean(reply_times['yours'])

    # Preferred channel (which source has most interactions)
    channel_counts = Counter(i.source for i in interactions)
    preferred_channel = channel_counts.most_common(1)[0][0]

    # Response to different email lengths
    # Did they reply faster/more positively to short vs long emails?
    short_response_sentiment = mean_sentiment_for_length(interactions, max_words=100)
    long_response_sentiment  = mean_sentiment_for_length(interactions, min_words=300)

    prefers_short = short_response_sentiment > long_response_sentiment + 0.1

    # Formality score — LLM extraction on sample of their emails
    formality = llm_score_formality(sample_emails(interactions, n=5))
    # returns: 'formal' / 'semi-formal' / 'casual'

    return {
        'preferred_channel': preferred_channel,
        'preferred_length': 'short' if prefers_short else 'detailed',
        'avg_reply_hours': round(their_avg_reply, 1),
        'formality': formality,
        'initiates_contact': your_avg_reply < their_avg_reply,
        'best_send_time': compute_best_send_time(interactions),
        'responds_to_questions': question_response_rate(interactions),
    }
```

**How it updates:** Rebuilt every time there are 5 new interactions. Not nightly — only when enough new signal exists to change the profile meaningfully.

---

## Section 7 — Commitment Detection and Tracking Score

**What it is:** Commitments are extracted from interactions and tracked separately from sentiment. They have their own lifecycle: OPEN → FULFILLED / MISSED / OVERDUE.

**Detection:**

```python
def extract_commitments(email_body, direction):

    prompt = f"""
    Extract any commitments from this email.
    A commitment is a specific promise to do something by a time.

    For each commitment found, return:
    - text: what was promised
    - owner: 'sender' or 'recipient'
    - due_signal: any date/time mentioned (or null)
    - confidence: how clear is this commitment (0.0–1.0)

    Only extract explicit commitments, not vague statements.
    "I'll send that over" = commitment (owner: sender)
    "We should chat sometime" = NOT a commitment (too vague)

    Email: {email_body}
    Direction: {direction}

    Return JSON array only.
    """

    commitments = llm_call(prompt)
    # Filter by confidence threshold
    return [c for c in commitments if c['confidence'] >= 0.7]
```

**Commitment score per node:**

```python
def commitment_health_score(node):
    open_commits = node.open_commitments
    overdue      = [c for c in open_commits if c.is_overdue]
    fulfilled    = node.fulfilled_commitments
    missed       = node.missed_commitments

    # Penalty for overdue
    overdue_penalty = len(overdue) * 0.15

    # Historical reliability
    total_historical = len(fulfilled) + len(missed)
    if total_historical > 0:
        reliability = len(fulfilled) / total_historical
    else:
        reliability = 1.0  # no history = no penalty

    score = reliability - overdue_penalty
    return round(max(0.0, min(1.0, score)), 2)
```

**Overdue detection:**

```python
# Nightly job
for commitment in all_open_commitments():
    if commitment.due_date and commitment.due_date < today:
        commitment.status = 'OVERDUE'
        flag_insight(commitment, priority='P1')

    # No due date — check if it's been too long
    elif days_since(commitment.created_at) > 14:
        commitment.status = 'OVERDUE'
        flag_insight(commitment, priority='P2')
```

---

## Section 8 — Topic Relevance Score

**What it is:** Which topics repeatedly appear across interactions with this contact, and how recently. Used to determine what to lead with in agent-drafted communications.

```python
def build_topic_profile(node):

    # Extract topics from all interactions via LLM
    all_topics = []
    for interaction in node.interactions:
        topics = extract_topics(interaction.content_summary)
        # topics = ['Series A', 'retention metrics', 'India GTM']
        all_topics.extend([
            {'topic': t, 'days_ago': interaction.days_ago}
            for t in topics
        ])

    # Score each unique topic
    topic_scores = {}
    for entry in all_topics:
        t = entry['topic']
        weight = recency_weight(entry['days_ago'], halflife=60)
        topic_scores[t] = topic_scores.get(t, 0) + weight

    # Normalize and rank
    max_score = max(topic_scores.values()) if topic_scores else 1
    ranked = sorted(
        [(t, round(s/max_score, 2)) for t, s in topic_scores.items()],
        key=lambda x: -x[1]
    )

    return ranked[:8]  # top 8 topics

# Output: [('retention metrics', 1.0), ('Series A', 0.87),
#          ('India GTM', 0.72), ('unit economics', 0.45), ...]
```

**How it updates:** Rebuilt on every new interaction. New topics added, old ones decay in score over time via recency weighting.

---

## Section 9 — Relationship Depth Score

**What it is:** A composite score that answers "how real is this relationship?" — distinct from stage (which is about recency) and sentiment (which is about tone). Depth measures how multi-dimensional and sustained the relationship is.

```python
def relationship_depth_score(node):

    # Dimension 1: Source diversity (max 0.25)
    # Relationship across multiple channels = deeper
    source_count = len(node.sources)
    source_score = min(source_count / 4, 1.0) * 0.25

    # Dimension 2: Interaction span in months (max 0.20)
    months_known = months_between(node.first_interaction, today)
    span_score = min(months_known / 12, 1.0) * 0.20

    # Dimension 3: Bidirectionality (max 0.20)
    # They reach out to you, not just you to them
    inbound = len([i for i in node.interactions if i.direction == 'INBOUND'])
    total   = len(node.interactions)
    bidir_ratio = inbound / total if total > 0 else 0
    bidir_score = bidir_ratio * 0.20

    # Dimension 4: Commitment exchange (max 0.20)
    # Commitments = real working relationship
    commit_count = len(node.all_commitments)
    commit_score = min(commit_count / 10, 1.0) * 0.20

    # Dimension 5: Meeting history (max 0.15)
    meeting_count = len([i for i in node.interactions
                         if i.type == 'meeting_attended'])
    meeting_score = min(meeting_count / 5, 1.0) * 0.15

    depth = source_score + span_score + bidir_score + commit_score + meeting_score
    return round(depth, 2)

# Interpretation:
# 0.80+ = deep, multi-dimensional relationship
# 0.50–0.79 = established relationship
# 0.25–0.49 = surface relationship
# < 0.25 = barely a relationship — agent should be very cautious
```

---

## Section 10 — Churn Risk Score (Customer Nodes Only)

**What it is:** A predictive score for customer contacts — probability that this customer will churn in the next 30 days.

```python
def churn_risk_score(customer_node):

    score = 0.0

    # Signal 1: Sentiment trend declining
    if customer_node.sentiment_trend == 'DECLINING':
        score += 0.25
    elif customer_node.sentiment_trend == 'STABLE' and \
         customer_node.sentiment_avg < 0.1:
        score += 0.10

    # Signal 2: Engagement frequency dropping
    recent_freq   = interaction_frequency(customer_node, months=1)
    previous_freq = interaction_frequency(customer_node, months=2,
                                          offset_months=1)
    if previous_freq > 0:
        freq_drop = (previous_freq - recent_freq) / previous_freq
        if freq_drop > 0.5:   score += 0.20  # frequency halved
        elif freq_drop > 0.3: score += 0.10

    # Signal 3: Support ticket spike
    open_tickets = get_open_support_tickets(customer_node)
    if open_tickets >= 3:   score += 0.20
    elif open_tickets >= 1: score += 0.08

    # Signal 4: Explicit language in emails
    churn_keywords = ['evaluating alternatives', 'looking at other',
                      'cancell', 'discontinue', 'too expensive',
                      'not seeing value', 'going with']
    recent_emails = get_recent_emails(customer_node, days=30)
    for email in recent_emails:
        if any(kw in email.body.lower() for kw in churn_keywords):
            score += 0.30  # explicit churn signal — high weight
            break

    # Signal 5: Post-onboarding silence (days 15-30 = critical window)
    if customer_node.is_new_customer:
        days_since_onboarding = customer_node.days_since_onboarding
        if 15 <= days_since_onboarding <= 45 and recent_freq < 1:
            score += 0.15  # classic silent churn pattern

    # Signal 6: No product usage signal from HubSpot
    if 'hubspot' in customer_node.sources:
        if customer_node.hubspot_last_activity_days > 21:
            score += 0.10

    return round(min(score, 1.0), 2)

# Thresholds:
# 0.70+ = HIGH RISK → P1 insight, immediate action
# 0.40–0.69 = MEDIUM RISK → P2 insight, action this week
# 0.20–0.39 = LOW RISK → monitor
# < 0.20 = healthy
```

---

## Section 11 — Conversion Potential Score (Free → Paid)

**What it is:** For product-led growth — scores free users on their likelihood to convert to paid based on behavioral signals in the graph.

```python
def conversion_potential_score(free_user_node):

    score = 0.0

    # Usage depth signal (from HubSpot / product events)
    feature_usage = get_feature_usage_count(free_user_node)
    if feature_usage >= 10:  score += 0.30
    elif feature_usage >= 5: score += 0.15

    # Days active on free tier
    days_active = free_user_node.days_since_signup
    if days_active >= 30:    score += 0.20
    elif days_active >= 14:  score += 0.10

    # Inbound engagement (they emailed you, asked questions)
    inbound_count = len([i for i in free_user_node.interactions
                         if i.direction == 'INBOUND'])
    if inbound_count >= 3:   score += 0.20
    elif inbound_count >= 1: score += 0.10

    # Positive sentiment on interactions
    if free_user_node.sentiment_avg > 0.4:  score += 0.15
    elif free_user_node.sentiment_avg > 0.1: score += 0.07

    # Upgrade intent language in emails
    upgrade_keywords = ['pricing', 'plan', 'upgrade', 'paid',
                        'team plan', 'billing', 'more features']
    recent_emails = get_recent_emails(free_user_node, days=60)
    for email in recent_emails:
        if any(kw in email.body.lower() for kw in upgrade_keywords):
            score += 0.25
            break

    # No pricing prompt seen yet (opportunity window)
    if not has_seen_pricing_prompt(free_user_node):
        score *= 1.1  # boost — untouched opportunity

    return round(min(score, 1.0), 2)
```

---

## How All Scores Feed Into Each Other

```
Raw interactions (email, calendar, slack, hubspot, notion)
        ↓
Sentiment Score (per interaction, EWMA aggregated)
Commitment Detection (per interaction, extracted by LLM)
Topic Extraction (per interaction, LLM + keyword)
Interaction Weight (per interaction type)
        ↓
Relationship Sentiment Avg
Sentiment Trend (IMPROVING / STABLE / DECLINING)
Interaction Frequency
Topic Profile (ranked, recency-weighted)
Communication Style Profile
        ↓
Relationship Stage (ACTIVE / WARM / DORMANT / COLD / AT_RISK)
Relationship Depth Score
Commitment Health Score
Churn Risk Score (customer nodes only)
Conversion Potential Score (free user nodes only)
        ↓
Confidence Score (data quality + freshness across all sources)
        ↓
Context Bundle Assembly
        ↓
context_for_agent paragraph (LLM-generated on top of structured scores)
        ↓
Agent receives full context in <100ms
```

**The core principle behind all of this:** LLM is used only for extraction (sentiment, topics, commitments from raw text) and for the final prose generation of the `context_for_agent` paragraph. Every aggregation, scoring, trending, stage decision, and insight detection is deterministic code — not LLM calls. This is what makes the system reliable, fast, and auditable. You can explain exactly why a score is what it is. No black box.