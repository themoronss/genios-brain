"""The day, read for one seat at one instant — every item of the morning brief, with its material and its sources
(STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 1, tree `yc2_w27_s15` M44.C3.L-logic.V0.U02. Each input existed one file or
one meeting at a time, and nothing read them together (`03` s15-F13, s15-F14). The day reads, over one connection,
with no model:

  * every FILE (`context/workstreams.files_for`) with its current judgment (`reason/expert/store.current_judgments`)
    — the newest review that stands, through its check. A shown act is a DECISION; a find-out, or a move the check
    held, is a QUESTION; a wait or a block is a WATCHED file; nothing, a suppressed or a refused review is no item.
    A file decided on the shadow lane — its domain not switched on — is left out (s15-D2's default: `06` D2 governs
    what reaches you, and a brief line is not built for it here);
  * every open QUESTION a file asks (`context/your_desk.open_questions`, STEP-13's questions), with the card that
    asks it when one is open (STEP-13's question card — where the brief's line leads, `06` D60);
  * the open DECISION cards, ranked by the book re-rank already on for the tenant (`reason/brief_ranking`), so the
    brief and `GET /v1/intelligence/brief` agree on #1;
  * YOUR DESK (`context/your_desk`), when someone waits on you;
  * the day's MEETINGS with their prep (`reason/meetings/prep`, composed for the day — not the desktop's three-hour
    precompute), and the external meetings nobody followed up (`context/meeting_days`);
  * your PROMISES due (`context/promises_due`), each in the file it belongs to;
  * your REPLY TIME beside a file waiting on you, where it holds (n >= 5, `06` D37 — F45).

EVERY ITEM CARRIES ITS MATERIAL — what its words may use, and nothing else: the CHECKED words (the headline, the
situation, what done looks like, the question); the expert's wait rule and appraisal reasons only where they pass
the engine's invention rule against those checked words and the file's names, and never where they speak of you by
name; each number with the calculator that made it and its n; the dates, as local dates in the org's timezone; the
names, said as names (`platform/self_identity.spoken_name`), never an address. And its SOURCES.

Read only; nothing written, no model.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from genios_engine.context.meeting_days import meetings_of_day
from genios_engine.context.promises_due import promises_due
from genios_engine.context.workstreams import files_for
from genios_engine.context.your_desk import desk_for, open_questions
from genios_engine.contracts import morning_brief as B
from genios_engine.contracts.claim_check import HELD, SHOWN
from genios_engine.contracts.measured import count_of
from genios_engine.platform.grounding import corpus_of, invention_ok
from genios_engine.platform.self_identity import identity_for, spoken_name
from genios_engine.reason.expert.store import SHADOW_LANE, current_judgments
from genios_engine.reason.expert.verify import EARNED

#: The timezone a brief is read in when the org names none — UTC, as the engine's other readers fall back
#: (`platform/wiring._org_timezone`); STEP-15 §8.7: set it at deploy, never leave it inferred.
DEFAULT_TZ = "UTC"
#: The brief's sections of the company brief whose lines name a counterparty — where a file's name is read from.
NAMING_SECTIONS: tuple[str, ...] = ("in_motion", "watchlist", "connectors", "people")
#: How many of the expert's appraisal reasons an item carries — the writer gives each of today's five one.
REASONS_KEPT = 2

_THE_FOUNDER = re.compile(r"\bthe founder\b", re.I)
_EARNED = re.compile(r"\b(?:" + "|".join(sorted(EARNED)) + r")\b", re.I)

_SEAT = text("select lower(s.email) as email, lower(o.email) as owner, o.name, o.company, o.timezone "
             "  from orgs o left join org_seats s on s.org_id = o.id and s.seat_id = :s where o.id = :o")

_PEOPLE = text("select node_id, node_type, display_name, canonical_key from graph_nodes "
               " where org_id = :o and node_id = any(:ids) and valid_to is null")



@dataclass(frozen=True)
class Day:
    """One seat's day at one instant: every item, in a stable order."""
    org_id: str
    seat_id: str
    now: datetime
    tz: str
    local_date: date
    items: tuple[B.Item, ...]


