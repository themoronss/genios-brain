"""ALG-08 · the Evidence Span Validator — L1.5.1, units U1 (span resolution) and U2 (monitor).

**This is the difference between "the AI said so" and "here is the sentence."** An extractor
hands us a quote and a pair of offsets and asserts they line up. Nothing about that assertion is
checkable from inside the extraction: a hallucinated quote and a real one arrive in the same
JSON, with the same confidence, wearing the same typography. This module is the only place that
opens the prepared text and looks. Without it, Globe Rule 04 — *confidence without receipts is a
guess* — is a slogan; with it, the rule is a function that returns a verdict.

**U1 grades, then corrects.** The cascade is ordered cheapest-first and every step is a weaker
claim about the same quote:

    BOUNDS      the offsets cannot describe a region of this text at all -> INVALID_BOUNDS
    EXACT       source[start:end] is the quote                           -> VERIFIED
    WHITESPACE  it is the quote modulo whitespace, at the stated start   -> VERIFIED_WHITESPACE
    RELOCATE    the quote is in the source, somewhere else               -> VERIFIED_RELOCATED
    FUZZY       it is in the source modulo whitespace, somewhere else    -> VERIFIED_FUZZY
    otherwise   the sentence the model cited does not exist              -> UNVERIFIED

Step 6 is the hallucination catch, and the four steps before it exist so that a real citation is
not thrown away over a reflowed newline. **Fuzzy here means whitespace, never semantics.** There
is deliberately no edit distance, no similarity ratio and no embedding anywhere in this file: a
validator that accepts a near-enough quote accepts a paraphrase, and a paraphrase is precisely
what an inventing model produces. If the words are not literally in the source, the answer is
UNVERIFIED.

**Offsets are corrected, never trusted.** Every verified grade returns a REWRITTEN span whose
quote is the source's own bytes at the offsets we actually found. A span that verified against
text but kept the model's offsets would highlight the wrong sentence in the card, which is a
worse failure than an honest UNVERIFIED — the reader checks the receipt, sees unrelated text,
and stops believing the receipts that are right.

**The drop policy is graded, not binary** (the spec's table, implemented verbatim in
`_POLICY`). A fabricated `Money` or `ResolvedDate` is DROPPED: an amount and a deadline are
acted on, and a wrong one does damage a missing one does not — the Globe fault was a card
reading "$84K" against a contract that said "$8.4K". A `Commitment`, `DecisionState` or
`Dependency` SURVIVES at `confidence_bp * 5 // 10` PER FABRICATED RECEIPT, with every failing
span left `verified=False`, which is the flag: an unverified commitment is still an open loop
worth tracking, it is just not evidence. Per receipt and not per claim, because ALG-08 states
its multipliers inside `verify_span`, which grades one span — and a per-claim penalty would make
stapling one true quote beside an invention completely free. `intent`, `stance` and `topics` are
untouched — they are summary judgements about the message, not citations into it, so there is
nothing for a span to substantiate.

**`Money` is graded twice, because it can fail two different ways.** It is the one policy type
carrying no `evidence` list, so its receipt is `as_written` — and finding that literal in the
source only proves somebody wrote the STRING. The Globe fault is the other failure: a real
literal beside a wrong integer ("$8.4K" carrying 8_400_000 minor units, which is $84,000). Upper
layers compare integers and render strings, so the two halves have to be checked against each
other by re-deriving the amount through ALG-10 under the connection's `locale`. A REFUSAL from
`money.py` is not a contradiction and never drops anything — see `_money_contradicts_its_literal`.

**`verified` is forced, never forwarded.** Every span leaving here carries a flag this module
decided, on the failure branches as much as the verified ones. The flag is an ordinary field
that an extractor can set itself, so passing a span through on UNVERIFIED would let an invention
keep a checkmark that V-5 downstream reads as a receipt. The seam in front of this one (S-9 in
`schema.py`) refuses such an extraction outright; `_as_unverified` here is the second lock.

**U2 makes a degrading extractor visible.** `unverified_rate_bp` is the proportion of distinct
spans that failed to resolve, in integer basis points. It is the earliest signal that a prompt
edit broke citation behaviour, and it is a release gate: a candidate prompt version whose rate
exceeds the incumbent's by more than 5 percentage points does not ship
(`rate_regression_blocks_release`). Without it a broken prompt does not fail — it quietly emits
weaker signals for a week and nobody can name the day it changed.

PURE. No database, no network, no model, no clock, no float — gate G1 greps this file for all
of them. Confidence arithmetic is integer basis points throughout: `bp * 9 // 10`, never
`bp * 0.9`, because a ratio composed across five layers is a number nobody can trace back to
the weakest source that produced it.
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from genios_engine.capture.validate.money import parse_money
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.units import Money, ResolvedDate

#: Full confidence in basis points. Every factor below is applied as `bp * num // den` against a
#: value already in this scale — never as a ratio, and never renormalized through a float.
BP_FULL = 10_000

#: The release gate from L1.5.1-U2, in the unit the monitor actually reports. The doc states it
#: as "5 percentage points"; 5 pp is 500 bp, and stating it once here is what stops the two
#: spellings from drifting apart the first time somebody compares a rate to a threshold.
MAX_RATE_REGRESSION_BP = 500


class SpanVerdict(str, Enum):
    """How a span resolved against real source text — the six outcomes of the ALG-08 cascade.

    `str`-valued so a verdict can be written straight into a metrics row or a log line without a
    second mapping table that would drift from this one. The order of declaration is the order
    of strength, which `_STRENGTH` below depends on.
    """

    #: `source[start:end]` is the quote, byte for byte. The model measured what it read.
    VERIFIED = "verified"
    #: The quote is at the stated start but whitespace differs — a newline the extractor read as
    #: a space, a collapsed run of indentation. Real citation, cosmetic disagreement, no penalty.
    VERIFIED_WHITESPACE = "verified_whitespace"
    #: The quote is in the source, but not where the model said. The words are real and the
    #: measurement is not, so confidence is cut to `9 // 10`.
    VERIFIED_RELOCATED = "verified_relocated"
    #: Found only after whitespace normalization and only by searching the whole source — the
    #: weakest grade that is still a literal match. Confidence is cut to `7 // 10`.
    VERIFIED_FUZZY = "verified_fuzzy"
    #: The quote is not in the source at all. The model invented the sentence it claims to cite.
    UNVERIFIED = "unverified"
    #: The offsets could not describe a region of this text — past its end, or inverted. The
    #: span was never resolvable, which for policy purposes is the same fact as UNVERIFIED.
    INVALID_BOUNDS = "invalid_bounds"


#: Strongest first. A claim's SURVIVING confidence is set by its best receipt — one verbatim
#: quote substantiates the claim, and a weaker literal match beside it is an additional receipt
#: rather than evidence against it. That is the whole of what "best" decides. A receipt that
#: resolved to NOTHING is a different animal and is priced separately, once each, by
#: `_UNVERIFIED_FACTOR`: see `_grade_claim`.
_STRENGTH: tuple[SpanVerdict, ...] = (
    SpanVerdict.VERIFIED,
    SpanVerdict.VERIFIED_WHITESPACE,
    SpanVerdict.VERIFIED_RELOCATED,
    SpanVerdict.VERIFIED_FUZZY,
)

#: `(numerator, denominator)` per resolved grade, exactly as ALG-08 states them. Integer
#: division, so the penalty always rounds against the claim — a validator that rounded up would
#: hand back confidence it just decided was not earned.
_CONFIDENCE_FACTOR: dict[SpanVerdict, tuple[int, int]] = {
    SpanVerdict.VERIFIED: (1, 1),
    SpanVerdict.VERIFIED_WHITESPACE: (1, 1),
    SpanVerdict.VERIFIED_RELOCATED: (9, 10),
    SpanVerdict.VERIFIED_FUZZY: (7, 10),
}

#: The price of ONE receipt that resolved to nothing, for the claim types the policy keeps.
#: Half, and flagged — not deleted, because an unverified commitment is still an open loop
#: somebody may be waiting on, and not full, because nothing has confirmed anybody wrote it.
#:
#: PER SPAN, applied once for each fabricated receipt (D5). ALG-08 states its multipliers inside
#: `verify_span`, which grades one span, so the penalties are properties of receipts and not of
#: claims. Charging a claim once regardless of how many inventions it carries makes stapling a
#: real quote beside a false one FREE — the strongest verdict sets the grade and the invention
#: rides along at full confidence — which is the cheapest possible way to launder a fabrication
#: through the one unit built to catch it. Compounding is deliberate: the second invention is
#: not less damning than the first.
_UNVERIFIED_FACTOR: tuple[int, int] = (5, 10)


def _apply_factor(confidence_bp: int, factor: tuple[int, int]) -> int:
    """`bp * num // den`, and nothing else may ever compute a confidence in this file.

    One function so the integer-basis-point law has exactly one implementation to audit. The
    result is clamped to the 0..10000 band only from above by construction — every factor here
    is <= 1 — so a claim can never leave this module more confident than it entered.
    """
    numerator, denominator = factor
    return confidence_bp * numerator // denominator


# ---------------------------------------------------------------------------------------------
# Folded views of the source text
#
# Two comparisons in the cascade cannot be made on the raw string: NFC-vs-NFD (the same "café"
# written two ways is two different lengths) and whitespace normalization (a newline for a
# space, a run of indentation for one gap). Both are handled by folding the text ONCE into a
# comparable form that carries an index back to the original characters, so a match found in the
# folded view still yields REAL offsets into the real source. Normalizing and then reporting
# folded offsets would be the same defect as trusting the model's — a receipt pointing at
# coordinates that exist in no document anybody can open.
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _FoldedText:
    """A comparable view of some text plus the map back to it.

    `offsets[i]` is the position in the ORIGINAL string of the character `text[i]`, and
    `offsets[len(text)]` is the original length — so a match at folded `[i, i+n)` translates to
    original `[offsets[i], offsets[i + n])` with no arithmetic at the call site. Non-decreasing
    rather than strictly increasing, because one folded character can stand for several original
    ones (a composed accent, a collapsed run of spaces); that is exactly why the map exists.
    """

    text: str
    offsets: tuple[int, ...]

    def original_span(self, folded_start: int, folded_length: int) -> tuple[int, int]:
        """Folded match -> the original `[start, end)` it came from."""
        return self.offsets[folded_start], self.offsets[folded_start + folded_length]

    def anchor(self, original_offset: int) -> int:
        """Original offset -> the first folded position at or after it.

        `bisect_left` rather than a scan because `apply_verdicts` anchors once per span and a
        long document would otherwise make verification quadratic in the number of receipts.
        """
        return bisect_left(self.offsets, original_offset)


def _fold(text: str, *, collapse_whitespace: bool) -> _FoldedText:
    """Build a folded view: NFC-composed, optionally whitespace-collapsed, index preserved.

    Composition is done per CANONICAL SEGMENT — a starter character plus the combining marks
    that follow it — rather than over the whole string at once. That is what makes the index map
    possible: NFC never composes across a starter boundary, so segment-wise normalization
    produces the same text as normalizing the whole string while telling us, for each output
    character, which input characters it came from. Normalizing the whole string first would
    give a correct comparison and destroy every offset in it.

    Whitespace collapse maps a whole run to a single space anchored at the run's start, so a
    match ending on collapsed whitespace still resolves to the end of the real run.
    """
    folded: list[str] = []
    offsets: list[int] = []
    index = 0
    length = len(text)
    while index < length:
        if collapse_whitespace and text[index].isspace():
            run_start = index
            while index < length and text[index].isspace():
                index += 1
            folded.append(" ")
            offsets.append(run_start)
            continue
        segment_start = index
        index += 1
        while index < length and unicodedata.combining(text[index]):
            index += 1
        segment = text[segment_start:index]
        composed = unicodedata.normalize("NFC", segment)
        last = len(segment) - 1
        for position, character in enumerate(composed):
            folded.append(character)
            # A composed character stands for the whole segment; clamp so the map stays inside
            # it even in the rare case where NFC yields more characters than it consumed.
            offsets.append(segment_start + min(position, last))
    offsets.append(length)
    return _FoldedText(text="".join(folded), offsets=tuple(offsets))


@dataclass(frozen=True)
class _SourceIndex:
    """The prepared text plus its two folded views, built once and reused for every span.

    A message carries dozens of receipts and folding the source per span would re-walk the whole
    document each time. `verify_span` builds one of these for its single span (the convenient
    entry point); `apply_verdicts` builds one for the whole extraction (the hot path).
    """

    raw: str
    nfc: _FoldedText
    whitespace: _FoldedText


def _index_source(source_text: str) -> _SourceIndex:
    return _SourceIndex(raw=source_text,
                        nfc=_fold(source_text, collapse_whitespace=False),
                        whitespace=_fold(source_text, collapse_whitespace=True))


def _normalize_ws(text: str) -> str:
    """NFC-compose, collapse every whitespace run to one space, strip the ends.

    This is the `normalize_ws` of ALG-08 steps 3 and 5. Stripping is part of it: a quote that
    differs from the source only by a trailing newline is the same citation, and treating it as
    a different one would make the validator fail on the most common way an extractor copies
    text out of an email.
    """
    return " ".join(unicodedata.normalize("NFC", text).split())


def _stated_region(span: EvidenceSpan, source_text: str) -> tuple[int, int] | None:
    """The stated region, trimmed of its whitespace edges -> real `[start, end)`, or None.

    ALG-08 step 3 is written against `source[start:end]` — the region the span itself claims to
    have measured — so this is the only slice that step is allowed to look at. Trimming the ends
    is what "offsets corrected, span rewritten" means for that step: the comparison is made on
    whitespace-normalized text, which ignores the edges, so a region accepted with a leading
    newline or a trailing space must not be STORED with them, or the highlighted receipt carries
    characters the quote does not.

    None when the region is entirely whitespace, which is a region no correction can rescue.
    """
    start, end = span.start_offset, span.end_offset
    region = source_text[start:end]
    lead = len(region) - len(region.lstrip())
    trail = len(region) - len(region.rstrip())
    if lead + trail >= len(region):
        return None
    return start + lead, end - trail


def _stated_start_is_content(source_text: str, start: int) -> bool:
    """Is the character the span points AT part of the text, rather than the gap before it?

    D7's bound. `start_offset` is the one number in a span that CV-01 does not derive — the end
    is `start + len(quote)` by construction — so it is the only measurement the model actually
    made, and step 3's relaxation (below) may forgive the derived quantity without ever
    forgiving the measured one. A start sitting on whitespace the quote does not itself account
    for is a start that is WRONG, by however much; the grade for that is VERIFIED_RELOCATED.

    This is checked on the raw source and never through `_FoldedText.anchor`, which rounds an
    offset FORWARD to the next folded character: an offset landing anywhere inside a collapsed
    run resolves to the first real character after it, which would re-admit through the index
    the exact forgiveness this predicate exists to refuse.
    """
    return start < len(source_text) and not source_text[start].isspace()


def _rewrite(span: EvidenceSpan, start: int, end: int,
             source_text: str) -> EvidenceSpan | None:
    """Build the CORRECTED span: the source's own bytes at the offsets we actually found.

    `EvidenceSpan` is frozen precisely so a correction goes back through the constructor and is
    revalidated — `model_copy(update=...)` would skip the coherence check that makes the quote
    and the offsets self-describing. Returns None when the correction cannot be expressed as a
    valid span at all (a region longer than `MAX_QUOTE_CHARS`, or one that is entirely
    whitespace); the caller then reports UNVERIFIED, because a receipt we cannot render is a
    receipt a human cannot check, and claiming otherwise is the failure this module exists to
    prevent.
    """
    quote = source_text[start:end]
    if not quote.strip() or len(quote) > MAX_QUOTE_CHARS:
        return None
    # The locator travels with the correction. `page` may be stale after a move — the caller's
    # `_relocated_locator` is what re-examines it, because only that caller holds the map.
    return EvidenceSpan(source_ref=span.source_ref, quote=quote, start_offset=start,
                        end_offset=end, verified=True, page=span.page, section=span.section)


def _as_unverified(span: EvidenceSpan) -> EvidenceSpan:
    """The span the extractor sent, with a checkmark it was not entitled to REMOVED.

    D1. `EvidenceSpan.verified` is documented as "False on every span an extractor produces,
    and only the span validator may construct one with True" — but it is an ordinary field with
    an ordinary default, so the extractor whose claims this module exists to check can set it
    itself. Returning the input unchanged on a failing grade therefore let a fabricated quote
    keep a flag that V-5 reads downstream as a receipt: the verdict said UNVERIFIED, the counter
    said 1, and the only bit that actually travels with the span said "checked".

    Everything else is kept verbatim — the quote and the offsets are the record of what the
    extractor CLAIMED, which is the evidence about the extractor that U2's rate is computed
    from. Rebuilt through the constructor rather than `model_copy`, for the reason `_rewrite`
    states: the type is frozen so that a change is revalidated, not patched.

    Returns the span itself when the flag is already False, so the overwhelmingly common case
    allocates nothing and a caller comparing identity still sees the object it passed in.
    """
    if not span.verified:
        return span
    return EvidenceSpan(source_ref=span.source_ref, quote=span.quote,
                        start_offset=span.start_offset, end_offset=span.end_offset,
                        verified=False, page=span.page, section=span.section)


def _match_at(folded: _FoldedText, original_offset: int, needle: str) -> tuple[int, int] | None:
    """Does `needle` start at this original offset, in this folded view? -> original span."""
    if not needle:
        return None
    anchor = folded.anchor(original_offset)
    if not folded.text.startswith(needle, anchor):
        return None
    return folded.original_span(anchor, len(needle))


def _find_first(folded: _FoldedText, needle: str) -> tuple[int, int] | None:
    """First occurrence anywhere, in this folded view -> original span.

    First, not best, and not "the one nearest the model's guess": `str.find` makes the answer a
    property of the text rather than of the search, so the same span and the same source resolve
    to the same offsets on every replay. A quote that occurs twice is a coin flip only if
    somebody writes it as one.
    """
    if not needle:
        return None
    hit = folded.text.find(needle)
    if hit < 0:
        return None
    return folded.original_span(hit, len(needle))


def _verify(span: EvidenceSpan, index: _SourceIndex) -> tuple[SpanVerdict, EvidenceSpan]:
    """The ALG-08 cascade itself. Each step is a weaker claim than the one above it, and the
    first that holds wins — so a span is never graded lower than the truth about it."""
    source = index.raw

    # 1 · BOUNDS. `EvidenceSpan` already refuses a negative offset and an inverted range at
    # construction, so only the over-long case can reach here through a well-formed span; the
    # other two are kept because this function is the definition of the algorithm, not a
    # commentary on which of its branches the current contract happens to make unreachable.
    if (span.start_offset < 0 or span.end_offset <= span.start_offset
            or span.end_offset > len(source)):
        return SpanVerdict.INVALID_BOUNDS, _as_unverified(span)

    # 2 · EXACT. The cheap literal case first — no folding, no allocation.
    if source[span.start_offset:span.end_offset] == span.quote:
        corrected = _rewrite(span, span.start_offset, span.end_offset, source)
        if corrected is not None:
            return SpanVerdict.VERIFIED, corrected

    # 2b · EXACT, modulo Unicode composition. "café" written NFC is one character shorter than
    # the same word written NFD, so a correct quote and a correct start can still disagree about
    # the end. Anchoring at the start and re-deriving the end is what makes that a VERIFIED
    # rather than a spurious hallucination report.
    composed_quote = unicodedata.normalize("NFC", span.quote)
    hit = _match_at(index.nfc, span.start_offset, composed_quote)
    if hit is not None:
        corrected = _rewrite(span, hit[0], hit[1], source)
        if corrected is not None:
            return SpanVerdict.VERIFIED, corrected

    # 3 · WHITESPACE, at the stated position. Offsets corrected to the real region: the model
    # read the right sentence and copied it with the newlines flattened.
    #
    # 3a is ALG-08's step 3 verbatim — `normalize_ws(source[start:end]) == normalize_ws(quote)`,
    # compared on the STATED REGION and on nothing else, with the accepted region's whitespace
    # edges trimmed off before it is stored ("offsets corrected, span rewritten").
    normalized_quote = _normalize_ws(span.quote)
    region = _stated_region(span, source)
    if normalized_quote and region is not None \
            and _normalize_ws(source[span.start_offset:span.end_offset]) == normalized_quote:
        corrected = _rewrite(span, region[0], region[1], source)
        if corrected is not None:
            return SpanVerdict.VERIFIED_WHITESPACE, corrected

    # 3b · THE ONE DIVERGENCE FROM DOC 05, stated because it is deliberate, and scoped to the
    # single quantity the contract makes non-measurable (D7).
    #
    # CV-01 in contracts/evidence.py refuses any span where `len(quote) != end - start`, so the
    # stated END is not an independent measurement — it is `start + len(quote)`, derived by the
    # constructor. Whitespace normalization can only reconcile two strings of different length
    # by collapsing or expanding a run, and a region of EXACTLY the quote's length cannot
    # contain a collapsed run; 3a therefore forgives length-PRESERVING whitespace ("\n" for
    # " ") and redistribution within the window, and nothing else — while the same document's
    # ACCEPTANCE list demands "extra whitespace -> VERIFIED_WHITESPACE, offsets corrected",
    # which is a length CHANGE. A source that indents or double-spaces is the commonest thing a
    # real extractor reflows, and grading it FUZZY would price "the model reflowed the
    # whitespace" as "the model did not know where it was reading" — step 5's meaning — skipping
    # RELOCATE's 9/10 on the way. So 3b re-derives the END.
    #
    # It never re-derives the START. `_stated_start_is_content` requires the stated start to sit
    # ON the first character of the match, so the match BEGINS exactly where the model said it
    # did; a gap of any length in front of the sentence — one space or forty newlines — leaves
    # 3b skipped and the span falls to RELOCATE, which is the grade for a wrong measurement.
    # The needle is the normalized quote matched literally in a whitespace-folded view, so the
    # accepted region equals the quote modulo whitespace and never modulo a word.
    if normalized_quote and _stated_start_is_content(source, span.start_offset):
        hit = _match_at(index.whitespace, span.start_offset, normalized_quote)
        if hit is not None:
            corrected = _rewrite(span, hit[0], hit[1], source)
            if corrected is not None:
                return SpanVerdict.VERIFIED_WHITESPACE, corrected

    # 4 · RELOCATE. The words are real; the measurement was not.
    hit = _find_first(index.nfc, composed_quote)
    if hit is not None:
        corrected = _rewrite(span, hit[0], hit[1], source)
        if corrected is not None:
            return SpanVerdict.VERIFIED_RELOCATED, corrected

    # 5 · FUZZY — whitespace-normalized, anywhere. Still a literal match; never a similar one.
    hit = _find_first(index.whitespace, normalized_quote)
    if hit is not None:
        corrected = _rewrite(span, hit[0], hit[1], source)
        if corrected is not None:
            return SpanVerdict.VERIFIED_FUZZY, corrected

    # 6 · The quote is not in the source at all. The span is kept as testimony that the
    # extractor asserted it — quote and offsets verbatim — but the `verified` flag is FORCED to
    # False rather than passed through. A span that arrives pre-stamped and fails every step of
    # the cascade would otherwise leave here still wearing the checkmark this module is the only
    # thing entitled to grant, and downstream that checkmark IS the receipt.
    return SpanVerdict.UNVERIFIED, _as_unverified(span)


def verify_span(span: EvidenceSpan, source_text: str) -> tuple[SpanVerdict, EvidenceSpan]:
    """Grade ONE span against real source text and return it with its offsets corrected.

    The returned span is the one to store: on any verified grade it carries the source's bytes
    at the offsets that were actually found, with `verified=True` — the only place in the system
    allowed to set that flag, because the moment another caller can, the flag stops meaning
    "checked" and starts meaning "claimed". On UNVERIFIED and INVALID_BOUNDS the quote and the
    offsets come back verbatim and `verified` comes back FALSE — forced, not passed through
    (`_as_unverified`), because an extractor can set that field itself and a failing grade must
    take it away. The assertion is evidence about the extractor even when it is not evidence
    about the world, and it is stored as exactly that.

    Confidence is NOT adjusted here — a span carries no confidence, a claim does. `apply_verdicts`
    is what turns these verdicts into the policy.
    """
    return _verify(span, _index_source(source_text))


# ---------------------------------------------------------------------------------------------
# The drop policy (ALG-08's table) and the counters it produces
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SpanCounters:
    """What one extraction's verification actually did — the input to U2 and to the metrics row.

    A typed record rather than the `dict[str, int]` the reverse prompt sketches: these numbers
    cross a module boundary and get compared against a release threshold, and a bare dict makes
    a misspelled key a zero instead of an error. Frozen for the same reason `EvidenceSpan` is —
    a tally that can be edited after the fact is not a tally.

    Span counts are over DISTINCT spans. Four claims extracted from one sentence share one
    receipt, and counting it four times would let a single popular quote swing the monitor that
    is supposed to be watching the extractor.
    """

    verified: int = 0
    verified_whitespace: int = 0
    verified_relocated: int = 0
    verified_fuzzy: int = 0
    unverified: int = 0
    invalid_bounds: int = 0
    #: Claims removed outright by the policy: a fabricated `Money` or `ResolvedDate`.
    claims_dropped: int = 0
    #: Claims kept but PENALISED for carrying at least one receipt that resolved to nothing.
    #: Not "claims with no receipt at all": a claim citing one real sentence and one invented
    #: one is flagged too, because it is carrying a fabrication and the flag is how anybody
    #: downstream learns that without re-walking every span.
    claims_flagged: int = 0

    @property
    def total_spans(self) -> int:
        return (self.verified + self.verified_whitespace + self.verified_relocated
                + self.verified_fuzzy + self.unverified + self.invalid_bounds)

    @property
    def resolved_spans(self) -> int:
        return (self.verified + self.verified_whitespace + self.verified_relocated
                + self.verified_fuzzy)

    @property
    def failed_spans(self) -> int:
        """UNVERIFIED plus INVALID_BOUNDS. Both are spans that did not resolve, and separating
        them in the rate would let an extractor emitting garbage offsets look healthy."""
        return self.unverified + self.invalid_bounds

    @classmethod
    def from_verdicts(cls, verdicts: Iterable[SpanVerdict], *, claims_dropped: int = 0,
                      claims_flagged: int = 0) -> SpanCounters:
        """Tally a run's verdicts. The field names are the verdict values, so a new grade cannot
        be added to the enum without this failing loudly rather than silently undercounting."""
        tally = {verdict.value: 0 for verdict in SpanVerdict}
        for verdict in verdicts:
            tally[verdict.value] += 1
        return cls(claims_dropped=claims_dropped, claims_flagged=claims_flagged, **tally)


#: The ALG-08 policy table, as data. `True` means DROP the claim outright when none of its spans
#: resolved; `False` means keep it at `_UNVERIFIED_FACTOR` with its spans flagged. Money and
#: ResolvedDate are the two dropped types for one reason: they are acted on. A wrong deadline
#: produces a false chase and a wrong amount produces a wrong renewal, and neither failure is
#: recoverable by the human reading the card, who has no way to know the number was invented.
_POLICY: dict[type, bool] = {
    Money: True,
    ResolvedDate: True,
    Commitment: False,
    DecisionState: False,
    Dependency: False,
    UnclassifiedObservation: False,
    # DIVERGENCE FROM DOC 05: the policy table does not mention EntityMention, which is
    # citation-bearing and therefore cannot be "untouched" like intent or stance. It is filed
    # with the keep-and-flag family: an invented surface form at half confidence is reviewable,
    # while dropping the mention would silently delete an entity L2 is the layer that resolves.
    EntityMention: False,
}

def _policy_drops(claim_type: type) -> bool:
    """Does the policy DELETE an instance of this type that nothing substantiates?

    Raising on an unlisted type is the point. A new citation-bearing claim added to C-09 without
    a row here is a claim whose fabricated instances would be handled by whatever the default
    happened to be — and a silent default is exactly how "a wrong deadline is acted on" stops
    being enforced for the newest kind of deadline. Better a loud KeyError at the seam than a
    quiet policy hole.
    """
    try:
        return _POLICY[claim_type]
    except KeyError as exc:
        raise KeyError(
            f"{claim_type.__name__} carries evidence but has no row in the ALG-08 drop policy. "
            "Give it one explicitly: defaulting would silently decide whether a fabricated "
            "instance is deleted or merely halved.") from exc


def _rebuild(claim: Any, **changes: Any) -> Any:
    """Reconstruct a claim through its own constructor so every validator runs again.

    `model_copy(update=...)` is the tempting one-liner and it skips validation, which would let
    this module write a confidence outside the basis-point band or an empty evidence list into a
    contract whose whole job is to refuse both. Rebuilding costs one dump and buys the guarantee
    that whatever leaves here is a valid claim.
    """
    return type(claim)(**{**claim.model_dump(), **changes})


@dataclass(frozen=True)
class _ClaimGrade:
    """How one claim's receipts came out: the corrected spans, the best grade, the failure count.

    All three are needed to price the claim, and the third is the one D5 was missing. `best`
    alone answers "is this claim substantiated at all"; it cannot answer "how much of what this
    claim cites is invented", and a policy that only asks the first question charges nothing for
    the second.
    """

    #: Every span the claim carried, corrected — INCLUDING the ones that failed. Deleting the
    #: fabricated ones would leave a claim that looks fully substantiated and erase the only
    #: record that the extractor invented them.
    spans: list[EvidenceSpan]
    #: The strongest grade any receipt reached, or None when not one of them resolved.
    best: SpanVerdict | None
    #: How many receipts resolved to nothing — UNVERIFIED plus INVALID_BOUNDS, which are two
    #: diagnoses of the same fact: this claim cites text nobody can open.
    unresolved: int


def _grade_claim(evidence: list[EvidenceSpan],
                 graded: dict[EvidenceSpan, tuple[SpanVerdict, EvidenceSpan]],
                 ) -> _ClaimGrade:
    """Grade one claim's whole receipt list. See `_ClaimGrade` for what comes back."""
    corrected: list[EvidenceSpan] = []
    best: SpanVerdict | None = None
    unresolved = 0
    for span in evidence:
        verdict, rewritten = graded[span]
        corrected.append(rewritten)
        if verdict not in _CONFIDENCE_FACTOR:
            unresolved += 1
        elif best is None or _STRENGTH.index(verdict) < _STRENGTH.index(best):
            best = verdict
    return _ClaimGrade(spans=corrected, best=best, unresolved=unresolved)


