"""One way to expire a card — and every expiry says why (STEP-06, `yc2_w27_s06 · M24.C1`).

⛔ WHAT WAS WRONG. Eleven places set a card `expired`; nine of them wrote nothing about it
(`speedrun008/YC-II W27/` STEP-06 §8.2): the composite lane four times, the legacy lane twice, the
publisher, the compiled lane and calibration. A card replaced by a fresher one, a card whose rule
cleared and a card nobody looked at in time all reached History the same way — gone, with no line
saying why. The 4 Oct audit counted 15 such cards on the design partner's queue.

⛔ SO THIS MODULE IS THE ONLY WRITER OF THAT STATE. `expire_cards` moves the named cards that are still
open and writes one `card_events` row per card it moved, in the CALLER'S transaction, so the move
and its reason commit or roll back together. `expire_lapsed` is the cron's half: every card still
waiting past its window, across tenants, with the kind and cause L6's ignore-rate has always read
(`window.lapsed`, `expired`). `tests/platform/test_one_way_to_expire_a_card.py` fails on any other SQL
that sets a card `expired`.

⛔ THE CAUSE IS A CLOSED VOCABULARY. History shows it as the card's last line (`deliver/store.history`),
and a free-text reason is a second place a meaning lives. An unknown cause or kind raises before
anything moves.

The kinds an ending writes stay the ones their readers already expect: `card.expired` for the sites
that wrote nothing before; `window.lapsed` (the sweep), `card.dismissed` (the extension) and
`card.retired` (STEP-04's repair) are kept, because History, L6 and the repair's own audit read them.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from sqlalchemy import text

from genios_engine.platform.ids import new_id

#: `CardStore.OPEN_STATES` — a card in any of these is still in front of somebody. Every expiry site
#: used exactly this set; the lapse sweep alone used the narrower `LAPSE_STATES` below.
OPEN_STATES = ("queued", "surfaced", "snoozed", "claimed", "delivered")
#: The sweep never expired a card an agent holds or one already delivered: their own clocks run.
LAPSE_STATES = ("queued", "surfaced", "snoozed")

# ── why a card left ──────────────────────────────────────────────────────────────────────────────
REPLACED = "replaced"              # a newer signal for the same subject replaced the one it carried
RULE_CLEARED = "rule_cleared"      # the rule that fired no longer holds on its subject
BUDGET_HELD = "budget_held"        # a composite no longer true, and today's budget holds its successor
NOT_AUTHORIZED = "not_authorized"  # a composite whose fresh audit no longer authorizes delivery
PLAN_GONE = "plan_gone"            # a composite whose parent plan disappeared
RULE_MUTED = "rule_muted"          # calibration muted the rule (only on a tenant armed by `06` D13)
LAPSED = "expired"                 # its window passed with nobody acting — the sweep's cause, kept
EXTENSION = "extension"            # dismissed from the browser extension
SUBJECT_IS_US = "subject_is_us"    # STEP-04's repair: the card's subject was one of us
CAUSES: frozenset[str] = frozenset({REPLACED, RULE_CLEARED, BUDGET_HELD, NOT_AUTHORIZED, PLAN_GONE,
                                    RULE_MUTED, LAPSED, EXTENSION, SUBJECT_IS_US})

# ── what the event is called ─────────────────────────────────────────────────────────────────────
EXPIRED = "card.expired"
LAPSED_KIND = "window.lapsed"
DISMISSED = "card.dismissed"
RETIRED = "card.retired"
KINDS: frozenset[str] = frozenset({EXPIRED, LAPSED_KIND, DISMISSED, RETIRED})

_EXPIRE = text(
    "update cards set state = 'expired' "
    " where org_id = :o and state = any(:states) "
    "   and (signal_id = any(:signals) or card_id = any(:cards)) "
    "returning card_id, signal_id")

_EXPIRE_LAPSED = text(
    "update cards set state = 'expired' "
    " where state = any(:states) and expires_at < :now "
    "returning card_id, org_id, signal_id")

_EVENT = text(
    "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
    "values (:id, :card, :o, :kind, :cause, :actor, cast(:detail as jsonb))")


def _event(conn, *, card_id: str, org_id: str, kind: str, cause: str, actor: str,
           detail: Mapping | None, signal_id: str | None) -> None:
    conn.execute(_EVENT, {"id": new_id("cev"), "card": card_id, "o": org_id, "kind": kind,
                          "cause": cause, "actor": actor,
                          "detail": json.dumps({**(detail or {}), "signal_id": signal_id},
                                               default=str)})


def expire_cards(conn, *, org_id: str, cause: str, signal_ids: Sequence[str] = (),
                 card_ids: Sequence[str] = (), kind: str = EXPIRED, actor: str = "system",
                 detail: Mapping | None = None,
                 states: Sequence[str] = OPEN_STATES) -> list[str]:
    """Expire this tenant's still-open cards of `signal_ids` and `card_ids`; one event each, saying why.

    Returns the ids of the cards it moved — a card already decided, or another tenant's, is neither
    moved nor given an event.
    """
    if cause not in CAUSES:
        raise ValueError(f"unknown expiry cause {cause!r}; add it to platform/card_lifecycle.CAUSES")
    if kind not in KINDS:
        raise ValueError(f"unknown expiry kind {kind!r}; add it to platform/card_lifecycle.KINDS")
    signals, cards = [str(s) for s in signal_ids], [str(c) for c in card_ids]
    if not signals and not cards:
        return []
    moved = conn.execute(_EXPIRE, {"o": org_id, "states": list(states), "signals": signals,
                                   "cards": cards}).fetchall()
    for row in moved:
        _event(conn, card_id=row.card_id, org_id=org_id, kind=kind, cause=cause, actor=actor,
               detail=detail, signal_id=row.signal_id)
    return [row.card_id for row in moved]


def expire_lapsed(conn, *, now) -> list[tuple[str, str]]:
    """The cron's half: every card still waiting past its window, every tenant — `window.lapsed`.

    Returns `(card_id, org_id)` for each card it moved.
    """
    moved = conn.execute(_EXPIRE_LAPSED, {"states": list(LAPSE_STATES), "now": now}).fetchall()
    for row in moved:
        _event(conn, card_id=row.card_id, org_id=row.org_id, kind=LAPSED_KIND, cause=LAPSED,
               actor="system", detail=None, signal_id=row.signal_id)
    return [(row.card_id, row.org_id) for row in moved]
