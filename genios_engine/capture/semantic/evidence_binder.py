"""L1.4.6 · the evidence binder — the unit that makes the rest of Layer 1 honest.

Two jobs, both about the same thing: a claim's receipt must point at text a human can open.

**U1 · span attachment enforcement** (`bind_evidence`). Rule 04: *confidence without receipts
is a guess.* Every claim leaving S2 carries at least one `EvidenceSpan`, and this is the pass
that guarantees it. Three outcomes, exactly as doc-04 writes them, and the third is the one a
lenient implementation quietly loses:

    claim already cites something          -> kept, untouched
    cites nothing, its words ARE in the text -> span SYNTHESIZED, confidence * 7 // 10
    cites nothing, its words are nowhere   -> DROPPED, `no_evidence` counter incremented

Dropping is correct. A claim nobody can point at is not an extraction, it is an assertion —
and the counter is what turns a prompt regression from "signals got a bit worse for everyone"
into an observable step change on a date (`no_evidence_rate_bp`, `rate_blocks_prompt_release`).

**U2 · offset alignment** (`align_span`). The model never sees the stored text. It sees a
PII-masked, possibly chunked VIEW of it, and the offsets it returns are measured against that
view. Handed to the store unchanged they point at the wrong sentence — off by the length of
every mask token above them, plus the chunk's own start. `prepared_content` has carried the
map that fixes this since the preprocessor was written and, until this unit, had no reader.

THREE COORDINATE SYSTEMS, and confusing two of them is the whole class of bug this unit exists
to remove:

    view      what the model was shown: one chunk of the masked text (or all of it)
    prepared  `PreparedContent.clean_text` — masked, whole message. EvidenceSpan's own frame
    source    the original untouched text, where the PII still is

`prepared = view + chunk.start_offset` is U2's stated rule ("for chunked documents, add
`chunk_start` to every offset"), and `prepared -> source` runs through `offset_map`, the
segment list `capture/preprocess/pii.mask` builds. That map is REUSED, never re-derived:
`PreparedContent.to_source_offset` is its reader for an inclusive start, and `_source_end` here
is the reader for an exclusive end that the contract never grew — the one direction the
existing map could not answer, because a mask has no interior to be halfway through.

**A mask is atomic.** A quote that begins inside `[AADHAAR]` corresponds, in the original, to
the whole Aadhaar number: there is no source character at "the third character of the token".
So a source region EXPANDS to mask boundaries, and `AlignedSpan.crosses_mask` says when that
happened. Without the flag a caller comparing `len(quote)` to `source_end - source_start` would
read a correct expansion as an off-by-N.

**Frames are named by the `source_ref`, not chosen here.** C-01 documents exactly two shapes —
`prepared_content:<event_id>`, offsets into `clean_text`, and `chunk:<doc_id>:<n>`, offsets into
chunk n — so the emitted span is measured in whichever one the caller names, and an unrecognised
shape raises rather than defaulting. A span whose offsets are in one frame and whose `source_ref`
names another is the exact receipt-pointing-at-nothing this unit was built to prevent, and it is
invisible: both numbers look plausible.

PRECONDITION FOR CHUNKED INPUT — mask first, then chunk. `chunk.start_offset` must be an offset
into `clean_text`, because that is the only ordering in which adding it yields a prepared offset.
Chunking the raw text and masking the chunks would give every chunk after the first a start that
means nothing in either frame. `align_span` checks it (the chunk's text must be the prepared
text's own bytes at the chunk's offsets) rather than trusting it, for the reason
`capture/documents/chunking.py` states about rebuilt chunk text: a chunk that is a NEW string
makes a correctly-read quote look like a hallucination.

No clock, no DB, no model. The one LLM in this package is the extractor; the binder only ever
reads the text the model was shown and the text it was shown a view OF.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field as dataclass_field

from genios_engine.capture.documents.chunking import Chunk
from genios_engine.capture.validate.spans import BP_FULL, SpanVerdict, verify_span
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.validators import require_bp, require_text

#: C-01's two literal `source_ref` shapes, as prefixes. Kept as constants because
#: `align_span` dispatches the emitted span's coordinate frame on them, and a frame chosen by a
#: string literal repeated at three call sites is a frame that drifts.
PREPARED_FRAME_PREFIX = "prepared_content:"
CHUNK_FRAME_PREFIX = "chunk:"

#: The synthesis penalty, as doc-04 writes it (`confidence_bp *= 0.7`) in the only arithmetic
#: this codebase permits for a score: `bp * 7 // 10`. Integer division rounds AGAINST the claim,
#: which is the right direction for a receipt we had to find ourselves — the model asserted
#: something and then could not say where it read it, and rounding up would hand back
#: confidence that was just decided not to have been earned. A float here would be the same
#: defect as a ratio anywhere else in Layer 1: `int(700 * 0.7)` is 489, not 490.
SYNTHESIS_FACTOR: tuple[int, int] = (7, 10)

#: U1's monitored gate: *"a sustained rise above 5% blocks the next prompt version."* 5% is
#: 500 bp, stated once so the two spellings cannot drift — the same reason
#: `capture/validate/spans.py` states `MAX_RATE_REGRESSION_BP` exactly once.
MAX_NO_EVIDENCE_RATE_BP = 500

#: The verdicts that count as "the claim's words are in the text". All four are LITERAL matches
#: — ALG-08 has no similarity step — so accepting the weaker three is not accepting a paraphrase;
#: it is accepting that the model reflowed whitespace, or could not say where it read. The other
#: two verdicts, UNVERIFIED and INVALID_BOUNDS, are the drop case.
#:
#: Listed positively rather than as "everything except the two failures": a seventh verdict added
#: to the cascade would then default to RECOVERY, which is the wrong way for a default to fail in
#: the unit that decides whether an unsubstantiated claim survives. `test_evidence_binder.py`
#: asserts this set plus the two failures covers the enum, so a new grade breaks a test instead
#: of quietly changing the policy.
_RECOVERED: frozenset[SpanVerdict] = frozenset({
    SpanVerdict.VERIFIED,
    SpanVerdict.VERIFIED_WHITESPACE,
    SpanVerdict.VERIFIED_RELOCATED,
    SpanVerdict.VERIFIED_FUZZY,
})


def _reduced(confidence_bp: int) -> int:
    """The synthesis penalty, in one place, so the integer-bp law has one implementation here."""
    numerator, denominator = SYNTHESIS_FACTOR
    return confidence_bp * numerator // denominator


# ---------------------------------------------------------------------------------------------
# U2 · offset alignment
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelSpan:
    """One citation as the MODEL stated it: its words, and where in the view it says it read them.

    Deliberately not an `EvidenceSpan`. C-01's constructor enforces `len(quote) == end - start`,
    and raw model output routinely violates it — a model that counted UTF-16 units, or that
    reported the end of the sentence rather than the end of the quote, would crash the pipeline
    at parse time instead of being aligned and then graded. This type holds what was said; the
    `EvidenceSpan` is what `align_span` produces once the numbers have been made to mean
    something.

    `view_end` is therefore carried and NOT trusted as a measurement: ALG-08's own reasoning
    (D7) is that the end is `start + len(quote)` by construction, so the quote is the testimony
    and the start is the single number the model actually measured. `view_end` survives only to
    catch an inverted range, which is evidence the output is garbage rather than merely
    mis-measured.
    """

    quote: str
    view_start: int
    view_end: int


@dataclass(frozen=True)
class AlignedSpan:
    """A model citation translated into every frame anybody downstream asks it about.

    `span` is the receipt to store — measured in the frame its own `source_ref` names, with
    `verified` False, because the extractor seam may never stamp a span checked (C-01, and
    ALG-08's `_as_unverified` exists because an extractor tried).

    `prepared_*` and `source_*` are the same region in the other two frames. Both are carried
    rather than recomputed by the caller: the prepared pair is what ALG-08 verifies against, the
    source pair is what "click the fact, show me the untouched sentence" opens, and a caller
    re-deriving either would be the second offset map this unit exists to avoid.
    """

    span: EvidenceSpan
    prepared_start: int
    prepared_end: int
    source_start: int
    source_end: int
    #: The quote touched masked PII, so the source region is WIDER than the quote — it was
    #: expanded to the mask's own boundaries. Without this flag, `source_end - source_start !=
    #: len(quote)` reads as an off-by-N in a unit whose whole job is offsets.
    crosses_mask: bool = False


def _source_end(prepared: PreparedContent, prep_end: int) -> int:
    """Exclusive prepared offset -> exclusive source offset, through the SAME `offset_map`.

    `PreparedContent.to_source_offset` answers this for an inclusive start and cannot answer it
    for an exclusive end: it locates the segment CONTAINING an offset, and an end sits one past
    the last character it covers — at a segment boundary it would resolve into the NEXT segment
    and return that segment's start, silently truncating the region to nothing.

    So the segment is found for `prep_end - 1`, the last character actually inside the region,
    and the end is then read off that segment: a masked segment yields its `src_end` (a mask is
    atomic — the original has no character at "halfway through the token"), a passthrough yields
    the 1:1 translation. An empty map means nothing was masked, so prepared and source are the
    same string and the offset is already correct.
    """
    if not prepared.offset_map:
        return prep_end
    last_char = prep_end - 1
    for segment in prepared.offset_map:
        if segment.prep_start <= last_char < segment.prep_end:
            if segment.masked:
                return segment.src_end
            return segment.src_start + (prep_end - segment.prep_start)
    return prepared.offset_map[-1].src_end


def _touches_mask(prepared: PreparedContent, prep_start: int, prep_end: int) -> bool:
    """Does `[prep_start, prep_end)` overlap any masked segment of the prepared text?"""
    return any(segment.masked and segment.prep_start < prep_end and prep_start < segment.prep_end
               for segment in prepared.offset_map)


def _emitted_offsets(source_ref: str, *, view_start: int, prepared_start: int,
                     length: int, chunk: Chunk | None) -> tuple[int, int]:
    """The frame the `source_ref` names, resolved to the offsets the stored span carries."""
    if source_ref.startswith(CHUNK_FRAME_PREFIX):
        if chunk is None:
            raise ValueError(
                f"source_ref {source_ref!r} names a chunk frame but no chunk was given; the "
                "offsets would be measured against a document the reference does not name")
        return view_start, view_start + length
    if source_ref.startswith(PREPARED_FRAME_PREFIX):
        return prepared_start, prepared_start + length
    raise ValueError(
        f"source_ref {source_ref!r} names no known frame; C-01 defines exactly "
        f"{PREPARED_FRAME_PREFIX!r} and {CHUNK_FRAME_PREFIX!r}, and a span whose offsets are in "
        "one frame while its reference names another points at the wrong sentence invisibly")


def align_span(model_span: ModelSpan, prepared: PreparedContent, *, source_ref: str,
               chunk: Chunk | None = None) -> AlignedSpan | None:
    """L1.4.6-U2 · one model citation -> a span whose offsets mean something in the store.

    Returns None when the citation cannot describe a region of the text at all — a negative or
    inverted range, an empty or whitespace-only quote, a quote longer than `MAX_QUOTE_CHARS`, or
    one running past the end of the view or of the prepared text. None is not a verdict on
    whether the model read the quote correctly: that is ALG-08's question, asked later against
    the aligned offsets. It only means there is no region to ask about, and emitting a span
    anyway would put a receipt into the store that no source text can resolve.

    `chunk` is the piece of `prepared.clean_text` the model was shown; omit it when the model
    was shown the whole prepared text. Masking happens BEFORE chunking (see the module
    docstring), and that precondition is checked, not assumed: a chunk whose text is not the
    prepared text's own bytes at the chunk's offsets raises, because every offset derived from
    it would be wrong by an amount nothing downstream could detect.

    Raises on a caller mistake (an unknown `source_ref` shape, a chunk frame with no chunk, a
    chunk that does not belong to this prepared content) and returns None on bad MODEL output.
    The split is deliberate: the first is a bug in code that must be fixed, the second is a
    Tuesday.
    """
    require_text(source_ref, "source_ref")
    quote = model_span.quote
    if not quote.strip():
        return None
    if len(quote) > MAX_QUOTE_CHARS:
        return None
    if model_span.view_start < 0 or model_span.view_end <= model_span.view_start:
        return None

    chunk_start = 0
    if chunk is not None:
        chunk_start = chunk.start_offset
        if prepared.clean_text[chunk.start_offset:chunk.end_offset] != chunk.text:
            raise ValueError(
                "chunk.text is not the prepared text at the chunk's own offsets — the document "
                "was chunked before it was masked, or from a different string; every offset "
                "derived from it would be wrong by an undetectable amount")
        if model_span.view_start + len(quote) > len(chunk.text):
            return None

    prepared_start = chunk_start + model_span.view_start
    prepared_end = prepared_start + len(quote)
    if prepared_end > len(prepared.clean_text):
        return None

    start_offset, end_offset = _emitted_offsets(source_ref, view_start=model_span.view_start,
                                                prepared_start=prepared_start, length=len(quote),
                                                chunk=chunk)
    return AlignedSpan(
        span=EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start_offset,
                          end_offset=end_offset, verified=False),
        prepared_start=prepared_start,
        prepared_end=prepared_end,
        source_start=prepared.to_source_offset(prepared_start),
        source_end=_source_end(prepared, prepared_end),
        crosses_mask=_touches_mask(prepared, prepared_start, prepared_end),
    )


# ---------------------------------------------------------------------------------------------
# U1 · span attachment enforcement
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimDraft:
    """One claim-bearing field of the parsed model output, BEFORE it becomes a typed claim.

    This type exists because the typed claims cannot hold the state U1 is built to fix: every
    citation-bearing contract in C-09 refuses an empty `evidence` list at construction, so a
    claim with no receipt has no legal typed form and the enforcement pass must therefore run
    between parsing and typing. That ordering is doc-04's own — *"post-parse pass over the model
    output"* — and it is what makes the drop cheap: one malformed draft is discarded instead of
    a whole `ExtractionResult` failing to build.

    `claim_text` is the needle. It is the model's own words for what it claims — a commitment's
    action, an entity's surface form, an observation's description — and recovery searches the
    prepared text for exactly it. Empty is allowed and means unrecoverable: a claim that cannot
    even say what it asserts cannot be pointed at.
    """

    #: Which `ExtractionResult` field this draft will become — "commitments", "entity_mentions".
    #: Carried so the counters and the dropped-claim log name the lane that regressed rather
    #: than reporting a total that could be any of six prompts.
    field: str
    claim_text: str
    confidence_bp: int
    evidence: tuple[EvidenceSpan, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.field, "claim draft field")
        require_bp(self.confidence_bp, "claim draft confidence_bp")
        if not isinstance(self.claim_text, str):
            raise TypeError("claim_text must be a string — it is the needle recovery searches for")
        if isinstance(self.evidence, (str, bytes)) or not isinstance(self.evidence, Sequence):
            raise TypeError("evidence must be a sequence of EvidenceSpan")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        for span in self.evidence:
            if not isinstance(span, EvidenceSpan):
                raise TypeError("evidence must contain EvidenceSpan values")


@dataclass(frozen=True)
class BoundClaim:
    """A draft that survived U1, with a receipt it is guaranteed to have.

    `evidence` is non-empty by construction — that guarantee is the unit's entire output — and
    `synthesized` says whether the receipt came from the model or from the binder finding the
    words itself. The flag is not cosmetic: a synthesized receipt has already been paid for in
    confidence, and a caller that re-applied the penalty would charge the same claim twice.
    """

    draft: ClaimDraft
    evidence: tuple[EvidenceSpan, ...]
    confidence_bp: int
    synthesized: bool

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("a bound claim with no evidence is the state U1 exists to remove")


@dataclass(frozen=True)
class BinderCounters:
    """What one binding pass did — U1's monitored metric and its denominator.

    `no_evidence` is the counter doc-04 names, and it counts DROPS: claims that cited nothing and
    whose words were nowhere in the text. Recoveries are counted separately as `synthesized`,
    because the two say opposite things about a prompt. A rise in synthesis means the model is
    quoting without offsets — annoying, priced, still grounded. A rise in `no_evidence` means the
    model is asserting things the message does not say, and that is the one that blocks a
    release.

    `claims_in` is carried so the rate has a denominator that survives the drops: computing it
    from the survivors would make a prompt that dropped everything look like it dropped nothing.
    """

    claims_in: int = 0
    carried_own_evidence: int = 0
    synthesized: int = 0
    no_evidence: int = 0

    @property
    def bound(self) -> int:
        """Claims that left with a receipt, by either route."""
        return self.carried_own_evidence + self.synthesized


@dataclass(frozen=True)
class BindOutcome:
    """The bound claims and the tally, together, because neither is readable alone.

    An empty `claims` list is either "the model produced nothing" or "the model produced six
    fabrications", and only the counters tell you which. Returning them separately would let a
    caller keep the first and drop the second, which is how a mass-drop regression becomes
    invisible.
    """

    claims: tuple[BoundClaim, ...] = ()
    counters: BinderCounters = dataclass_field(default_factory=BinderCounters)


def _synthesize(claim_text: str, prepared_text: str, source_ref: str) -> EvidenceSpan | None:
    """Find a claim's own words in the text and build the receipt it failed to bring.

    ALG-08's `verify_span` does the locating. That is reuse, not a shortcut: it is this
    codebase's single implementation of "where in this text are these words", it already handles
    NFC composition and whitespace reflow, and — the point — the offsets it returns are computed
    the same way the validator that will re-check this span computes them. A second locator here
    would eventually disagree with it, and a binder that synthesizes spans its own validator then
    grades UNVERIFIED is worse than one that synthesizes none.

    The candidate is anchored at 0 so the cascade's steps 4 and 5 do the searching; the anchor is
    a probe, not a claim about position, and whatever offsets come back are the ones stored.

    Two shapes are refused before the search. A whitespace-only needle cannot be a receipt
    (ALG-08 refuses to rewrite a span onto blank text). A needle longer than `MAX_QUOTE_CHARS` is
    truncated rather than dropped: a prefix matches wherever the whole string does, so the search
    is no less exact, and the receipt then quotes the first two sentences of the claim instead of
    a wall of text nobody checks — which is what the cap is for.

    `verified` is forced False on the way out. `verify_span` returns its corrected span stamped
    True, and that stamp belongs to L1.5.1 alone: the binder runs at the extractor seam, so a
    span leaving here wearing a checkmark would be the extractor grading its own homework.
    """
    needle = claim_text.strip()
    if not needle:
        return None
    if len(needle) > MAX_QUOTE_CHARS:
        needle = needle[:MAX_QUOTE_CHARS]
    candidate = EvidenceSpan(source_ref=source_ref, quote=needle, start_offset=0,
                             end_offset=len(needle), verified=False)
    verdict, corrected = verify_span(candidate, prepared_text)
    if verdict not in _RECOVERED:
        return None
    return EvidenceSpan(source_ref=source_ref, quote=corrected.quote,
                        start_offset=corrected.start_offset, end_offset=corrected.end_offset,
                        verified=False)


def _require_same_frame(draft: ClaimDraft, source_ref: str) -> None:
    """Every receipt a draft brought is measured in the frame this binding pass names.

    Names the claim's own field as well as the two references, because the two facts a reader
    needs are which lane produced it — the counters and the dropped-claim log are per-field for
    the same reason — and which two frames disagreed. "source_ref mismatch" alone sends whoever
    reads it back to the extractor to work out which of the six prompts was involved.
    """
    for span in draft.evidence:
        if span.source_ref != source_ref:
            raise ValueError(
                f"{draft.field}: a carried receipt names {span.source_ref!r} but this binding "
                f"pass is measured against {source_ref!r}. Its offsets are into a different "
                "document, so the receipt points at the wrong sentence — and does it invisibly, "
                "because both numbers look plausible. Bind each frame's claims in its own pass.")


def bind_evidence(drafts: Iterable[ClaimDraft], *, prepared_text: str,
                  source_ref: str) -> BindOutcome:
    """L1.4.6-U1 · every claim leaves with a receipt, or it does not leave.

    The three outcomes doc-04 states, in order of preference:

    * the draft already cites something — kept verbatim, confidence untouched. The binder does
      not second-guess a receipt; grading one is ALG-08's job and doing it here would price the
      same span twice;
    * it cites nothing but its words ARE in `prepared_text` — a span is synthesized at the
      offsets the words were found at, and confidence drops to `bp * 7 // 10`. The claim is
      real and the model was sloppy about saying where it read it, which is worth less than a
      claim that brought its own receipt and much more than one nothing substantiates;
    * it cites nothing and its words are nowhere — DROPPED, `no_evidence` incremented.

    `prepared_text` must be the text the emitted spans' offsets are measured against — the
    prepared `clean_text` for a `prepared_content:` reference, the chunk's own text for a
    `chunk:` one. Searching one and citing the other synthesizes receipts that resolve in no
    document, which is the failure this unit exists to prevent rather than commit.

    A carried receipt must be measured in the frame this pass is FOR. `source_ref` and
    `prepared_text` are one pair — the name of a coordinate system and the text it addresses —
    and a span arriving under a different name is offsets into some other document. That is a
    caller mistake, so it raises: it is the same confusion `_emitted_offsets` refuses one
    function up ("a span whose offsets are in one frame while its reference names another points
    at the wrong sentence invisibly"), and refusing it there while waving it through on the path
    every model-supplied receipt takes made the check decorative. Left unchecked it counted as a
    claim WITH a receipt, resolved to the empty string in the pass's own text, and surfaced one
    unit later as ALG-08's INVALID_BOUNDS — which reads as a model that invented an offset when
    what happened is an extractor that stamped the wrong frame.

    Order is preserved and nothing is merged: two claims quoting the same sentence get one
    receipt each, and `EvidenceSpan` is frozen and hashable so the duplicate costs one shared
    object rather than a copy.
    """
    require_text(source_ref, "source_ref")
    bound: list[BoundClaim] = []
    seen = carried = synthesized = dropped = 0
    for draft in drafts:
        seen += 1
        if draft.evidence:
            _require_same_frame(draft, source_ref)
            carried += 1
            bound.append(BoundClaim(draft=draft, evidence=draft.evidence,
                                    confidence_bp=draft.confidence_bp, synthesized=False))
            continue
        span = _synthesize(draft.claim_text, prepared_text, source_ref)
        if span is None:
            dropped += 1
            continue
        synthesized += 1
        bound.append(BoundClaim(draft=draft, evidence=(span,),
                                confidence_bp=_reduced(draft.confidence_bp), synthesized=True))
    return BindOutcome(claims=tuple(bound),
                       counters=BinderCounters(claims_in=seen, carried_own_evidence=carried,
                                               synthesized=synthesized, no_evidence=dropped))


def no_evidence_rate_bp(counters: BinderCounters) -> int:
    """The share of claims dropped for having no recoverable receipt, in integer basis points.

    Integer division, so the rate is truncated and never overstated and two prompt versions
    are compared like for like — the same arithmetic `unverified_rate_bp` uses one unit
    downstream, for the same reason. No claims reports 0, which is why a caller reads it beside
    `claims_in`: an extraction that produced nothing did not produce nothing WELL.
    """
    if counters.claims_in == 0:
        return 0
    return counters.no_evidence * BP_FULL // counters.claims_in


def rate_blocks_prompt_release(rate_bp: int) -> bool:
    """U1's release gate: *"a sustained rise above 5% blocks the next prompt version."*

    Strictly greater, so a candidate landing exactly on 500 bp passes — the doc says "above",
    and a gate that also blocked the boundary would fail a prompt that met its stated bar.
    """
    return rate_bp > MAX_NO_EVIDENCE_RATE_BP


__all__ = ["CHUNK_FRAME_PREFIX", "MAX_NO_EVIDENCE_RATE_BP", "PREPARED_FRAME_PREFIX",
           "SYNTHESIS_FACTOR", "AlignedSpan", "BindOutcome", "BinderCounters", "BoundClaim",
           "ClaimDraft", "ModelSpan", "align_span", "bind_evidence", "no_evidence_rate_bp",
           "rate_blocks_prompt_release"]
