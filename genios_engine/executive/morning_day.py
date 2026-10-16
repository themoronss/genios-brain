"""The day, read for one seat at one instant — every item of the morning brief, with its material and its sources
(STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 1, tree `yc2_w27_s15` M44.C3.L-logic.V0.U02. Each input existed one file or
one meeting at a time, and nothing read them together (`03` s15-F13, s15-F14). The day reads, over one connection,
with no model:

  * every FILE (`context/workstreams.files_for`) with its current judgment (`reason/expert/store.current_judgments`)
    — the newest review that stands, through its check. A shown act is a DECISION; a find-out, or a move the check
    held, is a QUESTION; a wait or a block is a WATCHED file; nothing, a suppressed or a refused review is no item.
    A file decided on the shadow lane — its domain not switched on — is a line too, on s15-D2 = yes (`yc2_w27_s15`
    M45.C4.L-logic.V0.U01): its headline or question carries "outside your switched-on work", and it never carries a
    card — `06` D2 still governs what a CARD shows, never a line (F53: "Larkspur went quiet after four exchanges in
    March — six months", which `executive/morning_order` seats among today's five, 03 s15-F22). A QUESTION carries
    what its file is about — the review's situation, beside the ask (03 s15-F19) — and a file whose review found
    nothing owed has no change line either (03 s15-F20);
  * every open QUESTION a file asks (`context/your_desk.open_questions`, STEP-13's questions), with the card that
    asks it when one is open (STEP-13's question card — where the brief's line leads, `06` D60);
  * the open DECISION cards, ranked by the book re-rank already on for the tenant (`reason/brief_ranking`), so the
    brief and `GET /v1/intelligence/brief` agree on #1;
  * YOUR DESK (`context/your_desk`), when someone waits on you;
  * the day's MEETINGS with their prep (`reason/meetings/prep`, composed for the day — not the desktop's three-hour
    precompute), and the external meetings nobody followed up (`context/meeting_days`);
  * your PROMISES due (`context/promises_due`), each in the file it belongs to;
  * your REPLY TIME beside a file waiting on you, where it holds (n >= 5, `06` D37 — F45);
  * WHAT CHANGED since the seat's last kept brief (`executive/morning_store.last_before`; a first brief reads the
    day before): each file's latest review since, with what triggered it in words — "Hub71 wrote", "their move,
    quiet 18 days — past the 5 days they usually take" (0199's triggers, a mail's id said as who wrote it) — and
    each line of the last brief gone today, with why: answered, no longer asked, done on its card, closed.

EVERY ITEM CARRIES ITS MATERIAL — what its words may use, and nothing else: the CHECKED words (the headline, the
situation, what done looks like, the question); the expert's wait rule and appraisal reasons only where they pass
the engine's invention rule against those checked words and the file's names, and never where they speak of you by
name; each number with the calculator that made it and its n; the dates, as local dates in the org's timezone; the
names, said as names (`platform/self_identity.spoken_name`), never an address. And its SOURCES.

A WATCHED file whose review cites a correction of yours that still stands (STEP-16, `yc2_w27_s16`
M46.C6.L-interface.V2.U01) carries the day you said it (`you_said`, the newest such correction's, a local date) —
its Watching line says so: *"waiting for a real milestone (you said so on 12 Oct)"* (`executive/morning_template`).

Read only; nothing written, no model.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from genios_engine.context import founder_corrections as corrections
from genios_engine.context.meeting_days import meetings_of_day
from genios_engine.context.promises_due import promises_due
from genios_engine.context.workstreams import files_for
from genios_engine.context.your_desk import desk_for, open_questions
from genios_engine.contracts import morning_brief as B
from genios_engine.contracts.claim_check import HELD, SHOWN
from genios_engine.contracts.measured import count_of
from genios_engine.executive.morning_screen import screen_items
from genios_engine.executive.morning_store import last_before
from genios_engine.platform.grounding import corpus_of, invention_ok
from genios_engine.platform.identity import person_name_key
from genios_engine.platform.self_identity import identity_for, spoken_name
from genios_engine.reason.expert.store import SHADOW_LANE, current_judgments
from genios_engine.reason.expert.verify import EARNED, cited_anywhere

#: The timezone a brief is read in when the org names none — UTC, as the engine's other readers fall back
#: (`platform/wiring._org_timezone`); STEP-15 §8.7: set it at deploy, never leave it inferred.
DEFAULT_TZ = "UTC"
#: The brief's sections of the company brief whose lines name a counterparty — where a file's name is read from.
NAMING_SECTIONS: tuple[str, ...] = ("in_motion", "watchlist", "connectors", "people")
#: How many of the expert's appraisal reasons an item carries — the writer gives each of today's five one.
REASONS_KEPT = 2
#: s15-D2 (`yc2_w27_s15` M45.C4.L-logic.V0.U01) — how a shadow-lane file's line says what a card never does: its
#: domain is not switched on, `06` D2 still governs the card, and the line says so rather than reading as any
#: other file's.
SHADOW_LABEL = "outside your switched-on work"

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


#: What a question line says when neither the question nor the review's checked words can say it to you as "you".
ASKED_ON_ITS_CARD = "a question waits for your answer on its card"


def _asked_as_you(question: str | None, headline: str | None, founder: Iterable[str | None]) -> str | None:
    """A question in words that speak of you as you: the question; else the review's checked headline; else code's
    words. F54's question asked "whether Arjun went to the event" — the founder's name, in his own brief."""
    for words in (question, headline):
        if str(words or "").strip() and not speaks_of_you(words, founder):
            return words
    return ASKED_ON_ITS_CARD if str(question or headline or "").strip() else None


def _about(checked, founder: Iterable[str | None]) -> str | None:
    """What the file is about, in the review's own checked words — the situation, the sentence the file's card carries
    beside its question (STEP-14) — unless it speaks of you as anyone but you. A question line that is only the ask
    does not say what the ask is for: STEP-14 made F22's the plain "Can you tell us whether you are a startup
    incubated on the university's campus?", which no longer says it is about a seed grant (03 s15-F19)."""
    said = checked.words.situation if checked is not None else None
    return said if str(said or "").strip() and not speaks_of_you(said, founder) else None


