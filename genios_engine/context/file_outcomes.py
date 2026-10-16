"""How each decision of a file ended — read from what is already written, no table of its own (STEP-16).

`speedrun008/YC-II W27/` STEP-16 §8.4 item 8, tree `yc2_w27_s16` M47.C1.L-data.V2.U03. Every end of a card is written
once, somewhere: the card's own ending (`card_events` — STEP-06's causes, and since M47.C1.L-data.V0.U01 a resolution's),
the button you pressed (`human.card_action`), your verdict (`card_feedback_verdicts`) and, for a decision cleared, the
ask's closure it carries (`closed_by`). This reads them back, per card:

  VERIFIED      resolved `verified` — the ask its move answered closed answered, BY the event that closed it;
  REPLIED       cleared while its ask closed only replied (the closing event said, nothing proven answered);
  TAKEN         you took it — `run_play` or `do_it_myself`;
  CALLED_WRONG  you called it wrong — and WHY, the reason you gave;
  LAPSED        its window passed with nobody acting;
  DISMISSED     you dismissed it from the extension;
  REPLACED      a newer decision replaced it (and the team lane's superseded card);
  CLEARED       the decision behind it stopped holding (cleared, held by the budget, no longer authorised, its plan
                gone, muted, its subject one of us — and the team lane's cleared situation);
  OPEN          still in front of somebody;
  UNRECORDED    ended with no cause written — said, never guessed.

`ended_for_files` reads the cards of one file or several, `ended_for_cards` the cards a dossier shows,
`ended_between` a tenant's cards created in a window; `rates` counts them by
the kind of work their file is and by their lane — each a count of what ENDED (open cards apart), the verified share a
`Measured` with its n, a habit only at n ≥ 5 (`06` D37). Org-level: no seat-private card is read here that delivery did
not already show the org.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.measured import Measured, rate_of

# One name to a line: `tests/test_no_missing_module_deps` reads what a module defines by its assignments.
VERIFIED = "verified"
REPLIED = "replied"
TAKEN = "taken"
CALLED_WRONG = "called_wrong"
LAPSED = "lapsed"
DISMISSED = "dismissed"
REPLACED = "replaced"
CLEARED = "cleared"
OPEN = "open"
UNRECORDED = "unrecorded"
ENDS: tuple[str, ...] = (VERIFIED, REPLIED, TAKEN, CALLED_WRONG, LAPSED, DISMISSED, REPLACED, CLEARED, OPEN,
                         UNRECORDED)
#: The card states that are still in front of somebody (`platform/card_lifecycle.OPEN_STATES`, and `built`).
_OPEN_STATES = ("built", "queued", "surfaced", "snoozed", "claimed", "delivered")
#: The buttons that are you taking a card.
_TAKEN = ("run_play", "do_it_myself")
#: The endings an event names — `platform/card_lifecycle`'s kinds, read as words: context reads delivery's table and
#: may not import the platform's writer for its vocabulary.
_ENDING_KINDS = ("card.expired", "window.lapsed", "card.dismissed", "card.retired", "card.resolved")

_CARDS = (
    "select k.card_id, k.file_id, k.state, k.output_lane, k.created_at, k.resolved_at from cards k "
    "where k.org_id = :o and (cast(:fs as text[]) is null or k.file_id = any(:fs)) "
    "and (cast(:ids as text[]) is null or k.card_id = any(:ids)) "
    "and (cast(:since as timestamptz) is null or k.created_at >= :since) "
    "and (cast(:until as timestamptz) is null or k.created_at < :until) "
    "order by k.created_at, k.card_id")
_ENDINGS = (
    "select distinct on (e.card_id) e.card_id, e.kind, e.cause, e.detail, e.occurred_at from card_events e "
    "where e.org_id = :o and e.card_id = any(:cards) and e.kind = any(:kinds) "
    "order by e.card_id, e.occurred_at desc, e.id desc")
_PRESSED = (
    "select distinct on (e.card_id) e.card_id, e.cause, e.occurred_at from card_events e "
    "where e.org_id = :o and e.card_id = any(:cards) and e.kind = 'human.card_action' "
    "order by e.card_id, e.occurred_at desc, e.id desc")
_VERDICTS = (
    "select card_id, cause, reason, occurred_at from card_feedback_verdicts "
    "where org_id = :o and card_id = any(:cards)")


@dataclass(frozen=True, slots=True)
class Ended:
    """How one card of a file ended — and what proved it, why, when."""
    card_id: str
    file_id: str | None
    lane: str | None
    ended: str                          # one of ENDS
    by: str | None = None               # VERIFIED: the event that closed the ask; REPLIED: the reply's
    reason: str | None = None           # CALLED_WRONG: the reason you gave; otherwise the cause written
    at: datetime | None = None


def _detail(value: Any) -> Mapping:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str) and value:
        import json
        try:
            out = json.loads(value)
        except ValueError:
            return {}
        return out if isinstance(out, Mapping) else {}
    return {}


def _ended(card, end, pressed, verdict) -> Ended:
    base = {"card_id": card.card_id, "file_id": card.file_id, "lane": card.output_lane}
    detail = _detail(end.detail) if end is not None else {}
    if card.state == "resolved":
        if end is not None and end.kind == "card.resolved" and end.cause == "verified":
            return Ended(**base, ended=VERIFIED, by=detail.get("event_id"), at=end.occurred_at)
        if end is not None and end.kind == "card.resolved" and end.cause == "superseded":
            return Ended(**base, ended=REPLACED, reason=end.cause, at=end.occurred_at)
        if end is not None and end.kind == "card.resolved":
            return Ended(**base, ended=CLEARED, reason=end.cause, at=end.occurred_at)
        return Ended(**base, ended=UNRECORDED, at=card.resolved_at)
    if card.state == "acted":
        cause = verdict.cause if verdict is not None else (pressed.cause if pressed is not None else None)
        at = verdict.occurred_at if verdict is not None else (pressed.occurred_at if pressed is not None else None)
        if cause == "wrong":
            return Ended(**base, ended=CALLED_WRONG, reason=verdict.reason if verdict is not None else None, at=at)
        if cause in _TAKEN:
            return Ended(**base, ended=TAKEN, reason=cause, at=at)
        return Ended(**base, ended=UNRECORDED, at=at)
    if card.state == "expired" and end is not None:
        if end.kind == "window.lapsed" or end.cause == "expired":
            return Ended(**base, ended=LAPSED, reason=end.cause, at=end.occurred_at)
        if end.kind == "card.dismissed" or end.cause == "extension":
            return Ended(**base, ended=DISMISSED, reason=end.cause, at=end.occurred_at)
        if end.cause == "replaced":
            return Ended(**base, ended=REPLACED, reason=end.cause, at=end.occurred_at)
        closed = _detail(detail.get("closed_by"))
        if end.cause == "rule_cleared" and closed.get("basis") == "replied":
            return Ended(**base, ended=REPLIED, by=closed.get("event_id"), reason=end.cause, at=end.occurred_at)
        return Ended(**base, ended=CLEARED, reason=end.cause, at=end.occurred_at)
    if card.state in _OPEN_STATES:
        return Ended(**base, ended=OPEN)
    return Ended(**base, ended=UNRECORDED, at=end.occurred_at if end is not None else None)


def _read(conn, org_id: str, *, file_ids: list[str] | None, since: datetime | None,
          until: datetime | None, card_ids: list[str] | None = None) -> tuple[Ended, ...]:
    cards = conn.execute(text(_CARDS), {"o": org_id, "fs": file_ids, "since": since, "until": until,
                                        "ids": card_ids}).fetchall()
    if not cards:
        return ()
    ids = [c.card_id for c in cards]
    ends = {r.card_id: r for r in conn.execute(text(_ENDINGS), {"o": org_id, "cards": ids,
                                                                "kinds": list(_ENDING_KINDS)})}
    pressed = {r.card_id: r for r in conn.execute(text(_PRESSED), {"o": org_id, "cards": ids})}
    verdicts = {r.card_id: r for r in conn.execute(text(_VERDICTS), {"o": org_id, "cards": ids})}
    return tuple(_ended(c, ends.get(c.card_id), pressed.get(c.card_id), verdicts.get(c.card_id)) for c in cards)


def ended_for_files(conn, org_id: str, file_ids: Iterable[str]) -> tuple[Ended, ...]:
    """How each card of these files ended, oldest first — one file's, or a kind of work's files in one read
    (`context/kind_numbers`)."""
    ids = sorted({str(f) for f in file_ids})
    return _read(conn, org_id, file_ids=ids, since=None, until=None) if ids else ()


def ended_for_cards(conn, org_id: str, card_ids: Iterable[str]) -> tuple[Ended, ...]:
    """How each of these cards of the tenant ended — the cards a file's dossier shows (`context/file_judgments`)."""
    ids = sorted({str(c) for c in card_ids})
    return _read(conn, org_id, file_ids=None, since=None, until=None, card_ids=ids) if ids else ()