def _money_is_grounded(amount: Money, index: _SourceIndex) -> bool:
    """Is the literal a human wrote actually in the source?

    GAP FLAG (contract): `Money` is the one claim type the policy names that carries no
    `evidence` list — C-02 has `as_written` and nothing else — so there is no span to grade. Its
    receipt is therefore `as_written` itself, which C-02 defines as the source's own bytes:
    "$84,000" is verified by finding "$84,000" in the message. Same rules as everywhere else in
    this file — exact, then whitespace-normalized, and never anything looser — so a normalizer
    that reported an amount the message never contained loses it, which is the outcome the drop
    policy asks for.

    This is HALF the check. Groundedness asks whether anybody wrote the literal; it cannot see a
    wrong digit, because a wrong digit leaves the literal untouched — see
    `_money_contradicts_its_literal`.
    """
    if amount.as_written in index.raw:
        return True
    literal = _normalize_ws(amount.as_written)
    return bool(literal) and literal in index.whitespace.text


def _money_contradicts_its_literal(amount: Money, locale: str | None) -> bool:
    """Do the integer and the string on this `Money` disagree about how much money it is?

    D4, and it is the group's own headline fault. "Total annual commitment of $8.4K under the
    renewal" grounds perfectly — "$8.4K" is right there in the message — while the integer beside
    it says 8_400_000 minor units, which is $84,000. Upper layers compare integers and render
    strings, so the card reads "$8.4K", the renewal forecast reads $84,000, and the two disagree
    by 10x with no seam that can notice. Groundedness cannot see it: the literal is real. The two
    halves of the claim have to be checked against EACH OTHER.

    ALG-10 (`money.py`) is pure and importable, so the cross-check costs one call. The
    connection's declared locale is threaded in for the reason ALG-10 needs it at all: "$84,000"
    is 84000 in en-US and ambiguous everywhere else, and re-deriving the number under a different
    convention than the normalizer used would manufacture disagreements rather than find them.

    **REFUSING IS NOT CONTRADICTING, and the distinction decides whether money survives.**
    `parse_money` returns None for a dozen reasons that all mean "I will not guess" — a range,
    a trailing word ("$84,000 annual"), an ambiguous separator with no locale, a bare number.
    None of those is evidence that the extractor's integer is wrong; they are evidence that this
    string is outside ALG-10's grammar. Dropping on refusal would delete every amount ALG-10
    happens not to read, which on a connection with no declared locale is most of them, and the
    deletion would be invisible — the card simply would not mention the number the message did.
    So a refusal returns False here and the amount is kept on its groundedness alone.

    Currency is compared only when ALG-10 names one. An ambiguous symbol resolves to `UNKNOWN`
    by design (ALG-10 step 1 forbids defaulting to USD), and `UNKNOWN` is the absence of an
    opinion, not a contradiction of the extractor's — which may have been read from thread
    context this function cannot see.
    """
    parsed = parse_money(amount.as_written, locale=locale)
    if parsed is None:
        return False
    if parsed.minor_units != amount.minor_units:
        return True
    return parsed.currency != "UNKNOWN" and parsed.currency != amount.currency


