from __future__ import annotations

import re

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


def protected_line_spans(text: str) -> list[tuple[int, int]]:
    """Lines carrying money / dates / deadlines / questions / important keywords are
    protected — the token-budget trimmer may never drop them."""
    spans: list[tuple[int, int]] = []
    idx = 0
    for line in text.splitlines(keepends=True):
        if ("?" in line or _DEADLINE.search(line) or _MONEY.search(line)
                or _IMPORTANT.search(line)):
            spans.append((idx, idx + len(line.rstrip("\n"))))
        idx += len(line)
    return spans
