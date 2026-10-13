"""What the company says of itself, in its own mail — the record every file's dossier may read (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 1, tree `yc2_w27_s13b` M37.C2.L-data.V0.U04, `06` D63 and
D-s13b-7. F52: Ridgeline's Gautam set a bar in April — *"re-engage once you have ten paying customers"* —
and on 12 Sep the founder wrote to Vertex Angels, on ANOTHER file, *"we crossed 12 paying customers this
month"*. A file's dossier reads its own mail only, so Ridgeline's review asked the founder whether the bar
was met — a question his own mail had already answered (`03` s13b-F14).

THE RECORD is every statement the company made about itself in its own KEPT mail, across every file of
the tenant: an outbound mail (its sender is us — `platform/self_identity`), its words as memory holds them
(`prepared_content`; an archive's words are never read — the outcome is asked first, as the timeline asks
it, `03` F57), and of those words only the sentences that name US — the company by its own name, whole,
or "we" — beside a NUMBER or a MILESTONE. Newest first, at most `RECORD_LIMIT` lines, the rest counted;
each line its event id, so the dossier prints it as `[self:<event>]`, citable and quotable as a touch is.

WHAT IS NOT A STATEMENT ABOUT US, each refused for a reason:

  * a sentence that names us with no number and no milestone — "we will send the deck tomorrow";
  * a QUESTION — "can we meet on 14 Oct?" asks, it does not state;
  * a date or a time — "we are free on 14 Oct", "we spoke at 10:30" — a number of the calendar, not of
    the company: dates, times, ordinal days and years are read out before a number is looked for;
  * a PROJECTION — "we'll hit 20 customers by December", "we'd be at…": the record is what the company
    says it IS or HAS DONE, and a promise about itself is a different thing (the promises section's);
  * "we" inside another word ("weekly") — names are matched as whole words.

ONE READ PER SWEEP, NOT PER FILE (`read_company_record`): the newest `SCAN_LIMIT` outbound kept mails of
the tenant, the older ones counted as unread; the dossier leaves out a file's own mail (`excluding`) —
it is already that file's timeline. The selection itself (`record_of`) is pure over its rows.

Read-only: nothing here writes (a test reads every statement the module hands `text()`).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

#: The most lines the record keeps, newest first; the rest are counted in `cut`.
RECORD_LIMIT = 12
#: The most of one mail's statements a line carries, cut on a word; the rest counted in `said_cut`.
SAID_CHARS = 600
#: The newest outbound kept mails one sweep reads; older ones are counted in `unread`.
SCAN_LIMIT = 500

#: The words by which a mail of ours speaks for the company. Present and past only: "we'll" and "we'd"
#: speak of what the company WILL or WOULD do — a projection is no record of what it is.
WE_WORDS: tuple[str, ...] = ("we", "we've", "we're", "our", "ours")
#: What the company did, in the past tense its own mail writes it — a milestone needs no number.
MILESTONE_WORDS: tuple[str, ...] = (
    "crossed", "launched", "raised", "closed", "signed", "hired", "reached", "shipped", "onboarded",
    "went live", "incorporated", "registered", "won", "completed", "released", "doubled", "tripled",
    "secured", "acquired", "converted", "renewed", "selected", "accepted into", "graduated")

_MONTHS = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
           r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
#: A number of the calendar — read out of a sentence before a number about us is looked for.
_CALENDAR = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b"                                  # 2026-09-01
    r"|\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b"                  # 14/10, 14.10.2026
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b"                 # 10:30, 3:15 pm
    r"|\b\d{1,2}\s*(?:am|pm)\b"                                   # 3pm
    r"|\b\d{1,2}(?:st|nd|rd|th)\b"                                # the 18th
    rf"|\b\d{{1,2}}\s+(?:{_MONTHS})\b"                            # 14 Oct
    rf"|\b(?:{_MONTHS})\.?\s+\d{{1,2}}\b"                         # Oct 14
    r"|\b(?:19|20)\d{2}\b",                                       # a year
    re.IGNORECASE)
_DIGIT = re.compile(r"\d")
_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")


def _words(*words: str) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in words)
    return re.compile(rf"(?<![\w'’])(?:{alternatives})(?![\w'’])", re.IGNORECASE)


_WE = _words(*WE_WORDS)
_MILESTONE = _words(*MILESTONE_WORDS)


@dataclass(frozen=True, slots=True)
class SelfLine:
    """One mail of ours, and what it said of the company."""
    event_id: str
    at: datetime
    said: str                          # its statements about us, each whole, in order
    said_cut: int = 0                  # the characters of them left out
    thread: str | None = None
    mailbox: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "at": self.at.isoformat(), "said": self.said,
                "said_cut": self.said_cut, "thread": self.thread, "mailbox": self.mailbox}


@dataclass(frozen=True, slots=True)
class CompanyRecord:
    org_id: str
    as_of: datetime
    lines: tuple[SelfLine, ...]        # newest first
    cut: int = 0                       # statements past RECORD_LIMIT, left out
    unread: int = 0                    # outbound mail past SCAN_LIMIT, never read
    names: tuple[str, ...] = ()        # the company's names it read as us, beside "we"

    @property
    def newest(self) -> str | None:
        """The newest line's event — what a file's fingerprint names as the record it saw."""
        return self.lines[0].event_id if self.lines else None

    def excluding(self, events: Iterable[str]) -> tuple[SelfLine, ...]:
        """The record without a file's own mail: that mail is already the file's timeline."""
        own = set(events)
        return tuple(line for line in self.lines if line.event_id not in own)

    def newest_excluding(self, events: Iterable[str]) -> str | None:
        rest = self.excluding(events)
        return rest[0].event_id if rest else None

    def as_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "as_of": self.as_of.isoformat(),
                "lines": [line.as_dict() for line in self.lines], "cut": self.cut,
                "unread": self.unread, "names": list(self.names)}


def _speaks_of_us(sentence: str, name: re.Pattern[str] | None) -> bool:
    """A statement naming us beside a number or a milestone — see the module's list of what is not."""
    if sentence.rstrip().endswith("?"):
        return False
    if not (_WE.search(sentence) or (name is not None and name.search(sentence))):
        return False
    return bool(_MILESTONE.search(sentence) or _DIGIT.search(_CALENDAR.sub(" ", sentence)))