def _kept(claims: list[Any], resolve: Any) -> list[Any]:
    """Run the policy over one claim list and keep what survives it."""
    return [resolved for resolved in (resolve(claim) for claim in claims) if resolved is not None]


def _relocated_locator(original: EvidenceSpan, resolved: EvidenceSpan, prepared: Any,
                       page_map: Any, section: str | None) -> EvidenceSpan:
    """The graded span, with its page recomputed if — and only if — its offsets moved.

    A relocation is a statement that the quote is somewhere else in the document, and "somewhere
    else" can be a different page. The three ways this can go, and only the first is free:

    * offsets unchanged  -> the extractor's page is still right. Returned untouched, which is the
      overwhelmingly common case and allocates nothing.
    * offsets moved, map available -> the page is looked up at the NEW position, through the same
      prepared -> source translation the extractor used.
    * offsets moved, no map -> the page is DROPPED. A page number that survives a relocation
      unexamined is a confident citation pointing at the wrong page, which is worse than a
      citation that admits it does not know.

    `section` is a property of the whole event and does not move with an offset, so it is
    preserved rather than recomputed.
    """
    if resolved.start_offset == original.start_offset or resolved.page is None:
        return resolved
    source_start = None
    if prepared is not None:
        try:
            source_start = prepared.to_source_offset(resolved.start_offset)
        except Exception:      # noqa: BLE001 — an unusable map costs a page, never a claim
            source_start = None
    page = None if (page_map is None or source_start is None) else page_map.page_at(source_start)
    if page == resolved.page:
        return resolved
    return EvidenceSpan(source_ref=resolved.source_ref, quote=resolved.quote,
                        start_offset=resolved.start_offset, end_offset=resolved.end_offset,
                        verified=resolved.verified, page=page,
                        section=section if section is not None else resolved.section)


