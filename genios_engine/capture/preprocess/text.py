from __future__ import annotations

import re
from collections.abc import Sequence

# Deterministic text signals: language, protected lines (never trimmed).

_HINGLISH = {
    "kal", "parso", "tak", "bhej", "karo", "kar", "dunga", "dungi", "jaldi",
    "urgent", "hai", "padega", "band", "update", "final", "chahiye", "ho",
    "jayega", "kitna", "abhi", "milta",
}
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_DEADLINE = re.compile(
    r"\b(by|before|eod|tomorrow|today|deadline|"
    r"mon|tue|wed|thu|fri|sat|sun|friday|monday|tuesday|wednesday|thursday|"
    r"kal|parso|aaj)\b",
    re.I,
)
_MONEY = re.compile(r"(₹|\$|rs\.?|inr|usd)\s?\d|[\d,]+\s?(lakh|crore|k)\b", re.I)
_IMPORTANT = re.compile(
    r"\b(invoice|contract|proposal|agreement|order\s*form|renewal|payment|overdue|"
    r"legal|compliance|sev1|outage|cancel|refund)\b",
    re.I,
)


def detect_language(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    toks = re.findall(r"[a-zA-Z]+", text.lower())
    if not toks:
        return "other"
    hits = sum(1 for t in toks if t in _HINGLISH)
    return "hinglish" if hits / len(toks) >= 0.12 else "en"


def protected_line_spans(text: str,
                         history: Sequence[Sequence[int]] | None = None) -> list[tuple[int, int]]:
    """Lines carrying money / dates / deadlines / questions / important keywords are
    protected — the token-budget trimmer may never drop them.

    NOTHING INSIDE REPLY HISTORY IS EVER PROTECTED, and until `history` was passed here the
    trimmer was doing the opposite of its job. `_DEADLINE` matches
    `\b(mon|tue|wed|thu|fri|sat|sun)\b`, and every mail client writes its attribution line with a
    weekday in it — so `"On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:"` scored as a deadline
    line and the trimmer was FORBIDDEN from dropping it. A quoted paragraph mentioning "renewal"
    or "invoice" was protected by `_IMPORTANT` for the same reason. The budget was being spent
    keeping the one part of the message nobody in it wrote.

    `history` is optional and defaults to none, so a caller with only a string still gets the old
    behaviour rather than a TypeError. Every in-tree caller passes it.
    """
    ranges = tuple((int(a), int(b)) for a, b in (history or ()))
    spans: list[tuple[int, int]] = []
    idx = 0
    for line in text.splitlines(keepends=True):
        end = idx + len(line.rstrip("\n"))
        if ("?" in line or _DEADLINE.search(line) or _MONEY.search(line)
                or _IMPORTANT.search(line)):
            # Any overlap disqualifies, matching `in_quoted_history`: a line that begins live and
            # runs into the history is not wholly the sender's either.
            if not any(idx < hi and end > lo for lo, hi in ranges):
                spans.append((idx, end))
        idx += len(line)
    return spans
