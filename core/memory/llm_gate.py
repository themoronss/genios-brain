"""LLM-backed business-value gate.

Runs AFTER pattern noise_gate (so it only sees what survived the cheap
checks). One tiny Haiku call per record asks "is this a business
conversation worth tracking?" with a yes/no contract.

Why it's worth the cost:
  - Pattern noise_gate catches ~70% of obvious junk but misses domain-
    specific traps (HR rejections from real-looking senders, SaaS
    onboarding emails, varied bank-statement senders, etc).
  - One Haiku call ≈ $0.0001 (≤50 input + ≤5 output tokens). The full
    extract Haiku call (capped at 4096 output) is ~$0.003. So killing
    one junk extract pays for ~30 gate calls.
  - Customer NEVER pays for the gate. It's our cost. The customer pays
    only for records that pass and get extracted.

Fail-soft: any LLM error → keep the record (we'd rather over-extract
once than block a legitimate email on a transient error).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.foundations.config import settings
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

# Operator escape hatch. Disable when debugging or comparing baselines.
_LLM_GATE_DISABLED = os.getenv("GENIOS_LLM_GATE_DISABLED", "0") == "1"

# Cap input the LLM sees so the gate is always cheap. Subject + first chunk
# of body is enough to judge business value; the full body still goes to the
# real extractor downstream.
_MAX_GATE_INPUT_CHARS = 800

_PROMPT = """You are a strict business-relevance filter for a CRM-class memory graph.

Answer ONLY with: YES or NO

Mark NO for:
- bank / credit-card statements, balance alerts, EMI reminders
- payment / invoice / receipt / refund / transaction notifications
- order / shipping / delivery updates from e-commerce
- "thanks for applying", interview rejections, job-board alerts
- SaaS welcome / onboarding / trial-ended / drip marketing
- newsletters, weekly/daily digests, product announcements
- security alerts (sign-in from new device, password reset)
- OTP, verification codes, 2FA
- government / regulatory notices, tax statements, utility bills

Mark YES for:
- human-to-human conversations
- real meeting requests, agenda discussions, deal negotiation
- proposal / contract / quote correspondence
- customer support tickets where the customer typed a question
- direct calendar invites between named people
- code review or PR comments authored by humans

Email:
\"\"\"
From: {sender}
Subject: {subject}
Body: {body}
\"\"\"

Answer:"""


@dataclass(frozen=True)
class GateLLMDecision:
    keep: bool
    reason: str


def is_business_relevant(*, sender: str, subject: str, body: str) -> GateLLMDecision:
    """Single Haiku call, returns (keep, reason).

    Caller is responsible for swallowing errors — this function logs and
    raises so the caller can decide whether to fail open or closed.
    Default operator behaviour is fail-open (keep) — see caller in
    sync_runner.
    """
    if _LLM_GATE_DISABLED:
        return GateLLMDecision(True, "gate_disabled")
    if not settings.ANTHROPIC_API_KEY:
        return GateLLMDecision(True, "no_api_key")

    prompt = _PROMPT.format(
        sender=(sender or "")[:200],
        subject=(subject or "")[:200],
        body=(body or "")[:_MAX_GATE_INPUT_CHARS],
    )

    from anthropic import Anthropic
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=settings.ANTHROPIC_HAIKU_MODEL,
        max_tokens=4,  # YES or NO + maybe punctuation
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip().upper()

    # Cost row — separate purpose so we can see how much the gate
    # itself costs vs the main extract that's downstream.
    try:
        from core.foundations.llm_costs import record_llm_call, usage_extract
        it, ot = usage_extract(resp)
        # org_id isn't threaded into noise_gate yet; record without it
        # for now and we'll wire org propagation in a follow-up if the
        # gate's total cost is non-trivial.
        record_llm_call(
            org_id="system",
            model=settings.ANTHROPIC_HAIKU_MODEL,
            purpose="other",
            input_tokens=it, output_tokens=ot,
        )
    except Exception:
        pass

    if raw.startswith("YES"):
        return GateLLMDecision(True, "llm_yes")
    if raw.startswith("NO"):
        return GateLLMDecision(False, "llm_no")
    # Garbled response — fail open
    log.warning("llm_gate_unexpected_response", raw=raw[:30])
    return GateLLMDecision(True, "llm_unparseable")
