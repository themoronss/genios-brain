"""L1.4.6-U2 · offset alignment — mask -> extract -> align -> the quote resolves in the SOURCE.

    pytest tests/capture/semantic/test_offset_alignment.py -q

The model never reads the stored text. It reads a PII-masked, possibly chunked VIEW of it, and
the offsets it returns are measured against that view — off from the prepared text by the
length of every mask token above them, and off again by the chunk's own start. This file is the
round trip that proves the translation back is exact, in all three frames:

    view      what the model was shown (one chunk of the masked text, or all of it)
    prepared  `PreparedContent.clean_text` — masked, whole message
    source    the ORIGINAL text, where the PII still is

The property test is the centre of the file. It generates text, plants real PII literals in it,
runs the REAL masker (`capture/preprocess`), optionally cuts it with the REAL chunker, picks a
random region of a random chunk as the model's quote, aligns it, and checks the result against a
naive per-character oracle built independently from the offset map. Random cases are seeded, so
a failure is reproducible from the case it prints rather than from the mood of the machine.

The awkward cases get their own named tests, because a generator finds them rarely and a reader
needs to see them stated: text beyond the BMP, CRLF, a mask at position 0, a mask at the very
end, two adjacent masks, and a quote that starts halfway through a mask token.

**A mask is atomic.** A quote beginning inside `[AADHAAR]` corresponds, in the original, to the
whole Aadhaar number — there is no source character at "the third character of the token" — so
the source region EXPANDS to the mask's boundaries and `crosses_mask` says it did. The
round-trip assertion is written the only way it can be honest: the source region, RE-MASKED,
contains the quote; and when no mask was touched, the source region IS the quote, byte for byte.
"""

from __future__ import annotations

import random

import pytest

from genios_engine.capture.documents.chunking import SENTENCE, Chunk, chunk_document
from genios_engine.capture.preprocess import pii
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.capture.semantic.evidence_binder import ModelSpan, align_span
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS
from genios_engine.contracts.prepared_content import PreparedContent

pytestmark = pytest.mark.unit

PREPARED_REF = "prepared_content:evt_align"
CHUNK_REF = "chunk:doc_align:0"

#: Literals the real detectors in `capture/preprocess/pii.py` actually match. Using real ones
#: keeps the whole pipeline under test — a fake "[MASK]" planted by hand would prove the test's
#: own arithmetic and nothing about the map the preprocessor really builds.
PAN = "ABCDE1234F"
AADHAAR = "1234 5678 9012"
IFSC = "HDFC0001234"


# ---------------------------------------------------------------------------------------------
# Helpers: build prepared content, and an oracle that is deliberately naive
# ---------------------------------------------------------------------------------------------


def prepare(original: str) -> PreparedContent:
    """The real preprocessor: detect PII, mask it, keep the offset map."""
    return preprocess(original, event_id="evt_align")


def prepare_with(original: str, matches: list[pii.PiiMatch]) -> PreparedContent:
    """Prepared content whose masked regions are stated rather than detected.

    `pii.mask` is the function that builds every offset map in the system and it masks the
    regions it is given, so this is the real map builder — it is only the DETECTION step that is
    replaced. That is what makes two zero-gap adjacent masks expressible: no pair of real
    detectors can fire back to back (each pattern is `\\b`-anchored, so the second would need a
    word boundary the first's last character denies), and the binder is a reader of the map, not
    of the detectors.
    """
    clean_text, offset_map, masked = pii.mask(original, matches)
    return PreparedContent(prepared_content_id="pc_align", event_id="evt_align",
                           clean_text=clean_text, language="en", masked_spans=masked,
                           offset_map=offset_map)


def char_origins(prepared: PreparedContent) -> list[tuple[int, int]]:
    """For each character of the prepared text, the source region it stands for.

    The oracle. One entry per prepared character, built by walking the segments and expanding
    them — obviously correct and obviously too slow to ship, which is the point: the unit under
    test does a segment search, this does not, and the two agreeing is evidence rather than a
    tautology. A masked segment's characters all stand for the WHOLE masked region, which is the
    atomicity rule expressed as data.
    """
    origins: list[tuple[int, int]] = []
    for segment in prepared.offset_map:
        width = segment.prep_end - segment.prep_start
        if segment.masked:
            origins.extend([(segment.src_start, segment.src_end)] * width)
        else:
            origins.extend((segment.src_start + i, segment.src_start + i + 1)
                           for i in range(width))
    return origins


