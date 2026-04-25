"""Reasoning prompt (spec §12.2 — verbatim).

The reasoner takes a candidate + supporting facts + precedents and decides:
  - should this become a recommendation? (keep: bool)
  - how confident? (confidence: float)
  - human-readable explanation (reason, action)

Strict JSON output so we can validate with Pydantic.
"""

REASON_SYSTEM = (
    "You are a relationship intelligence reasoner. "
    "Given a candidate signal plus supporting facts and up to 3 precedents, "
    "decide whether the signal is worth surfacing to the operator. "
    "Be specific. Cite numbers, names, and dates when you have them. "
    "Never invent facts. If the signal is weak or noisy, set keep=false. "
    "Output ONLY valid JSON."
)

REASON_USER_TEMPLATE = """Candidate:
{candidate}

Supporting facts (most recent first):
{facts}

Precedents (historical similar situations):
{precedents}

Return exactly this JSON shape, nothing else:
{{
  "keep": true,
  "confidence": 0.0,
  "reason": "one sentence citing the specific signal and why it matters now",
  "action": "one concrete next step the operator should take",
  "subject_importance": 0.0,
  "time_urgency": 0.0,
  "novelty": 0.0,
  "actionability": 0.0
}}

Rules:
- confidence in [0,1]; subject_importance/time_urgency/novelty/actionability each in [0,1].
- actionability = how realistically the operator can do something useful in the next 7 days.
  Reachable contact + clear next step + recent context → high (0.8+).
  Cold/dormant entity, no mutual connection, vague action → low (<0.3).
- keep=false if confidence < 0.35 or the signal duplicates a recent one.
- reason must reference data points in the supporting facts or precedents.
"""
