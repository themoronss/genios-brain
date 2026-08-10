from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from genios_engine.capture.gate.context import GateContext
from genios_engine.contracts.prepared_content import PreparedContent


@dataclass
class RelevanceVerdict:
    relevant: bool
    relevance: float
    domains: list[str] = field(default_factory=list)
    reason: str | None = None
    # What the gate should DO with this verdict. "" lets the gate fall back to the legacy
    # rule (relevant→route, else park). The LLM classifier sets it explicitly so it can
    # DROP confident junk (the deterministic classifier never drops — it only parks).
    disposition: str = ""            # "" | "keep" | "park" | "drop"


class RelevanceClassifier(Protocol):
    """S2 relevance gate (defense-in-depth). The gate slot is identical whether this
    is deterministic or an LLM — at LLM-integration time we swap in a temp-0 classifier
    and NOTHING else in the pipeline changes."""

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict: ...


_BUSINESS = re.compile(
    r"\b(deal|pricing|contract|invoice|payment|meeting|proposal|budget|renewal|issue|"
    r"ticket|demo|quote|order|refund|escalat\w*|cancel\w*|approv\w*|sign|overdue|"
    r"security|compliance|legal|kitna|payment pending)\b",
    re.I,
)


class DeterministicRelevanceClassifier:
    """Safe default + dev impl — no LLM. Known sender or business keyword → relevant;
    otherwise low relevance (parks for review, never a hard drop)."""

    name = "relevance-deterministic-1"

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        if ctx.sender_known:
            return RelevanceVerdict(True, 0.90, reason="known_sender")
        text = prepared.clean_text if prepared else (ctx.raw.get("snippet") or "")
        if _BUSINESS.search(text):
            return RelevanceVerdict(True, 0.70, reason="business_keyword")
        return RelevanceVerdict(False, 0.30, reason="no_business_signal")

_GATE_PROMPT = """You are a junk filter deciding whether ONE email should enter a company's \
business-intelligence knowledge graph. This is the LAST filter before storage.

The graph is for REAL work relationships and decisions. The test: is a specific HUMAN writing to \
this person, or is there a live deal / meeting / interview / commitment / customer / prospect / \
vendor / support thread they must personally READ or REPLY to?

DROP when it is an automated, one-to-many, or self-service message with no human expecting a \
reply — even if it contains numbers, money, or PDF attachments:
- marketing / promotions / offers / product announcements / newsletters / digests
- OTP / verification / login codes, password resets, social-network reminders
- subscription / plan / account notices, bank / broker / wallet / payment-app STATEMENTS, \
auto-receipts, statement PDFs
- marketplace or platform listings & alerts (property, jobs, shopping, rides, etc.)
- automated matchmaking / profile-digest emails ("you matched", co-founder or candidate profile \
lists) and repeated event-platform auto-pings ("event updated") — a digest of many people or event \
notifications, not one person writing to you
An automated account statement or a marketplace notification is NOT business intelligence, \
however much data it carries — there is no relationship and nothing to act on.

KEEP when a real named person is corresponding, or there is a genuine deal, meeting, interview, \
commitment, question, complaint, or an invoice/contract from a vendor they actually work with — \
anything a founder must personally read or reply to. When genuinely torn between a real person \
and an automated system, KEEP (a wrong drop loses real signal; a wrong keep is only scored down).

Return ONLY JSON, no prose:
{{"disposition":"keep"|"drop","relevance":0.0-1.0,"reason":"<=6 words"}}

SOURCE: {source}
EMAIL:
{content}"""


class LLMRelevanceClassifier:
    """S2 LLM junk-gate — the single reliable filter that keeps noise OUT of the graph.

    Runs only on emails that already survived the cheap deterministic rules (spam/promotions/
    bulk are gone by now), and never on a known sender (whitelisted, no spend). It is the ONE
    place allowed to DROP on judgment; it FAILS OPEN (keep) on any LLM/parse error so an infra
    hiccup never silently discards real mail. `llm` is any object exposing `.call(prompt, max_tokens=)`.
    """

    name = "relevance-llm-1"

    def __init__(self, llm) -> None:
        self._llm = llm

    def classify(self, ctx: GateContext, prepared: PreparedContent | None) -> RelevanceVerdict:
        if ctx.sender_known:                                  # already trusted — never spend a call
            return RelevanceVerdict(True, 0.90, disposition="keep", reason="known_sender")
        subject = ctx.raw.get("subject") or ""
        body = (prepared.clean_text if prepared else (ctx.raw.get("snippet") or ""))[:1500]
        content = f"Subject: {subject}\n{body}".strip()
        if not content:                                       # nothing to judge → don't drop blind
            return RelevanceVerdict(True, 0.50, disposition="keep", reason="empty_pass")
        res = self._llm.call(_GATE_PROMPT.format(source=ctx.event.source, content=content),
                             max_tokens=120)
        if not res.ok:                                        # fail OPEN — never lose mail on an error
            return RelevanceVerdict(True, 0.50, disposition="keep", reason="gate_llm_unavailable")
        p = res.parsed
        disp = str(p.get("disposition", "keep")).lower()
        if disp not in ("keep", "drop"):
            disp = "keep"
        try:
            rel = max(0.0, min(1.0, float(p.get("relevance", 0.5) or 0.5)))
        except (TypeError, ValueError):
            rel = 0.5
        return RelevanceVerdict(relevant=(disp == "keep"), relevance=rel, disposition=disp,
                                reason=str(p.get("reason", "") or "")[:60])
