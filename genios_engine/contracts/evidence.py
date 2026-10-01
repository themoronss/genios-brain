"""C-01 · EvidenceSpan — the receipt a claim carries so it can be checked instead of believed.

Every typed thing Layer 1 asserts about the world (an entity mention, a commitment, a decision
state, a dependency, a resolved date, a claim inside a conflict, the qualified signal itself)
embeds a list of these, and a claim whose list is empty is refused at the publishing seam. That
is the whole doctrine in one sentence: a claim with no receipt is a guess, and a guess must not
reach a human wearing the same typography as a fact.

The span carries BOTH the quote and the offsets, on purpose. Offsets alone rot the moment the
prepared text is re-derived by a newer preprocessor and silently point at the wrong sentence;
the quote alone cannot be highlighted, ranked, or deduplicated. Carried together they are
self-checking — slice the source at ``[start_offset:end_offset]`` and compare — and that
comparison is the only mechanism that distinguishes a real citation from a fluent invention.

**Verification does not happen here.** This module owns the shape of a span and the invariants
that make one worth checking at all. Resolving a span against real source text is ALG-08, the
Evidence Span Validator (L1.5.1) at ``genios_engine/capture/validate/spans.py``: it grades a
span exact / whitespace-normalised / relocated / fuzzy / UNVERIFIED, corrects offsets, and
applies the per-claim-type policy (a fabricated Money or ResolvedDate is dropped outright, a
Commitment is kept at halved confidence and flagged). None of that belongs in a contract —
it needs the prepared content, a verdict type and a drop policy, and contracts may import
nothing above ``platform``. Contracts describe the object; the seam that produced it decides.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from genios_engine.contracts.validators import require_bool, require_non_negative, require_text

#: The doc-stated ceiling on a quote. A "quote" longer than a few sentences is a paraphrase of a
#: paragraph, and a receipt that quotes everything proves nothing — it just moves the reader's
#: work from "is this true" to "where in this wall of text". 400 characters is roughly two
#: sentences: enough to carry the claim's context, short enough that a human checks it in a
#: glance rather than skipping it.
MAX_QUOTE_CHARS = 400


class EvidenceSpan(BaseModel):
    """A verbatim pointer back into source text — the anti-hallucination primitive.

    ``quote`` must appear byte-for-byte in the prepared content at
    ``[start_offset:end_offset]``. L1.5.1 (ALG-08) is what actually checks that; a span that
    does not resolve marks its parent claim unverified rather than deleting it, because an
    unverified span degrades trust and does not by itself destroy a signal.

    The constructor enforces only what can be known without the source text: that the three
    parts describe the same region. A span whose ``quote`` is shorter than the range it names
    is already incoherent before anyone opens the document, and catching that here — at the
    seam that produced it — is cheaper than discovering it three layers later, inside a card a
    founder is reading.
    """

    #: Frozen, for two reasons. A receipt that can be edited after the fact is not a receipt:
    #: spans are copied into audit rows, decision hashes and rendered cards, and an in-place
    #: edit would leave those pointing at text the span no longer claims. And the invariants
    #: below only hold for the three fields together — relocating a quote moves the start, the
    #: end and sometimes the text at once, with no valid intermediate state — so a patch would
    #: have to pass through a state the constructor refuses. ALG-08 says the same thing in its
    #: own words: a corrected span is REWRITTEN. L1.5.1 therefore builds a new EvidenceSpan
    #: through this constructor, which revalidates it; ``model_copy(update=...)`` deliberately
    #: does not, so it is not the sanctioned path for a correction.
    #:
    #: Frozen also makes a span hashable, which is what lets the many claims extracted from one
    #: sentence share a single receipt instead of each carrying a near-identical copy.
    model_config = ConfigDict(frozen=True)

    #: Where the quote lives. Two literal shapes, and only two:
    #:   ``"prepared_content:<event_id>"`` — a span into one prepared message's clean_text
    #:   ``"chunk:<doc_id>:<n>"``          — a span into chunk n of a registered document
    #: The offsets below are meaningless without it: character 412 *of what* is not a receipt.
    #: Kept as one opaque string rather than a parsed pair because this is also the join key
    #: the card renderer and the audit row carry verbatim, and a parsed form re-serialised at
    #: each hop is one more place for the two halves to drift apart.
    source_ref: str

    #: The source text, verbatim — never trimmed, never tidied, never re-encoded. Whitespace is
    #: part of the receipt: ``len(quote)`` must equal ``end_offset - start_offset``, so a
    #: helpful ``.strip()`` here would break the single invariant that lets L1.5.1 tell a real
    #: citation from a plausible-looking one. Capped at MAX_QUOTE_CHARS.
    quote: str

    #: Inclusive, and an offset into the PREPARED ``clean_text`` — not the raw source. The
    #: prepared form is what the extractor was shown, so it is the only coordinate system in
    #: which the model's offsets can be right; ``PreparedContent.to_source_offset`` maps back
    #: to original characters when a human clicks the fact and wants the untouched sentence.
    start_offset: int

    #: Exclusive, matching Python slicing, so ``clean_text[start_offset:end_offset]`` is the
    #: quote with no off-by-one arithmetic at any call site.
    end_offset: int

    #: True means the quote was FOUND in real source text by L1.5.1 — never that a model said
    #: it was there. It is False on every span an extractor produces, and only the span
    #: validator may construct one with True. The moment any other caller can set this, the
    #: flag stops meaning "checked" and starts meaning "claimed", which is the exact
    #: distinction this entire type exists to preserve. A span still False at the qualified
    #: signal seam does not kill the signal: V-5 downgrades confidence, flags it, and emits.
    verified: bool = False

    #: WHICH PAGE, 1-based, or None when the source has no pages.
    #:
    #: Offsets alone are a receipt a machine can resolve and a human cannot open. "Character 4,812
    #: of the prepared text" is not something anybody can check against a signed PDF; *page 4* is.
    #: Filled at the alignment seam from the page map the document extractor produced (a PDF's
    #: page boundaries, native or rasterized), and recomputed rather than carried when ALG-08
    #: relocates a quote — a moved span may have moved across a page break, and a page number
    #: that no longer matches its offsets is worse than none.
    #:
    #: None for everything without pages: an email body, a chat message, a calendar event. Not 1 —
    #: "page one of an email" is a number invented to fill a column.
    page: int | None = None

    #: WHICH SECTION — the heading the quote sits under, verbatim, or None.
    #:
    #: `capture/documents/chunking.py` already detects section boundaries and refuses to split a
    #: clause across them, so the title is known at the moment the model is shown the text and is
    #: unrecoverable afterwards. A quote from *Termination* and a quote from *Payment Terms* are
    #: different facts about a contract, and until this field existed both resolved to "somewhere
    #: in the agreement".
    #:
    #: NOT a table cell. `documents/native.py` flattens a DOCX table into lines, so no row or
    #: column identity survives extraction and a `cell` field here could only ever be filled with
    #: a guess. Table-cell provenance needs a table-aware extractor first; the gap is recorded in
    #: `docs/plans/L1_PRODUCTION_READINESS.md` rather than papered over with a column nothing can
    #: honestly fill.
    section: str | None = None

    @field_validator("page", mode="before")
    @classmethod
    def _require_page(cls, value: Any) -> Any:
        """1-based, or absent. Page 0 is a coordinate system nobody prints on a document."""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("page must be a 1-based integer page number or None")
        if value < 1:
            raise ValueError(f"page must be 1 or greater, got {value} — pages are numbered the "
                             "way they are printed, not the way a list is indexed")
        return value

    @field_validator("section", mode="before")
    @classmethod
    def _require_section(cls, value: Any) -> Any:
        """The heading verbatim, or None. An empty string is not a section — it is the absence of
        one wearing the shape of a value, and it would render as an empty crumb in a citation."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("section must be the heading text or None")
        return value if value.strip() else None

    @field_validator("source_ref", mode="before")
    @classmethod
    def _require_source_ref(cls, value: Any) -> str:
        """A span that does not say what it points into cannot be resolved by anyone, ever."""
        return require_text(value, "source_ref")

    @field_validator("quote", mode="before")
    @classmethod
    def _require_quote(cls, value: Any) -> str:
        """Non-empty and within the cap — but returned unmodified, whitespace and all."""
        if not isinstance(value, str):
            raise TypeError("quote must be verbatim source text")
        if not value.strip():
            raise ValueError("quote is required — a span quoting nothing cites nothing")
        if len(value) > MAX_QUOTE_CHARS:
            raise ValueError(f"quote must be at most {MAX_QUOTE_CHARS} characters")
        return value

    @field_validator("start_offset", "end_offset", mode="before")
    @classmethod
    def _require_offset(cls, value: Any, info: ValidationInfo) -> int:
        """Offsets are positions in a string, so a negative one is not a near-miss — it is a
        different kind of value. ALG-08 treats it as INVALID_BOUNDS; refusing it here means the
        validator never has to reason about a span that could not have come from real text."""
        return require_non_negative(value, info.field_name or "offset")

    @field_validator("verified", mode="before")
    @classmethod
    def _require_verified(cls, value: Any) -> bool:
        """A literal bool only. Truthiness coercion (``1``, ``"true"``) is exactly how an
        unchecked span would acquire a checkmark by accident."""
        return require_bool(value, "verified")

    @model_validator(mode="after")
    def _require_coherent_span(self) -> EvidenceSpan:
        """CV-01 — the three parts must describe one region of text.

        Both failures are silent corruption if allowed through: an empty or inverted range
        highlights nothing, and a quote whose length disagrees with its range means the model
        reported a sentence it did not measure, so every offset-based check downstream is
        comparing against the wrong characters.
        """
        if self.end_offset <= self.start_offset:
            raise ValueError(
                f"end_offset must be greater than start_offset "
                f"({self.end_offset} <= {self.start_offset})")
        span_length = self.end_offset - self.start_offset
        if len(self.quote) != span_length:
            raise ValueError(
                f"quote length must equal end_offset - start_offset "
                f"({len(self.quote)} != {span_length})")
        return self