def apply_verdicts(result: ExtractionResult, source_text: str, *,
                   locale: str | None = None, prepared: Any = None,
                   page_map: Any = None,
                   section: str | None = None) -> tuple[ExtractionResult, SpanCounters]:
    """Verify every span in an extraction and apply the per-claim-type policy to the whole thing.

    Returns a NEW `ExtractionResult` — the input is left alone, because the unverified original
    is what a replay and an audit need to see. In the returned one:

    * every span, on a claim or in `all_evidence`, carries corrected offsets and an honest
      `verified` flag;
    * an `amount` whose `as_written` is nowhere in the source is GONE, and so is one whose
      integer contradicts its own literal under `locale` — the $84K/$8.4K fault, which
      groundedness alone cannot see because the literal in that fault is genuine;
    * a `dates_mentioned` entry none of whose spans resolved is GONE;
    * a `Commitment` whose `due` was fabricated keeps the commitment and loses the date — which
      the contract reads as "no date was stated", so it is tracked as an open loop and never
      escalated as a missed one. That is the point: an invented deadline must not be able to
      produce a false overdue, and a false chase is how a founder stops reading our nudges;
    * every other citation-bearing claim keeps its place with `confidence_bp` scaled by its
      strongest surviving receipt AND halved once for every receipt that resolved to nothing,
      so a real quote stapled beside an invention does not buy the invention a free ride.

    `all_evidence` keeps its failures deliberately. It is the extractor's ledger, not the claim's
    receipt list, and pruning it would hide exactly the trend U2 is monitoring.

    `page_map`, `prepared` and `section` are L1.3.4-U5's locator, and they are here for ONE
    reason: this module RELOCATES quotes. A span whose offsets were wrong and whose words are
    real is rewritten at its true position, and a rewritten span may have crossed a page break —
    so the page has to be recomputed against the map rather than carried, and carrying it is the
    one option that produces a confident citation naming the wrong page. Omitting all three is
    supported and means "no locator available": pages are then left exactly as the extractor
    attached them, which is right for every caller that is not re-positioning anything.

    `locale` is the CONNECTION's declared locale — the same one the normalizer was given, and
    None when the connection declares none. It is used for one thing: re-deriving an amount from
    its own `as_written` to check the extractor's integer against it. Passing a different locale
    than the normalizer used would manufacture disagreements instead of finding them, and
    passing None simply means most amounts are un-rederivable and survive on groundedness alone
    (see `_money_contradicts_its_literal`). No clock, no I/O, no model: it is a string.
    """
    index = _index_source(source_text)
    graded: dict[EvidenceSpan, tuple[SpanVerdict, EvidenceSpan]] = {}

    def grade(span: EvidenceSpan) -> tuple[SpanVerdict, EvidenceSpan]:
        # Frozen and hashable, so one receipt shared by four claims is verified once and — more
        # importantly — counted once.
        cached = graded.get(span)
        if cached is None:
            verdict, resolved = _verify(span, index)
            cached = (verdict, _relocated_locator(span, resolved, prepared, page_map, section))
            graded[span] = cached
        return cached

    for span in result.evidence_from_claims():
        grade(span)
    for span in result.all_evidence:
        grade(span)

    dropped = 0
    flagged = 0

    def resolve(claim: Any) -> Any:
        """Apply the ALG-08 policy to one citation-bearing claim. Returns None when it is
        dropped — which only ever happens to a claim NO span of which resolved, and only for the
        types the table marks."""
        nonlocal dropped, flagged
        grade = _grade_claim(claim.evidence, graded)
        if grade.best is None and _policy_drops(type(claim)):
            dropped += 1
            return None
        changes: dict[str, Any] = {"evidence": grade.spans}
        if "confidence_bp" in type(claim).model_fields:
            # `ResolvedDate` is the one kept type with no confidence to carry doubt in, which is
            # precisely why the table drops it instead of downgrading it.
            confidence_bp = claim.confidence_bp
            if grade.best is not None:
                confidence_bp = _apply_factor(confidence_bp, _CONFIDENCE_FACTOR[grade.best])
            # D5 · once per fabricated receipt, not once per claim. The multipliers ALG-08
            # states live inside `verify_span`, which grades ONE span, so the penalty is a
            # property of a receipt. Charging it per claim made a claim with one real quote and
            # one invention cost exactly the same as a fully substantiated one, which prices
            # laundering an invention at zero.
            for _ in range(grade.unresolved):
                confidence_bp = _apply_factor(confidence_bp, _UNVERIFIED_FACTOR)
            changes["confidence_bp"] = confidence_bp
        if grade.unresolved:
            flagged += 1
        return _rebuild(claim, **changes)

    amounts: list[Money] = []
    for amount in result.amounts:
        # `Money` is the one claim type with no `evidence` list, so it is graded on its literal
        # rather than on a span — see `_money_is_grounded` — and then on whether that literal and
        # its own integer agree — see `_money_contradicts_its_literal`. Two checks because a
        # fabricated amount and a MIS-READ amount are different faults: the first invents a
        # string nobody wrote, the second keeps a real string beside a wrong number. The Globe
        # fault is the second one, and the first check is blind to it. The policy row still
        # decides what happens to either.
        unsubstantiated = (not _money_is_grounded(amount, index)
                           or _money_contradicts_its_literal(amount, locale))
        if unsubstantiated and _policy_drops(Money):
            dropped += 1
            continue
        amounts.append(amount)

    dates: list[ResolvedDate] = [kept for kept in
                                 (resolve(date) for date in result.dates_mentioned)
                                 if kept is not None]

    commitments: list[Commitment] = []
    for commitment in result.commitments:
        rebuilt = resolve(commitment)
        if rebuilt is None:
            continue
        if rebuilt.due is not None:
            rebuilt = _rebuild(rebuilt, due=resolve(rebuilt.due))
        commitments.append(rebuilt)

    verified_result = ExtractionResult(**{
        **result.model_dump(),
        "entity_mentions": _kept(result.entity_mentions, resolve),
        "amounts": amounts,
        "dates_mentioned": dates,
        "commitments": commitments,
        "decision_states": _kept(result.decision_states, resolve),
        "dependencies": _kept(result.dependencies, resolve),
        "unclassified_observations": _kept(result.unclassified_observations, resolve),
        "all_evidence": [graded[span][1] for span in result.all_evidence],
    })
    counters = SpanCounters.from_verdicts((verdict for verdict, _ in graded.values()),
                                          claims_dropped=dropped, claims_flagged=flagged)
    return verified_result, counters