class _ThisConnection:
    """An engine-shaped handle on the connection the day is read over — for a reader that opens its own."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def connect(self):
        return nullcontext(self._conn)


def speaks_of_you(words: str | None, founder: Iterable[str | None] = ()) -> bool:
    """Whether words speak of you as anyone but "you": "the founder", or your name — any word of it of three
    letters or more, whole (`03` F178)."""
    said = str(words or "")
    if _THE_FOUNDER.search(said):
        return True
    for name in founder:
        for word in str(name or "").split():
            if len(word) >= 3 and re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", said, re.I):
                return True
    return False


def _holds(words: str | None, grounds: Iterable[str | None], founder: Iterable[str | None]) -> bool:
    """Words the expert wrote that no check held (its wait rule, its reasons) may join an item's material only when
    the invention rule finds every name and number of theirs in what the check did hold — the ordinary words the
    expert's check earned (`reason/expert/verify.EARNED`: "File the form", "Say whether") read as the words they
    are — and they speak of you as you."""
    if not str(words or "").strip() or speaks_of_you(words, founder):
        return False
    corpus, nums = corpus_of(grounds)
    plain = _EARNED.sub(lambda m: m.group(0).lower(), str(words))
    return invention_ok(plain, corpus, nums)[0]


def spoken_names(rows: Iterable, us) -> dict[str, str | None]:
    """node → how the brief says it (`platform/self_identity.spoken_name`), for every node that is not us: a node of
    ours is never a name the brief gives a file, a meeting or a promise."""
    return {r.node_id: spoken_name(r.display_name, r.canonical_key) for r in rows
            if not us.is_us_node(r.node_type, r.canonical_key)}


def zone_of(conn, org_id: str) -> str:
    """The org's IANA timezone, or UTC when it names none or one Python does not know."""
    tz = conn.execute(text("select timezone from orgs where id = :o"), {"o": org_id}).scalar()
    try:
        ZoneInfo(str(tz))
        return str(tz)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return DEFAULT_TZ


def _local(at: datetime | date | None, zone: ZoneInfo) -> str | None:
    if at is None:
        return None
    if isinstance(at, datetime):
        return at.astimezone(zone).date().isoformat()
    return at.isoformat()


def _end_of(day: date | None, zone: ZoneInfo) -> datetime | None:
    """A date as a deadline: the end of that day in the org's timezone."""
    return None if day is None else datetime.combine(day, time(23, 59, 59), tzinfo=zone)


def _line_name(words: str) -> str:
    """The name a company-brief line gives its counterparty: "Program · Awadh Enterprise Centre — applied" says
    "Awadh Enterprise Centre"."""
    return words.split(" · ", 1)[-1].split(" — ", 1)[0].strip()


def _named_by_brief(lines, key: str | None, keys: set[str]):
    """The company brief's line naming this file — by an address of its people, or its anchor's domain (or a parent
    of it) — and the name it gives; or (None, None)."""
    key = str(key or "").lower()
    domain = key.rsplit("@", 1)[-1] if key else ""
    for line in lines:
        if line.section not in NAMING_SECTIONS:
            continue
        if line.address and (line.address == key or line.address in keys):
            return line, _line_name(line.text)
        if line.domain and domain and (domain == line.domain or domain.endswith("." + line.domain)):
            return line, _line_name(line.text)
    return None, None


def _quiet(f) -> B.Number | None:
    if f.days_quiet is None:
        return None
    days = count_of(math.floor(f.days_quiet), basis="file", unit="days")
    return B.Number(name="quiet", says=days.says(), value=days.value, n=days.n,
                    calculator="context/workstreams.days_quiet", unit="days")


def _reply_time(conn, org_id: str, f, now: datetime, names: dict[str, str]):
    """Your reply time to someone in a file waiting on you — the first that is normal (n >= 5, `06` D37)."""
    from genios_engine.context.workstream_numbers import numbers_for
    from genios_engine.context.workstream_timeline import timeline_for
    numbers = numbers_for(conn, org_id, f, timeline_for(conn, org_id, f.file_id, now=now), now=now)
    for person in numbers.people:
        measured = person.your_reply_time
        if measured.normal:
            return (B.Number(name="your_reply_time", says=measured.says(), value=measured.value, n=measured.n,
                             calculator="context/workstream_numbers.your_reply_time", unit=measured.unit),
                    names.get(person.node_id) or spoken_name(person.name, person.key))
    return None, None


