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

# When the LLM classifier is wired (LLM-integration step), it implements the same
# RelevanceClassifier interface (temp-0, relevance + domains + evidence). Slot below
# in gate.run_gate stays unchanged.
