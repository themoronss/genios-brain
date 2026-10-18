"""What was judged before, for ONE file — the expert's reviews, the cards on its people, how its situations ended, its past.

STEP-12 (`speedrun008/YC-II W27/` §8.3 N6; tree `yc2_w27_s12` M32.C2.L-data.V0.U02). The parts existed and
had no reader by FILE: `expert_reviews` (0197) is new; the cards about a person, their events and the
founder's verdicts are read by delivery per card; how a situation ended (`situation_outcomes`, 0194) is
read per situation; and a file's own past (`derived.history.*@<domain>`, `context/correlation_history`)
is read by the compiled lane's predicates. An expert reviewing a file must be told all four — what it
said about this file before and what came of that, what the founder did with the cards, whether the
situations reached a decision or stopped and why, and how it went the last time — or it re-decides
every file as a stranger.

ONE READ PER PART, EACH BY THE FILE. The reviews by `file_id`; the cards whose signal's subject is the
file's anchor or one of its people (`context/workstreams.WorkFile.people`); the situations anchored on
it, each with its latest end; the history facts on its anchor, each domain's under its own field — and
each ending placed on its own generation since `yc2_w27_align` M34.C2 U07 (`03` F113).

BOUNDED, AND THE CUT COUNTED (`LIMITS`). Newest first in every part, at most so many of each, and a
card's events at most so many (the newest kept). What is left out is counted per part in `cut` — a
dossier that silently dropped the oldest cards would read as a file with no history.

AN ORG-LEVEL READER. A fact a seat captured privately is not read (`visibility_scope`), as
`context/workstreams` reads none.

A CARD'S VERSIONS (STEP-14, `yc2_w27_s14` M42.C2.L-data.V2.U03). A file's card lives (`migrations/0220`): the
file's next decision or question versions it (`platform/card_lifecycle.version_card`) where it used to be a new
card beside a replaced one. Each card carries its versions, read from its `card.versioned` events
(`contracts/card_version`) — each version's headline, when, what changed and whether it was material, the first
version's words from the event that replaced them — so the expert still sees the advice it gave before. Newest
kept, the cut counted (`versions`); an event that is no version is counted out, never shown as advice; and a
version is said once, as a version — not again among what happened to the card.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

#: How much of each part the dossier carries — newest first; the rest is counted in `cut`.
LIMITS: Mapping[str, int] = {"reviews": 3, "cards": 10, "events": 5, "situations": 10,
                             "history": 24, "versions": 5}

#: The event a card's version writes (`platform/card_lifecycle.VERSIONED`) — a literal here: context reads
#: delivery's table and may not import the platform's writer for a word.
VERSIONED = "card.versioned"

_REVIEWS = text(
    "select fingerprint, status, reason, review ->> 'mode' as mode, model, prompt_version, "
    "       reviewed_at, count(*) over () as total "
    "  from expert_reviews where org_id = :o and file_id = :f "
    " order by reviewed_at desc, fingerprint limit :n")

_CARDS = text(
    "select c.card_id, s.subject_node_id, s.rule_id, c.headline, c.level, c.state, c.created_at, "
    "       c.resolved_at, count(*) over () as total, "
    "       (select coalesce(json_agg(json_build_object('kind', e.kind, 'cause', e.cause, "
    "                                                  'at', e.occurred_at, 'detail', "
    "                                                  case when e.kind = :versioned then e.detail end) "
    "                                 order by e.occurred_at, e.id), '[]'::json) "
    "          from card_events e where e.org_id = c.org_id and e.card_id = c.card_id) as events, "
    "       (select coalesce(json_agg(json_build_object('cause', v.cause, 'reason', v.reason, "
    "                                                  'at', v.occurred_at) "
    "                                 order by v.occurred_at, v.feedback_id), '[]'::json) "
    "          from card_feedback_verdicts v "
    "         where v.org_id = c.org_id and v.card_id = c.card_id) as verdicts "
    "  from cards c join signals s on s.org_id = c.org_id and s.signal_id = c.signal_id "
    " where c.org_id = :o and s.subject_node_id = any(:subjects) "
    " order by c.created_at desc, c.card_id limit :n")

_SITUATIONS = text(
    "select cs.situation_id, cs.situation_type, cs.domain, cs.status, cs.first_seen_at, "
    "       cs.last_seen_at, cs.resolved_by, cs.resolved_at, o.outcome, o.reason, "
    "       count(*) over () as total "
    "  from context_situations cs "
    "  left join lateral (select so.outcome, so.reason from situation_outcomes so "
    "                      where so.org_id = cs.org_id and so.situation_id = cs.situation_id "
    "                      order by so.last_seen_at desc, so.decision_id desc limit 1) o on true "
    " where cs.org_id = :o and cs.anchor_node_id = :f "
    " order by cs.last_seen_at desc nulls last, cs.situation_id limit :n")

_HISTORY = text(
    "select field, value, value_type, valid_from, count(*) over () as total "
    "  from graph_facts "
    " where org_id = :o and subject_node_id = :f and field like 'derived.history.%' "
    "   and valid_to is null and visibility_scope <> 'private' "
    " order by field limit :n")


def _utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@dataclass(frozen=True, slots=True)
class PriorReview:
    """One of the expert's own reviews of this file: on which fingerprint, and what came of it."""
    fingerprint: str
    status: str
    reason: str | None
    mode: str | None
    model: str
    prompt_version: str
    reviewed_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, "status": self.status, "reason": self.reason,
                "mode": self.mode, "model": self.model, "prompt_version": self.prompt_version,
                "reviewed_at": _iso(self.reviewed_at)}


