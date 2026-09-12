"""Availability claims — strict validation and deterministic date resolution.

The extractor quotes the words that state a window ("15th to 22nd", "kal se 3 din", "back on
Monday"); this module turns those words into two dates against the MESSAGE's own date. The model
never does date arithmetic: a language model asked for "next Friday" answers plausibly and is wrong
often enough that a leave window would drift by a week without anyone noticing.

The rule is the guard wall's rule applied to time — evidence or it did not happen:
  * the claim's evidence must be a verbatim substring of the message;
  * a date phrase must itself appear in the message (or, for an ISO date the model resolved, be
    corroborated by a day number / weekday / month / relative word in the evidence);
  * a phrase that is stated but cannot be read makes the claim MALFORMED → dropped, never guessed;
  * an unstated start defaults to the message date (the message is evidence that the person is away
    as of then) and an unstated end stays open-ended — neither is an invented date.
"""
from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from genios_engine.context.guard import evidence_ok
from genios_engine.contracts.availability import AvailabilityClaim, normalize_kind

MAX_CLAIMS = 10
#: A window longer than this is a sabbatical or a misreading — neither belongs in this lane.
MAX_WINDOW_DAYS = 366
#: A message may report an absence that already began ("on leave since the 2nd").
MAX_PAST_DAYS = 60
MAX_FUTURE_DAYS = 366

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_WEEKDAYS = {
    "monday": 0, "mon": 0, "somvar": 0, "tuesday": 1, "tues": 1, "tue": 1, "mangalvar": 1,
    "wednesday": 2, "wed": 2, "budhvar": 2, "thursday": 3, "thurs": 3, "thur": 3, "thu": 3,
    "guruvar": 3, "friday": 4, "fri": 4, "shukravar": 4, "saturday": 5, "sat": 5, "shanivar": 5,
    "sunday": 6, "sun": 6, "ravivar": 6,
}
_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "ek": 1, "two": 2, "do": 2, "three": 3, "teen": 3, "four": 4,
    "char": 4, "chaar": 4, "five": 5, "paanch": 5, "panch": 5, "six": 6, "seven": 7, "saat": 7,
    "ten": 10, "das": 10,
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WD_RE = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_NUM_RE = r"\d{1,3}|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_ORD = r"(?:st|nd|rd|th)?"
_SEP = r"(?:-|–|—|to|till|until|thru|through|se)"

_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC = re.compile(r"(?<![\d/.])(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?(?![\d/.])")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}}){_ORD}\s*(?:of\s+)?({_MONTH_RE})\b\.?(?:,?\s*(\d{{4}}))?")
_MONTH_DAY = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}}){_ORD}\b(?:,?\s*(\d{{4}}))?")
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b")
_BARE_DAY = re.compile(r"^(?:on\s+|from\s+|till\s+|until\s+|to\s+)?(\d{1,2})$")
_WEEKDAY = re.compile(rf"\b({_WD_RE})\b")
_DAY_RANGE = re.compile(
    rf"\b(\d{{1,2}}){_ORD}\s*{_SEP}\s*(\d{{1,2}}){_ORD}\b(?:\s*(?:of\s+)?({_MONTH_RE})\b)?")
_MONTH_DAY_RANGE = re.compile(
    rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}}){_ORD}\s*{_SEP}\s*(\d{{1,2}}){_ORD}\b")
_WEEKDAY_RANGE = re.compile(rf"\b({_WD_RE})\s*{_SEP}\s*({_WD_RE})\b")
_SPLIT = re.compile(r"\s+(?:to|till|until|through|thru|se)\s+|\s*[–—]\s*|\s+-\s+")
_DURATION = re.compile(
    rf"\b({_NUM_RE})\s*(?:working\s+|business\s+|full\s+)?(days?|din|weeks?|hafte|hafta|hafton)\b")
