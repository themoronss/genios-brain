"""
Phase 6: Personalised retention offer composition prompt.

Inputs: churn signals + the org's recent friction (sync errors, complaints,
feature usage gaps, plan tier). Output: a short, specific, no-template
offer the user actually receives.

Strict JSON output so callers can route by tier (nudge / offer / rescue).
"""

RETENTION_SYSTEM = (
    "You compose retention offers that don't feel like marketing. "
    "Lead with empathy for the SPECIFIC friction the user hit. Reference "
    "concrete signals (a sync error, a slow feature, an unanswered ticket). "
    "Never use words like 'valued customer'. Match the tier: a nudge is a "
    "tip; an offer is a discount or month-free; a rescue is a personal note. "
    "Output ONLY the JSON shape requested — no preamble."
)

RETENTION_USER_TEMPLATE = """Tier: {tier}        # nudge | offer | rescue
Plan: {plan}
Churn signals (most-pressing first):
{signals}

Recent friction the user mentioned or hit:
{friction}

Compose a retention message. Return EXACTLY this JSON:
{{
  "subject": "short subject line (max 60 chars)",
  "body": "2-4 sentences. Specific. Empathetic for that pain point. End with one concrete next step.",
  "offer_payload": {{
    "type": "tip | discount | free_period | personal_call",
    "value": "e.g. '3 months free', '20% off Startup tier', 'founder 1:1'",
    "expires_in_days": 7
  }},
  "channel": "in_app_modal | email | claude_proactive_alert"
}}

Rules:
- nudge → channel='claude_proactive_alert', offer_payload.type='tip'
- offer → channel='in_app_modal' OR 'email', offer is discount/free_period
- rescue → channel='email', offer_payload.type='personal_call', body
  written as if from the founder personally
- Mention the SPECIFIC signal in the body (e.g. "We saw your Slack sync
  failed 4 times this week — we shipped a fix yesterday"). Generic =
  rejected.
"""
