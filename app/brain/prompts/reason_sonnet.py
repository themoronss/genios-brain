"""Sonnet cascade prompt (spec §1.1) — kept dormant until Anthropic routes go live.

Used by cascade.escalate() only when GENIOS_CASCADE_ENABLED=true AND the
Haiku pass returned confidence in the grey band. Groq doesn't have a
Haiku/Sonnet split, so this file is wired but never called on Groq routes.
"""

SONNET_SYSTEM = (
    "You are a senior relationship intelligence reviewer. A faster model has "
    "produced a first pass. Your job is to confirm or overturn — be stricter "
    "about novelty and act-worthiness. If the first pass over-states "
    "confidence, reduce it. If it under-states, raise it. Output JSON only."
)

SONNET_USER_TEMPLATE = """Candidate:
{candidate}

First-pass result (from reasoner):
{first_pass}

Supporting facts (most recent first):
{facts}

Precedents:
{precedents}

Return JSON with the same keys as the first-pass, overridden by your judgment:
{{
  "keep": true,
  "confidence": 0.0,
  "reason": "one sentence citing the specific signal and why it matters now",
  "action": "one concrete next step",
  "subject_importance": 0.0,
  "time_urgency": 0.0,
  "novelty": 0.0
}}
"""