_NEXT_WEEK = re.compile(r"\b(next\s+week|agle\s+hafte|agla\s+hafta|coming\s+week)\b")
_THIS_WEEK = re.compile(r"\b(this\s+week|rest\s+of\s+(?:the\s+)?week|is\s+hafte)\b")
_END_OF_WEEK = re.compile(r"\bend\s+of\s+(?:the\s+|this\s+)?week\b")
_END_OF_MONTH = re.compile(r"\bend\s+of\s+(?:the\s+|this\s+)?month\b")
_DAY_AFTER = re.compile(r"\b(day\s+after\s+tomorrow|parso|parson)\b")
_TODAY = re.compile(r"\b(today|aaj|tonight)\b")
_TOMORROW = re.compile(r"\b(tomorrow|tmrw|kal)\b")
#: A start phrase that opens a window rather than naming a single day.
_OPEN_START = re.compile(r"\b(from|starting|starts?|since|onwards?|beginning|se|wef|w\.e\.f)\b")
#: An end phrase naming the day the person is BACK — the absence ends the day before.
_RETURN = re.compile(r"\b(back|return|returns|returning|resume|resuming|rejoin|rejoining|"
                     r"wapas|in\s+office)\b")
_SINCE = re.compile(r"\b(since|was|have\s+been|been)\b")
_SELF_WORDS = frozenset({"", "i", "me", "myself", "sender", "author", "self", "we", "us", "main"})


@dataclass(frozen=True, slots=True)
class ResolvedWindow:
    start: date
    end: date | None
    from_stated: bool
    to_stated: bool


def _clean(text: object) -> str:
    if not isinstance(text, str):
        return ""
    s = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(s.split()).strip(" .,;:!()[]\"'")


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _roll_year(candidate: date | None, ref: date) -> date | None:
    """A day-month with no year: this year, unless that is well before the reference."""
    if candidate is None:
        return None
    if candidate < ref - timedelta(days=MAX_PAST_DAYS):
        return _safe_date(candidate.year + 1, candidate.month, candidate.day)
    return candidate


def _day_in_month(day: int, ref: date, *, past_ok: bool) -> date | None:
    """A bare day number ("22nd"): in the reference month, or the next one if already gone."""
    candidate = _safe_date(ref.year, ref.month, day)
    if candidate is not None and (candidate >= ref or past_ok):
        return candidate
    month = ref.month % 12 + 1
    year = ref.year + (1 if ref.month == 12 else 0)
    return _safe_date(year, month, day)


def _next_monday(base: date) -> date:
    return base + timedelta(days=(7 - base.weekday()) or 7)


def _parse_point(text: str, base: date, anchor: date, *, inclusive: bool = False) -> date | None:
    """One date phrase → a date. `base` is the message date (relative words hang off it);
    `anchor` is what a bare day or weekday counts forward from (the start, for an end phrase).
    `inclusive` lets an END weekday land on the anchor itself: "tomorrow to Friday", said on a
    Thursday, ends tomorrow — not a week later."""
    t = _clean(text)
    if not t:
        return None
    past_ok = bool(_SINCE.search(t))
    if m := _ISO.search(t):
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _DAY_MONTH.search(t):
        year = int(m.group(3)) if m.group(3) else anchor.year
        d = _safe_date(year, _MONTHS[m.group(2)], int(m.group(1)))
        return d if m.group(3) else _roll_year(d, anchor)
    if m := _MONTH_DAY.search(t):
        year = int(m.group(3)) if m.group(3) else anchor.year
        d = _safe_date(year, _MONTHS[m.group(1)], int(m.group(2)))
        return d if m.group(3) else _roll_year(d, anchor)
    if m := _NUMERIC.search(t):               # India writes day first: 15/09 is 15 September
        year = int(m.group(3)) if m.group(3) else anchor.year
        year = year + 2000 if year < 100 else year
        d = _safe_date(year, int(m.group(2)), int(m.group(1)))
        return d if m.group(3) else _roll_year(d, anchor)
    if _DAY_AFTER.search(t):
        return base + timedelta(days=2)
    if _TODAY.search(t):
        return base
    if _TOMORROW.search(t):
        return base + timedelta(days=1)
    if m := _WEEKDAY.search(t):
        wd = _WEEKDAYS[m.group(1)]
        if past_ok:
            return anchor - timedelta(days=(anchor.weekday() - wd) % 7)
        ahead = (wd - anchor.weekday()) % 7
        return anchor + timedelta(days=ahead if (ahead or inclusive) else 7)
    if m := _ORDINAL.search(t):
        return _day_in_month(int(m.group(1)), anchor, past_ok=past_ok)
    if _NEXT_WEEK.search(t):
        return _next_monday(base)
    if _END_OF_WEEK.search(t):
        return base + timedelta(days=max(0, 4 - base.weekday()))
    if _END_OF_MONTH.search(t):
        return date(base.year, base.month, monthrange(base.year, base.month)[1])
    if m := _BARE_DAY.match(t):
        return _day_in_month(int(m.group(1)), anchor, past_ok=past_ok)
    return None


