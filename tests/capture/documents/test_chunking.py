"""L1.3.4-U4 · section-aware chunking (ALG-01) — the two properties everything above depends on.

The acceptance doc-03 states for this unit is one sentence: *a fixture contract with a
Termination clause spanning a would-be chunk boundary yields that clause whole, in one chunk,
with `section_title="Termination"`.* `CONTRACT` below is built so that clause genuinely straddles
a boundary — its two key sentences are further apart than `MAX` — and the sentence-strategy test
proves it, so the section-strategy test cannot pass for the wrong reason.

The second property is not in doc-03's acceptance line but is the reason W2 touched this file at
all: **a chunk is a slice of the source, not a rebuilt string.** `capture/validate/spans.py`
resolves `source[start:end] == quote` byte-for-byte and W3's evidence binder resolves against the
same offsets; a chunker that re-joins sentences with `" "` displaces every character after the
first paragraph break and turns correctly-cited quotes into apparent hallucinations. Every test
here that builds chunks also asserts the round-trip.
"""
from __future__ import annotations

import pytest

from genios_engine.capture.documents.chunking import (CHUNK_STRATEGIES, DEFAULT_CHUNK_CHARS,
                                                      NONE, SECTION, SENTENCE, Chunk,
                                                      chunk_document, chunk_text)

MAX = 600

#: Two sentences 900+ characters apart inside one clause. Any packer that respects `MAX` must
#: put them in different chunks — unless it refuses to split the clause, which is the point.
TERM_OPEN = "Either party may terminate this agreement on ninety days written notice."
TERM_CLOSE = "Notice under this clause must be delivered to the registered office."


def _body(stem: str, count: int) -> str:
    return " ".join(f"{stem} point {i} applies to both parties in full." for i in range(count))


CONTRACT = "\n\n".join([
    "This agreement is entered into between Acme Corp and Globe Industries. "
    "It records what each side owes the other. It is governed by the laws of England.",
    "1. Overview\n" + _body("Overview", 6),
    "2. Pricing\n" + _body("Pricing", 6),
    "3. Termination\n" + TERM_OPEN + " " + _body("Termination", 16) + " " + TERM_CLOSE,
    "## Service Levels\n" + _body("Availability", 6),
    "**Governing Law**\n" + _body("Jurisdiction", 4),
    "SCHEDULE A\n" + _body("Schedule", 4),
])


def _assert_slices(source: str, chunks: tuple[Chunk, ...]) -> None:
    """Every chunk is literally a region of the source, chunks advance, and nothing but
    whitespace falls between them."""
    cursor = 0
    for i, c in enumerate(chunks):
        assert c.index == i
        assert source[c.start_offset:c.end_offset] == c.text, f"chunk {i} is not a slice"
        assert c.start_offset >= cursor, f"chunk {i} overlaps or moves backwards"
        assert source[cursor:c.start_offset].strip() == "", f"text dropped before chunk {i}"
        cursor = c.end_offset
    assert source[cursor:].strip() == "", "text dropped after the last chunk"


# ── the doc-03 acceptance ─────────────────────────────────────────────────────────────────────

def test_the_termination_clause_really_does_straddle_a_sentence_boundary():
    """The fixture check. Without this the acceptance test below would pass on a contract whose
    Termination clause happened to fit, which proves nothing about clauses that do not."""
    chunks = chunk_document(CONTRACT, max_chars=MAX, strategy=SENTENCE)
    assert not any(TERM_OPEN in c.text and TERM_CLOSE in c.text for c in chunks)
    assert any(TERM_OPEN in c.text for c in chunks) and any(TERM_CLOSE in c.text for c in chunks)
    _assert_slices(CONTRACT, chunks)


