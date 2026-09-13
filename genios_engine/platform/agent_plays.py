"""Which agent runs a play — one small read over `agent_registry`, cross-cutting so the moment
producers (layer 4) and the delegation verbs (layer 5) share it without an upward import
(SCREEN_INTEL_P6_BUILD §3.5). An agent qualifies when it is ACTIVE, has a webhook, and lists the
play in `allowed_actions`; the default agent first, then by id."""
from __future__ import annotations

from sqlalchemy import text

from genios_engine.contracts.plays import PLAYS


def select_agent(conn, org_id: str, play: str, agent_id: str | None = None) -> str | None:
    """The agent that runs `play` for this org; `agent_id` narrows to that one (None when it does
    not qualify). One statement."""
    return conn.execute(text(
        "select agent_id from agent_registry where org_id = :o and status = 'active' "
        "and :p = any(allowed_actions) and coalesce(webhook_url, '') <> '' "
        "and (cast(:a as text) is null or agent_id = cast(:a as text)) "
        "order by is_default desc, agent_id limit 1"),
        {"o": org_id, "p": play, "a": agent_id}).scalar()


def agents_by_play(conn, org_id: str) -> dict[str, str]:
    """play → the agent `select_agent` would pick, for every play some agent allows. One
    statement — for producers that consider several plays per pass."""
    out: dict[str, str] = {}
    for r in conn.execute(text(
            "select agent_id, allowed_actions from agent_registry where org_id = :o "
            "and status = 'active' and coalesce(webhook_url, '') <> '' "
            "order by is_default desc, agent_id"), {"o": org_id}):
        for play in (r.allowed_actions or ()):
            if play in PLAYS:
                out.setdefault(play, r.agent_id)
    return out


__all__ = ["agents_by_play", "select_agent"]