def _carded(conn, org_id: str, now: datetime) -> dict[str, tuple[int, str]]:
    """file → (its decision card's book score, the card) for every open decision card — the book re-rank's order."""
    from genios_engine.reason.brief_ranking import book_rank, open_decisions
    decisions = open_decisions(_ThisConnection(conn), org_id=org_id, eval_time=now)
    ranked = book_rank(org_id=org_id, eval_time=now, decisions=decisions, entry_cap=len(decisions) or 1)
    out: dict[str, tuple[int, str]] = {}
    for receipt in ranked.receipts:
        subject = receipt.get("subject_node_id")
        if subject and subject not in out:
            out[subject] = (int(receipt["components"]["book_score_bp"]), str(receipt.get("card_id")))
    return out


def read_day(conn, org_id: str, seat_id: str, *, now: datetime) -> Day:
    """Every item of the seat's day as of `now`, in a stable order."""
    seat = conn.execute(_SEAT, {"o": org_id, "s": seat_id}).first()
    tz = zone_of(conn, org_id)
    zone = ZoneInfo(tz)
    us = identity_for(conn, org_id)
    founder = (seat.name,) if seat is not None else ()
    owner = seat is not None and (seat.email is None or seat.email == seat.owner)
    emails = sorted(us.addresses) if owner else [seat.email] if seat is not None and seat.email else []
    if owner and seat is not None and seat.owner:
        emails = [seat.owner, *[e for e in emails if e != seat.owner]]

    files = files_for(conn, org_id, now=now).files
    judgments = current_judgments(conn, org_id, now=now)
    from genios_engine.platform.company_brief_store import accepted
    lines = accepted(conn, org_id, at=now)
    everyone = sorted({p for f in files for p in f.people})
    people = {r.node_id: r for r in conn.execute(_PEOPLE, {"o": org_id, "ids": everyone})} if everyone else {}
    said = spoken_names(people.values(), us)
    carded = _carded(conn, org_id, now)
    asked = {q.file_id: q for q in open_questions(conn, org_id, now=now)}

    items: list[B.Item] = []
    file_names: dict[str, str] = {}
    for f in sorted(files, key=lambda f: f.file_id):
        keys = {str(people[p].canonical_key or "").lower() for p in f.people if p in people}
        line, name = _named_by_brief(lines, f.counterparty_key, keys)
        name = name or spoken_name(f.counterparty, f.counterparty_key) or "a file"
        file_names[f.file_id] = name
        names = [name, *[said[p] for p in f.people if said.get(p)]]
        j = judgments.get(f.file_id)
        if j is not None and j.lane == SHADOW_LANE:
            continue                                          # s15-D2's default: the shadow lane reaches no brief
        q = asked.get(f.file_id)
        base_sources = [B.Source(B.SOURCE_BRIEF, line.line_id)] if line is not None else []
        quiet = _quiet(f)
        review = j.stored.review if j is not None and j.valid else None
        checked = j.checked if review is not None else None
        by = review.next_move.by_when if review is not None and review.next_move is not None else None
        if q is not None:
            sources = [B.Source(B.SOURCE_QUESTION, q.question_id)]
            card = q.card_id
            if card:
                sources.append(B.Source(B.SOURCE_CARD, card))
            if review is not None:
                sources.append(B.Source(B.SOURCE_REVIEW, f"{f.file_id}@{j.stored.fingerprint}"))
            items.append(B.Item(
                item_id=B.item_id_for(B.QUESTION, f.file_id), kind=B.QUESTION, about=f.file_id, subject=name,
                material=B.Material(words=(("name", name), ("question", q.question)),
                                    dates=(("asked", _local(q.asked_at, zone)), ("by", _local(by, zone))),
                                    names=names),
                sources=tuple(sources + base_sources), mode=review.mode if review else None,
                stakes=review.appraisal.stakes if review else None,
                urgency=review.appraisal.urgency if review else None, at=q.asked_at, quiet_days=f.days_quiet,
                our_move=True, card_id=card, lane=j.lane if j else None))
        if checked is None:
            continue
        words = checked.words
        grounds = [words.headline, words.situation, words.done_when, checked.question, *names]
        material_words = [("name", name), ("headline", words.headline), ("situation", words.situation),
                          ("done_when", words.done_when)]
        sources = [B.Source(B.SOURCE_REVIEW, f"{f.file_id}@{j.stored.fingerprint}")]
        numbers = [n for n in (quiet,) if n is not None]
        if quiet is not None:
            sources.append(B.Source(B.SOURCE_CALCULATOR, quiet.calculator))
        common = dict(about=f.file_id, subject=name, mode=review.mode, stakes=review.appraisal.stakes,
                      urgency=review.appraisal.urgency, quiet_days=f.days_quiet, lane=j.lane)
        if q is None and (checked.fate == HELD or (checked.fate == SHOWN and review.mode == "find_out")):
            asked = checked.question or words.headline
            if asked:
                items.append(B.Item(
                    item_id=B.item_id_for(B.QUESTION, f.file_id), kind=B.QUESTION,
                    material=B.Material(words=(("name", name), ("question", asked)),
                                        dates=(("by", _local(by, zone)),), names=names),
                    sources=tuple(sources + base_sources), our_move=True, at=j.stored.reviewed_at, **common))
            continue
        if checked.fate != SHOWN:
            continue
        if review.mode == "act":
            score, card = carded.get(f.file_id, (None, None))
            if card:
                sources.append(B.Source(B.SOURCE_CARD, card))
            if any(a.owed_by == "us" for a in f.open_asks):
                reply, who = _reply_time(conn, org_id, f, now, said)
                if reply is not None:
                    numbers.append(reply)
                    sources.append(B.Source(B.SOURCE_CALCULATOR, reply.calculator))
                    material_words.append(("reply_with", who))
            reasons = [r for r in review.appraisal.reasons if _holds(r, grounds, founder)][:REASONS_KEPT]
            items.append(B.Item(
                item_id=B.item_id_for(B.DECISION, f.file_id), kind=B.DECISION,
                material=B.Material(words=(*material_words, *(("reason", r) for r in reasons)),
                                    numbers=tuple(numbers),
                                    dates=(("by", _local(by, zone)), ("last_touch", _local(f.last_touch, zone))),
                                    names=names),
                sources=tuple(sources + base_sources), at=_end_of(by, zone), our_move=True, book_score_bp=score,
                card_id=card, **common))
        elif review.mode in ("wait", "blocked"):
            rule = review.wait_or_stop if _holds(review.wait_or_stop, grounds, founder) else None
            items.append(B.Item(
                item_id=B.item_id_for(B.WATCHED, f.file_id), kind=B.WATCHED,
                material=B.Material(words=(*material_words, ("wait_rule", rule)), numbers=tuple(numbers),
                                    dates=(("last_touch", _local(f.last_touch, zone)),), names=names),
                sources=tuple(sources + base_sources), our_move=False, **common))

    items += _desk(conn, org_id, files, now, zone)
    items += _meetings(conn, org_id, seat_id, emails, now, tz, zone)
    items += _promises(conn, org_id, files, file_names, now, zone)
    return Day(org_id=org_id, seat_id=seat_id, now=now, tz=tz, local_date=now.astimezone(zone).date(),
               items=tuple(items))