def _duration_days(text: str) -> int | None:
    m = _DURATION.search(_clean(text))
    if not m:
        return None
    raw = m.group(1)
    n = int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw)
    if not n or n <= 0:
        return None
    return n * 7 if m.group(2).startswith(("week", "haft")) else n


def _parse_range(text: str, base: date) -> tuple[date, date] | None:
    """A phrase that states BOTH ends ("15-22 Sept", "Mon to Wed", "next week")."""
    t = _clean(text)
    isos = _ISO.findall(t)
    if len(isos) >= 2:
        a = _safe_date(*map(int, isos[0]))
        b = _safe_date(*map(int, isos[-1]))
        return (a, b) if a and b else None
    if isos:
        return None                               # one ISO date is a point; "09-15" is not a range
    if m := _MONTH_DAY_RANGE.search(t):
        month = _MONTHS[m.group(1)]
        a = _roll_year(_safe_date(base.year, month, int(m.group(2))), base)
        if a is None:
            return None
        b = _safe_date(a.year, month, int(m.group(3)))
        if b is not None and b < a:
            b = _day_in_month(int(m.group(3)), a, past_ok=False)
        return (a, b) if b else None
    if m := _DAY_RANGE.search(t):
        d1, d2 = int(m.group(1)), int(m.group(2))
        if m.group(3):
            month = _MONTHS[m.group(3)]
            a = _roll_year(_safe_date(base.year, month, d1), base)
            b = _safe_date(a.year, month, d2) if a else None
            if a and b and b < a:                      # "28-3 Jan" — the start is in December
                a = _safe_date(a.year - (1 if month == 1 else 0), (month - 2) % 12 + 1, d1)
        else:
            a = _day_in_month(d1, base, past_ok=bool(_SINCE.search(t)))
            b = _day_in_month(d2, a, past_ok=False) if a else None
        return (a, b) if a and b else None
    if m := _WEEKDAY_RANGE.search(t):
        a = _parse_point(m.group(1), base, base)
        b = _parse_point(m.group(2), base, a, inclusive=True) if a else None
        if a and b and (b - a).days > 6:
            b = b - timedelta(days=7)
        return (a, b) if a and b and b >= a else None
    if _NEXT_WEEK.search(t) and not _OPEN_START.search(t):
        mon = _next_monday(base)
        return mon, mon + timedelta(days=4)
    if _THIS_WEEK.search(t):
        return base, base + timedelta(days=max(0, 4 - base.weekday()))
    parts = [p for p in _SPLIT.split(t) if p.strip()]
    if len(parts) == 2:
        a = _parse_point(parts[0], base, base)
        b = _parse_point(parts[1], base, a, inclusive=True) if a else None
        if a and b:
            if _RETURN.search(parts[1]):
                b = b - timedelta(days=1)
            return a, b
    return None


def resolve_window(from_text: str | None, to_text: str | None, base: date) -> ResolvedWindow | None:
    """Two quoted phrases + the message date → a window, or None when a STATED phrase is unreadable.

    None is "malformed", not "unknown": the caller drops the claim rather than storing a window
    whose dates it could not read. Absent phrases are fine — see the module docstring.
    """
    ft, tt = _clean(from_text), _clean(to_text)
    start: date | None = None
    end: date | None = None
    from_stated = to_stated = False

    if ft:
        rng = _parse_range(ft, base)
        if rng:
            start, end = rng
            from_stated = to_stated = True
        else:
            start = _parse_point(ft, base, base)
            dur = _duration_days(ft)
            if start is None and dur is None:
                return None
            from_stated = start is not None
            start = start or base
            if dur:
                end, to_stated = start + timedelta(days=dur - 1), True
            elif not tt and not _OPEN_START.search(ft):
                end, to_stated = start, True          # "sick today", "leave on the 15th"
    if tt:
        anchor = start or base
        point = _parse_point(tt, base, anchor, inclusive=True)
        if point is not None:
            end = point - timedelta(days=1) if _RETURN.search(tt) else point
        else:
            dur = _duration_days(tt)
            if dur is None:
                return None
            end = anchor + timedelta(days=dur - 1)
        to_stated = True
    if start is None:
        start = base
    if end is not None and end < start:
        return None
    return ResolvedWindow(start, end, from_stated, to_stated)


