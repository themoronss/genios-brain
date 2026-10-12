"""The template brief — code's own words for every line, from its item's material and nothing else (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 items 2 and 6, tree `yc2_w27_s15` M44.C3.L-logic.V1.U03. What you read when no
model writes, and the words every written line is given back when the check refuses it (M45). Each line is built
from its item's material only: the checked headline, the expert's wait rule where it held, the question, the numbers
with their n, local dates. You are "you" (`03` F178) — a line never names you, and never calls you "the founder"; a
file is named by its counterparty (a name, never an address), never by the connector that introduced it; no quote.

THE ONE LINE says how many things need you today, a meeting today if there is one, and who waits on you — or, when
nothing is open, asked, due or watched, *"Nothing needs you today."* (`03` s15-F2: the ladder said "Nothing needs
you right now." while the expert held a wait rule and an open question.)

THE BRIEF is the day's items ordered (`executive/morning_order.order`), cut to the word budget from the back
(`fit`), each a line with its id, its words, its kind, who it is about and its sources; how it was written —
the template — and why. Pure: no I/O, no clock, no model.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from genios_engine.contracts import morning_brief as B
from genios_engine.executive.morning_order import Ordered, fit, order

#: Why a brief reads in code's words.
TEMPLATE_WHY = "the template: code's words from the day's material — no writer is armed for this tenant"
NOTHING = "Nothing needs you today."
#: The words the one line may take, kept out of the lines' budget.
ONE_LINE_RESERVE = 30


def _day(iso: str | None) -> str | None:
    """`2026-09-27` → `27 Sep`."""
    if not iso:
        return None
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b')}"


def _sentence(words: str | None) -> str:
    said = " ".join(str(words or "").split())
    return said if not said or said[-1] in ".!?" else said + "."


def _people(n: int) -> str:
    return "1 person" if n == 1 else f"{n} people"


def words_for(item: B.Item, section: str, *, local_date: date | None = None) -> str:
    """Code's words for one item in one section — from its material only."""
    m = item.material
    name = m.word("name") or item.subject or "A file"
    if item.kind == B.DECISION:
        out = f"{name}: {_sentence(m.word('headline'))}"
        if m.date("by"):
            out += f" By {_day(m.date('by'))}."
        reply, who = m.number("your_reply_time"), m.word("reply_with")
        if reply is not None and who:
            out += f" You usually answer {who} in {reply.value:g} days (n={reply.n})."
        quiet = m.number("quiet")
        if section == B.STUCK and quiet is not None:
            out += f" Quiet for {quiet.says}."
        return out
    if item.kind == B.QUESTION:
        out = f"{name}: {_sentence(m.word('question'))}"
        return out + (f" By {_day(m.date('by'))}." if m.date("by") else "")
    if item.kind == B.WATCHED:
        out = f"{name}: {_sentence(m.word('headline'))}"
        if m.word("wait_rule"):
            out += f" {_sentence(m.word('wait_rule'))}"
        quiet = m.number("quiet")
        return out + (f" Quiet for {quiet.says}." if quiet is not None else "")
    if item.kind == B.PROMISE:
        to = m.word("to")
        out = f"You promised {to}: " if to else "You promised: "
        out += " ".join(str(m.word("promise") or "").split())
        if m.word("file") and m.word("file") != to:
            out += f" ({m.word('file')})"
        due = m.date("due")
        late = due is not None and local_date is not None and date.fromisoformat(due) < local_date
        return out + (f" — was due {_day(due)}." if late else f" — due {_day(due)}." if due else ".")
    if item.kind == B.MEETING:
        out = f"{m.word('when')}: {m.word('title')}"
        if m.names:
            out += " with " + ", ".join(m.names)
        out += "."
        if m.word("prep"):
            out += " " + _sentence(m.word("prep"))
        return out
    if item.kind == B.NO_FOLLOW_UP:
        out = f"{m.word('title')}, {m.word('when')}: no follow-up from you to anyone you met there"
        return out + (" — " + ", ".join(m.names) + "." if m.names else ".")
    if item.kind == B.DESK:
        waiting = m.number("waiting")
        n = waiting.n if waiting is not None else 0
        who = []
        for number in m.numbers:
            if number.name.startswith("waiting:"):
                person = m.word(number.name)
                who.append(f"{person} ({number.says})" if person else f"someone ({number.says})")
        since = m.number("since_your_last_mail")
        wait = "waits" if n == 1 else "wait"
        head = (f"You have sent nothing for {since.says} while {_people(n)} {wait} on you" if since is not None
                else f"{_people(n)} {wait} on you")
        return head + (": " + ", ".join(who) + "." if who else ".")
    if item.kind == B.CHANGE:
        what = " ".join(str(m.word("what") or "").split())
        return _sentence(what) if what.lower().startswith(name.lower()) else f"{name}: {_sentence(what)}"
    raise ValueError(f"no words for an item of kind {item.kind!r}")


def one_line(ordered: Ordered) -> str:
    """How the brief begins: what needs you today — or that nothing does."""
    if not any(items for name, items in ordered.sections if name != B.CHANGED):
        return NOTHING
    today = ordered.items(B.TODAY)
    parts = []
    if today:
        n = len(today)
        parts.append(f"{n} thing{'s' if n != 1 else ''} need{'s' if n == 1 else ''} you")
    else:
        parts.append("Nothing urgent today")
    meeting = next((i for i in today if i.kind == B.MEETING), None)
    if meeting is not None:
        parts.append(f"a meeting today: {meeting.material.word('title')}")
    desk = next(iter(ordered.items(B.YOUR_DESK)), None)
    if desk is not None and desk.material.number("waiting") is not None:
        parts.append(f"{_people(desk.material.number('waiting').n)} waiting on you")
    if not today:
        rest = sum(len(items) for name, items in ordered.sections if name not in (B.TODAY, B.CHANGED))
        parts.append(f"{rest} thing{'s' if rest != 1 else ''} to know")
    return "; ".join(parts) + "."


def template_brief(*, org_id: str, seat_id: str, items: Iterable[B.Item], now: datetime, tz: str) -> B.Brief:
    """The day in code's words: ordered, cut to the budget, every line with its id and sources."""
    items = tuple(items)
    local = now.astimezone(ZoneInfo(tz)).date()
    ordered = order(items, now=now, tz=tz)
    ordered = fit(ordered, lambda section, item: B.count_words(words_for(item, section, local_date=local)),
                  budget=B.WORD_BUDGET - ONE_LINE_RESERVE)
    lines = tuple(
        B.Line(line_id=B.line_id_for(org_id, seat_id, local, section, item.item_id), item_id=item.item_id,
               section=section, words=words_for(item, section, local_date=local), kind=item.kind,
               subject=item.subject, sources=item.sources)
        for section, held in ordered.sections for item in held)
    return B.Brief(org_id=org_id, seat_id=seat_id, local_date=local, timezone=tz, as_of=now,
                   one_line=one_line(ordered), lines=lines, items=items, written_by=B.TEMPLATE_BRIEF,
                   why=TEMPLATE_WHY, model=None, tier=None, cost_micro_usd=0, cut=ordered.cut,
                   material_digest=B.digest_of(items), flexed=ordered.flexed)


__all__ = ["NOTHING", "ONE_LINE_RESERVE", "TEMPLATE_WHY", "one_line", "template_brief", "words_for"]
