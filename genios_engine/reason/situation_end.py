"""How each active situation ended — one reader, one answer per situation (STEP-06).

`yc2_w27_s06 · M24.C2.L-logic.V2.U02`. "Why did this situation never become a card?" used to be an
afternoon of tracing: three ledgers answered parts of it (the admission gate's, the change gate's and,
from STEP-06, `situation_outcomes`) and nothing answered for a situation on a domain the tenant never
switched on — 126 of the golden set's 227 active situations had no record anywhere of how they ended
(`speedrun008/YC-II W27/` STEP-06 §8.1, 03 F77). This reader names exactly one end for each:

  no_corpus    no corpus serves its domain — it can never be live (`fundraising`, `general`)
  not_live     its domain is not activated for the tenant — measured in shadow, never delivered
  held         the admission gate held it; the reasons are the ledger's
  rejected     the admission gate rejected it; the reasons are the ledger's
  carded       a card for it is open
  decided      a decision was made; the detail is what the change gate recorded
  stopped      admitted, then stopped before a decision; the detail is the outcome and its reason
  unrecorded   live, and nothing says how it ended — what the receipt counts, and what must be 0

NOTHING HERE DECIDES ANYTHING: every field was written by the layer that made the call. A shadow or
unroutable situation's end is a fact of the tenant's activation, read here rather than written every
sweep (STEP-06 §8.3).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

NO_CORPUS = "no_corpus"
NOT_LIVE = "not_live"
HELD = "held"
REJECTED = "rejected"
CARDED = "carded"
DECIDED = "decided"
STOPPED = "stopped"
UNRECORDED = "unrecorded"
ENDS: frozenset[str] = frozenset({NO_CORPUS, NOT_LIVE, HELD, REJECTED, CARDED, DECIDED, STOPPED,
                                  UNRECORDED})

#: `CardStore.OPEN_STATES` — a card in any of these is still in front of somebody.
_OPEN = ("queued", "surfaced", "snoozed", "claimed", "delivered")

_SITUATIONS = text(
    "select s.situation_id, s.domain, s.situation_type, "
    "       a.decision_id, a.outcome as admission, a.reasons, "
    "       o.outcome as stop, o.reason as stop_reason, "
    "       (select string_agg(f.outcome, ',' order by f.subject_key) "
    "          from reasoning_fingerprints f "
    "         where f.org_id = s.org_id and f.subject_key like s.situation_id || '|%') as gate, "
    "       (select string_agg(k.card_id, ',' order by k.card_id) "
    "          from signals g join cards k on k.signal_id = g.signal_id and k.org_id = g.org_id "
    "         where g.org_id = s.org_id and g.situation_id = s.situation_id "
    "           and k.state = any(:open)) as cards "
    "  from context_situations s "
    "  left join lateral (select d.decision_id, d.outcome, d.reasons "
    "                       from situation_admission_decisions d "
    "                      where d.org_id = s.org_id and d.situation_id = s.situation_id "
    "                      order by d.decided_at desc, d.decision_id desc limit 1) a on true "
    "  left join situation_outcomes o on o.org_id = s.org_id and o.decision_id = a.decision_id "
    " where s.org_id = :o and s.status in ('active', 'partial') "
    " order by s.situation_id")


@dataclass(frozen=True, slots=True)
class SituationEnd:
    situation_id: str
    domain: str
    situation_type: str
    end: str
    detail: tuple[str, ...] = ()


def _reasons(raw) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(str(r) for r in raw) if isinstance(raw, (list, tuple)) else (str(raw),)


def end_of(row, *, live_domains: frozenset[str], forced: bool = False) -> SituationEnd:
    """One situation's end, from one row of `_SITUATIONS` and the tenant's activated corpora.

    Live or not is `domain_shadow.live_lane`'s answer, not a second opinion: the compiled lane asks
    the same function with the same two switches.
    """
    from genios_engine.reason.domain_shadow import l3_domain_for, live_lane

    sid, domain = str(row.situation_id), str(row.domain or "")
    kind = str(row.situation_type or "")
    corpus = l3_domain_for(domain)
    if corpus is None:
        return SituationEnd(sid, domain, kind, NO_CORPUS, (domain,))
    if not live_lane(forced=forced, domain=corpus, activated=live_domains):
        return SituationEnd(sid, domain, kind, NOT_LIVE, (corpus,))
    if row.cards:
        return SituationEnd(sid, domain, kind, CARDED, tuple(row.cards.split(",")))
    if row.admission == "hold":
        return SituationEnd(sid, domain, kind, HELD, _reasons(row.reasons))
    if row.admission == "reject":
        return SituationEnd(sid, domain, kind, REJECTED, _reasons(row.reasons))
    if row.admission == "admit":
        if row.stop and row.stop != "decided":
            return SituationEnd(sid, domain, kind, STOPPED,
                                (row.stop,) + ((row.stop_reason,) if row.stop_reason else ()))
        if row.stop == "decided":
            return SituationEnd(sid, domain, kind, DECIDED,
                                (row.stop_reason,) if row.stop_reason else ())
        if row.gate:                     # decided before `situation_outcomes` existed
            return SituationEnd(sid, domain, kind, DECIDED, tuple(row.gate.split(",")))
    return SituationEnd(sid, domain, kind, UNRECORDED)


def situation_ends(conn, org_id: str) -> list[SituationEnd]:
    """Every active situation of one tenant, each with exactly one end."""
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.l3_activation import activated_domains

    live = frozenset(activated_domains(conn.engine, org_id))
    forced = bool(get_settings().use_domain_compiler)
    rows = conn.execute(_SITUATIONS, {"o": org_id, "open": list(_OPEN)}).fetchall()
    return [end_of(r, live_domains=live, forced=forced) for r in rows]