@dataclass(frozen=True, slots=True)
class CardEvent:
    kind: str
    cause: str | None
    at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "cause": self.cause, "at": _iso(self.at)}


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the founder did with a card: ran its play, did it themselves, or called it wrong."""
    cause: str
    reason: str | None
    at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {"cause": self.cause, "reason": self.reason, "at": _iso(self.at)}


@dataclass(frozen=True, slots=True)
class PriorVersion:
    """One version of a file's card (`contracts/card_version`): the advice it showed, when, and what changed."""
    version: int
    headline: str
    change: str
    material: bool
    changed: tuple[str, ...]
    at: datetime | None
    #: The mode its words were shown in (`contracts/card_version.VersionWords.mode`) — `question` or `answered` on a
    #: version that ASKED you (STEP-14 fix, the crosscheck's finding 1, `yc2_w27_s14` M42.C2.L-interface.V3.U06):
    #: its headline is our question, never a ground (STEP-13's B2), whatever the card carries now.
    mode: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.version, "headline": self.headline, "change": self.change,
                "material": self.material, "changed": list(self.changed), "at": _iso(self.at)}


@dataclass(frozen=True, slots=True)
class PriorCard:
    card_id: str
    subject_node_id: str
    headline: str
    level: str
    state: str
    created_at: datetime
    resolved_at: datetime | None
    events: tuple[CardEvent, ...]
    verdicts: tuple[Verdict, ...]
    versions: tuple[PriorVersion, ...] = ()
    #: The rule its signal fired under — `founder_question` for a question card (STEP-13
    #: M36.C2.L-logic.V2.U12: its headline is OUR question, never a ground for the claim it asked about).
    rule_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"card_id": self.card_id, "subject_node_id": self.subject_node_id,
                "headline": self.headline, "level": self.level, "state": self.state,
                "created_at": _iso(self.created_at), "resolved_at": _iso(self.resolved_at),
                "events": [e.as_dict() for e in self.events],
                "verdicts": [v.as_dict() for v in self.verdicts],
                "versions": [v.as_dict() for v in self.versions]}


@dataclass(frozen=True, slots=True)
class SituationEnd:
    """One situation anchored on the file, and how it last ended (`situation_outcomes`), if it did."""
    situation_id: str
    situation_type: str
    domain: str
    status: str | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    resolved_by: str | None
    resolved_at: datetime | None
    outcome: str | None
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"situation_id": self.situation_id, "situation_type": self.situation_type,
                "domain": self.domain, "status": self.status,
                "first_seen_at": _iso(self.first_seen_at), "last_seen_at": _iso(self.last_seen_at),
                "resolved_by": self.resolved_by, "resolved_at": _iso(self.resolved_at),
                "outcome": self.outcome, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class PastFact:
    """One `derived.history.*@<domain>` fact on the file's anchor — how it went the last time."""
    field: str
    value: Any
    value_type: str | None
    valid_from: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "value": self.value, "value_type": self.value_type,
                "valid_from": _iso(self.valid_from)}


def _no_cut() -> dict[str, int]:
    return {part: 0 for part in LIMITS}


@dataclass(frozen=True, slots=True)
class FileJudgments:
    file_id: str
    reviews: tuple[PriorReview, ...] = ()
    cards: tuple[PriorCard, ...] = ()
    situations: tuple[SituationEnd, ...] = ()
    history: tuple[PastFact, ...] = ()
    cut: Mapping[str, int] = field(default_factory=_no_cut)    # per part, what was left out

    def as_dict(self) -> dict[str, Any]:
        return {"file_id": self.file_id, "reviews": [r.as_dict() for r in self.reviews],
                "cards": [c.as_dict() for c in self.cards],
                "situations": [s.as_dict() for s in self.situations],
                "history": [h.as_dict() for h in self.history], "cut": dict(self.cut)}