def statements(words: str | None, names: Iterable[str] = ()) -> tuple[str, ...]:
    """The sentences of one mail that speak of us, in order, each whole. Pure."""
    folded_names = [" ".join(str(n).split()) for n in names if str(n or "").strip()]
    name = _words(*folded_names) if folded_names else None
    out: list[str] = []
    for raw in _SENTENCES.split(str(words or "")):
        sentence = " ".join(raw.split())
        if sentence and _speaks_of_us(sentence, name):
            out.append(sentence)
    return tuple(out)


def _cut_on_a_word(said: str) -> tuple[str, int]:
    if len(said) <= SAID_CHARS:
        return said, 0
    head = said[:SAID_CHARS]
    if said[SAID_CHARS] != " " and " " in head:          # the limit falls inside a word: cut before it
        head = head.rsplit(" ", 1)[0]
    head = head.rstrip()
    return head, len(said) - len(head)


def _get(row: Any, name: str) -> Any:
    return row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def record_of(rows: Iterable[Any], *, org_id: str, as_of: datetime, names: Iterable[str] = (),
              limit: int | None = None, unread: int = 0) -> CompanyRecord:
    """The record from a sweep's outbound kept mail — each row its `event_id`, `occurred_at`, `words`,
    `thread` and `mailbox`. Pure: the same rows, the same record."""
    kept_names = tuple(" ".join(str(n).split()) for n in names if str(n or "").strip())
    limit = RECORD_LIMIT if limit is None else limit
    seen: set[str] = set()
    found: list[SelfLine] = []
    for row in rows:
        event_id, at = str(_get(row, "event_id") or ""), _get(row, "occurred_at")
        if not event_id or event_id in seen or at is None or _aware(at) > as_of:
            continue
        said = statements(_get(row, "words"), kept_names)
        if not said:
            continue
        seen.add(event_id)
        words, cut = _cut_on_a_word(" ".join(said))
        found.append(SelfLine(event_id=event_id, at=_aware(at), said=words, said_cut=cut,
                              thread=_get(row, "thread"), mailbox=_get(row, "mailbox")))
    found.sort(key=lambda line: (line.at, line.event_id), reverse=True)
    return CompanyRecord(org_id=org_id, as_of=as_of, lines=tuple(found[:limit]),
                         cut=max(0, len(found) - limit), unread=unread, names=kept_names)


#: The tenant's own kept mail, newest first: sent by an address of ours or at a domain of ours (or a
#: subdomain of one — `SelfIdentity.is_us`, spelled in SQL so the scan's limit counts only our mail), its
#: words read only through a KEPT event, never a private capture, never after the instant.
_OURS = text(
    "select se.event_id, se.occurred_at, se.parent_object_id as thread, se.connection_id as mailbox, "
    "       pc.clean_text as words, count(*) over () as total "
    "  from source_events se "
    "  join prepared_content pc on pc.org_id = se.org_id and pc.event_id = se.event_id "
    " where se.org_id = :o and se.source = 'gmail' and se.object_type = 'email_message' "
    "   and se.outcome = 'emitted' and se.visibility_scope is distinct from 'private' "
    "   and se.occurred_at <= :now "
    "   and (lower(se.actor->>'email') = any(cast(:addresses as text[])) "
    "        or exists (select 1 from unnest(cast(:domains as text[])) d(domain) "
    "                    where lower(split_part(se.actor->>'email', '@', 2)) = d.domain "
    "                       or lower(split_part(se.actor->>'email', '@', 2)) like '%.' || d.domain)) "
    " order by se.occurred_at desc, se.event_id desc limit :n")

_COMPANY = text("select company from orgs where id = :o")


def read_company_record(conn, org_id: str, *, now: datetime, names: Iterable[str] | None = None,
                        us: Any = None) -> CompanyRecord:
    """The record, read once for a sweep. `names` defaults to the company's own (`orgs.company`, as the
    brief names it); `us` to `platform/self_identity.identity_for`."""
    if us is None:
        from genios_engine.platform.self_identity import identity_for
        us = identity_for(conn, org_id)
    if names is None:
        company = conn.execute(_COMPANY, {"o": org_id}).scalar()
        names = (company,) if company else ()
    rows = conn.execute(_OURS, {"o": org_id, "now": now, "n": SCAN_LIMIT,
                                "addresses": sorted(us.addresses),
                                "domains": sorted(us.domains)}).fetchall()
    total = int(rows[0].total) if rows else 0
    return record_of(rows, org_id=org_id, as_of=now, names=names, unread=max(0, total - len(rows)))


__all__ = ["CompanyRecord", "MILESTONE_WORDS", "RECORD_LIMIT", "SAID_CHARS", "SCAN_LIMIT", "SelfLine",
           "WE_WORDS", "read_company_record", "record_of", "statements"]