def _desk(conn, org_id: str, files, now: datetime, zone: ZoneInfo) -> list[B.Item]:
    """Your desk — an item only when somebody waits on you."""
    desk = desk_for(conn, org_id, files, now=now)
    if not desk.waiting:
        return []
    numbers = [B.Number(name="waiting", says=desk.waiting_count.says(), value=desk.waiting_count.value,
                        n=desk.waiting_count.n, calculator="context/your_desk.waiting", unit="people")]
    for w in desk.waiting:
        numbers.append(B.Number(name=f"waiting:{w.file_id}", says=w.days.says(), value=w.days.value, n=w.days.n,
                                calculator="context/your_desk.waiting", unit="days"))
    if desk.days_since is not None and desk.silence_can_be_said:
        numbers.append(B.Number(name="since_your_last_mail", says=desk.days_since.says(),
                                value=desk.days_since.value, n=desk.days_since.n,
                                calculator="context/your_desk.last_out", unit="days"))
    sources = [B.Source(B.SOURCE_CALCULATOR, "context/your_desk")]
    sources += [B.Source(B.SOURCE_RECEIPT, m.connection_id) for m in desk.mailboxes]
    if desk.last_out_event:
        sources.append(B.Source(B.SOURCE_MAIL, desk.last_out_event))
    return [B.Item(item_id=B.item_id_for(B.DESK, None), kind=B.DESK, about=None, subject=None,
                   material=B.Material(numbers=tuple(numbers), dates=(("last_mail", _local(desk.last_out, zone)),),
                                       names=tuple(w.who for w in desk.waiting if w.who),
                                       words=tuple((f"waiting:{w.file_id}", w.who) for w in desk.waiting if w.who)),
                   sources=tuple(sources), at=desk.last_out, our_move=True)]