def _left_out(rows, limit: int) -> int:
    return max(0, int(rows[0].total) - limit) if rows else 0


def _json_list(value: Any) -> list:
    if isinstance(value, str):
        import json
        value = json.loads(value)
    return list(value or ())


def _versions(created_at: datetime | None, raw: list[dict]) -> tuple[list[PriorVersion], int]:
    """A card's versions, oldest first, from its version events — and how many events were no version."""
    from genios_engine.contracts.card_version import CardVersion

    out: list[PriorVersion] = []
    unread = 0
    for event in raw:
        try:
            v = CardVersion.from_mapping(event.get("detail") or {})
        except (TypeError, ValueError):
            unread += 1
            continue
        if not out and v.before is not None:
            # The first version's words are the ones its first replacement kept.
            out.append(PriorVersion(version=v.version - 1, headline=v.before.headline, change="created",
                                    material=True, changed=(), at=created_at, mode=v.before.mode))
        out.append(PriorVersion(version=v.version, headline=v.words.headline, change=v.change,
                                material=v.material, changed=v.changed, at=_utc(event.get("at")),
                                mode=v.words.mode))
    return out, unread


def judgments_for(conn, org_id: str, file_id: str, *, people: Iterable[str] = (),
                  limits: Mapping[str, int] = LIMITS) -> FileJudgments:
    """What was judged before about ONE file: its anchor `file_id` and its `people` (node ids — the
    file's own `WorkFile.people`), each part newest first, bounded by `limits`, the cut counted."""
    subjects = sorted({str(file_id), *(str(p) for p in people)})
    cut = _no_cut()

    rows = conn.execute(_REVIEWS, {"o": org_id, "f": file_id, "n": limits["reviews"]}).fetchall()
    cut["reviews"] = _left_out(rows, limits["reviews"])
    reviews = tuple(PriorReview(fingerprint=r.fingerprint, status=r.status, reason=r.reason,
                                mode=r.mode, model=r.model, prompt_version=r.prompt_version,
                                reviewed_at=_utc(r.reviewed_at)) for r in rows)

    rows = conn.execute(_CARDS, {"o": org_id, "subjects": subjects, "versioned": VERSIONED,
                                 "n": limits["cards"]}).fetchall()
    cut["cards"] = _left_out(rows, limits["cards"])
    cards = []
    for r in rows:
        raw = _json_list(r.events)
        events = [CardEvent(kind=e["kind"], cause=e.get("cause"), at=_utc(e.get("at")))
                  for e in raw if e["kind"] != VERSIONED]
        kept = events[-limits["events"]:] if limits["events"] else []
        cut["events"] += len(events) - len(kept)
        versions, unread = _versions(_utc(r.created_at), [e for e in raw if e["kind"] == VERSIONED])
        shown = versions[-limits["versions"]:] if limits["versions"] else []
        cut["versions"] += len(versions) - len(shown) + unread
        cards.append(PriorCard(
            card_id=r.card_id, subject_node_id=r.subject_node_id, headline=r.headline,
            level=r.level, state=r.state, created_at=_utc(r.created_at),
            resolved_at=_utc(r.resolved_at), events=tuple(kept),
            verdicts=tuple(Verdict(cause=v["cause"], reason=v.get("reason"), at=_utc(v.get("at")))
                           for v in _json_list(r.verdicts)),
            versions=tuple(shown), rule_id=r.rule_id))

    rows = conn.execute(_SITUATIONS, {"o": org_id, "f": file_id,
                                      "n": limits["situations"]}).fetchall()
    cut["situations"] = _left_out(rows, limits["situations"])
    situations = tuple(SituationEnd(
        situation_id=r.situation_id, situation_type=r.situation_type, domain=r.domain,
        status=r.status, first_seen_at=_utc(r.first_seen_at), last_seen_at=_utc(r.last_seen_at),
        resolved_by=r.resolved_by, resolved_at=_utc(r.resolved_at), outcome=r.outcome,
        reason=r.reason) for r in rows)

    rows = conn.execute(_HISTORY, {"o": org_id, "f": file_id, "n": limits["history"]}).fetchall()
    cut["history"] = _left_out(rows, limits["history"])
    history = tuple(PastFact(field=r.field, value=r.value, value_type=r.value_type,
                             valid_from=_utc(r.valid_from)) for r in rows)

    return FileJudgments(file_id=str(file_id), reviews=reviews, cards=tuple(cards),
                         situations=situations, history=history, cut=cut)


__all__ = ["CardEvent", "FileJudgments", "LIMITS", "PastFact", "PriorCard", "PriorReview", "PriorVersion",
           "SituationEnd", "VERSIONED", "Verdict", "judgments_for"]