def test_the_clause_that_straddles_a_boundary_arrives_whole_and_titled():
    """doc-03's acceptance for L1.3.4-U4, verbatim: whole, one chunk, `section_title`.

    A cancellation right whose trigger is in chunk 7 and whose notice period is in chunk 8 is a
    clause that no extractor reading one chunk at a time can ever find.
    """
    chunks = chunk_document(CONTRACT, max_chars=MAX, strategy=SECTION)
    holding = [c for c in chunks if TERM_OPEN in c.text]
    assert len(holding) == 1
    clause = holding[0]
    assert TERM_CLOSE in clause.text                      # whole, both ends in the same chunk
    assert clause.section_title == "Termination"
    assert clause.oversized is True                       # flagged, not destroyed
    _assert_slices(CONTRACT, chunks)


def test_every_chunk_carries_the_title_of_the_section_it_came_from():
    titles = {c.section_title for c in chunk_document(CONTRACT, max_chars=MAX, strategy=SECTION)}
    assert titles == {None, "Overview", "Pricing", "Termination", "Service Levels",
                      "Governing Law", "SCHEDULE A"}


# ── heading detection: the four forms, and the false positive that would split a clause ───────

@pytest.mark.parametrize("line, expected", [
    ("# Termination",                       "Termination"),          # markdown atx
    ("### Termination of Services",         "Termination of Services"),
    ("3. Termination",                      "Termination"),          # numbered clause
    ("3.2.1 Payment Terms",                 "Payment Terms"),        # nested numbering
    ("IV. Renewal",                         "Renewal"),              # roman numeral
    ("TERMINATION",                         "TERMINATION"),          # all caps
    ("12. SERVICE LEVELS",                  "SERVICE LEVELS"),       # numbered all caps
    ("**Governing Law**",                   "Governing Law"),        # bold run
    ("2. Fees and Charges",                 "Fees and Charges"),     # connector word
    # ── refusals: a false heading splits a clause, which is the harm the unit prevents ──
    ("1. The parties agree to pay $5,000 within 30 days.", None),    # numbered PROSE
    ("The agreement terminates on 30 June.", None),                  # a sentence
    ("**the fee is 5% of revenue**",         None),                  # bold, not title-like
    ("A VERY LONG ALL CAPS LINE THAT RUNS WELL PAST EIGHTY CHARACTERS AND IS THEREFORE PROSE",
     None),
    ("",                                     None),
    # ── W2·D3: block capitals are EMPHASIS as often as they are structure ──────────────────
    # doc-03 L1.3.4-U4 step 1 lists ALL-CAPS as a heading form; it does not say that every
    # capitalised line is one. A negotiator shouting one line of a reply, and a warranty
    # disclaimer set in block capitals because consumer law requires it, are both prose, and
    # reading either as a section break tears the clause in half — the exact harm the section
    # strategy was added to prevent.
    ("WE WILL NOT ACCEPT THESE TERMS",       None),    # real-world all-caps PROSE
    ("LIMITATION OF LIABILITY",              "LIMITATION OF LIABILITY"),   # genuine heading
    ("TERMINATION AND Survival",             None),    # mixed case: not a caps heading at all
    ("EXPRESS OR IMPLIED INCLUDING BUT NOT LIMITED TO MERCHANTABILITY", None),  # clause line
])
def test_heading_forms_and_the_lines_that_must_not_be_headings(line, expected):
    """Each row is one heading form from doc-03 step 1, or one line that must NOT be taken for
    a heading. Driven through the public API: a detected heading starts a section, so a line is
    a heading exactly when the text after it becomes a chunk carrying it as `section_title`."""
    text = f"{line}\nBody sentence one here. Body sentence two here."
    chunks = chunk_document(text, max_chars=DEFAULT_CHUNK_CHARS, strategy=SECTION)
    assert chunks[0].section_title == expected
    _assert_slices(text, chunks)


# ── W2·D3 · all-caps prose vs an all-caps heading, in real document shapes ────────────────────