def remask(original: str, matches: list[pii.PiiMatch], start: int, end: int) -> str:
    """`original[start:end]`, re-masked with the PII that falls inside it.

    The other half of the round trip. Aligned source offsets are expanded to mask boundaries, so
    every match overlapping the region is wholly inside it, and re-masking must reproduce exactly
    the prepared text over the same region.
    """
    inside = [pii.PiiMatch(m.start - start, m.end - start, m.pii_type)
              for m in matches if m.start >= start and m.end <= end]
    return pii.mask(original[start:end], inside)[0]


def expanded_prepared_region(prepared: PreparedContent, start: int, end: int) -> tuple[int, int]:
    """The prepared region grown to whole mask tokens — what the source region corresponds to."""
    low, high = start, end
    for segment in prepared.offset_map:
        if not segment.masked:
            continue
        if segment.prep_start <= start < segment.prep_end:
            low = segment.prep_start
        if segment.prep_start < end <= segment.prep_end:
            high = segment.prep_end
    return low, high


def assert_round_trip(original: str, prepared: PreparedContent, aligned, quote: str,
                      *, case: str = "") -> None:
    """mask -> extract -> align -> the quote resolves in the ORIGINAL text.

    Four claims, and each is a different way for alignment to be wrong:

    1. the prepared offsets slice the quote out of the prepared text, exactly;
    2. the source offsets match the naive per-character oracle;
    3. the source region, re-masked, is the prepared text over the same (mask-expanded) region —
       so the region really is the original of what the model read;
    4. the quote is inside that, and when no mask was touched it IS the region, byte for byte.
    """
    matches = pii.detect(original) if prepared.masked_spans else []
    if prepared.masked_spans and not matches:
        matches = [pii.PiiMatch(m.src_start, m.src_end, m.pii_type)
                   for m in prepared.masked_spans]
    origins = char_origins(prepared)

    assert prepared.clean_text[aligned.prepared_start:aligned.prepared_end] == quote, case
    assert aligned.source_start == origins[aligned.prepared_start][0], case
    assert aligned.source_end == origins[aligned.prepared_end - 1][1], case
    assert 0 <= aligned.source_start < aligned.source_end <= len(original), case

    low, high = expanded_prepared_region(prepared, aligned.prepared_start, aligned.prepared_end)
    rebuilt = remask(original, matches, aligned.source_start, aligned.source_end)
    assert rebuilt == prepared.clean_text[low:high], case
    assert quote in rebuilt, case
    if not aligned.crosses_mask:
        assert original[aligned.source_start:aligned.source_end] == quote, case


# ---------------------------------------------------------------------------------------------
# The property: a generated round trip
# ---------------------------------------------------------------------------------------------

_FILLER = ["Please ", "confirm ", "the ", "invoice ", "by Friday. ", "a", "b", " ", "\n",
           "\r\n", "café ", "😀 ", "𝐀𝐁 ", ", ", "Rohit said. "]
_PII = [PAN, AADHAAR, IFSC]


def _generate(rng: random.Random) -> str:
    """Text with real PII planted in it, padded so the `\\b`-anchored detectors actually fire."""
    parts: list[str] = []
    for _ in range(rng.randint(4, 30)):
        if rng.random() < 0.22:
            parts.append(" " + rng.choice(_PII) + " ")
        else:
            parts.append(rng.choice(_FILLER))
    return "".join(parts)


@pytest.mark.parametrize("seed", range(40))
def test_property_every_generated_quote_round_trips_to_the_original_text(seed):
    """Ten generated messages per seed, each aligned whole and again in chunks.

    A quote is a random region of what the model was shown, which is exactly the thing whose
    offsets have no meaning until this unit translates them.
    """
    rng = random.Random(seed)
    checked = 0
    for case in range(10):
        original = _generate(rng)
        prepared = prepare(original)
        clean = prepared.clean_text
        if len(clean.strip()) < 2:
            continue

        chunks: list[Chunk | None] = [None]
        chunks.extend(chunk_document(clean, max_chars=rng.randint(20, 120), strategy=SENTENCE))

        for chunk in chunks:
            view = clean if chunk is None else chunk.text
            if len(view) < 2:
                continue
            for _ in range(3):
                start = rng.randrange(len(view))
                length = rng.randint(1, min(MAX_QUOTE_CHARS, len(view) - start))
                quote = view[start:length + start]
                if not quote.strip():
                    continue
                aligned = align_span(ModelSpan(quote=quote, view_start=start,
                                               view_end=start + length),
                                     prepared, source_ref=PREPARED_REF, chunk=chunk)
                assert aligned is not None, (seed, case, start, length, repr(quote))
                assert_round_trip(original, prepared, aligned, quote,
                                  case=f"seed={seed} case={case} start={start} len={length}")
                checked += 1
    assert checked > 0, "the generator produced nothing to check — the property proved nothing"


