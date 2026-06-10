"""
Intent + Emotion classification prompt.

Single Haiku call at the start of /v1/context. Output drives:
  - whether to trigger live tool fetch
  - which response tone to use (response_shaper)
  - urgency tagging on suggested_action

Strict JSON output — validated by Pydantic in classifier.py.
"""

INTENT_SYSTEM = (
    "You are an intent + emotion classifier for an agent that talks to "
    "founders about their relationships and tools. "
    "Given a free-text query (and optional prior context), output a single "
    "JSON object with the user's intent, domain, emotional state, urgency, "
    "and whether the answer likely needs a real-time tool fetch (vs cached "
    "graph data). "
    "Be conservative: when unsure, choose 'informational', 'casual', 'med'. "
    "Output ONLY the JSON — no markdown, no prose, no preamble."
)

INTENT_USER_TEMPLATE = """Query:
{query}

Prior context (last 1-2 turns, if any):
{prior_context}

Return EXACTLY this JSON shape:
{{
  "intent": "informational | transactional | action_request | emotional | troubleshooting",
  "domain": "billing | meeting | contact | project | document | personal | unknown",
  "emotion": "neutral | frustrated | urgent | casual | confused | grateful",
  "urgency": "low | med | high",
  "requires_live_fetch": true,
  "confidence": 0.0
}}

Rules:
- intent: what is the user TRYING to do?
- domain: what category of data is involved?
- emotion: what tone should the answer match?
  • frustrated: complaint words, repeated asks, "tang aagaya", "frustrated", "useless"
  • urgent: "now", "asap", "in 10 min", "before X", "urgent", deadline mentioned
  • casual: short, conversational, "yaar", "bhai", emojis
  • confused: question marks, "samajh nahi", "what is", "how does"
  • grateful: "thanks", "perfect", "great"
- urgency: how time-sensitive?
  • high: explicit deadline within 24h, frustrated AND ongoing issue
  • med: needs answer today
  • low: background curiosity / FYI
- requires_live_fetch: true when query references SPECIFIC transactional data
  (an invoice, a doc, a single meeting, a recent transaction). False when
  query is about a relationship/contact in general.
- confidence: 0.0-1.0 — your own confidence in this classification.
"""
