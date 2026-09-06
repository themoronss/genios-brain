"""L1.3.4-U4 · Chunking (ALG-01) — section-aware, and offset-preserving.

A document is split into retrieval-sized pieces before S2 reads it. The naive approach — slicing
every N characters — cuts mid-sentence, mid-word, mid-table:

    "...refunds are accepted within | 30 days of purchase..."

Neither half means anything alone, so the fact is silently destroyed. The previous version of
this module fixed that much: it packed whole sentences to 2000 chars and never cut inside one.
Doc-03 names the two things it still got wrong.

**1 · It was not section-aware, and a clause split across two chunks is a clause never found.**
Globe's requirement is that a 50-page agreement becomes semantically bounded pieces — Overview,
Pricing, Renewal, Termination, SLA — because the extractor reads one chunk at a time and a
cancellation right whose trigger is in chunk 7 and whose notice period is in chunk 8 is, to
every layer above, two fragments that mean nothing rather than one clause that means everything.
The `section` strategy (the one doc-04 assigns to the `document` and `transcript` profiles)
therefore splits on **heading boundaries first** and sentence boundaries only inside text that
belongs to no heading.

**Rule 3 is absolute, and it is in tension with `max_chars` on purpose.** *"Never split inside a
detected clause, even if it exceeds max_chars — emit the oversized chunk and flag it, rather
than destroying the clause."* So a detected section is atomic: one section, one chunk, however
long, with `oversized=True` when it exceeds the cap. Sentence packing does not apply *inside* a
detected section — if it did, a long Termination clause would be split exactly the way the rule
forbids, and the acceptance fixture would fail for the reason the fixture exists. Sentence
boundaries govern the preamble (text before the first heading) and any document with no
headings at all, which is where "sentence boundaries second" bites. `oversized` is the contract
with the caller: pay for the longer prompt, or page the chunk yourself — but the clause arrives
whole either way, because a destroyed clause cannot be recovered downstream and a large one can.

**One chunk per section, never two sections merged.** Packing three short clauses into one chunk
would be safe for rule 3 and would cut the chunk count, and it is still refused: `section_title`
is carried *"so evidence spans can cite it"*, and a chunk spanning Pricing and Renewal has no
answer to which one a span is in. An ambiguous citation is worth less than an extra chunk.

**1b · It read EMPHASIS as structure (W2·D3).** Doc-03 step 1 lists ALL-CAPS as one of the
four heading forms; it does not say that every capitalised line is a heading. A negotiator who
shouts one line of a reply — `WE WILL NOT ACCEPT THESE TERMS` — and a warranty disclaimer set in
block capitals because consumer law requires it are both PROSE, and the module read both as
section breaks. The clause was then torn in half at the point of its own emphasis, which is the
exact harm the section strategy was added to prevent, on the exact lines that matter most.

Three signals separate a capitalised LABEL from a capitalised SENTENCE, and `_heading_title`
applies all three because each one alone has a documented way around it:

* **length** — a heading is at most `_MAX_HEADING_CHARS` characters *and* at most
  `_MAX_HEADING_WORDS` words. The word cap is new: `WE WILL NOT ACCEPT THESE TERMS` is thirty
  characters and passes every length rule this module used to have;
* **shape** — a heading is a noun phrase naming what follows (`LIMITATION OF LIABILITY`,
  `TERM AND TERMINATION`). A sentence needs a subject and a finite verb, and the closed part of
  that is `_PROSE_MARKERS`: no table of contents has ever contained `WE`, `WILL` or `NOT`;
* **surrounding context** — a heading does not continue the line above it and is not continued
  by the line below it. This is what saves a wrapped block-capitals clause, whose middle lines
  are short, unpunctuated and marker-free and would otherwise each open a section of their own.

Context is applied to the ALL-CAPS form and not to `#` or `**`, because those are explicit
authorial acts: an author who typed `## Termination` said it is a heading. A run of capitals is
not a declaration of structure, it is emphasis, and emphasis inside a paragraph is precisely the
case this module now refuses.

**2 · It destroyed offsets, which is the change that matters to W1 and W3.** The old packer
rebuilt chunk text with `" ".join(...)`, so a chunk was a *new string* whose relationship to the
source was unrecoverable: `"a.\n\nb."` came back as `"a. b."` and every character after the join
was displaced. `capture/validate/spans.py` resolves `source[start:end] == quote` byte-for-byte
and W3's evidence binder resolves spans against the same source text — against a rebuilt chunk
both silently report the model hallucinated a quote it in fact read correctly. Every chunk here
is therefore a **slice**: `Chunk.text is text[start_offset:end_offset]`, exactly, always, and
that identity is the module's central test.

PURE — no I/O, no clock, no model, no float. Every length and offset is an integer character
index into the string that was passed in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_CHUNK_CHARS = 2000

#: The strategies doc-04's profile registry names in its `chunk_strategy` column.
SENTENCE = "sentence"
SECTION = "section"
NONE = "none"
CHUNK_STRATEGIES = (NONE, SENTENCE, SECTION)

# sentence ends (. ! ? followed by whitespace) OR a paragraph break (blank line)
_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n{2,}")

# ── heading detection (ALG-01 step 1: numbered clauses, ALL-CAPS, markdown, bold runs) ────────
# Every pattern is anchored to a WHOLE LINE and length-capped. A false heading is worse than a
# missed one: it splits a clause in half, which is the exact harm this unit exists to prevent,
# so each rule below is deliberately narrow and the ambiguous cases are left to sentence packing.
_MAX_HEADING_CHARS = 80

#: A heading is a LABEL, and a label is short. `_is_title_like` has always capped title-case
#: headings at eight words; the ALL-CAPS form was capped only in characters, so a thirty-character
#: sentence in capitals passed. One cap, one number, both forms.
_MAX_HEADING_WORDS = 8

#: Words that name no section and appear in almost every sentence: pronouns, auxiliaries, modals
#: and the negation. A heading is a noun phrase — `LIMITATION OF LIABILITY`, `TERM AND
#: TERMINATION`, `NO WARRANTY` — while a clause needs a subject and a finite verb, and this is the
#: closed, checkable part of that difference.
#:
#: The list is deliberately conservative, because a missed heading costs one over-packed section
#: and a false heading destroys a clause. `NO` is absent (`NO WARRANTY` is a real heading), `IT`
#: is absent (`IT SERVICES` is a department), `US` is absent (`US LAW` is a jurisdiction) and
#: `MAY` is absent (it is also a month). What remains cannot be read as a noun phrase in any
#: contract, invoice or transcript this layer reads.
_PROSE_MARKERS = frozenset({
    "i", "we", "our", "ours", "you", "your", "yours", "he", "him", "his", "she", "her", "hers",
    "they", "them", "their", "theirs", "its", "who", "whom", "whose",
    "am", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did",
    "will", "would", "shall", "should", "must", "can", "cannot", "could",
    "not",
})

#: What the line ABOVE a heading ends with when the heading starts something new: a finished
#: sentence, a colon introducing a list, or nothing at all. A line ending in a word or a comma is
#: a sentence still in progress, and a capitalised run inside it is emphasis.
_SENTENCE_END = frozenset(".!?:;")

_ATX = re.compile(r"^\s{0,3}#{1,6}\s+(\S.*?)\s*#*$")
_BOLD = re.compile(r"^\s{0,3}\*\*\s*(\S.*?)\s*\*\*\s*:?$")
_NUMBERED = re.compile(r"^\s{0,3}(?:\d{1,3}(?:\.\d{1,3}){0,3}|[IVXLC]{1,7})[.)]?\s+(\S.*?)\.?$")
_ALLCAPS = re.compile(r"^\s{0,3}(?:(?:\d{1,3}(?:\.\d{1,3}){0,3}|[IVXLC]{1,7})[.)]?\s+)?"
                      r"([A-Z][A-Z0-9 ,&/'’\-()]*[A-Z0-9)])\s*:?$")

#: Lowercase words allowed inside a Title Case heading. Without them "Terms of Service" and
#: "Notice and Cure" are not title-like and every numbered clause heading with a preposition
#: in it is missed.
_TITLE_CONNECTORS = frozenset({
    "of", "and", "the", "to", "for", "in", "or", "a", "an", "by", "on", "with", "at", "from",
    "de", "per", "vs",
})


def _reads_as_label(candidate: str) -> bool:
    """Is this a NOUN PHRASE naming a section, rather than a sentence?

    The half of the heading test that does not depend on capitalisation, so the title-case form
    and the ALL-CAPS form share one rule instead of drifting apart — which is how the caps form
    ended up with a character cap and no word cap and let `WE WILL NOT ACCEPT THESE TERMS`
    through while `1. The parties agree to pay $5,000 within 30 days` was correctly refused.

    Two conditions: at most `_MAX_HEADING_WORDS` words, and not one word from `_PROSE_MARKERS`.
    A line carrying a pronoun, an auxiliary, a modal or a negation is a clause with a subject and
    a verb; a section heading has neither.
    """
    words = candidate.split()
    if not words or len(words) > _MAX_HEADING_WORDS:
        return False
    if not any(ch.isalpha() for ch in candidate):
        return False
    return not any(w.lower().strip(".,;:()'\u2019\"") in _PROSE_MARKERS for w in words)


def _is_title_like(candidate: str) -> bool:
    """Does this read as a heading rather than as the first sentence of a paragraph?

    The discriminator that carries the weight: `1. Termination` is a heading and `1. The
    parties agree to pay $5,000 within 30 days` is a numbered *clause body*, and both match the
    same numbered-prefix regex. A heading is a label (`_reads_as_label`) and every word in it is
    capitalised or is a connector. Prose fails on its third word.
    """
    if not _reads_as_label(candidate):
        return False
    return all(w[0].isupper() or w[0].isdigit() or w.lower().strip(".,;:") in _TITLE_CONNECTORS
               for w in candidate.split())


def _stands_apart(previous: str | None, following: str | None) -> bool:
    """Is a line structurally separated from its neighbours, or is it inside a paragraph?

    The third D3 signal, and the one that saves a wrapped clause in block capitals: every middle
    line of such a clause is short, unpunctuated and marker-free, and only its NEIGHBOURS say it
    is not a heading.

    A heading starts something: the line above it is absent, blank, or a finished sentence. And a
    heading is not finished by the line below it: a following line that begins with a lowercase
    letter is the same sentence continuing, which no heading ever is.

    `previous`/`following` are `None` at the edges of the document, where there is no neighbour to
    contradict the reading — the first line of a file is exactly where a title lives.
    """
    if previous is not None:
        above = previous.strip()
        if above and above[-1] not in _SENTENCE_END:
            return False
    if following is not None:
        below = following.lstrip()
        if below and below[0].islower():
            return False
    return True


def _heading_title(line: str, *, previous: str | None = None,
                   following: str | None = None) -> str | None:
    """The heading text of `line`, or None if the line is not a heading.

    Order matters only in that markdown markers are unambiguous and are therefore trusted
    without the title-like test — an author who wrote `## Termination of Services for Cause`
    said it is a heading, and second-guessing that would drop real structure.

    `previous` and `following` are the raw neighbouring lines, and they are consulted for the
    ALL-CAPS form only (W2·D3, see the module docstring): `#` and `**` are declarations of
    structure, a run of capitals is not. `None` for either means "no neighbour" — the top or the
    bottom of the document — which is where a title legitimately sits with nothing around it.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_CHARS:
        return None
    m = _ATX.match(line)
    if m:
        return m.group(1).strip() or None
    m = _BOLD.match(line)
    if m and _is_title_like(m.group(1)):
        return m.group(1).strip()
    m = _ALLCAPS.match(line)
    if m:
        title = m.group(1).strip()
        if (sum(ch.isalpha() for ch in title) >= 3 and not any(ch.islower() for ch in title)
                and _reads_as_label(title) and _stands_apart(previous, following)):
            return title
    m = _NUMBERED.match(line)
    if m and _is_title_like(m.group(1)):
        return m.group(1).strip()
    return None