# ---------------------------------------------------------------------------------------------
# L1.5.1-U2 · the unverified-rate monitor
# ---------------------------------------------------------------------------------------------


def unverified_rate_bp(counters: SpanCounters) -> int:
    """The share of distinct spans that failed to resolve, in integer basis points (0..10000).

    This is the number that makes a silently-degrading extractor visible. A prompt edit that
    breaks citation behaviour does not raise, does not log an error and does not fail a test —
    it produces slightly weaker signals, for everyone, until somebody happens to notice. The
    rate is what turns that into an observable step change on a date.

    Integer division, so the rate is truncated and never overstated; a comparison between two
    prompt versions is like-for-like because both were computed the same way. Zero spans reports
    0, which is why the caller must read it beside `total_spans`: an extraction that cited
    nothing is not an extraction that cited well, and the two are only distinguishable together.

    Dimensioning by org and prompt version belongs to the metrics writer — this file may not
    touch storage, and the counters carry no identity for the same reason.
    """
    total = counters.total_spans
    if total == 0:
        return 0
    return counters.failed_spans * BP_FULL // total


def rate_regression_blocks_release(previous_bp: int, candidate_bp: int) -> bool:
    """L1.5.1-U2's release gate: a candidate prompt whose unverified rate is more than 5
    percentage points worse than the incumbent's does not ship.

    Strictly greater, so a candidate landing exactly on the threshold passes — the doc says
    "exceeds by more than", and a gate that also blocked the boundary would fail a prompt that
    met the stated bar. An IMPROVEMENT never blocks, however large: the gate exists to catch
    citation behaviour falling apart, not to freeze the prompt.
    """
    return candidate_bp - previous_bp > MAX_RATE_REGRESSION_BP


__all__ = ["BP_FULL", "MAX_RATE_REGRESSION_BP", "SpanCounters", "SpanVerdict", "apply_verdicts",
           "rate_regression_blocks_release", "unverified_rate_bp", "verify_span"]
