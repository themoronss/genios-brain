"""Neural signal detectors — turn the per-entity signals the ingest extract()
emits (sentiment, buying_intent, ball_in_court, domain) into SignalUpserts.

NO extra LLM call: these ride on the SAME Haiku extraction already run at ingest
(0-credit). This module only PARSES that output; the prompt + dataclass extension
that makes extract() emit these fields lives in core/worldmodel/extract.py.
"""

from __future__ import annotations

from core.signals.types import (
    SIG_BALL_IN_COURT,
    SIG_BUYING_INTENT,
    SIG_COMMITMENT,
    SIG_COMPETITOR,
    SIG_DOMAIN,
    SIG_OBJECTION,
    SIG_SENTIMENT,
    SignalUpsert,
)

_VALID_DOMAINS = {
    "investor", "customer", "hire", "partner", "team", "vendor", "advisor", "other",
}


def _clampf(x, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.0


def signals_from_extraction(
    *,
    org_id: str,
    subject_node_id: str,
    subject_name: str,
    extracted_signals: dict | None,
    source_item_id: str | None = None,
) -> list[SignalUpsert]:
    """extracted_signals e.g. {"sentiment": -0.3, "buying_intent": 0.8,
    "ball_in_court": true, "domain": "investor"}. Missing keys are skipped."""
    s = extracted_signals or {}
    ev = [source_item_id] if source_item_id else []
    base = dict(
        org_id=org_id,
        subject_node_id=subject_node_id,
        subject_name=subject_name,
        produced_by="neural:ingest",
        evidence=ev,
    )
    out: list[SignalUpsert] = []

    if s.get("sentiment") is not None:
        out.append(SignalUpsert(signal_type=SIG_SENTIMENT, value_num=_clampf(s["sentiment"], -1.0, 1.0), half_life_days=21, **base))
    if s.get("buying_intent") is not None:
        out.append(SignalUpsert(signal_type=SIG_BUYING_INTENT, value_num=_clampf(s["buying_intent"], 0.0, 1.0), half_life_days=14, **base))
    if s.get("ball_in_court") is not None:
        # boolean "do you owe the reply" — crisp, no decay (staleness is captured
        # by engagement/momentum instead, so rules can check `>= 1` cleanly).
        out.append(SignalUpsert(signal_type=SIG_BALL_IN_COURT, value_num=1.0 if s["ball_in_court"] else 0.0, **base))
    dom = s.get("domain")
    if dom and str(dom).lower() in _VALID_DOMAINS:
        out.append(SignalUpsert(signal_type=SIG_DOMAIN, value_cat=str(dom).lower(), **base))

    # Text signals — the counterpart's open objection, what WE still owe them, and
    # any competitor named. value_cat carries the short phrase so downstream can
    # NAME it (anti-"naam ka"). Capped so a runaway phrase can't bloat the row.
    for tkey, sigtype in (
        ("open_objection", SIG_OBJECTION),
        ("open_commitment", SIG_COMMITMENT),
        ("competitor", SIG_COMPETITOR),
    ):
        tv = s.get(tkey)
        if isinstance(tv, str) and tv.strip():
            out.append(SignalUpsert(signal_type=sigtype, value_cat=tv.strip()[:120], **base))

    return out