#: A negotiation reply that shouts one line in the middle of a paragraph. The caps run is a
#: CONTINUATION — the line under it starts lowercase and finishes the sentence — so a chunker
#: that reads it as a heading splits one clause into two fragments that each mean nothing.
EMPHATIC_REPLY = (
    "Thanks for sending the revised draft over on Friday:\n"
    "WE WILL NOT ACCEPT THESE TERMS\n"
    "unless the liability cap is raised to two million dollars and the notice period "
    "is cut to thirty days.\n"
)

#: A warranty disclaimer set in block capitals under a genuine all-caps heading — the shape
#: every commercial agreement uses, because consumer law requires the disclaimer to be
#: conspicuous. The heading is structure; the four lines under it are one clause.
BLOCK_CAPS_CLAUSE = (
    "9. WARRANTY DISCLAIMER\n"
    "\n"
    "THE SERVICES ARE PROVIDED ON AN AS-IS BASIS WITHOUT WARRANTY OF ANY KIND,\n"
    "EXPRESS OR IMPLIED INCLUDING BUT NOT LIMITED TO THE IMPLIED WARRANTIES\n"
    "OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE, AND THE VENDOR\n"
    "DISCLAIMS ALL LIABILITY FOR ANY LOSS ARISING FROM RELIANCE ON THEM.\n"
)


def test_an_emphatic_all_caps_line_inside_a_paragraph_is_not_a_section_break():
    """W2·D3. `WE WILL NOT ACCEPT THESE TERMS` is a clause, not a clause heading.

    Two independent signals say so and either one alone is enough: the line is built out of a
    pronoun, a modal and a negation — words no table of contents has ever contained — and the
    line under it starts lowercase, so the sentence is still running. Read as a heading, the
    refusal and the condition it is subject to land in different chunks, and an extractor
    reading one chunk at a time sees a party who refuses unconditionally.
    """
    chunks = chunk_document(EMPHATIC_REPLY, max_chars=MAX, strategy=SECTION)
    assert all(c.section_title is None for c in chunks), \
        [c.section_title for c in chunks]
    holding = [c for c in chunks if "WE WILL NOT ACCEPT THESE TERMS" in c.text]
    assert len(holding) == 1
    assert "unless the liability cap" in holding[0].text, "the clause was torn in half"
    _assert_slices(EMPHATIC_REPLY, chunks)


def test_a_legal_clause_in_block_capitals_stays_whole_under_its_real_heading():
    """The genuine heading is detected and the four capitalised body lines are not.

    Every one of those body lines is short enough, capitalised enough and unpunctuated enough
    to match the ALL-CAPS form on its own; what separates them from the heading is that each
    continues the line above it. Without that reading, one disclaimer becomes five sections and
    `section_title` — carried "so evidence spans can cite it" — names a fragment.
    """
    chunks = chunk_document(BLOCK_CAPS_CLAUSE, max_chars=4000, strategy=SECTION)
    assert [c.section_title for c in chunks] == ["WARRANTY DISCLAIMER"]
    assert len(chunks) == 1
    assert "MERCHANTABILITY" in chunks[0].text and "DISCLAIMS ALL LIABILITY" in chunks[0].text
    _assert_slices(BLOCK_CAPS_CLAUSE, chunks)


def test_a_genuine_all_caps_heading_still_opens_a_section_when_it_stands_alone():
    """The neutralisation of the two tests above: the fix must not cost a real heading.

    `SCHEDULE A` in `CONTRACT` and this one are the same form — a short capitalised label on
    its own line, after a sentence that ended — and both must still cut a section, or D3's fix
    has traded a torn clause for a 50-page chunk.
    """
    doc = ("The parties agree as follows.\n"
           "LIMITATION OF LIABILITY\n"
           "Neither party is liable for indirect loss. Liability is capped at fees paid.\n")
    chunks = chunk_document(doc, max_chars=MAX, strategy=SECTION)
    assert [c.section_title for c in chunks] == [None, "LIMITATION OF LIABILITY"]
    _assert_slices(doc, chunks)


# ── strategies ────────────────────────────────────────────────────────────────────────────────