def _answered_since(conn, org_id: str, file_id: str, reviewed_at: datetime) -> bool:
    """Whether you answered the file's question after this review asked it — then the brief asks nothing until the
    expert reads your answer (`context/founder_questions.answers_for`, read only)."""
    from genios_engine.context.founder_questions import answers_for
    return any(a.answered_at is not None and a.answered_at >= reviewed_at
               for a in answers_for(conn, org_id, file_id))


def you_said_on(conn, org_id: str, review, zone: ZoneInfo) -> str | None:
    """The day you said the newest correction this review cites that still stands — a local date in `zone` — or
    None: it cites none, or you took each back (`context/founder_corrections`, STEP-16)."""
    said = [c for c in (corrections.by_id(conn, org_id, ref.removeprefix("corr:"))
                        for ref in sorted(cited_anywhere(review)) if ref.startswith("corr:"))
            if c is not None and c.state == corrections.STANDING]
    return _local(max(c.corrected_at for c in said), zone) if said else None


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
    # A file's last touch may be a meeting still to come — no quiet at all, never a negative one.
    days = count_of(max(0, math.floor(f.days_quiet)), basis="file", unit="days")
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
    shown: dict[str, str] = {}                                # the files this brief may speak of, by name
    for f in sorted(files, key=lambda f: f.file_id):
        keys = {str(people[p].canonical_key or "").lower() for p in f.people if p in people}
        line, name = _named_by_brief(lines, f.counterparty_key, keys)
        name = name or spoken_name(f.counterparty, f.counterparty_key) or "a file"
        file_names[f.file_id] = name
        names = [name, *[said[p] for p in f.people if said.get(p)]]
        j = judgments.get(f.file_id)
        shadow = j is not None and j.lane == SHADOW_LANE
        shown[f.file_id] = name
        q = asked.get(f.file_id)
        base_sources = [B.Source(B.SOURCE_BRIEF, line.line_id)] if line is not None else []
        quiet = _quiet(f)
        review = j.stored.review if j is not None and j.valid else None
        checked = j.checked if review is not None else None
        by = review.next_move.by_when if review is not None and review.next_move is not None else None
        if q is not None:
            sources = [B.Source(B.SOURCE_QUESTION, q.question_id)]
            card = None if shadow else q.card_id        # s15-D2: a shadow file's line never carries a card
            if card:
                sources.append(B.Source(B.SOURCE_CARD, card))
            if review is not None:
                sources.append(B.Source(B.SOURCE_REVIEW, f"{f.file_id}@{j.stored.fingerprint}"))
            asked_wording = _asked_as_you(q.question, checked.words.headline if checked is not None else None,
                                          founder)
            if shadow and asked_wording:
                asked_wording += f" — {SHADOW_LABEL}"
            items.append(B.Item(
                item_id=B.item_id_for(B.QUESTION, f.file_id), kind=B.QUESTION, about=f.file_id, subject=name,
                material=B.Material(words=(("name", name), ("situation", _about(checked, founder)),
                                           ("question", asked_wording)),
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
        headline = words.headline
        if shadow and headline:
            headline = f"{headline} — {SHADOW_LABEL}"
        material_words = [("name", name), ("headline", headline), ("situation", words.situation),
                          ("done_when", words.done_when)]
        sources = [B.Source(B.SOURCE_REVIEW, f"{f.file_id}@{j.stored.fingerprint}")]
        numbers = [n for n in (quiet,) if n is not None]
        if quiet is not None:
            sources.append(B.Source(B.SOURCE_CALCULATOR, quiet.calculator))
        common = dict(about=f.file_id, subject=name, mode=review.mode, stakes=review.appraisal.stakes,
                      urgency=review.appraisal.urgency, quiet_days=f.days_quiet, lane=j.lane)
        if q is None and (checked.fate == HELD or (checked.fate == SHOWN and review.mode == "find_out")):
            wording = _asked_as_you(checked.question, words.headline, founder)
            if shadow and wording:
                wording += f" — {SHADOW_LABEL}"
            if wording and not _answered_since(conn, org_id, f.file_id, j.stored.reviewed_at):
                items.append(B.Item(
                    item_id=B.item_id_for(B.QUESTION, f.file_id), kind=B.QUESTION,
                    material=B.Material(words=(("name", name), ("situation", _about(checked, founder)),
                                               ("question", wording)),
                                        dates=(("by", _local(by, zone)),), names=names),
                    sources=tuple(sources + base_sources), our_move=True, at=j.stored.reviewed_at, **common))
            continue
        if checked.fate != SHOWN:
            continue
        if review.mode == "act":
            score, card = (None, None) if shadow else carded.get(f.file_id, (None, None))
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
                                    dates=(("last_touch", _local(f.last_touch, zone)),
                                           ("you_said", you_said_on(conn, org_id, review, zone))), names=names),
                sources=tuple(sources + base_sources), our_move=False, **common))

    resolved = _resolved_nothing(judgments)
    items += _desk(conn, org_id, [f for f in files if f.file_id not in resolved], now, zone)
    items += _meetings(conn, org_id, seat_id, emails, now, tz, zone)
    items += _promises(conn, org_id, files, file_names, now, zone)
    items += screen_items(conn, org_id=org_id, seat_id=seat_id, file_by_person=_file_by_person(files, said),
                          file_names=file_names, now=now)
    local = now.astimezone(zone).date()
    last = last_before(conn, org_id, seat_id, local)
    items += read_changes(conn, org_id, now=now, items=items, last=last, file_names=shown, founder=founder,
                          zone=zone, resolved=resolved)
    return Day(org_id=org_id, seat_id=seat_id, now=now, tz=tz, local_date=local, items=tuple(items))


