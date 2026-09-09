"""Reply history — which characters of a message the SENDER did not write.

**Why this is a Layer 1 module.** Mail is quoted. Every reply carries the message it answers, and
often the whole thread beneath that, so the raw body of a twelfth-turn email contains eleven
older messages. An extractor reading that body extracts eleven old messages' claims and attributes
them to today's, which is not a ranking mistake — it is the wrong facts, on the wrong date, from
the wrong person.

Measured on the pilot before this module moved here: 23 qualified signals whose entire receipt was
an attribution line (`"On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:"` stored as a
`financial_obligation` at 4560 bp, the second-highest importance on the tenant), and roughly sixty
more that were ONE sentence counted once per message that quoted it — `copies == distinct_events`
in every duplicate group, with no within-event duplication anywhere.

**This code is not new. It was on the wrong side of the pipeline.** It lived in
`context/lifecycle/textguard.py`, where Layer 2 asks a different and much later question — is this
completion claim the sender's own sentence — and `genios_engine/capture/` had zero references to
it. Layer 2 importing Layer 1 is the direction dependencies are supposed to run; Layer 1 reaching
up into Layer 2 is not. So the implementation moved down and `textguard` re-exports it, which
leaves `judge.py` and its adversarial suite untouched.

Nothing about the detection changed in the move. The regexes, the merging of contiguous quoted
runs, the any-overlap rule and the half-open convention are byte-for-byte what L2 has been using.
"""
from __future__ import annotations

import re

__all__ = ["in_quoted_history", "quoted_regions"]


#: An attribution line — the header a mail client writes above the text it is quoting. Everything
#: from here to the end of the message is history. Deliberately anchored to the START of a line
#: and deliberately narrow: matching "wrote:" anywhere would swallow "as Priya wrote: this is
#: done" mid-paragraph, which is live text and must stay quotable.
_ATTRIBUTION = re.compile(
    r"^[ \t]*(?:"
    r"-{2,}\s*(?:original message|forwarded message)\s*-{2,}"          # Outlook / Gmail forward
    r"|_{5,}"                                                          # Outlook's rule
    r"|on\b.{0,200}?\bwrote:[ \t]*$"                                   # "On 12 Feb, X wrote:"
    r"|from:.{0,200}$(?=\n[ \t]*(?:sent|date|to):)"                    # Outlook header block
    r"|(?:begin|-+)\s*forwarded message"
    r")",
    re.IGNORECASE | re.MULTILINE | re.DOTALL)

#: A quote marker: one or more '>' at the start of a line, the convention every plain-text mail
#: client emits.
_QUOTE_LINE = re.compile(r"^[ \t]*>+", re.MULTILINE)


def quoted_regions(text: str) -> tuple[tuple[int, int], ...]:
    """The character ranges of `text` that are REPLY HISTORY rather than this sender's words.

    Two shapes, because mail clients produce two. A run of `>`-prefixed lines is its own region;
    an attribution line makes everything after it history, since no client writes one and then
    resumes the live message below it (top-posting is the norm and bottom-posting puts the live
    text ABOVE the attribution too).

    Returns ranges in ascending order. Half-open, `[start, end)`, the same convention
    `EvidenceSpan` uses, so a caller can compare them against a span's offsets directly.
    """
    if not text:
        return ()
    regions: list[tuple[int, int]] = []

    attribution = _ATTRIBUTION.search(text)
    if attribution is not None:
        regions.append((attribution.start(), len(text)))

    # Contiguous runs of quoted lines are merged, so a quoted paragraph is ONE region rather than
    # one per line — a span crossing two quoted lines must still land inside a single range.
    run_start: int | None = None
    run_end = 0
    for match in _QUOTE_LINE.finditer(text):
        line_end = text.find("\n", match.start())
        line_end = len(text) if line_end == -1 else line_end + 1
        if run_start is not None and match.start() <= run_end:
            run_end = max(run_end, line_end)
            continue
        if run_start is not None:
            regions.append((run_start, run_end))
        run_start, run_end = match.start(), line_end
    if run_start is not None:
        regions.append((run_start, run_end))

    return tuple(sorted(regions))


def in_quoted_history(text: str, start: int, end: int) -> bool:
    """Whether the span at `[start, end)` lies inside quoted history.

    ANY OVERLAP COUNTS, not containment. A quote that begins in the live text and runs into the
    history is not a sentence the sender wrote either, and requiring full containment would make
    the guard avoidable by widening the quote by one character.
    """
    if end <= start:
        return False
    return any(start < region_end and end > region_start
               for region_start, region_end in quoted_regions(text))
