"""Plays as the delegation verbs use them — SCREEN_INTEL_P6_BUILD §3.2 (frozen).

The vocabulary (ids, schemas, strict validator, words, frozen request bytes, the `delegate` action)
is `contracts/plays.py` and the agent lookup is `platform/agent_plays.py`, so layer-4 moment
producers use them without importing up. This module adds the one layer-5 concern: evidence
travels to an agent only through P2 fact visibility (`context/fact_visibility`).
"""
from __future__ import annotations

from typing import Any, Iterable

from genios_engine.contracts.plays import (PLAYS, PLAY_FOLLOW_UP, PLAY_REASSIGN,  # noqa: F401
                                           PLAY_RESCHEDULE, SCHEMAS, body_sha256,
                                           delegate_action, instruction, iso_utc, request_body,
                                           request_document, reschedule_windows, summary,
                                           validate)
from genios_engine.platform.agent_plays import agents_by_play, select_agent  # noqa: F401


def request_evidence(conn, org_id: str, evidence: Iterable[Any], audience: Iterable[str] | None,
                     *, limit: int = 20) -> list[dict]:
    """`evidence` minus every item naming a (node, field) whose active fact is PRIVATE to
    principals `audience` does not cover. An empty audience (an agent bound to nobody) reads no
    private fact at all — the conservative default."""
    from genios_engine.context.fact_visibility import PRIVATE, audience_may_read, private_fact_index
    private = private_fact_index(conn, org_id)
    who = [a for a in (audience or ()) if a]
    out: list[dict] = []
    for item in evidence or ():
        if not isinstance(item, dict):
            continue
        fields = private.get(str(item.get("node_id") or "")) or {}
        field = item.get("field")
        if field and field in fields and not audience_may_read(PRIVATE, fields[field], who):
            continue
        out.append(dict(item))
        if len(out) >= limit:
            break
    return out


__all__ = ["PLAYS", "PLAY_FOLLOW_UP", "PLAY_REASSIGN", "PLAY_RESCHEDULE", "SCHEMAS",
           "agents_by_play", "body_sha256", "delegate_action", "instruction", "iso_utc",
           "request_body", "request_document", "request_evidence", "reschedule_windows",
           "select_agent", "summary", "validate"]
