"""Boundary-aware text chunking for documents (uploads, Drive files, any long text).

A document is split into retrieval-sized pieces before L2 extraction. The naive approach —
slicing every N characters — cuts mid-sentence, mid-word, mid-table:

    "...refunds are accepted within | 30 days of purchase..."

Neither half means anything on its own, so the fact is silently destroyed. This packs whole
sentences/paragraphs into pieces of at most `max_chars`, only hard-splitting a single run
that has no sentence break inside it (a minified blob). Pure + deterministic → unit-testable
with no API/DB/LLM dependency.
"""
from __future__ import annotations

import re

DEFAULT_CHUNK_CHARS = 2000

# sentence ends (. ! ? followed by whitespace) OR a paragraph break (blank line)
_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def chunk_text(text_content: str, *, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split text into ≤`max_chars` chunks without cutting mid-sentence. Returns every
    chunk (no cap) — callers that bound the count must report the truncation, never drop
    silently."""
    t = (text_content or "").strip()
    if not t:
        return []
    chunks: list[str] = []
    cur = ""
    for unit in _BOUNDARY.split(t):
        unit = unit.strip()
        if not unit:
            continue
        if len(unit) > max_chars:                      # one oversized unit, no sentence break
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(unit[i:i + max_chars] for i in range(0, len(unit), max_chars))
            continue
        if cur and len(cur) + 1 + len(unit) > max_chars:
            chunks.append(cur)
            cur = unit
        else:
            cur = f"{cur} {unit}" if cur else unit
    if cur:
        chunks.append(cur)
    return chunks