def _resolved_nothing(judgments) -> frozenset[str]:
    """File ids whose current valid judgment's effective mode is "nothing" (`reason/expert/decide.mode_of`): the
    expert has read the file and found nothing owed, even where its open ask is stale (`03` s15-F17 — a question
    answered on another channel leaves the loop open, but the review's own facts and `wait_or_stop` say it is
    closed; the desk must read the same judgment the day's items do, not the raw loop)."""
    from genios_engine.reason.expert.decide import mode_of
    out = set()
    for file_id, j in judgments.items():
        if j.valid and j.checked is not None and mode_of(j.stored.review, j.checked) == "nothing":
            out.add(file_id)
    return frozenset(out)


def _file_by_person(files, said: dict[str, str | None]) -> dict[str, str]:
    """`06` D8 — every file's own people, by `platform/identity.person_name_key`, so a screen follow-up naming
    one of them reads beside that file rather than standing alone. The first file a name is shown on wins; two
    files sharing a person is the weak case `person_name_key`'s own docstring already names."""
    out: dict[str, str] = {}
    for f in sorted(files, key=lambda f: f.file_id):
        for p in f.people:
            key = person_name_key(said.get(p))
            if key:
                out.setdefault(key, f.file_id)
    return out


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


# ── what changed since your last brief (M44.C3.L-logic.V1.U04) ─────────────────────────────────────────────────

