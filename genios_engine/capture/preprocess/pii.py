from __future__ import annotations

import re
from dataclasses import dataclass

from genios_engine.contracts.prepared_content import MaskedSpan, OffsetSegment

# Deterministic high-risk PII detectors. Aadhaar/PAN/card/IFSC are ALWAYS masked
# before any LLM call; phone is tenant-configurable (default off — sales/support
# workflows often need it). Mask always wins over "protected" for high-risk PII.

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("AADHAAR", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("PHONE_IN", re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")),
]


@dataclass
class PiiMatch:
    start: int
    end: int
    pii_type: str


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def detect(text: str, *, mask_phone: bool = False) -> list[PiiMatch]:
    matches: list[PiiMatch] = []
    for typ, pat in _PATTERNS:
        if typ == "PHONE_IN" and not mask_phone:
            continue
        for m in pat.finditer(text):
            if typ == "CARD":
                digits = re.sub(r"\D", "", m.group())
                if not (13 <= len(digits) <= 19 and _luhn_ok(digits)):
                    continue
            matches.append(PiiMatch(m.start(), m.end(), typ))
    # resolve overlaps: earliest start, then longest; keep non-overlapping
    matches.sort(key=lambda x: (x.start, -(x.end - x.start)))
    kept: list[PiiMatch] = []
    last_end = -1
    for m in matches:
        if m.start >= last_end:
            kept.append(m)
            last_end = m.end
    return kept


def mask(text: str, matches: list[PiiMatch]) -> tuple[str, list[OffsetSegment], list[MaskedSpan]]:
    """Build masked text + an offset map (segments) + the masked spans. Length-changing
    replacement is fine because the offset map tracks the mapping precisely."""
    parts: list[str] = []
    segments: list[OffsetSegment] = []
    masked_spans: list[MaskedSpan] = []
    prep = 0
    src = 0
    for m in matches:
        if m.start > src:                       # passthrough before this match
            seg = text[src:m.start]
            parts.append(seg)
            segments.append(OffsetSegment(prep_start=prep, prep_end=prep + len(seg),
                                          src_start=src, src_end=m.start, masked=False))
            prep += len(seg)
        token = f"[{m.pii_type}]"
        parts.append(token)
        segments.append(OffsetSegment(prep_start=prep, prep_end=prep + len(token),
                                      src_start=m.start, src_end=m.end, masked=True))
        masked_spans.append(MaskedSpan(src_start=m.start, src_end=m.end,
                                       pii_type=m.pii_type, token=token))
        prep += len(token)
        src = m.end
    if src < len(text):                         # trailing passthrough
        seg = text[src:]
        parts.append(seg)
        segments.append(OffsetSegment(prep_start=prep, prep_end=prep + len(seg),
                                      src_start=src, src_end=len(text), masked=False))
    return "".join(parts), segments, masked_spans
