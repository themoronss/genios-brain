"""V-02 invention validator — the hallucination guard for every executive surface.

CANONICAL HOME. The same algorithm lives temporarily in deliver/render.py (the card
path); per the layer plan the validators belong to the executive layer, and deliver
(6) may import DOWNWARD from here once its split lands — executive (5) must never
import deliver. Until then the two copies are kept semantically identical; the shared
tests in tests/test_executive_validate.py are the contract.

Rule: rendered text may contain ONLY names, numbers and dates that exist in the fact
corpus it was given. A set difference over typed tokens — never a second model call
judging the first."""
from __future__ import annotations

import json
import re
from datetime import datetime


def _digit_runs(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def _proper_nouns(s: str) -> list[str]:
    """Capitalised, non-sentence-initial alphabetic tokens — the shape of a name."""
    out: list[str] = []
    for sent in re.split(r"[.!?]\s+", s):
        for i, w in enumerate(sent.split()):
            core = re.sub(r"[^A-Za-z0-9]", "", w)
            if i == 0 or len(core) < 2 or not core.isalpha():
                continue                          # sentence-initial cap is grammar, not a name
            if core[0].isupper():
                out.append(core)
    return out


def _expand_dates(s: str) -> list[str]:
    """A faithful reformatting of a fact date is NOT invention: expand ISO dates into
    their human forms so 'July 22' for 2026-07-22 is grounded, while a hallucinated
    'March 22' (wrong month word) stays ungrounded and is rejected."""
    out: list[str] = []
    for m in re.finditer(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?", s):
        try:
            dt = datetime.fromisoformat(m.group(0).replace(" ", "T"))
        except ValueError:
            continue
        mon, abbr = dt.strftime("%B").lower(), dt.strftime("%b").lower()
        out += [mon, abbr, str(dt.day), str(dt.year), f"{mon} {dt.day}"]
    return out


def build_corpus(facts: dict, slots: dict | None = None) -> tuple[str, set[str]]:
    """Everything a rendering is ALLOWED to say: fact values + computed slots
    (+ human date expansions), lowercased, plus the legitimate digit runs."""
    parts: list[str] = []
    for f in (facts or {}).values():
        v = f.get("value") if isinstance(f, dict) else f
        s = json.dumps(v, default=str) if not isinstance(v, str) else v
        parts.append(s)
        parts.extend(_expand_dates(s))
    for v in (slots or {}).values():
        parts.append(str(v))
    text = " ".join(parts)
    nums: set[str] = set()
    for p in parts:
        nums |= _digit_runs(p)
    return text.lower(), nums


def invention_ok(text: str, corpus_text: str, corpus_nums: set[str]) -> tuple[bool, str | None]:
    """(ok, offending_token). Fails CLOSED: an ungrounded number or name rejects."""
    for num in _digit_runs(text):
        if num not in corpus_nums and num not in corpus_text:
            return False, f"number:{num}"
    for pn in _proper_nouns(text):
        if pn.lower() not in corpus_text:
            return False, f"name:{pn}"
    return True, None


def validate_text(text: str, facts: dict, slots: dict | None = None) -> tuple[bool, str | None]:
    """One-call convenience: is this rendering fully grounded in these facts?"""
    corpus_text, corpus_nums = build_corpus(facts, slots)
    return invention_ok(text, corpus_text, corpus_nums)