#: With no brief kept before, what changed is read over the day before — "since yesterday".
FIRST_BRIEF_LOOKBACK = timedelta(days=1)
#: How a trigger (`reason/expert/triggers`, kept with each review since 0199) is said in the brief.
_TRIGGER_WORDS = {"founder_asked": "you asked about it", "date_closing_in": "a date it holds is closer"}
#: Triggers that say the same thing — how long the file has been quiet — of which a change line keeps the first.
_QUIET_TRIGGERS = ("reply_overdue", "past_normal")
#: A number as a trigger writes it ("quiet 25.12 days") and as the brief says it: whole days.
_DECIMAL = re.compile(r"\b(\d+)\.\d+\b")
_EVENT_ID = re.compile(r"\bevt_[0-9a-f]+\b")

#: Every review since an instant, up to now — with what triggered it (0199).
_REVIEWS_SINCE = text(
    "select file_id, fingerprint, reviewed_at, triggers from expert_reviews "
    " where org_id = :o and status = 'valid' and reviewed_at > :since and reviewed_at <= :now "
    " order by reviewed_at, file_id")

#: Who sent each mail a trigger names — a name, or an address said as one.
_ACTORS = text(
    "select event_id, source, actor->>'name' as name, lower(actor->>'email') as email from source_events "
    " where org_id = :o and event_id = any(:ids)")

#: The questions and cards a brief's gone lines named — what came of each.
_QUESTION_STATES = text("select question_id, state from founder_questions where org_id = :o and question_id = any(:ids)")
_CARD_STATES = text("select card_id, state from cards where org_id = :o and card_id = any(:ids)")


def _said_triggers(triggers, actors: dict[str, str], us) -> str | None:
    """What triggered a review, in the brief's words: who wrote — never you: your own mail is no news to you — or
    the file's own words for a quiet crossed, once, in whole days. A first look is no change: a new file stands in
    its own section, or needs nothing of you."""
    parts: list[str] = []
    quiet = False
    for kind, says in triggers or ():
        if kind == "new_evidence":
            for eid in _EVENT_ID.findall(says or ""):
                who = actors.get(eid)
                if who and who != "you" and f"{who} wrote" not in parts:
                    parts.append(f"{who} wrote")
        elif kind in _TRIGGER_WORDS:
            if _TRIGGER_WORDS[kind] not in parts:
                parts.append(_TRIGGER_WORDS[kind])
        elif kind in _QUIET_TRIGGERS and says and not quiet:
            quiet = True
            parts.append(_DECIMAL.sub(r"\1", says))
    return "; ".join(parts[:2]) if parts else None


