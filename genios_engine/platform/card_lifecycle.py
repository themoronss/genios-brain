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

⛔ AND THE ONE WRITER OF A CARD'S SIGNAL (STEP-14, `yc2_w27_s14` M42.C1.L-data.V1.U03). A file's card lives
(`migrations/0220`): the file's next decision or question is a VERSION of it, never a second card.
`version_card` re-points the card at the file's newest signal — open, or closed by the clock, a replacement or a
clearing (reopened, s14-D2); never one the founder decided (acted, resolved, dismissed, retired) nor one an agent
holds (it waits) — moves its window to the new signal's, and writes ONE `card.versioned` event carrying the
version (`contracts/card_version`): its words, the words before, the signal it carried and the one it came from,
the change and whether it is material — in the caller's transaction. Its words are the card store's to write
(`deliver/store.CardStore.version_card`). `file_card` reads which card a file's next version goes to, by the same
rule. `tests/platform/test_one_way_to_version_a_card.py` fails on any other SQL that sets `cards.signal_id`.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import text

from genios_engine.contracts.card_version import CREATED, CardVersion
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
    "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
    "values (:id, :card, :o, :kind, :cause, :actor, cast(:detail as jsonb), "
    "        coalesce(cast(:at as timestamptz), now()))")


def _event(conn, *, card_id: str, org_id: str, kind: str, cause: str, actor: str,
           detail: Mapping | None, signal_id: str | None, at=None) -> None:
    """One event — at the database's clock, or (`at`) at the instant the caller decided it."""
    conn.execute(_EVENT, {"id": new_id("cev"), "card": card_id, "o": org_id, "kind": kind,
                          "cause": cause, "actor": actor, "at": at,
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


# ── the one writer of a card's signal (STEP-14) ─────────────────────────────────────────────────────────────
#: The event a version writes — not an ending, so not one of `KINDS`.
VERSIONED = "card.versioned"
#: A card the founder decided stays decided: by its state, or — its state `expired` — by how it ended.
DECIDED_STATES = ("acted", "resolved")
DECIDING_KINDS = (DISMISSED, RETIRED)

#: Nobody decided it: not acted or resolved, never dismissed from the extension or retired by STEP-04's repair.
_UNDECIDED = (
    "k.state <> all(:decided) and k.resolved_at is null "
    "and not exists (select 1 from card_events e where e.org_id = k.org_id and e.card_id = k.card_id "
    "                and e.kind = any(:deciding))")
#: An agent holds it: claimed, or an agent's claim on it neither released nor finished.
_HELD = (
    "(k.state = 'claimed' or exists (select 1 from agent_claims ac where ac.org_id = k.org_id "
    " and ac.card_id = k.card_id and ac.released_at is null and ac.result is null))")

_FILE_CARD = text(
    "select k.card_id, k.signal_id, k.version, k.state, " + _HELD + " as held from cards k "
    " where k.org_id = :o and k.file_id = :f and " + _UNDECIDED +
    " order by k.created_at desc, k.card_id desc limit 1")

_VERSION = text(
    "with before as (select card_id, signal_id, state from cards where org_id = :o and card_id = :card) "
    "update cards k set signal_id = :signal, version = :version, expires_at = :expires, "
    "       state = case k.state when 'expired' then 'queued' else k.state end "
    # `before` is this tenant's card or nothing, and `card_id` is the key: the join names one row of this tenant.
    "  from before where k.card_id = before.card_id and k.file_id is not null "
    "   and k.version = :version - 1 and not " + _HELD + " and " + _UNDECIDED +
    "   and not exists (select 1 from cards other where other.signal_id = :signal "
    "                   and other.card_id <> k.card_id) "
    "returning before.signal_id as from_signal, before.state as from_state")


@dataclass(frozen=True, slots=True)
class FileCard:
    """The card a file's next version goes to: which, the signal it carries, its version and state — and
    whether an agent holds it (the file's next version then waits)."""
    card_id: str
    signal_id: str
    version: int
    state: str
    held: bool


def _rule() -> dict:
    return {"decided": list(DECIDED_STATES), "deciding": list(DECIDING_KINDS)}


def file_card(conn, *, org_id: str, file_id: str) -> FileCard | None:
    """The file's newest card nobody decided — open, or closed by the clock, a replacement or a clearing.
    None: the file has no such card, and its next decision is a new card."""
    row = conn.execute(_FILE_CARD, {"o": org_id, "f": str(file_id), **_rule()}).first()
    if row is None:
        return None
    return FileCard(card_id=row.card_id, signal_id=row.signal_id, version=int(row.version), state=row.state,
                    held=bool(row.held))


def version_card(conn, *, org_id: str, card_id: str, version: CardVersion, expires_at,
                 actor: str = "system", at=None) -> bool:
    """Move this tenant's file card onto `version.signal_id`, its window to `expires_at` (the new signal's),
    reopen it if the clock, a replacement or a clearing closed it, and write its one `card.versioned` event — in
    the caller's transaction, at `at`: the instant the version was decided (the pass's evaluation time, the
    press's), so a version is dated by the decision and never by when a database happened to write it. False,
    nothing moved and nothing written: the card is decided, held by an agent, no file's, another tenant's, not at
    the version before this one, or the signal already has a card."""
    if not isinstance(version, CardVersion):
        raise TypeError("a card is versioned by a contracts/card_version.CardVersion")
    if version.change == CREATED:
        raise ValueError("a card is created by its insert, never versioned into being")
    moved = conn.execute(_VERSION, {"o": org_id, "card": card_id, "signal": version.signal_id,
                                    "version": version.version, "expires": expires_at, **_rule()}).first()
    if moved is None:
        return False
    _event(conn, card_id=card_id, org_id=org_id, kind=VERSIONED, cause=version.change, actor=actor,
           detail={**version.as_mapping(), "from_signal": moved.from_signal,
                   "reopened": moved.from_state == "expired"},
           signal_id=version.signal_id, at=at)
    return True