def test_a_document_with_no_headings_degrades_to_sentence_packing():
    """"Heading boundaries first, sentence boundaries second" — with no headings, second is all
    there is. An email or a scanned page must not become one 40-page chunk."""
    prose = _body("Prose", 40)
    section = chunk_document(prose, max_chars=MAX, strategy=SECTION)
    sentence = chunk_document(prose, max_chars=MAX, strategy=SENTENCE)
    assert len(section) > 1
    assert [c.text for c in section] == [c.text for c in sentence]
    assert all(c.section_title is None for c in section)


def test_the_preamble_before_the_first_heading_is_packed_not_held_whole():
    """Text that belongs to no clause is not a clause, so rule 3 does not protect it — holding
    a 50-page unheaded preamble whole would be the un-chunked document the unit exists to
    divide."""
    doc = _body("Recital", 30) + "\n\n1. Termination\n" + _body("Termination", 4)
    chunks = chunk_document(doc, max_chars=MAX, strategy=SECTION)
    preamble = [c for c in chunks if c.section_title is None]
    assert len(preamble) > 1 and all(len(c.text) <= MAX for c in preamble)
    assert [c.section_title for c in chunks if c.section_title] == ["Termination"]
    _assert_slices(doc, chunks)


def test_strategy_none_is_one_chunk_flagged_when_it_exceeds_the_cap():
    small = chunk_document("Short note. Two lines.", max_chars=MAX, strategy=NONE)
    assert len(small) == 1 and small[0].oversized is False
    big = chunk_document(_body("Long", 40), max_chars=MAX, strategy=NONE)
    assert len(big) == 1 and big[0].oversized is True


def test_a_run_with_no_sentence_break_is_hard_split_and_loses_nothing():
    """A minified blob has no boundary to respect, so splitting it destroys nothing a boundary
    would have preserved — and refusing to split would hand S2 the whole blob."""
    blob = "A" * 5000
    chunks = chunk_document(blob, max_chars=DEFAULT_CHUNK_CHARS, strategy=SENTENCE)
    assert all(len(c.text) <= DEFAULT_CHUNK_CHARS for c in chunks)
    assert "".join(c.text for c in chunks) == blob
    _assert_slices(blob, chunks)


@pytest.mark.parametrize("strategy", CHUNK_STRATEGIES)
def test_no_non_whitespace_character_is_ever_dropped(strategy):
    """The no-loss invariant, on every strategy. A chunker that silently drops a paragraph is
    indistinguishable from a document that never contained it."""
    chunks = chunk_document(CONTRACT, max_chars=MAX, strategy=strategy)
    assert "".join("".join(c.text.split()) for c in chunks) == "".join(CONTRACT.split())
    _assert_slices(CONTRACT, chunks)


@pytest.mark.parametrize("blank", ["", "   ", "\n\n \t\n"])
def test_empty_input_is_no_chunks_rather_than_one_empty_chunk(blank):
    assert chunk_document(blank, strategy=SECTION) == ()
    assert chunk_text(blank) == []


def test_an_unknown_strategy_raises_rather_than_silently_chunking_by_sentence():
    """The value comes from an in-code registry, so a strategy that is not in the vocabulary is
    a typo — and falling back to `sentence` would chunk a 50-page agreement exactly the way this
    upgrade exists to stop, with nothing in the output to say it happened."""
    with pytest.raises(ValueError, match="unknown chunk strategy"):
        chunk_document(CONTRACT, strategy="paragraph")
    with pytest.raises(ValueError, match="max_chars"):
        chunk_document(CONTRACT, max_chars=0)


def test_chunk_text_is_a_projection_of_chunk_document_not_a_second_implementation():
    """The upload door and the extractor must never disagree about where a document divides."""
    assert chunk_text(CONTRACT, max_chars=MAX) == [
        c.text for c in chunk_document(CONTRACT, max_chars=MAX, strategy=SENTENCE)]
