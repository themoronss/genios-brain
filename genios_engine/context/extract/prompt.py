B3_PROMPT = '''You read ONE business message and do two things: judge its relevance, and
extract STATED facts with exact evidence. Output JSON ONLY — no prose.

Message (source: {source}):
"""
{content}
"""

Return EXACTLY this shape:
{{
  "relevance": 0.0,               // your judgment: is this decision-relevant business signal?
                                  // 0 = noise/newsletter/automated, 1 = clearly actionable (real reply, request, commitment)
  "noise_type": "none",           // none | newsletter | automated | personal | spam
  "domains": [],                  // e.g. ["sales"], ["support"], ["admin"]
  "entity_mentions": [
    {{"type": "person", "name": "...", "email": null,
      "evidence_text": "exact substring from the message proving this entity"}}
  ],
  "fact_candidates": [
    {{"subject": "person or company name", "field": "role|company|budget|deal.stage|...",
      "value": "...", "evidence_text": "exact substring proving this fact"}}
  ],
  "commitments": [
    {{"actor": "who owes it (a name, or 'us')", "action": "what is owed",
      "due_text": null, "evidence_text": "exact substring"}}
  ],
  "questions": [
    {{"text": "the question", "directed_at": "us", "evidence_text": "exact substring"}}
  ],
  "observations": [
    {{"kind": "<one CANONICAL signal from the SIGNAL KINDS list below>",
      "evidence_text": "exact substring"}}
  ]
}}

SIGNAL KINDS — for observations.kind use these EXACT strings (emit only when the message clearly
states it; omit if unsure — a wrong signal is worse than none). This is how the system detects
sales + relationship moments:
  Buying:    budget_approved · verbal_yes · next_step_agreed · contract_requested · demo_requested ·
             security_review_started · stakeholder_added · pricing_discussed · proposal_sent
  Risk:      competitor · discount_pressure · budget_freeze · champion_change · legal_review ·
             timeline_slip · going_dark · closed_lost_mention
  Objection: objection · objection_price · objection_timing · objection_security ·
             objection_authority · objection_integration
  Sentiment: positive_reply · negative_reply · price_pushback
  General:   meeting_request · followup_sent · introduction

Hard rules:
- evidence_text MUST be an EXACT substring copied verbatim from the message. Never paraphrase.
  If you cannot quote it word-for-word, DO NOT emit that item.
- Extract only what is STATED. Never invent names, numbers, dates, companies, or facts.
- CAP each array at 15 items; pick the most central if there are more.
- relevance is YOUR judgment of business signal — an automated/marketing/newsletter message is low;
  a real prospect/customer message with a request, question, or commitment is high.
Output only the JSON object.'''