def _person(value: object) -> str | None:
    """A claim's person / cover → a clean identifier, None when it names the author."""
    if not isinstance(value, str):
        return None
    s = " ".join(value.split()).strip(" .,;:")
    if s.casefold() in _SELF_WORDS or len(s) > 200:
        return None
    return s.lower() if "@" in s else s


def _iso_corroborated(d: date, evidence: str, base: date) -> bool:
    """A model-resolved ISO date is accepted only when the quote carries something that names THAT
    day: its day number, its own weekday, or a relative word that resolves to it. A month name
    alone names thirty days, so "on leave in September" never licenses the 1st."""
    ev = _clean(evidence)
    if re.search(rf"(?<!\d)0?{d.day}(?!\d)", ev):
        return True
    if any(_WEEKDAYS[w] == d.weekday() for w in _WEEKDAY.findall(ev)):
        return True
    if _TODAY.search(ev) and d == base:
        return True
    if _TOMORROW.search(ev) and d == base + timedelta(days=1):
        return True
    if _DAY_AFTER.search(ev) and d == base + timedelta(days=2):
        return True
    monday = _next_monday(base)
    return bool(_NEXT_WEEK.search(ev)) and monday <= d <= monday + timedelta(days=6)


def _date_text_ok(text: str, *, content: str, evidence: str, base: date) -> bool:
    if not text:
        return True
    iso = _ISO.fullmatch(_clean(text))
    if iso:
        d = _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        return d is not None and (evidence_ok(content, text, min_len=2)
                                  or _iso_corroborated(d, evidence, base))
    return evidence_ok(content, text, min_len=2)


def _validate_one(item: object, *, content: str, base: date) -> AvailabilityClaim | None:
    if not isinstance(item, dict):
        return None
    kind = normalize_kind(item.get("kind"))
    if kind is None:
        return None
    evidence = str(item.get("evidence_text") or item.get("evidence") or "").strip()
    if not evidence_ok(content, evidence):
        return None                               # evidence or it did not happen
    raw_from = item.get("from")
    raw_to = item.get("to")
    from_text = raw_from.strip() if isinstance(raw_from, str) else ""
    to_text = raw_to.strip() if isinstance(raw_to, str) else ""
    if raw_from not in (None, "") and not from_text:
        return None                               # a non-string date is malformed
    if raw_to not in (None, "") and not to_text:
        return None
    for phrase in (from_text, to_text):
        if not _date_text_ok(phrase, content=content, evidence=evidence, base=base):
            return None
    window = resolve_window(from_text or None, to_text or None, base)
    if window is None:
        return None
    if window.start < base - timedelta(days=MAX_PAST_DAYS):
        return None
    if window.start > base + timedelta(days=MAX_FUTURE_DAYS):
        return None
    if window.end is not None and (window.end - window.start).days >= MAX_WINDOW_DAYS:
        return None
    return AvailabilityClaim(
        person=_person(item.get("person")), kind=kind, from_date=window.start,
        to_date=window.end, coverage_person=_person(item.get("coverage_person")),
        evidence=evidence, from_stated=window.from_stated, to_stated=window.to_stated)


def validate_availability_claims(raw_claims: object, *, content: str,
                                 base: datetime | date) -> list[AvailabilityClaim]:
    """The extractor's `availability` array → validated claims. Malformed items are dropped."""
    if not isinstance(raw_claims, list):
        return []
    base_date = base.date() if isinstance(base, datetime) else base
    out: list[AvailabilityClaim] = []
    seen: set[tuple] = set()
    for item in raw_claims[: MAX_CLAIMS * 2]:
        claim = _validate_one(item, content=content, base=base_date)
        if claim is None:
            continue
        key = (claim.person, claim.kind, claim.from_date, claim.to_date)
        if key in seen:
            continue
        seen.add(key)
        out.append(claim)
        if len(out) >= MAX_CLAIMS:
            break
    return out
