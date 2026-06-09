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

_PROMPT_DEFAULT = """You are a permissive relevance filter for a context graph.

The customer has NOT yet told us what their business is, so default to
KEEPING anything that could plausibly matter. Only filter out emails
that are noise for EVERY business:

Answer NO only for:
- OTPs, verification codes, 2FA codes
- security / sign-in alerts ("new device signed in")
- password reset emails
- pure marketing newsletters from public-facing brands
- mailer-daemon / bounce messages

Answer YES for EVERYTHING ELSE — including bank statements, job
applications, invoices, shipping updates, SaaS notifications, support
threads, calendar invites, and ALL human-to-human conversations. When
the customer fills in their business context, the filter becomes more
selective.

Email:
\"\"\"
From: {sender}
Subject: {subject}
Body: {body}
\"\"\"

Answer YES or NO:"""


# When the org tells us what they do, the prompt asks the model to score
# relevance FROM THAT VIEWPOINT. A "thanks for applying" email is junk
# for a sales SaaS but signal for a recruiting agency; the model gets
# to use that context instead of a blanket rule.
_PROMPT_WITH_CONTEXT = """You are a strict relevance filter for a CRM-class memory graph.

The graph belongs to a company described as:
\"\"\"
{business_context}
\"\"\"

Answer ONLY with: YES or NO

YES = this email is meaningful business signal for the company described above.
      Real conversations with their customers, prospects, vendors, candidates,
      partners; deal updates; meeting requests; commitments; events that affect
      their pipeline or operations.

NO  = noise for the company above. Universal junk (OTPs, sign-in alerts,
      password resets, newsletters, marketing drips, generic welcome emails)
      OR transactional/automated emails that are NOT what the company
      ABOVE does (e.g. bank statements ARE noise for a sales SaaS but ARE
      signal for a fintech; job-application emails ARE noise for a sales
      SaaS but ARE signal for a recruiting agency).

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


def is_business_relevant(
    *,
    sender: str,
    subject: str,
    body: str,
    org_id: str | None = None,
    business_context: str | None = None,
) -> GateLLMDecision:
    """Single Haiku call, returns (keep, reason).

    Caller can pass either `business_context` directly OR an `org_id` we
    look it up from. If both are missing we fall back to the
    generic-business prompt — works for first-connect before the user
    has filled the field in Settings.
    """
    if _LLM_GATE_DISABLED:
        return GateLLMDecision(True, "gate_disabled")
    if not settings.ANTHROPIC_API_KEY:
        return GateLLMDecision(True, "no_api_key")

    ctx = (business_context or "").strip()
    if not ctx and org_id:
        ctx = (_lookup_business_context(org_id) or "").strip()

    if ctx:
        prompt = _PROMPT_WITH_CONTEXT.format(
            business_context=ctx[:500],
            sender=(sender or "")[:200],
            subject=(subject or "")[:200],
            body=(body or "")[:_MAX_GATE_INPUT_CHARS],
        )
    else:
        prompt = _PROMPT_DEFAULT.format(
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

    # Cost row — log under the actual org when we have one so the
    # founder's /v1/usage/llm endpoints can attribute gate spend to a
    # tenant. Falls back to 'system' for callers that haven't threaded
    # org_id yet (e.g. ad-hoc smoke tests).
    try:
        from core.foundations.llm_costs import record_llm_call, usage_extract
        it, ot = usage_extract(resp)
        record_llm_call(
            org_id=org_id or "system",
            model=settings.ANTHROPIC_HAIKU_MODEL,
            purpose="other",  # 'noise_gate' once Purpose Literal is widened
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


# Tiny in-process cache keyed by org_id. The gate fires once per record
# during a batch sync (typically 15-50 records back-to-back), so even a
# few-second TTL kills the per-batch DB hit. We do NOT cache across
# processes — Settings UI edits show up in the next batch's first call.
_ORG_CTX_CACHE: dict[str, tuple[float, str | None]] = {}
_ORG_CTX_TTL_S = 60.0


def _lookup_business_context(org_id: str) -> str | None:
    """Fetch orgs.business_context. Returns None on miss / lookup failure.

    Failures here are silent on purpose — we'd rather fall back to the
    generic gate prompt than block the whole sync because the v1 DB
    pool blipped.
    """
    import time as _t

    now = _t.monotonic()
    hit = _ORG_CTX_CACHE.get(org_id)
    if hit is not None and now - hit[0] < _ORG_CTX_TTL_S:
        return hit[1]

    try:
        from sqlalchemy import text as _text

        from core.foundations.db import get_session

        with get_session() as s:
            row = s.execute(
                _text("SELECT business_context FROM orgs WHERE id = :o"),
                {"o": org_id},
            ).fetchone()
            ctx = (row.business_context or "").strip() if row else ""
            ctx = ctx or None
    except Exception as e:
        log.warning("llm_gate_ctx_lookup_failed", org_id=org_id, error=str(e))
        ctx = None

    _ORG_CTX_CACHE[org_id] = (now, ctx)
    return ctx