def read_changes(conn, org_id: str, *, now: datetime, items: Iterable[B.Item], last: B.Brief | None,
                 file_names: dict[str, str], founder: Iterable[str | None], zone: ZoneInfo,
                 resolved: frozenset[str]) -> list[B.Item]:
    """What changed since the seat's last brief (or since the day before, for a first brief): each review since,
    with what triggered it, in words; and each item of the last brief that is gone today, with why.

    `resolved` is the files whose current judgment found nothing owed (`_resolved_nothing`): a review that reads
    "nothing for you to do in this file" has no line in the day, so it has no change line either, however sayable
    its trigger — a connector's nudge about an introduction that was declined is old activity (03 s15-F20, F64).
    Required, not defaulted: a caller that forgets it would silently reopen every closed file as a change."""
    items = list(items)
    since = last.as_of if last is not None else now - FIRST_BRIEF_LOOKBACK
    us = identity_for(conn, org_id)
    reviews = list(conn.execute(_REVIEWS_SINCE, {"o": org_id, "since": since, "now": now}))
    ids = sorted({e for r in reviews for _k, says in ((t.get("kind"), t.get("says")) for t in (r.triggers or ()))
                  for e in _EVENT_ID.findall(says or "")})
    actors = {}
    for a in (conn.execute(_ACTORS, {"o": org_id, "ids": ids}) if ids else ()):
        actors[a.event_id] = "you" if us.is_us(a.email) else spoken_name(a.name, a.email)
    out: list[B.Item] = []
    latest: dict[str, object] = {}
    for r in reviews:
        latest[r.file_id] = r                                   # one change line per file: its latest review
    for file_id, r in sorted(latest.items()):
        name = file_names.get(file_id)
        if name is None:
            continue                                            # a file not in this brief (the shadow lane's)
        if file_id in resolved:
            continue                                            # the review found nothing owed: nothing changed for you
        what = _said_triggers([(t.get("kind"), t.get("says")) for t in (r.triggers or ())], actors, us)
        if not what or speaks_of_you(what, founder):
            continue
        out.append(B.Item(
            item_id=B.item_id_for(B.CHANGE, file_id, "review"), kind=B.CHANGE, about=file_id, subject=name,
            material=B.Material(words=(("name", name), ("what", what)),
                                dates=(("reviewed", _local(r.reviewed_at, zone)),), names=(name,)),
            sources=(B.Source(B.SOURCE_REVIEW, f"{file_id}@{r.fingerprint}"),), at=r.reviewed_at))
    if last is None:
        return out
    today = {i.item_id for i in items}
    gone = [l for l in last.lines if l.item_id not in today and l.kind != B.CHANGE]
    refs = {kind: sorted({s.ref for l in gone for s in l.sources if s.kind == kind})
            for kind in (B.SOURCE_QUESTION, B.SOURCE_CARD)}
    questions = dict(conn.execute(_QUESTION_STATES, {"o": org_id, "ids": refs[B.SOURCE_QUESTION]}).all()) \
        if refs[B.SOURCE_QUESTION] else {}
    cards = dict(conn.execute(_CARD_STATES, {"o": org_id, "ids": refs[B.SOURCE_CARD]}).all()) \
        if refs[B.SOURCE_CARD] else {}
    for l in gone:
        why = _why_gone(l, questions, cards)
        about = last.item(l.item_id).about if last.item(l.item_id) is not None else None
        out.append(B.Item(
            item_id=B.item_id_for(B.CHANGE, about or l.item_id, "gone"), kind=B.CHANGE, about=about,
            subject=l.subject,
            material=B.Material(words=(("name", l.subject or "A line of your last brief"), ("what", why)),
                                names=tuple(n for n in (l.subject,) if n)),
            sources=tuple(l.sources), at=last.as_of))
    return out


def _why_gone(line: B.Line, questions: dict[str, str], cards: dict[str, str]) -> str:
    """Why a line of the last brief is not in today's — answered, closed, done, or no longer open."""
    for source in line.sources:
        if source.kind == B.SOURCE_QUESTION:
            state = questions.get(source.ref)
            if state == "answered":
                return "answered — you answered its question"
            if state == "retired":
                return "no longer asked"
        if source.kind == B.SOURCE_CARD:
            state = cards.get(source.ref)
            if state == "acted":
                return "done — you acted on its card"
            if state in ("dismissed", "expired", "superseded"):
                return f"closed — its card was {state}"
    if line.kind == B.PROMISE:
        return "no longer due — kept, or no longer open"
    if line.kind == B.MEETING:
        return "the meeting has passed"
    return "no longer open"


__all__ = ["ASKED_ON_ITS_CARD", "DEFAULT_TZ", "Day", "FIRST_BRIEF_LOOKBACK", "NAMING_SECTIONS", "REASONS_KEPT",
           "SHADOW_LABEL", "read_changes", "read_day", "speaks_of_you", "spoken_names", "you_said_on", "zone_of"]