@dataclass(frozen=True)
class Chunk:
    """One retrieval-sized piece of a document, and where in the document it came from.

    `text` is `source[start_offset:end_offset]` — an identity, not an approximation. Frozen
    because a chunk is a claim about a region of a document: a caller that could edit the text
    without moving the offsets would produce a receipt that points at something else.
    """

    index: int
    text: str
    start_offset: int
    end_offset: int
    section_title: str | None = None
    #: The clause was longer than `max_chars` and was emitted whole rather than destroyed.
    oversized: bool = False


@dataclass(frozen=True)
class _Region:
    """A span of the source that chunks may not cross: one detected section, or the preamble."""

    title: str | None
    start: int
    end: int
    atomic: bool


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink `[start, end)` past leading and trailing whitespace. Returns an empty region as
    `(start, start)`; the caller drops those rather than emitting a chunk of blanks."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """The sentence/paragraph units of `text[start:end]`, as trimmed offset pairs.

    Split points come from `_BOUNDARY.finditer` over the region, so a unit is always a slice of
    the original string and never a rebuilt one.
    """
    spans: list[tuple[int, int]] = []
    cursor = start
    for m in _BOUNDARY.finditer(text, start, end):
        s, e = _trim(text, cursor, m.start())
        if e > s:
            spans.append((s, e))
        cursor = m.end()
    s, e = _trim(text, cursor, end)
    if e > s:
        spans.append((s, e))
    return spans


def _regions(text: str, strategy: str) -> list[_Region]:
    """Cut the document into the spans that chunking may not cross.

    For `section`, that is: the preamble before the first heading (not atomic — it is prose, not
    a clause), then one atomic region per heading, running from the heading line to the line
    before the next heading. For every other strategy the whole document is one non-atomic
    region, which is how `sentence` and `none` reduce to special cases of the same packer.
    """
    if strategy != SECTION:
        return [_Region(title=None, start=0, end=len(text), atomic=strategy == NONE)]

    headings: list[tuple[int, str]] = []           # (line start offset, title)
    offset = 0
    # Materialised because the ALL-CAPS rule reads the neighbours: a capitalised run wedged
    # between two halves of a sentence is emphasis, and only the lines around it say so.
    lines = text.splitlines(keepends=True)
    bare = [line.rstrip("\r\n") for line in lines]
    for i, line in enumerate(lines):
        title = _heading_title(bare[i],
                               previous=bare[i - 1] if i else None,
                               following=bare[i + 1] if i + 1 < len(bare) else None)
        if title:
            headings.append((offset, title))
        offset += len(line)

    if not headings:
        return [_Region(title=None, start=0, end=len(text), atomic=False)]

    regions: list[_Region] = []
    if headings[0][0] > 0:
        regions.append(_Region(title=None, start=0, end=headings[0][0], atomic=False))
    for i, (start, title) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        regions.append(_Region(title=title, start=start, end=end, atomic=True))
    return regions


def _pack(text: str, region: _Region, max_chars: int, out: list[Chunk]) -> None:
    """Fill `out` with the chunks of one region, greedily and without crossing its edges."""
    start, end = _trim(text, region.start, region.end)
    if end <= start:
        return

    def emit(s: int, e: int, oversized: bool = False) -> None:
        out.append(Chunk(index=len(out), text=text[s:e], start_offset=s, end_offset=e,
                         section_title=region.title, oversized=oversized))

    if region.atomic:
        # Rule 3: a detected clause is emitted whole, flagged when it exceeds the cap.
        emit(start, end, oversized=(end - start) > max_chars)
        return

    spans = _sentence_spans(text, start, end)
    cur_start: int | None = None
    cur_end = start
    for s, e in spans:
        if cur_start is not None:
            if e - cur_start <= max_chars:
                cur_end = e
                continue
            emit(cur_start, cur_end)
            cur_start = None
        if e - s > max_chars:
            # A single run with no sentence break inside it — a minified blob, a base64 payload.
            # There is no boundary to respect, so a hard split loses nothing that a boundary
            # would have preserved, and refusing to split would hand S2 the whole blob.
            for cut in range(s, e, max_chars):
                emit(cut, min(cut + max_chars, e))
            continue
        cur_start, cur_end = s, e
    if cur_start is not None:
        emit(cur_start, cur_end)


def chunk_document(text_content: str, *, max_chars: int = DEFAULT_CHUNK_CHARS,
                   strategy: str = SENTENCE) -> tuple[Chunk, ...]:
    """Split a document into chunks that carry their own offsets and their section title.

    `strategy` takes the vocabulary of doc-04's profile registry:

    * ``"none"`` — one chunk, the whole document, flagged `oversized` if it exceeds `max_chars`.
      For `chat` and `crm_note`, which are short by construction.
    * ``"sentence"`` — greedy packing of whole sentences and paragraphs. For `email`.
    * ``"section"`` — heading boundaries first, sentence boundaries only in un-headed text, and
      a detected clause is never split. For `document` and `transcript`.

    An unknown strategy raises. It arrives from an in-code registry rather than from user data,
    so a value that is not in `CHUNK_STRATEGIES` is a typo in a constant — and the alternative,
    silently falling back to `sentence`, would chunk a 50-page agreement the way this unit was
    upgraded to stop chunking it, with nothing in the output to say so.
    """
    if strategy not in CHUNK_STRATEGIES:
        raise ValueError(f"unknown chunk strategy {strategy!r}; expected one of {CHUNK_STRATEGIES}")
    if max_chars < 1:
        raise ValueError(f"max_chars must be positive, got {max_chars}")
    text = text_content or ""
    if not text.strip():
        return ()
    out: list[Chunk] = []
    for region in _regions(text, strategy):
        _pack(text, region, max_chars, out)
    return tuple(out)


def chunk_text(text_content: str, *, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """The sentence-strategy chunk texts, for callers that only want the strings.

    Kept because `api/upload_routes.py` chunks an upload into events and has no use for offsets
    yet. It is a projection of `chunk_document`, not a second implementation — the upload door
    and the extractor must never disagree about where a document divides.
    """
    return [c.text for c in chunk_document(text_content, max_chars=max_chars, strategy=SENTENCE)]