def ended_between(conn, org_id: str, *, since: datetime, until: datetime) -> tuple[Ended, ...]:
    """How each card of the tenant created in [since, until) ended, oldest first."""
    return _read(conn, org_id, file_ids=None, since=since, until=until)


@dataclass(frozen=True, slots=True)
class Rates:
    """What came of a group's cards: each end counted, and the share that ended verified."""
    counts: Mapping[str, int]
    verified: Measured

    def as_dict(self) -> dict[str, Any]:
        return {"counts": dict(self.counts), "verified": {"value": self.verified.value, "n": self.verified.n,
                                                          "says": self.verified.says()}}


def _rates(items: Iterable[Ended], basis: str) -> Rates:
    counts = Counter(e.ended for e in items)
    ended = sum(n for end, n in counts.items() if end != OPEN)
    return Rates(counts={end: counts.get(end, 0) for end in ENDS},
                 verified=rate_of(counts.get(VERIFIED, 0), ended, basis=basis))


def rates(endings: Iterable[Ended], *, kinds: Mapping[str, str | None]) -> dict[str, dict[str, Rates]]:
    """What came of the cards by the kind of work their file is (`kinds`: file → kind; no kind, `none`) and by their
    lane — pure over what `ended_between` read."""
    items = tuple(endings)
    by_kind: dict[str, list[Ended]] = {}
    by_lane: dict[str, list[Ended]] = {}
    for e in items:
        by_kind.setdefault(str(kinds.get(e.file_id) or "none") if e.file_id else "no file", []).append(e)
        by_lane.setdefault(str(e.lane or "none"), []).append(e)
    return {"kind": {k: _rates(v, f"cards of {k} files") for k, v in sorted(by_kind.items())},
            "lane": {k: _rates(v, f"cards in the {k} lane") for k, v in sorted(by_lane.items())},
            "all": {"all": _rates(items, "every card of the window")}}


__all__ = ["CALLED_WRONG", "CLEARED", "DISMISSED", "ENDS", "Ended", "LAPSED", "OPEN", "REPLACED", "REPLIED", "Rates",
           "TAKEN", "UNRECORDED", "VERIFIED", "ended_between", "ended_for_cards", "ended_for_files", "rates"]
