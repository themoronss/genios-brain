"""Attention — how much of GeniOS a captured mail gets, and why (STEP-03, the gate keeps everything).

The gate used to DELETE a mail the noise rules (N-01 … N-10) or the AI filter (`llm_junk`) called
noise: a drop kept no body, so a Boardy introduction carrying an unsubscribe header, or a government
portal's update filed under Promotions, was gone for good (`speedrun008/YC-II W27/` STEP-03 §1, §8).
It now ARCHIVES it — the mail is kept, encrypted, for 180 days (06 D4) and read by no model — and
every kept mail carries a tier and the reason for it:

    deep      read: emitted, or parked waiting to be read
    skim      declared for STEP-07, which assigns it from the company brief; nothing writes it yet
    archive   kept, unread: what the noise rules and the AI filter would have deleted

The schema closes the same vocabulary (migration 0192's check). `attention_for` is the one place an
outcome becomes a tier, so the pipeline and any reader cannot disagree about it.
"""
from __future__ import annotations

DEEP = "deep"
SKIM = "skim"
ARCHIVE = "archive"
ATTENTIONS: tuple[str, ...] = (DEEP, SKIM, ARCHIVE)

#: The outcome an archived mail lands with, beside `emitted`, `parked` and `dropped`.
ARCHIVED = "archived"


def attention_for(outcome: str, gate) -> tuple[str | None, str | None]:
    """(tier, reason) for one gate verdict, or (None, None) for an outcome that is not a kept mail.

    archived → archive, with the rule that archived it; emitted → deep, with what let it through
    (a whitelist code, N-05 for an availability notice, `structured`, or `passed`); parked → deep,
    with the park code — it is waiting to be read.
    """
    if outcome == ARCHIVED:
        return ARCHIVE, gate.reason_code
    if outcome == "emitted":
        if gate.whitelist_code:
            return DEEP, gate.whitelist_code
        if gate.availability:
            return DEEP, "N-05"
        if gate.route == "structured":
            return DEEP, "structured"
        return DEEP, "passed"
    if outcome == "parked":
        return DEEP, gate.reason_code
    return None, None