#: What an unmet need is still doing. Closed, and `unavailable` is the member that matters.
NEED_STATES = ("open", "met", "unavailable")


class EvidenceNeed(BaseModel):
    """L2 → L1 · the one fact that would change the conclusion, asked for by name.

    ⛔ THE EDGE THIS SYSTEM DID NOT HAVE. Layer 2 could only HOLD and wait: a situation missing its
    signed contract stayed incomplete until some later sweep happened to bring the document in by
    luck. Meanwhile `context/residue.py` was already computing the demand — `signal_unreached`
    measures *"the Layer 1 verdicts no Layer 2 reading consumes"* — and that number reached the
    model angles and stopped. **The measurement half existed; only the wire did not.**

    ⛔ IT IS NOT A BACKFILL. A backfill fetches everything and hopes. This names ONE fact, for ONE
    decision, with a cost limit and an expiry, and records what would and would not settle it. That
    is the difference between widening a window and asking a question.

    ⛔ `unacceptable_sources` IS NOT DECORATION, AND IT IS WHY THIS IS A CONTRACT AND NOT A STRING.
    A vendor's quote email may not stand in for the signed contract. Without the negative list, an
    executor that found *something* mentioning the right words would close the need and Layer 2
    would proceed on evidence that cannot carry the claim — which is worse than the hold it
    replaced, because the hold at least knew it was missing something.

    ⛔ AND `unavailable` IS A REAL OUTCOME, NOT A FAILURE. A need that can never be met must CLOSE,
    with a reason. One left open forever is a hold that can never clear — exactly the state this
    contract exists to end, re-created one layer down.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Deterministic over the question and its subject, so the same need raised on two sweeps is
    #: one row. An unmet need re-raised every sweep would be a queue that grows forever.
    need_id: str
    org_id: str
    trace_id: str
    #: What is being asked, in words a person could act on. Not a code.
    question: str
    #: ⛔ WHY IT CHANGES THE DECISION. A need that cannot say this is not decision-relevant, and
    #: fetching for it spends a tenant's budget on curiosity.
    why_it_matters: str
    #: What the need is about — `contract:CTR-441`, `thread:…`, `signal:…`.
    subject_ref: str | None = None
    #: What WOULD settle it.
    acceptable_sources: tuple[str, ...] = ()
    #: ⛔ What would NOT, however well it matches. See the class docstring.
    unacceptable_sources: tuple[str, ...] = ()
    #: The period to look in. `None` means the executor's own default, not "all time".
    window_from: Any | None = None
    window_to: Any | None = None
    #: How much this question is worth. An unbounded fetch is a backfill wearing a question's
    #: clothes.
    max_cost_usd: float | None = None
    #: After this, the answer would arrive too late to change anything, so it is not worth buying.
    expires_at: Any | None = None
    state: str = "open"
    #: Set only when `state` is `unavailable` — the sentence a card can show instead of waiting.
    unavailable_reason: str | None = None

    @field_validator("question", "why_it_matters")
    @classmethod
    def _must_say_something(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("state")
    @classmethod
    def _state_is_closed(cls, value: str) -> str:
        if value not in NEED_STATES:
            raise ValueError(f"state must be one of {NEED_STATES}, not {value!r}")
        return value

    @model_validator(mode="after")
    def _closure_is_explained(self) -> "EvidenceNeed":
        if self.state == "unavailable" and not (self.unavailable_reason or "").strip():
            raise ValueError(
                "an unavailable need carries its reason: a need that closes without one is "
                "indistinguishable from a need nobody worked, and the card has nothing to say "
                "in place of the fact it was waiting for")
        if self.state != "unavailable" and self.unavailable_reason:
            raise ValueError("unavailable_reason belongs only to an unavailable need")
        overlap = set(self.acceptable_sources) & set(self.unacceptable_sources)
        if overlap:
            raise ValueError(
                f"{sorted(overlap)} is named as both acceptable and unacceptable; an executor "
                f"reading this could close the need with evidence the need itself rejects")
        return self

    def accepts(self, source: str) -> bool:
        """Whether evidence from `source` may close this need.

        ⛔ The negative list wins. A source named in both would be a contradiction the validator
        already refuses; a source in neither is allowed, because an executor that only ever
        accepted an enumerated list could not answer a question nobody anticipated a source for.
        """
        if source in self.unacceptable_sources:
            return False
        return not self.acceptable_sources or source in self.acceptable_sources


__all__ = ["MAX_QUOTE_CHARS", "NEED_STATES", "EvidenceNeed", "EvidenceSpan"]
