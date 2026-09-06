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


__all__ = ["MAX_QUOTE_CHARS", "EvidenceSpan"]
