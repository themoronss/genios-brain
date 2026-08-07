"""Deterministic segmentation — the spec's Chunking component, as a real one.

The only chunker that existed lived inside the upload endpoint and was
`[t[i:i+2000] for i in range(0, len(t), 2000)]`. It cut mid-sentence, mid-word and
mid-table, and neither half of a split fact means anything alone: *"the discount cap is"*
and *"15% for enterprise"* are two pieces of nothing. Everything extracted from every
uploaded document quietly inherited that.

Three properties this has to hold, in order of how much damage their absence does:

1. **Cut at a boundary.** Paragraph if one is in reach, then sentence, then word. A hard
   cut mid-word only when a single word is longer than the whole budget.
2. **Keep offsets.** Every chunk knows the `[start, end)` it came from, so evidence can
   point at source characters — the same promise `prepared_content`'s offset map makes.
   A chunker that loses offsets breaks the layer's one durable guarantee about evidence.
3. **Lose nothing.** Concatenating the chunks in order reproduces the source exactly when
   `overlap=0`. Tested, because "no gaps" is the property a reader cannot verify by eye.

No LLM, no tokeniser, no model-specific budget — characters only, so the same document
always splits the same way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 2000
# Enough to carry a sentence across a seam so a fact split across two chunks survives in
# at least one of them whole. Costs a little duplication; buys back split facts.
DEFAULT_OVERLAP = 200

# How far back from the budget we will look for a nicer boundary before giving up and
# cutting where the budget lands. A quarter of the chunk keeps chunks reasonably even.
_LOOKBACK = 0.25

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*\s")


@dataclass(frozen=True, slots=True)
class Chunk:
    """One segment, and where it came from in the source text."""

    index: int
    text: str
    start: int
    end: int


def _boundary(text: str, start: int, limit: int) -> int:
    """The best place to cut `text[start:limit]`, as an absolute offset.

    Preference order — paragraph, sentence, whitespace — each searched only inside the
    lookback window so a document with no paragraph breaks does not produce one enormous
    chunk and one tiny one.
    """
    window_start = start + int((limit - start) * (1 - _LOOKBACK))
    segment = text[start:limit]
    offset = window_start - start

    para = [m.end() for m in _PARAGRAPH.finditer(segment) if m.end() >= offset]
    if para:
        return start + para[-1]

    sentence = [m.end() for m in _SENTENCE_END.finditer(segment) if m.end() >= offset]
    if sentence:
        return start + sentence[-1]

    space = segment.rfind(" ", offset)
    if space > 0:
        return start + space + 1

    return limit                      # one unbroken word longer than the window


def chunk_text(text: str, *, max_chars: int = DEFAULT_MAX_CHARS,
               overlap: int = DEFAULT_OVERLAP) -> list[Chunk]:
    """Split `text` into segments of at most `max_chars`, cut at natural boundaries.

    `overlap` re-reads that many characters of the previous chunk so a fact spanning a
    seam lands whole in the later chunk. It is capped at a third of `max_chars`: beyond
    that the duplication costs more in extraction than the rescued facts are worth.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    body = text or ""
    if not body.strip():
        return []
    overlap = max(0, min(overlap, max_chars // 3))

    chunks: list[Chunk] = []
    pos = 0
    while pos < len(body):
        limit = min(pos + max_chars, len(body))
        end = limit if limit == len(body) else _boundary(body, pos, limit)
        if end <= pos:                                   # boundary search made no progress
            end = limit
        chunks.append(Chunk(index=len(chunks), text=body[pos:end], start=pos, end=end))
        if end >= len(body):
            break
        # Step back by the overlap, but never far enough to repeat a whole chunk — that
        # would be an infinite loop on a document with no boundaries at all.
        pos = max(end - overlap, pos + 1) if overlap else end
    return chunks