def _when(at: datetime, zone: ZoneInfo, *, clock: bool) -> str:
    local = at.astimezone(zone)
    day = f"{local.strftime('%a')} {local.day} {local.strftime('%b')}"
    return f"{day}, {local.strftime('%H:%M')}" if clock else f"{local.day} {local.strftime('%b')}"


def _prep(conn, org_id: str, seat_id: str, email: str | None, meeting_id: str, now: datetime) -> str | None:
    """The meeting's prep, composed for the day — or None. A prep that cannot be read costs that prep alone."""
    from genios_engine.reason.meetings import prep as P
    try:
        with conn.begin_nested():
            att = P.attendance(conn, org_id=org_id, meeting_node_id=meeting_id, email=email)
            if att is None:
                return None
            content = P.compose(P.read(conn, org_id=org_id, att=att, email=email, now=now, seat_id=seat_id), now=now)
            body = (content or {}).get("body") or ""
            # The prep's lines, one sentence apart — a material's words keep no line breaks.
            return "; ".join(line.strip() for line in body.splitlines() if line.strip()) or None
    except Exception:      # noqa: BLE001 — one meeting's prep is never the brief
        return None


def _meetings(conn, org_id: str, seat_id: str, emails: list[str], now: datetime, tz: str,
              zone: ZoneInfo) -> list[B.Item]:
    day = meetings_of_day(conn, org_id, emails=emails, now=now, tz=tz)
    out: list[B.Item] = []
    for m in (*day.today, *day.tomorrow):
        prep = _prep(conn, org_id, seat_id, emails[0] if emails else None, m.meeting_id, now)
        out.append(B.Item(
            item_id=B.item_id_for(B.MEETING, m.meeting_id), kind=B.MEETING, about=m.meeting_id,
            subject=m.title if "@" not in m.title else None,
            material=B.Material(words=(("title", m.title), ("when", _when(m.start_at, zone, clock=True)),
                                       ("prep", prep)),
                                dates=(("start", _local(m.start_at, zone)),), names=m.attendees),
            sources=(B.Source(B.SOURCE_MEETING, m.meeting_id),), at=m.start_at))
    for m in day.no_follow_up:
        days = count_of(math.floor((now - m.start_at).total_seconds() / 86400), basis="meeting", unit="days")
        out.append(B.Item(
            item_id=B.item_id_for(B.NO_FOLLOW_UP, m.meeting_id), kind=B.NO_FOLLOW_UP, about=m.meeting_id,
            subject=m.title if "@" not in m.title else None,
            material=B.Material(words=(("title", m.title), ("when", _when(m.start_at, zone, clock=False))),
                                numbers=(B.Number(name="since", says=days.says(), value=days.value, n=days.n,
                                                  calculator="context/meeting_days.no_follow_up", unit="days"),),
                                dates=(("start", _local(m.start_at, zone)),), names=m.attendees),
            sources=(B.Source(B.SOURCE_MEETING, m.meeting_id),
                     B.Source(B.SOURCE_CALCULATOR, "context/meeting_days.no_follow_up")),
            at=m.start_at, our_move=True))
    return out


def _promises(conn, org_id: str, files, file_names: dict[str, str], now: datetime,
              zone: ZoneInfo) -> list[B.Item]:
    file_of = {p: f.file_id for f in files for p in f.people}
    out: list[B.Item] = []
    for p in promises_due(conn, org_id, now=now):
        to = [o.name for o in p.owed_to if o.name]
        home = next((file_of[o.node_id] for o in p.owed_to if o.node_id in file_of), None)
        sources = [B.Source(B.SOURCE_PROMISE, p.promise_id)]
        if p.event_id:
            sources.append(B.Source(B.SOURCE_MAIL, p.event_id))
        out.append(B.Item(
            item_id=B.item_id_for(B.PROMISE, p.promise_id), kind=B.PROMISE, about=p.promise_id,
            subject=", ".join(to) or None,
            material=B.Material(words=(("promise", p.words), ("to", ", ".join(to) or None),
                                       ("file", file_names.get(home) if home else None)),
                                dates=(("due", _local(p.due_at, zone)),), names=tuple(to)),
            sources=tuple(sources), at=p.due_at, our_move=True))
    return out


__all__ = ["DEFAULT_TZ", "Day", "NAMING_SECTIONS", "REASONS_KEPT", "read_day", "speaks_of_you", "spoken_names",
           "zone_of"]
