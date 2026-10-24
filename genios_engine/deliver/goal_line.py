"""The goals a card's work moves, on the card (GeniOS-012 S31.U1; `speedrun008/GeniOS-012/07-GOALS.md`).

A card carries the LIVE goals (a human made them real) its work moves, as `cards.goal_refs` — `[{ref, statement}]`:

  * a goal PROPOSED FOR the card's file (`company_goals.subject_ref = file:<id>`) — the work a goal was born from
    moves it, so a goal the founder approves after its file was judged reaches the card with no new judgment;
  * a goal the card's file SERVES (`company_goals.evidence_refs` holds `file:<id>`, G012 H-19) — its judgment proposed
    the same goal in other words, or said its move bears on it while the goal waited for the founder;
  * a goal a judgment's `GoalImpact` LINKED to one of the file's admitted situations, or to the card's own
    situation (`goal_situation_links`, S30.U1).

Set-based, once at the end of a card build, over the org's open cards. Nothing here is a model's.
"""
from __future__ import annotations

from sqlalchemy import text

#: The open card states a goal line is kept current on.
OPEN_STATES = ("queued", "surfaced", "snoozed", "claimed")

_REFRESH = text(
    "with live as ("
    "  select distinct on (goal_id) goal_id, statement, status, subject_ref, evidence_refs from company_goals"
    "   where org_id = :o order by goal_id, revision desc), "
    "goals_of as ("
    "  select k.card_id, coalesce(jsonb_agg(distinct jsonb_build_object('ref', 'goal:' || g.goal_id, "
    "         'statement', g.statement)) filter (where g.goal_id is not null), '[]'::jsonb) as refs"
    "    from cards k left join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id"
    "    left join live g on g.status in ('approved', 'active') and ("
    "         g.subject_ref = 'file:' || k.file_id"
    "      or g.evidence_refs @> jsonb_build_array('file:' || k.file_id)"
    "      or exists (select 1 from goal_situation_links l where l.org_id = k.org_id and l.goal_id = g.goal_id"
    "                  and (l.situation_id = s.situation_id"
    "                       or l.situation_id in (select c.situation_id from context_situations c"
    "                                              where c.org_id = k.org_id and c.anchor_node_id = k.file_id))))"
    "   where k.org_id = :o and k.state = any(:states)"
    "   group by k.card_id) "
    "update cards k set goal_refs = goals_of.refs from goals_of"
    " where k.card_id = goals_of.card_id and k.goal_refs is distinct from goals_of.refs")


def refresh_card_goals(conn, org_id: str) -> int:
    """Bring every open card's `goal_refs` up to the live goals its work moves. Returns the cards that changed."""
    return conn.execute(_REFRESH, {"o": org_id, "states": list(OPEN_STATES)}).rowcount or 0


__all__ = ["OPEN_STATES", "refresh_card_goals"]
