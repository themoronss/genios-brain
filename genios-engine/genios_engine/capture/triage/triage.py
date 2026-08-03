from __future__ import annotations

import re

from genios_engine.capture.gate.context import GateContext
from genios_engine.contracts.prepared_content import PreparedContent

# Triage = PROCESSING ORDER only (which event gets worked first), not user priority
# (that is L3). Uses L1-cheap deterministic signals only — no graph data, no LLM.

_URGENT = re.compile(
    r"\b(urgent|asap|immediately|escalat\w*|cancel\w*|sev\s?1|outage|"
    r"legal notice|jaldi|turant)\b",
    re.I,
)
_DEADLINE = re.compile(
    r"\b(by|before|eod|tomorrow|today|deadline|friday|monday|tuesday|"
    r"wednesday|thursday|kal|parso|aaj)\b",
    re.I,
)


def triage_lane(ctx: GateContext, prepared: PreparedContent | None) -> str:
    text = (prepared.clean_text if prepared else (ctx.raw.get("snippet") or "")).lower()
    score = 0
    if _URGENT.search(text):
        score += 45
    if _DEADLINE.search(text):
        score += 25
    if ctx.sender_known:
        score += 15
    if "?" in text:
        score += 10
    if ctx.is_structured:
        score = max(score, 30)          # structured business events: at least normal

    if score >= 60:
        return "P0"       # immediate / high-risk, preempts queue
    if score >= 35:
        return "P1"       # priority
    if score >= 15:
        return "P2"       # normal
    return "P3"           # low-signal / digest / backfill
