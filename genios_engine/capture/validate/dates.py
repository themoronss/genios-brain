"""ALG-09 · L1.5.2 — the date/time normalizer: a phrase in, a window plus a certainty out.

*"Our renewal is coming up pretty soon"* is worthless as a string and dangerous as a
fabricated timestamp. Collapsing a relative phrase to a single instant invents precision the
source never carried, and the deadline-proximity term of the importance formula (ALG-17) then
reads that invented precision as real urgency — which is how a founder gets a red card about a
renewal nobody ever dated. So every phrase leaves here as a window plus an explicit
`DateCertainty`, and the two heuristic bands (ALG-09 rows 9 and 10) are labelled `RELATIVE`
precisely so nothing downstream may treat them as a deadline.

Three properties are load-bearing, and all three are properties of this SOURCE FILE rather
than of any test — gate G1 greps the directory, not the suite:

* **No clock.** `eval_time` is a required parameter on every entry point, and
  `resolved_against` is written onto every `ResolvedDate` returned. Replaying a March event
  has to resolve "next week" against March forever; a clock read here makes yesterday's
  extraction a different fact tomorrow, with nothing in the row to show it changed.
* **No float.** Integer and `timedelta` arithmetic only. A date normalizer has no honest use
  for binary fractions, and the moment one appears the arithmetic stops being replayable.
* **No model.** The extractor already emitted the phrase into `as_written`; turning a phrase
  into a range is arithmetic. A validator that calls a model is not a validator.

**Timezone.** Resolution happens in the ORG's timezone and the result is stored in UTC. "End
of month" for a Mumbai org closes five and a half hours earlier in UTC than for a London one;
a normalizer that resolved in UTC would hand both the same instant and be wrong for one of
them, by a margin that lands on the wrong calendar day.

**Time of day.** A calendar day named as a deadline is not missed until that day ends, so an
EXACT day resolves to the last whole second of the day in the org timezone (23:59:59 local)
and a RANGE runs from 00:00:00 local of its first day to 23:59:59 local of its last. Resolving
a named day to its midnight instead would make "today", said at 09:00, resolve to an instant
nine hours in the past and read as overdue the moment it was written. Both bounds of a RANGE
are converted from local wall clock independently, so a week straddling a DST transition is
seven LOCAL days and not 168 hours — an hour short of 168 across spring forward, an hour long
across fall back. Doc 05 requires only "resolve in org tz, store UTC" and is silent on the
straddling range; the choice made here is that "next week" names the same seven local days
whatever the offset does inside it. Anchoring the far end by elapsed seconds from the near one
instead would close the spring-forward week at 22:59:59 local, dropping the last hour of its
last day out of every proximity score computed from it.

**Past dates are returned as written** (ALG-09 rule 6). "The renewal was Friday", said on a
Monday, is a fact about a date that was missed; rolling it forward to the next Friday erases
the only interesting thing about it. `ResolvedDate.date_in_past` derives the flag from the
window and the `eval_time` it was resolved against, so nothing here needs to store it.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.units import DateCertainty, ResolvedDate
from genios_engine.contracts.validators import require_aware

#: The first and last instant of a local calendar day. See the module docstring: a day named as
#: a deadline stays open until it closes, so a resolved day is its final second, not its first.
DAY_START = time(0, 0, 0)
DAY_END = time(23, 59, 59)

#: ALG-09 rows 9 and 10. Both are admitted heuristics — the phrase carried no bound at all, and
#: these are the widths beyond which a "soon" stops being actionable and a "later" stops being a
#: plan. They are exposed as constants so a future recalibration is one edit and one test row,
#: not a magic number buried in two branches.
SOON_WINDOW_DAYS = 14
LATER_WINDOW_DAYS = 90

#: ALG-09 row 7 — "end of month" is the last three days of the period, not its final instant.
#: Someone who says "end of month" is describing a stretch they intend to act inside; pinning it
#: to the 31st alone would make the 29th look early when it was exactly what was meant.
END_OF_PERIOD_DAYS = 3

#: Saturday and Sunday, as `date.weekday()` numbers them. The default non-working days for
#: `add_business_days`; the org's actual holidays arrive as an injected parameter because this
#: module has no database to read a calendar out of and must not invent one.
WEEKEND = frozenset({5, 6})

#: The regions that write dates month-first. This is a fact about the world rather than a guess:
#: the United States and the Philippines write 03/04 as March 4th and essentially everybody else
#: writes it as the 3rd of April. A locale that names no region cannot settle the order, and an
#: ambiguous numeric date with no settled order is returned UNRESOLVED rather than guessed —
#: guessing here is exactly the class of fault that turns a March renewal into an April one.
MONTH_FIRST_REGIONS = frozenset({"US", "PH"})

_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}

#: Full weekday names only, and deliberately no three-letter abbreviations. "sat" is also the
#: past tense of "sit" and "wed" is a verb: "we sat down with them Friday" would resolve to
#: Saturday under an abbreviation table, because the cascade takes the leftmost match. A missed
#: weekday costs an UNRESOLVED; a wrong one costs a meeting.
_WEEKDAYS: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

#: Written-out counts, because "thirty days notice" and "two weeks" are how contracts and humans
#: actually phrase a period. Bounded on purpose — a general number-word parser would be a second
#: language in this file, and every entry here is one somebody has to be able to read back.
_NUMBER_WORDS: dict[str, int] = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "fourteen": 14, "fifteen": 15, "eighteen": 18, "twenty": 20, "thirty": 30,
    "forty five": 45, "forty-five": 45, "sixty": 60, "ninety": 90,
}


def _alternation(words: Sequence[str]) -> str:
    """Longest-first alternation, so "september" is never eaten by "sep" and "an" beats "a".

    Python's `re` takes the first branch that matches at a position rather than the longest, so
    the ordering here is not cosmetic: reversed, `sept` would match the first four characters of
    "september" and leave "ember" to break the surrounding pattern.
    """
    return "|".join(sorted(words, key=len, reverse=True))


_MONTH_ALT = _alternation(list(_MONTHS))
_WEEKDAY_ALT = _alternation(list(_WEEKDAYS))
_COUNT_ALT = r"\d{1,4}|" + _alternation(list(_NUMBER_WORDS))
_ORDINAL = r"(?:st|nd|rd|th)?"

_ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_ISO_SLASH = re.compile(r"\b(\d{4})[/.](\d{1,2})[/.](\d{1,2})\b")
_MONTH_DAY_YEAR = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}}){_ORDINAL},?\s+(\d{{4}})\b", re.IGNORECASE)
_DAY_MONTH_YEAR = re.compile(
    rf"\b(\d{{1,2}}){_ORDINAL}\s+(?:of\s+)?({_MONTH_ALT})\.?,?\s+(\d{{4}})\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")
_MONTH_DAY = re.compile(rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}}){_ORDINAL}\b", re.IGNORECASE)
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}}){_ORDINAL}\s+(?:of\s+)?({_MONTH_ALT})\b", re.IGNORECASE)
_WEEKDAY = re.compile(rf"\b({_WEEKDAY_ALT})\b", re.IGNORECASE)
_DAY_OFFSET = re.compile(r"\b(today|tonight|tomorrow|yesterday)\b", re.IGNORECASE)
#: Deliberately unguarded. These two patterns describe a bare period and nothing else; which
#: phrase they are ALLOWED to answer is settled once, by the order of `_CASCADE`, where row 7 is
#: consulted first and takes anything that names a period's end. The earlier design put a
#: `(?<!of )` lookbehind here instead, and it was wrong in both directions: it did not block
#: "end of THE next quarter" — a spelling row 7's own pattern accepts — so row 5 claimed that
#: phrase and returned ninety-one days where three were written, and it DID block "start of next
#: quarter" and "as of current month", which no other row wanted, so those resolved to nothing at
#: all. A lookbehind that has to re-list every prefix a sibling pattern accepts is a copy of that
#: pattern maintained by hand, and nothing fails when the copy falls behind.
_NEXT_PERIOD = re.compile(r"\bnext\s+(week|month|quarter|year)\b", re.IGNORECASE)
_THIS_PERIOD = re.compile(
    r"\b(?:this|current)\s+(week|month|quarter|year)\b", re.IGNORECASE)
_END_OF_PERIOD = re.compile(
    rf"\b(?:end|close)\s+of\s+(?:the\s+)?(?:(this|next|current)\s+)?"
    rf"(week|month|quarter|year|q[1-4]|{_MONTH_ALT})\b", re.IGNORECASE)
_IN_N_UNITS = re.compile(
    rf"\b(?:in|within|over\s+the\s+next)\s+(?P<count>{_COUNT_ALT})\s*[-\s]?\s*"
    rf"(?P<unit>business\s+days?|working\s+days?|calendar\s+days?|days?|weeks?|fortnights?|"
    rf"months?|quarters?|years?)\b", re.IGNORECASE)
_SOON = re.compile(
    r"\b(?:pretty\s+soon|very\s+soon|quite\s+soon|soon|shortly|in\s+the\s+near\s+future|"
    r"near[-\s]term)\b", re.IGNORECASE)
_LATER = re.compile(
    r"\b(?:later|some\s?time|down\s+the\s+line|down\s+the\s+road|eventually|"
    r"at\s+some\s+point|in\s+the\s+future)\b", re.IGNORECASE)

#: Duration units and what one of each is worth as (months, days, seconds). Months are carried
#: separately from days on purpose: a month has no fixed length, and writing 30 here would make
#: "3 months notice" silently mean 90 days — which is wrong in exactly the months a renewal is
#: most likely to fall in. `resolve_duration` refuses to return a `timedelta` for anything whose
#: months component is non-zero for the same reason.
_DURATION_UNITS: dict[str, tuple[int, int, int]] = {
    "minute": (0, 0, 60), "hour": (0, 0, 3600), "day": (0, 1, 0), "calendar day": (0, 1, 0),
    "week": (0, 7, 0), "fortnight": (0, 14, 0), "month": (1, 0, 0), "quarter": (3, 0, 0),
    "year": (12, 0, 0),
}
_DURATION = re.compile(
    rf"\b(?P<count>{_COUNT_ALT})\s*[-\s]?\s*(?P<unit>business\s+days?|working\s+days?|"
    rf"calendar\s+days?|days?|weeks?|fortnights?|months?|quarters?|years?|hours?|minutes?)"
    rf"['’]?s?\b", re.IGNORECASE)

_RECURRENCE_UNITS: dict[str, tuple[str, int]] = {
    "day": ("DAILY", 1), "week": ("WEEKLY", 1), "fortnight": ("WEEKLY", 2),
    "month": ("MONTHLY", 1), "quarter": ("MONTHLY", 3), "year": ("YEARLY", 1),
}
_RECURRENCE_LITERALS: dict[str, str] = {
    "daily": "FREQ=DAILY;INTERVAL=1",
    "weekly": "FREQ=WEEKLY;INTERVAL=1",
    "fortnightly": "FREQ=WEEKLY;INTERVAL=2",
    "monthly": "FREQ=MONTHLY;INTERVAL=1",
    "quarterly": "FREQ=MONTHLY;INTERVAL=3",
    "semi-annual": "FREQ=MONTHLY;INTERVAL=6",
    "semi-annually": "FREQ=MONTHLY;INTERVAL=6",
    "semiannual": "FREQ=MONTHLY;INTERVAL=6",
    "twice a year": "FREQ=MONTHLY;INTERVAL=6",
    "annual": "FREQ=YEARLY;INTERVAL=1",
    "annually": "FREQ=YEARLY;INTERVAL=1",
    "yearly": "FREQ=YEARLY;INTERVAL=1",
    "per annum": "FREQ=YEARLY;INTERVAL=1",
}
_RECURRENCE_EVERY = re.compile(
    rf"\b(?:every|each)\s+(?:(?P<count>{_COUNT_ALT})\s*[-\s]?\s*)?"
    rf"(?P<unit>days?|weeks?|fortnights?|months?|quarters?|years?)\b", re.IGNORECASE)
_RECURRENCE_LITERAL = re.compile(
    rf"\b({_alternation(list(_RECURRENCE_LITERALS))})\b", re.IGNORECASE)
#: "Biweekly" means both "every two weeks" and "twice a week" in ordinary English, and no rule
#: picks between them without guessing. A renewal cadence that is wrong by a factor of four is
#: worse than one the founder is asked about, so this phrase resolves to nothing at all.
_AMBIGUOUS_RECURRENCE = re.compile(r"\bbi[-\s]?(weekly|monthly)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _Window:
    """One cascade row's answer, still in the vocabulary of the contract it will become.

    Kept internal rather than returned: `ResolvedDate` is the boundary type and the only thing
    another module may hold. This exists so a rule function can say "matched, and here is the
    window" separately from "did not match", which a bare tuple of Nones could not express.
    """

    earliest: datetime | None
    latest: datetime | None
    certainty: DateCertainty


#: A phrase that MATCHED a rule and still cannot be resolved — the ambiguous numeric date with
#: no locale. Distinct from a rule returning None (no match), because a match that fails must
#: stop the cascade: letting "03/04/2026" fall through to the "later" row would answer a precise
#: question with a ninety-day guess.
_UNRESOLVED = _Window(None, None, DateCertainty.UNRESOLVED)


@dataclass(frozen=True)
class _Ctx:
    """Everything a cascade row is allowed to know. There is no fifth field called "now"."""

    eval_time: datetime
    zone: ZoneInfo
    local: datetime
    local_date: date
    locale: str | None
    holidays: frozenset[date]


@dataclass(frozen=True)
class CalendarDuration:
    """A notice period as it was actually written: months kept apart from days.

    L1.5.2-U2's WHY is that a renewal date without its notice period gives the founder the wrong
    deadline. "3 months notice" before a 1 November renewal is 1 August, which is 92 days on that
    anchor and 90 on another, so the only faithful representation of the phrase is the phrase's
    own units. `resolve_duration` converts to `timedelta` exactly when that conversion is lossless
    and returns nothing when it is not; `add_calendar_duration` applies the calendar half against
    a real anchor, where a month finally has a length.
    """

    months: int = 0
    days: int = 0
    seconds: int = 0

    def __post_init__(self) -> None:
        for label in ("months", "days", "seconds"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{label} must be an exact integer, not {type(value).__name__}")

    @property
    def is_exact_length(self) -> bool:
        """True when the duration has one length regardless of where it is anchored — which is
        true of days and weeks and false of every month-shaped phrase."""
        return self.months == 0

    def negated(self) -> CalendarDuration:
        """The same period pointing backwards — a notice period is almost always subtracted from
        a renewal date rather than added to one."""
        return CalendarDuration(months=-self.months, days=-self.days, seconds=-self.seconds)


def _zone_of(tz: str) -> ZoneInfo:
    """A bad timezone name raises rather than defaulting to UTC.

    A silently-defaulted zone is an unanswered question that expresses itself days later as a
    reminder on the wrong calendar day; a raise is answered by whoever configured the connection,
    in the minute they configured it.
    """
    if not isinstance(tz, str) or not tz.strip():
        raise ValueError("tz is required — resolution happens in the org's timezone, not UTC")
    return ZoneInfo(tz)


def _at(day: date, moment: time, zone: ZoneInfo) -> datetime:
    """A local wall-clock instant, returned in UTC.

    Across a spring-forward gap a wall-clock time may not exist; `astimezone` resolves it with
    the offset in force before the transition, which is deterministic and therefore replayable.
    Neither bound this module produces (00:00:00 and 23:59:59) falls in any real transition gap,
    so the branch is a guarantee rather than a workaround.
    """
    return datetime.combine(day, moment, tzinfo=zone).astimezone(timezone.utc)


def _day_start(day: date, zone: ZoneInfo) -> datetime:
    return _at(day, DAY_START, zone)


def _day_end(day: date, zone: ZoneInfo) -> datetime:
    return _at(day, DAY_END, zone)


def _exact_day(day: date, zone: ZoneInfo) -> _Window:
    """EXACT means one instant, and `ResolvedDate` enforces `earliest == latest`. The instant is
    the day's last second, so a deadline named as a day is not overdue while the day is running."""
    moment = _day_end(day, zone)
    return _Window(moment, moment, DateCertainty.EXACT)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Month arithmetic on an integer month index — no float division anywhere in the file."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _safe_date(year: int, month: int, day: int) -> date | None:
    """None rather than an exception for 31 February — a malformed date in a sentence is an
    UNRESOLVED phrase, not a crash in the extraction pipeline."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _period_bounds(anchor: date, kind: str, offset: int) -> tuple[date, date]:
    """First and last local day of the week / month / quarter / year containing `anchor`,
    shifted by `offset` whole periods. Weeks run Monday to Sunday, which is what ALG-09 row 5
    means by "next Mon" through "next Sun"."""
    if kind == "week":
        start = anchor - timedelta(days=anchor.weekday()) + timedelta(days=7 * offset)
        return start, start + timedelta(days=6)
    if kind == "month":
        year, month = _add_months(anchor.year, anchor.month, offset)
        return date(year, month, 1), date(year, month, _last_day(year, month))
    if kind == "quarter":
        first_month = ((anchor.month - 1) // 3) * 3 + 1
        year, month = _add_months(anchor.year, first_month, 3 * offset)
        end_year, end_month = _add_months(year, month, 2)
        return date(year, month, 1), date(end_year, end_month, _last_day(end_year, end_month))
    year = anchor.year + offset
    return date(year, 1, 1), date(year, 12, 31)


def _next_occurrence(month: int, day: int, anchor: date) -> date | None:
    """ALG-09 row 2 — a month and day with no year mean the next time that date comes round.

    Inclusive of `anchor` itself: "October 15", written on October 15, means today. Rolls to the
    following year otherwise, and returns None for a day the month never has, so that "February
    30" is UNRESOLVED rather than silently becoming March 2nd.
    """
    candidate = _safe_date(anchor.year, month, day)
    if candidate is None:
        return None
    if candidate >= anchor:
        return candidate
    return _safe_date(anchor.year + 1, month, day)


def _month_first(locale: str | None) -> bool | None:
    """Day/month order from the connection's locale, or None when the locale cannot settle it.

    None is the honest answer for `None`, for a bare language tag like "en" (spoken in both
    orders), and for anything that is not a locale at all. The caller turns None into UNRESOLVED
    rather than picking an order, because picking is how 3 April becomes 4 March.
    """
    if not isinstance(locale, str) or not locale.strip():
        return None
    parts = re.split(r"[-_]", locale.strip())
    if len(parts) < 2:
        return None
    region = parts[1].upper()
    if not re.fullmatch(r"[A-Z]{2}", region):
        return None
    return region in MONTH_FIRST_REGIONS


def _count_token(token: str) -> int | None:
    text = " ".join(token.replace("-", " ").lower().split())
    if text.isdigit():
        return int(text)
    return _NUMBER_WORDS.get(text) or _NUMBER_WORDS.get(text.replace(" ", "-"))


def _unit_key(token: str) -> str:
    """Normalise "Business Days" / "months" / "quarter" to the singular lookup key."""
    text = " ".join(token.lower().split())
    text = text.rstrip("s")
    return "calendar day" if text == "calendar day" else text


def _rule_01_explicit_date(text: str, ctx: _Ctx) -> _Window | None:
    """Row 1 — an explicit date, taken exactly as written including into the past.

    Four unambiguous shapes are read first (ISO, ISO with slashes, and the two month-name
    orders); the purely numeric shape is read last because it is the only one whose meaning
    depends on who typed it. 03/04/2026 is March 4th in Chicago and April 3rd in Chennai, and
    the Globe Worked fault is exactly this class of error surviving every layer above.
    """
    match = _ISO_DATE.search(text) or _ISO_SLASH.search(text)
    if match is not None:
        day = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return _exact_day(day, ctx.zone) if day else _UNRESOLVED

    match = _MONTH_DAY_YEAR.search(text)
    if match is not None:
        day = _safe_date(int(match.group(3)), _MONTHS[match.group(1).lower()],
                         int(match.group(2)))
        return _exact_day(day, ctx.zone) if day else _UNRESOLVED

    match = _DAY_MONTH_YEAR.search(text)
    if match is not None:
        day = _safe_date(int(match.group(3)), _MONTHS[match.group(2).lower()],
                         int(match.group(1)))
        return _exact_day(day, ctx.zone) if day else _UNRESOLVED

    match = _NUMERIC_DATE.search(text)
    if match is None:
        return None
    first, second, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if first > 12 and second <= 12:
        month, day_number = second, first          # only one reading exists: day-first
    elif second > 12 and first <= 12:
        month, day_number = first, second          # only one reading exists: month-first
    elif first <= 12 and second <= 12:
        month_first = _month_first(ctx.locale)
        if month_first is None:
            return _UNRESOLVED                     # two readings, no locale — never guess
        month, day_number = (first, second) if month_first else (second, first)
    else:
        return _UNRESOLVED
    day = _safe_date(year, month, day_number)
    return _exact_day(day, ctx.zone) if day else _UNRESOLVED


def _rule_02_month_day(text: str, ctx: _Ctx) -> _Window | None:
    """Row 2 — "October 15" with no year means the next October 15th, today included."""
    match = _MONTH_DAY.search(text)
    if match is not None:
        month, day_number = _MONTHS[match.group(1).lower()], int(match.group(2))
    else:
        match = _DAY_MONTH.search(text)
        if match is None:
            return None
        month, day_number = _MONTHS[match.group(2).lower()], int(match.group(1))
    day = _next_occurrence(month, day_number, ctx.local_date)
    return _exact_day(day, ctx.zone) if day else _UNRESOLVED


def _rule_03_weekday(text: str, ctx: _Ctx) -> _Window | None:
    """Row 3 — a bare weekday is the next such weekday STRICTLY after the eval date.

    This is the documented answer to "next Friday" said on a Friday: it means the coming one, a
    week out, not the day it was written. The alternative — treating same-day as a match — turns
    every "let's talk Friday" sent on a Friday afternoon into a deadline that is already half
    spent, and there is no phrasing that distinguishes the two intents, so the cascade picks one
    and says so here.
    """
    match = _WEEKDAY.search(text)
    if match is None:
        return None
    target = _WEEKDAYS[match.group(1).lower()]
    ahead = (target - ctx.local_date.weekday()) % 7 or 7
    return _exact_day(ctx.local_date + timedelta(days=ahead), ctx.zone)


def _rule_04_day_offset(text: str, ctx: _Ctx) -> _Window | None:
    """Row 4 — today / tonight / tomorrow / yesterday, counted in local days.

    "Yesterday" is the row's mirror image and is included deliberately: it is the commonest way a
    past-dated commitment enters a thread, and rule 6 says such a date is kept as written rather
    than rolled forward, which it cannot be if the phrase resolves to nothing.
    """
    match = _DAY_OFFSET.search(text)
    if match is None:
        return None
    offset = {"today": 0, "tonight": 0, "tomorrow": 1, "yesterday": -1}[match.group(1).lower()]
    return _exact_day(ctx.local_date + timedelta(days=offset), ctx.zone)


def _rule_05_next_period(text: str, ctx: _Ctx) -> _Window | None:
    """Row 5 — "next week" is Monday through Sunday of the following week, as a RANGE.

    The whole doctrine in one row. Nobody who writes "next week" has named Tuesday, and a single
    timestamp here is a deadline nobody agreed to.
    """
    match = _NEXT_PERIOD.search(text)
    if match is None:
        return None
    start, end = _period_bounds(ctx.local_date, match.group(1).lower(), 1)
    return _Window(_day_start(start, ctx.zone), _day_end(end, ctx.zone), DateCertainty.RANGE)


def _rule_06_this_period(text: str, ctx: _Ctx) -> _Window | None:
    """Row 6 — "this week" runs from the eval instant to the period's end, not from its start.

    The elapsed part of the week is not available to promise, so including it would widen the
    window into the past and dilute every proximity score computed from it. The clamp covers the
    one degenerate case — an eval instant inside the final second of the period — where the two
    bounds would otherwise cross and the contract would refuse the object.
    """
    match = _THIS_PERIOD.search(text)
    if match is None:
        return None
    _, end = _period_bounds(ctx.local_date, match.group(1).lower(), 0)
    latest = _day_end(end, ctx.zone)
    return _Window(ctx.eval_time, max(latest, ctx.eval_time), DateCertainty.RANGE)


def _rule_07_end_of_period(text: str, ctx: _Ctx) -> _Window | None:
    """Row 7 — "end of month/quarter" is the last three days of the period, as a RANGE.

    Named periods ("end of Q3", "end of October") resolve to the next such period that has not
    already closed, on the same terms as row 2: a Q3 phrase written in November means next year's
    Q3, because the one just past cannot be a deadline anybody is planning against.

    Consulted BEFORE rows 5 and 6 (see `_CASCADE`). Every qualified phrase this row reads — "end
    of next month", "close of the current quarter" — contains a bare period phrase those rows
    match too, and the whole period is the wrong answer to a sentence about its last three days:
    a ninety-one-day window is a deadline that never looks urgent to ALG-17, which reads the
    width and not the words.
    """
    match = _END_OF_PERIOD.search(text)
    if match is None:
        return None
    qualifier = (match.group(1) or "").lower()
    period = match.group(2).lower()
    if period.startswith("q") and len(period) == 2:
        first_month = (int(period[1]) - 1) * 3 + 1
        start, end = _named_period(ctx.local_date, first_month, first_month + 2)
    elif period in _MONTHS:
        month = _MONTHS[period]
        start, end = _named_period(ctx.local_date, month, month)
    else:
        start, end = _period_bounds(ctx.local_date, period, 1 if qualifier == "next" else 0)
    first = max(start, end - timedelta(days=END_OF_PERIOD_DAYS - 1))
    return _Window(_day_start(first, ctx.zone), _day_end(end, ctx.zone), DateCertainty.RANGE)


def _named_period(anchor: date, first_month: int, last_month: int) -> tuple[date, date]:
    """The next occurrence of a named month span — this year if it has not closed, else next."""
    year = anchor.year
    end = date(year, last_month, _last_day(year, last_month))
    if end < anchor:
        year += 1
        end = date(year, last_month, _last_day(year, last_month))
    return date(year, first_month, 1), end


def _rule_08_in_n_units(text: str, ctx: _Ctx) -> _Window | None:
    """Row 8 — "in N days / weeks / months" is EXACT because N was given.

    Business days route through `add_business_days` (L1.5.2-U3) rather than through calendar
    arithmetic: "in 5 business days" is seven calendar days at minimum and more across a holiday,
    and treating it as five is how every compliance deadline in a quarter lands early.
    """
    match = _IN_N_UNITS.search(text)
    if match is None:
        return None
    count = _count_token(match.group("count"))
    if count is None:
        return _UNRESOLVED
    unit = _unit_key(match.group("unit"))
    if unit in ("business day", "working day"):
        landed = add_business_days(ctx.eval_time, count, ctx.holidays, tz=ctx.zone.key)
        return _exact_day(landed.astimezone(ctx.zone).date(), ctx.zone)
    if unit in ("day", "calendar day"):
        return _exact_day(ctx.local_date + timedelta(days=count), ctx.zone)
    if unit == "week":
        return _exact_day(ctx.local_date + timedelta(days=7 * count), ctx.zone)
    if unit == "fortnight":
        return _exact_day(ctx.local_date + timedelta(days=14 * count), ctx.zone)
    months = {"month": 1, "quarter": 3, "year": 12}[unit] * count
    year, month = _add_months(ctx.local_date.year, ctx.local_date.month, months)
    day = _safe_date(year, month, min(ctx.local_date.day, _last_day(year, month)))
    return _exact_day(day, ctx.zone) if day else _UNRESOLVED


def _rule_09_soon(text: str, ctx: _Ctx) -> _Window | None:
    """Row 9 — "soon" gets a fourteen-day window and the RELATIVE band that says we made it up.

    The band is the point. The window exists so the phrase can be ranked at all; `RELATIVE` is
    what forbids anything downstream from rendering it as a due date.
    """
    if _SOON.search(text) is None:
        return None
    return _Window(ctx.eval_time, ctx.eval_time + timedelta(days=SOON_WINDOW_DAYS),
                   DateCertainty.RELATIVE)


def _rule_10_later(text: str, ctx: _Ctx) -> _Window | None:
    """Row 10 — "later" / "sometime" / "down the line": ninety days, and equally admitted."""
    if _LATER.search(text) is None:
        return None
    return _Window(ctx.eval_time, ctx.eval_time + timedelta(days=LATER_WINDOW_DAYS),
                   DateCertainty.RELATIVE)


#: What ONE period of an RRULE frequency is worth, as a `CalendarDuration`. The rule string is
#: `resolve_recurrence`'s own output and is parsed back rather than duplicated: the cadence has
#: exactly one owner, and a second table here saying "quarterly means three months" would be a
#: copy that nothing fails when it falls behind. Months stay months for the reason U2 gives —
#: a monthly cadence anchored in January is 31 days and in February is 28.
_FREQ_PERIOD: dict[str, CalendarDuration] = {
    "DAILY": CalendarDuration(days=1),
    "WEEKLY": CalendarDuration(days=7),
    "MONTHLY": CalendarDuration(months=1),
    "YEARLY": CalendarDuration(months=12),
}
_RRULE = re.compile(r"^FREQ=(?P<freq>[A-Z]+);INTERVAL=(?P<interval>\d+)$")


def _recurrence_period(rrule: str) -> CalendarDuration | None:
    """One cycle of a recurrence rule, or None for a frequency this file cannot size.

    None rather than a fallback: a cadence whose period is unknown must leave the phrase
    UNRESOLVED, because the alternative is a window whose width was invented by the default.
    """
    match = _RRULE.match(rrule)
    if match is None:
        return None
    period = _FREQ_PERIOD.get(match.group("freq"))
    if period is None:
        return None
    interval = int(match.group("interval"))
    if interval < 1:
        return None
    return CalendarDuration(months=period.months * interval, days=period.days * interval,
                            seconds=period.seconds * interval)


#: The recurrence literals that modify a NOUN instead of scheduling an EVENT. "Our annual
#: contract" and "$84K per annum" name a cadence for a THING, and neither says that anything is
#: going to happen — reading them as a date would hand the deadline-proximity term a year-wide
#: window every time somebody mentions the contract they are already inside. The adverbs
#: ("annually", "quarterly", "monthly", "fortnightly", ...) are the other half of the same table
#: and DO schedule something: "we review annually" names a next review. `resolve_recurrence`
#: answers all of them, correctly, because "what cadence is this" is a different question from
#: "does this phrase name a date"; row 12 is where the second question is asked.
_ADJECTIVAL_CADENCE = frozenset({"annual", "semi-annual", "semiannual", "per annum"})


def _schedules_something(text: str) -> bool:
    """Does this phrase put an event on a repeating clock, or only describe a noun?

    An explicit "every / each N units" always does. A bare literal does unless it is one of the
    four adjectival spellings above.
    """
    if _RECURRENCE_EVERY.search(text) is not None:
        return True
    literal = _RECURRENCE_LITERAL.search(text)
    if literal is None:
        return False
    return " ".join(literal.group(1).lower().split()) not in _ADJECTIVAL_CADENCE


def _rule_12_recurrence(text: str, ctx: _Ctx) -> _Window | None:
    """L1.5.2-U2 · a CADENCE — "every two weeks", "quarterly" — as the window its next
    occurrence falls in.

    The phrase names no day, and inventing one would be the whole fault this file exists to
    stop. What it does name is a period, and the next occurrence of a cadence is somewhere
    inside one period of it counted from now: [eval_time, eval_time + one period], RANGE. That
    is derived arithmetic on a stated interval, not a heuristic band, which is why it is RANGE
    rather than RELATIVE.

    Before this row existed the four `resolve_recurrence` phrases came back UNRESOLVED with no
    window at all, and a commitment promising a fortnightly update read to ALG-17 as a
    commitment with no deadline — an open loop that could never once be escalated.

    Consulted BEFORE row 13: "every two weeks" contains "two weeks", and reading a repeating
    obligation as a one-off two-week span drops the repetition on the floor.

    `_schedules_something` is asked FIRST, and it is not a re-implementation of
    `resolve_recurrence` — it answers the other question. "Our annual contract" has a cadence
    and names no date, and a row that took every phrase the cadence unit could read would put a
    year-wide window on every mention of the agreement somebody is already inside.
    """
    if not _schedules_something(text):
        return None
    rrule = resolve_recurrence(text)
    if rrule is None:
        return None
    period = _recurrence_period(rrule)
    if period is None:
        return None
    latest = add_calendar_duration(ctx.eval_time, period, tz=ctx.zone.key)
    return _Window(ctx.eval_time, latest, DateCertainty.RANGE)


def _rule_13_duration(text: str, ctx: _Ctx) -> _Window | None:
    """L1.5.2-U2/U3 · a BARE duration — "for 3 months", "30 days notice", "3 working days".

    Row 8 already reads a duration that carries a preposition ("in 3 days", "within two weeks"),
    where the phrase names a point and EXACT is the honest band. A bare period names the SPAN
    instead — a pilot that runs for three months, a clause that needs thirty days' notice — so
    it resolves to the whole span as a RANGE, from the instant it was stated to the instant it
    closes. Doc 05 L1.5.2-U2's WHY is exactly this: "a renewal date without its notice period
    gives the founder the wrong deadline", and a notice period with no window is not a period.

    Three arithmetics, and which one applies is a property of the phrase rather than a
    preference:

    * **business days** go to `add_business_days` (U3) with the org's holiday calendar, because
      "3 working days" is five calendar days from a Wednesday and more across a holiday;
    * **exact-length spans** (days, weeks, hours, minutes) go to `resolve_duration`, which
      returns a `timedelta` only when that conversion is lossless, and are added as ELAPSED
      time — that is what an hours-based or day-counted period means;
    * **month-shaped spans** are refused by `resolve_duration` on purpose (a 30-day "month" is
      wrong in exactly the months a renewal falls in) and go to `add_calendar_duration`, which
      applies them against this anchor, where a month finally has a length.
    """
    match = _DURATION.search(text)
    if match is None:
        return None
    if _unit_key(match.group("unit")) in ("business day", "working day"):
        # Parsed here rather than above because it is needed HERE and nowhere else: the two
        # branches below re-read the phrase through the U2 units themselves, which is what keeps
        # the "is this lossless" judgement in the one function that owns it.
        count = _count_token(match.group("count"))
        if count is None:
            return None
        return _Window(ctx.eval_time,
                       add_business_days(ctx.eval_time, count, ctx.holidays, tz=ctx.zone.key),
                       DateCertainty.RANGE)
    elapsed = resolve_duration(text)
    if elapsed is not None:
        return _Window(ctx.eval_time, ctx.eval_time + elapsed, DateCertainty.RANGE)
    calendar_span = resolve_calendar_duration(text)
    if calendar_span is None:
        return None
    return _Window(ctx.eval_time, add_calendar_duration(ctx.eval_time, calendar_span,
                                                        tz=ctx.zone.key), DateCertainty.RANGE)


#: The ordered cascade, first match wins. The order IS the algorithm, and it is the ONLY place
#: precedence is expressed — no rule's pattern carries a guard describing another rule's pattern.
#: Rule 3 before rule 5 is what makes "next Friday" a Friday rather than a week-long range, and
#: rule 7 before rules 5 and 6 is what keeps "end of (the) next quarter" three days wide instead
#: of ninety-one.
#:
#: Rule 7 leads that pair because it is the strictly more specific pattern: every phrase it
#: matches that rows 5 or 6 could also match is a phrase about a period's END, which is a three-
#: day window inside the very period those rows would return whole. It cannot starve them either,
#: because it never matches a bare "next quarter" at all. Rows keep their doc 05 numbers in their
#: names — the tuple's order is evaluation order, not the doc's numbering, and the two differ by
#: exactly this one deliberate move.
#:
#: Rows 12 and 13 continue the numbering past doc 05's table, which stops at eleven because U1 is
#: the only unit it tabulates; they are U2's and U3's phrases reaching the same entry point,
#: since `resolve_date` is the ONE function a caller has and a cadence or a notice period that
#: only a second, unreached function understood was a phrase this layer silently dropped. They
#: run LAST, immediately before row 11's default, so no phrase that already had an answer gets a
#: new one: everything reaching them was UNRESOLVED. Row 12 leads row 13 because every cadence
#: contains a bare period ("every two weeks" contains "two weeks") and a repeating obligation
#: read as a one-off drops the repetition on the floor.
_CASCADE = (
    _rule_01_explicit_date,
    _rule_02_month_day,
    _rule_03_weekday,
    _rule_04_day_offset,
    _rule_07_end_of_period,
    _rule_05_next_period,
    _rule_06_this_period,
    _rule_08_in_n_units,
    _rule_09_soon,
    _rule_10_later,
    _rule_12_recurrence,
    _rule_13_duration,
)


def resolve_date(as_written: str, *, eval_time: datetime, tz: str,
                 evidence: Sequence[EvidenceSpan], locale: str | None = None,
                 holidays: frozenset[date] = frozenset()) -> ResolvedDate:
    """L1.5.2-U1 · ALG-09 — a date phrase into a window plus a certainty. Row 11 is the default.

    The eleven-row cascade in doc 05 runs in order and the first row that matches answers; a row
    that matches but cannot resolve (an ambiguous numeric date with no locale) stops the cascade
    with UNRESOLVED rather than letting a later, vaguer row put a ninety-day guess where a
    specific date was written.

    `eval_time` is a parameter and never a clock read, and it is copied onto the result as
    `resolved_against`, so replaying the same phrase against the same instant reproduces the same
    object byte for byte and replaying last March's event resolves "next week" against March.
    `tz` is the ORG's timezone: resolution happens there and the bounds are stored in UTC.

    `holidays` is the org's non-working calendar, and rows 8 and 13 are where it lands. GAP, and
    a stated one: no caller on today's path supplies it — nothing in L1 reads an org holiday
    calendar, and this module may not invent a national one, since a hardcoded calendar is wrong
    for most orgs on most holidays. Weekends are always honoured, so "3 working days" is already
    right in every week without a public holiday in it; the parameter is the seam an org calendar
    arrives through the day one exists.

    Raises rather than returning a degraded object when the inputs are not resolvable at all — a
    naive `eval_time`, an unknown timezone, an empty phrase, or no evidence — because each of
    those is a caller defect that a plausible-looking UNRESOLVED would hide.
    """
    resolved_against = require_aware(eval_time, "eval_time")
    zone = _zone_of(tz)
    local = resolved_against.astimezone(zone)
    ctx = _Ctx(eval_time=resolved_against, zone=zone, local=local, local_date=local.date(),
               locale=locale, holidays=frozenset(holidays))

    window = _UNRESOLVED
    for rule in _CASCADE:
        matched = rule(as_written, ctx)
        if matched is not None:
            window = matched
            break

    return ResolvedDate(as_written=as_written, earliest=window.earliest, latest=window.latest,
                        certainty=window.certainty, resolved_against=resolved_against,
                        evidence=list(evidence))


def resolve_calendar_duration(as_written: str) -> CalendarDuration | None:
    """L1.5.2-U2 · a duration phrase in the units it was written in — "30 days notice" -> 30 days.

    Months stay months. A notice period is subtracted from a renewal date to produce the date the
    founder actually has to act on, and that subtraction is only correct against a real anchor:
    three months before 1 November is 1 August, which is 92 days, and calling it 90 moves the
    deadline two days in the direction nobody checks.

    Business days are matched and refused: a span of business days has no length until a calendar
    is supplied, and `add_business_days` is where that calendar arrives.
    """
    match = _DURATION.search(as_written)
    if match is None:
        return None
    count = _count_token(match.group("count"))
    if count is None:
        return None
    unit = _unit_key(match.group("unit"))
    if unit not in _DURATION_UNITS:
        return None
    months, days, seconds = _DURATION_UNITS[unit]
    return CalendarDuration(months=months * count, days=days * count, seconds=seconds * count)


def resolve_duration(as_written: str) -> timedelta | None:
    """L1.5.2-U2 · the same phrase as a `timedelta`, and ONLY when that is lossless.

    Days, weeks, hours and minutes have one length wherever they are anchored, so they convert.
    Anything with a months component returns None rather than a 30-day approximation — the
    approximation is the exact fault this layer exists to stop, and `resolve_calendar_duration`
    is the call that keeps such a phrase without flattening it.
    """
    duration = resolve_calendar_duration(as_written)
    if duration is None or not duration.is_exact_length:
        return None
    return timedelta(days=duration.days, seconds=duration.seconds)


def add_calendar_duration(anchor: datetime, duration: CalendarDuration, *,
                          tz: str = "UTC") -> datetime:
    """Apply a `CalendarDuration` to a real instant in the org timezone, then return UTC.

    Months are applied first and the day of month is clamped to the target month's length, so 31
    March minus one month is 28 February rather than an error or a rolled-over 3 March. Days are
    applied as local calendar days — wall-clock arithmetic, so a period spanning a DST change
    still lands at the same local time of day — and seconds are applied as absolute elapsed time,
    which is what an hours-based notice period means.
    """
    moment = require_aware(anchor, "anchor")
    zone = _zone_of(tz)
    local = moment.astimezone(zone)
    if duration.months:
        year, month = _add_months(local.year, local.month, duration.months)
        local = local.replace(year=year, month=month, day=min(local.day, _last_day(year, month)))
    local = local + timedelta(days=duration.days)
    return local.astimezone(timezone.utc) + timedelta(seconds=duration.seconds)


def resolve_recurrence(as_written: str) -> str | None:
    """L1.5.2-U2 · "every quarter" / "annual" -> an RFC 5545 recurrence rule body.

    Returned as the RRULE value ("FREQ=MONTHLY;INTERVAL=3") rather than a bespoke enum, so a
    renewal cadence can be handed to a calendar, a scheduler or a human without a translation
    table that only this repository owns. Quarterly is expressed as a three-month interval because
    that is what a quarterly renewal does — recur on a date every three months — not as a yearly
    rule with four BYMONTH values, which would pin the cadence to one anchor year.

    "Biweekly" returns None: it means both every-two-weeks and twice-a-week in ordinary English,
    and a cadence guessed wrong by a factor of four is worse than one left open.
    """
    if _AMBIGUOUS_RECURRENCE.search(as_written) is not None:
        return None
    match = _RECURRENCE_EVERY.search(as_written)
    if match is not None:
        unit = _unit_key(match.group("unit"))
        if unit in _RECURRENCE_UNITS:
            freq, base = _RECURRENCE_UNITS[unit]
            count = _count_token(match.group("count")) if match.group("count") else 1
            if count is None:
                return None
            return f"FREQ={freq};INTERVAL={base * count}"
    literal = _RECURRENCE_LITERAL.search(as_written)
    if literal is None:
        return None
    return _RECURRENCE_LITERALS[" ".join(literal.group(1).lower().split())]


def _is_business_day(day: date, holidays: frozenset[date]) -> bool:
    return day.weekday() not in WEEKEND and day not in holidays


def _advance_business_days(local: datetime, n: int, holidays: frozenset[date]) -> datetime:
    """Walk `n` business days from a LOCAL aware instant, keeping its wall-clock time of day.

    One day at a time, skipping non-working days on the way, so a holiday adjacent to a weekend
    costs the run of days it actually costs. The time of day is carried through the local
    calendar rather than through elapsed seconds, which is what keeps a 10:00 deadline at 10:00
    across a DST change instead of drifting to 09:00.
    """
    if n == 0:
        return local
    step = 1 if n > 0 else -1
    day = local.date()
    for _ in range(abs(n)):
        day = day + timedelta(days=step)
        while not _is_business_day(day, holidays):
            day = day + timedelta(days=step)
    return datetime.combine(day, local.timetz())


def add_business_days(start: datetime, n: int, holidays: frozenset[date] = frozenset(), *,
                      tz: str = "UTC") -> datetime:
    """L1.5.2-U3 · business-day arithmetic — weekends always, the org's holidays when supplied.

    "Five business days" is seven calendar days at minimum and more across a holiday, and every
    compliance deadline computed as five is wrong in the direction that looks fine until someone
    misses it. Weekends are Saturday and Sunday; the holiday calendar is an injected
    `frozenset[date]` because this module has no database to read one from and a hardcoded
    national calendar would be wrong for most orgs on most holidays (see the spec gap noted in
    the module's acceptance notes).

    `n == 0` returns `start` unchanged even when it lands on a weekend. Rolling a zero-day offset
    onto the next working day would silently move a date the caller did not ask to move; a caller
    that wants that behaviour asks for it by adding a day.

    Days are counted in `tz` so the local calendar date decides the weekend, not UTC's: 09:00
    Monday in Auckland is still Sunday in UTC, and counting there would skip a working day.
    """
    moment = require_aware(start, "start")
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"n must be an exact integer, not {type(n).__name__}")
    zone = _zone_of(tz)
    landed = _advance_business_days(moment.astimezone(zone), n, frozenset(holidays))
    return landed.astimezone(timezone.utc)


__all__ = [
    "DAY_END",
    "DAY_START",
    "END_OF_PERIOD_DAYS",
    "LATER_WINDOW_DAYS",
    "MONTH_FIRST_REGIONS",
    "SOON_WINDOW_DAYS",
    "WEEKEND",
    "CalendarDuration",
    "add_business_days",
    "add_calendar_duration",
    "resolve_calendar_duration",
    "resolve_date",
    "resolve_duration",
    "resolve_recurrence",
]