# ---------------------------------------------------------------------------------------------
# The awkward cases, stated
# ---------------------------------------------------------------------------------------------


def test_a_mask_at_position_zero_shifts_every_offset_after_it():
    """The commonest real shape: a message that opens with the number it is about."""
    original = f"{PAN} is the PAN on file."
    prepared = prepare(original)
    assert prepared.clean_text.startswith("[PAN]")

    quote = "[PAN] is the PAN"
    aligned = align_span(ModelSpan(quote=quote, view_start=0, view_end=len(quote)),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert aligned.crosses_mask is True
    assert aligned.source_start == 0
    assert aligned.source_end == len(f"{PAN} is the PAN")
    assert_round_trip(original, prepared, aligned, quote)


def test_a_mask_at_the_very_end_leaves_no_trailing_segment_to_fall_back_on():
    """There is no passthrough after the last match, so the exclusive-end reader has to take the
    masked segment's own `src_end` — the case a naive `to_source_offset(end)` gets wrong."""
    original = f"The PAN is {PAN}"
    prepared = prepare(original)
    assert prepared.clean_text.endswith("[PAN]")

    quote = "is [PAN]"
    aligned = align_span(ModelSpan(quote=quote, view_start=prepared.clean_text.index(quote),
                                   view_end=prepared.clean_text.index(quote) + len(quote)),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert aligned.source_end == len(original)
    assert original[aligned.source_start:aligned.source_end] == f"is {PAN}"
    assert_round_trip(original, prepared, aligned, quote)


def test_two_adjacent_masks_expand_independently():
    """No passthrough segment between them, so an implementation that assumed one would read the
    second token's source region off the first."""
    original = "AAAAAAAAAABBBBBBBBBB tail"
    prepared = prepare_with(original, [pii.PiiMatch(0, 10, "PAN"),
                                       pii.PiiMatch(10, 20, "IFSC")])
    assert prepared.clean_text == "[PAN][IFSC] tail"

    quote = "[IFSC] tail"
    aligned = align_span(ModelSpan(quote=quote, view_start=5, view_end=5 + len(quote)),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert (aligned.source_start, aligned.source_end) == (10, len(original))
    assert_round_trip(original, prepared, aligned, quote)


def test_a_quote_starting_halfway_through_a_mask_token_expands_to_the_whole_number():
    """A mask is atomic: the original has no character at "the third character of [AADHAAR]", so
    the source region grows to the whole number and `crosses_mask` says the width changed."""
    original = f"Aadhaar {AADHAAR} was shared."
    prepared = prepare(original)
    token_start = prepared.clean_text.index("[AADHAAR]")

    quote = prepared.clean_text[token_start + 3:token_start + 14]
    aligned = align_span(ModelSpan(quote=quote, view_start=token_start + 3,
                                   view_end=token_start + 14),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert aligned.crosses_mask is True
    assert aligned.source_start == original.index(AADHAAR)
    assert aligned.source_end - aligned.source_start > len(quote)
    assert_round_trip(original, prepared, aligned, quote)


def test_offsets_are_codepoints_so_text_beyond_the_bmp_does_not_shift_a_span():
    """An emoji is two UTF-16 units and one Python character. A model counting the former would
    hand us offsets that are short by one per emoji, and the alignment must not compound that by
    counting differently again on the way back."""
    original = f"Deal 😀 closed 𝐀𝐁 with {PAN} today."
    prepared = prepare(original)

    quote = "closed 𝐀𝐁 with [PAN]"
    start = prepared.clean_text.index(quote)
    aligned = align_span(ModelSpan(quote=quote, view_start=start, view_end=start + len(quote)),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert original[aligned.source_start:aligned.source_end] == f"closed 𝐀𝐁 with {PAN}"
    assert_round_trip(original, prepared, aligned, quote)


def test_crlf_line_endings_count_as_two_characters_on_both_sides_of_the_map():
    original = f"Line one\r\n{PAN}\r\nLine three"
    prepared = prepare(original)

    quote = "one\r\n[PAN]\r\nLine"
    start = prepared.clean_text.index(quote)
    aligned = align_span(ModelSpan(quote=quote, view_start=start, view_end=start + len(quote)),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert original[aligned.source_start:aligned.source_end] == f"one\r\n{PAN}\r\nLine"
    assert_round_trip(original, prepared, aligned, quote)


def test_text_with_no_pii_at_all_aligns_one_to_one():
    """The identity case still goes through the map, and an empty map must not fall over."""
    original = "Finance will confirm the increase by Friday."
    prepared = prepare(original)
    assert prepared.masked_spans == []

    quote = "confirm the increase"
    start = original.index(quote)
    aligned = align_span(ModelSpan(quote=quote, view_start=start, view_end=start + len(quote)),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert (aligned.source_start, aligned.source_end) == (start, start + len(quote))
    assert aligned.crosses_mask is False


# ---------------------------------------------------------------------------------------------
# Chunking: the offsets a chunked document's model call returns
# ---------------------------------------------------------------------------------------------


def chunked_fixture() -> tuple[str, PreparedContent, Chunk]:
    original = ("Section one is about nothing much at all. Section two states the PAN "
                f"{PAN} plainly. Section three closes the matter for good.")
    prepared = prepare(original)
    chunks = chunk_document(prepared.clean_text, max_chars=60, strategy=SENTENCE)
    target = next(c for c in chunks if "[PAN]" in c.text)
    return original, prepared, target


def test_a_chunk_local_offset_becomes_a_prepared_offset_by_adding_the_chunk_start():
    """U2's stated rule. Without it every chunk after the first cites the first chunk's text."""
    original, prepared, chunk = chunked_fixture()
    quote = "the PAN [PAN]"
    view_start = chunk.text.index(quote)
    assert chunk.start_offset > 0, "the fixture must exercise a chunk that is not the first"

    aligned = align_span(ModelSpan(quote=quote, view_start=view_start,
                                   view_end=view_start + len(quote)),
                         prepared, source_ref=PREPARED_REF, chunk=chunk)

    assert aligned is not None
    assert aligned.prepared_start == chunk.start_offset + view_start
    assert aligned.span.start_offset == aligned.prepared_start
    assert original[aligned.source_start:aligned.source_end] == f"the PAN {PAN}"
    assert_round_trip(original, prepared, aligned, quote)


def test_a_chunk_source_ref_keeps_the_stored_offsets_chunk_local():
    """C-01 defines two frames and the reference names which one the span is measured in.

    `chunk:<doc>:<n>` means "into chunk n", so the stored offsets stay view-local while the
    prepared and source pairs still carry the whole-document truth. A span whose offsets are in
    one frame while its reference names the other points at the wrong sentence invisibly.
    """
    original, prepared, chunk = chunked_fixture()
    quote = "the PAN [PAN]"
    view_start = chunk.text.index(quote)

    aligned = align_span(ModelSpan(quote=quote, view_start=view_start,
                                   view_end=view_start + len(quote)),
                         prepared, source_ref=CHUNK_REF, chunk=chunk)

    assert aligned is not None
    assert (aligned.span.start_offset, aligned.span.end_offset) == (view_start,
                                                                    view_start + len(quote))
    assert chunk.text[aligned.span.start_offset:aligned.span.end_offset] == quote
    assert aligned.prepared_start == chunk.start_offset + view_start
    assert_round_trip(original, prepared, aligned, quote)


def test_a_chunk_cut_from_a_different_string_is_a_caller_bug_and_raises():
    """Mask first, THEN chunk. Chunking the raw text and masking afterwards gives every chunk
    after the first a start that means nothing in either frame — wrong by an amount nothing
    downstream can detect, which is why it raises here instead of returning None."""
    original, prepared, chunk = chunked_fixture()
    raw_chunk = Chunk(index=chunk.index, text=original[chunk.start_offset:chunk.end_offset],
                      start_offset=chunk.start_offset, end_offset=chunk.end_offset)
    assert raw_chunk.text != chunk.text

    with pytest.raises(ValueError):
        align_span(ModelSpan(quote="Section", view_start=0, view_end=7), prepared,
                   source_ref=PREPARED_REF, chunk=raw_chunk)


def test_a_chunk_frame_with_no_chunk_raises():
    prepared = prepare("Finance will confirm the increase by Friday.")
    with pytest.raises(ValueError):
        align_span(ModelSpan(quote="Finance", view_start=0, view_end=7), prepared,
                   source_ref=CHUNK_REF)


@pytest.mark.parametrize("source_ref", ["", "   ", "evt_123", "prepared:evt_1", "chunks:doc:1"])
def test_a_source_ref_naming_no_known_frame_raises(source_ref):
    """Character 412 *of what*. C-01 defines exactly two shapes and a third is a caller bug."""
    prepared = prepare("Finance will confirm the increase by Friday.")
    with pytest.raises(ValueError):
        align_span(ModelSpan(quote="Finance", view_start=0, view_end=7), prepared,
                   source_ref=source_ref)


# ---------------------------------------------------------------------------------------------
# Model output that cannot describe a region at all
# ---------------------------------------------------------------------------------------------

TEXT = "Finance will confirm the increase by Friday."


@pytest.mark.parametrize("model_span, why", [
    (ModelSpan(quote="Finance", view_start=-1, view_end=6), "a negative start"),
    (ModelSpan(quote="Finance", view_start=10, view_end=4), "an inverted range"),
    (ModelSpan(quote="Finance", view_start=10, view_end=10), "an empty range"),
    (ModelSpan(quote="", view_start=0, view_end=7), "an empty quote"),
    (ModelSpan(quote="   \n ", view_start=0, view_end=5), "a whitespace-only quote"),
    (ModelSpan(quote="x" * (MAX_QUOTE_CHARS + 1), view_start=0, view_end=1),
     "a quote longer than the cap C-01 refuses to construct"),
    (ModelSpan(quote="Friday.", view_start=len(TEXT) - 2, view_end=len(TEXT) + 5),
     "a region running past the end of the prepared text"),
])
def test_model_output_that_describes_no_region_returns_none_rather_than_a_span(model_span, why):
    """None is not a verdict on whether the model read the quote correctly — that is ALG-08's
    question, asked later against aligned offsets. It means there is no region to ask about, and
    emitting a span anyway would put a receipt in the store no source text can resolve."""
    prepared = prepare(TEXT)
    assert align_span(model_span, prepared, source_ref=PREPARED_REF) is None, why


def test_a_quote_running_past_the_end_of_its_chunk_returns_none():
    """The model cannot have read past the view it was shown, so an offset that says it did is
    output to discard rather than translate."""
    _, prepared, chunk = chunked_fixture()
    over = ModelSpan(quote="z" * (len(chunk.text) + 1), view_start=0,
                     view_end=len(chunk.text) + 1)

    assert align_span(over, prepared, source_ref=PREPARED_REF, chunk=chunk) is None


def test_the_span_leaves_unverified_because_the_extractor_seam_may_not_stamp_one():
    """Alignment moves numbers. It does not check whether the words are really there, and a span
    that arrived from a model claiming `verified` has no way to acquire the flag here."""
    prepared = prepare(TEXT)
    aligned = align_span(ModelSpan(quote="Finance", view_start=0, view_end=7), prepared,
                         source_ref=PREPARED_REF)

    assert aligned is not None
    assert aligned.span.verified is False


def test_an_end_that_disagrees_with_the_quote_is_re_derived_from_the_quote():
    """ALG-08's D7: the end is `start + len(quote)` by construction, so the quote is the
    testimony and the start is the only number the model actually measured. A model that counted
    UTF-16 units reports a short end — that must not truncate the receipt."""
    prepared = prepare(TEXT)
    aligned = align_span(ModelSpan(quote="Finance will confirm", view_start=0, view_end=12),
                         prepared, source_ref=PREPARED_REF)

    assert aligned is not None
    assert aligned.span.quote == "Finance will confirm"
    assert aligned.span.end_offset == len("Finance will confirm")
    assert TEXT[aligned.span.start_offset:aligned.span.end_offset] == aligned.span.quote
    # Every frame, not only the stored one: a prepared or source end taken from the model's
    # number would truncate the region a card highlights while the span itself looked correct.
    assert aligned.prepared_end == len("Finance will confirm")
    assert aligned.source_end == len("Finance will confirm")
    assert_round_trip(TEXT, prepared, aligned, "Finance will confirm")
