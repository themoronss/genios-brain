"""L2.7.8 · the two shapes the situation publisher adds to a `BusinessSituationObject`.

**`BusinessSituationObject` itself is untouched, deliberately.** Doc 08 sketches the v2 additions
as new dataclass fields behind a schema version bump; H0 requires that *"an old-shaped
BusinessSituationObject still constructs"*, and that contract is frozen, slotted, hashed into the
expertise package's content address and constructed at four call sites outside Layer 2. Its
`evidence` is already a tuple of mappings and its `metadata` is already a free mapping, so
everything below travels inside the object that exists rather than beside a second version of it.
What this file adds is the part a free mapping cannot give you: a NAME for the shape, validation
at the point of construction, and one place the vocabulary is spelled.

TWO TYPES, ONE JOB EACH.

`VerifiedEvidenceSpan` is the evidence upgrade in doc 07's own words: *"today a situation's
evidence is a list of event references; in v2 it is a list of span-validated verbatim quotes — so
a card can show the sentence, not just name the email."* The difference between "there is an email
about this" and "he wrote: *we're pausing until Q3*" is this record, and the only thing that makes
it a receipt rather than a claim is `verdict` — ALG-08's grade, from L1's own validator, recorded
beside the quote it graded.

`SituationConfidenceVector` is the group gate's second row: *"confidence vector axes present — all
6"*. It exists so that "all 6" is a property of a typed object rather than of whichever keys a
caller happened to write, and so the sixth axis's not-applicable sentinel cannot be read as a zero.

NO IMPORT OF LAYER 1 HERE, and no import of the validator whose verdicts this file names. The
grade vocabulary is `capture/validate/spans.SpanVerdict`, one layer down and on the far side of a
seam `contracts/` is beneath: a contract package that imported a capture module would invert the
dependency every other file in this directory keeps. So the four passing grades are spelled as
strings, and `tests/context/test_situation_publisher.py` pins them against the real enum — the
same discipline `context/situation_bso.UNSCORED_VERSION` keeps for the same reason.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts.validators import require_bp, require_identifier, require_text

#: ALG-08's four RESOLVED grades — the ones that mean "these words are in that text". Spelled as
#: strings rather than imported (see the module docstring), listed positively rather than as
#: "everything except the two failures", for the reason `capture/semantic/evidence_binder` gives:
#: a seventh grade added to the cascade would otherwise default to ACCEPTED, which is the wrong
#: direction for a default in the decision "does this quote substantiate the claim".
VERIFIED_VERDICTS: frozenset[str] = frozenset({
    "verified", "verified_whitespace", "verified_relocated", "verified_fuzzy"})

#: HOW a span came to be trusted. Three states, and the distance between them is the whole point:
#:
#: * `l2_reverified` — Layer 2 fetched the stored source text and ran ALG-08 over the span again.
#:   The strongest claim available: the sentence is in the text NOW, at the offsets recorded here.
#: * `l1_verified` — the source text is no longer retrievable (prepared content past its retention
#:   window, or a frame Layer 2 holds no store for), and the span carries Layer 1's own
#:   `verified=True`, which only ALG-08 may set. A receipt from a check we cannot repeat.
#: * `unverified` — neither. The quote is carried, flagged, and never counted as a verified span.
#:   L1's rule, not a new one: an unverified span degrades trust and does not delete the claim.
VERIFICATION_REVERIFIED = "l2_reverified"
VERIFICATION_L1 = "l1_verified"
VERIFICATION_NONE = "unverified"

#: The verdict recorded when a stored span could not even be expressed as a span — an inverted
#: range, or a quote whose length disagrees with its offsets. ALG-08's own name for it, because
#: for policy purposes it is the same fact as UNVERIFIED and a second word would invite a reader
#: to think it is a different one.
VERDICT_INVALID_BOUNDS = "invalid_bounds"

#: `evidence.source` for a receipt that came from a qualified signal, as opposed to the graph
#: source ref the correlation reconstructs. One spelling: `tests/test_l2_reads_what_l1_publishes`
#: asserts on this exact string, and `situation_bso` has written it since the seam landed.
EVIDENCE_SOURCE_L1 = "l1_qualified_signal"


@dataclass(frozen=True, slots=True)
class VerifiedEvidenceSpan:
    """One span-validated verbatim quote, as it travels in `BusinessSituationObject.evidence`.

    Frozen for `EvidenceSpan`'s reason: a receipt that can be edited after the fact is not a
    receipt. It is NOT an `EvidenceSpan` — that type's constructor enforces
    `len(quote) == end - start` against the frame the extractor measured in, and this record must
    be able to carry a span that FAILED that check (`VERDICT_INVALID_BOUNDS`) so a reader can see
    that a signal cited something incoherent rather than seeing nothing at all.

    `verified` is DERIVED, never passed. That is what stops the flag drifting from the grade
    beside it — the failure mode `EvidenceSpan.verified` documents at the layer below, one hop
    later. Two ways to earn it, and only two:

    * `l2_reverified` AND one of ALG-08's four resolved grades — we ran the check ourselves;
    * `l1_verified` — we could not run it, and L1's own flag says ALG-08 ran it at publish time.
      `verdict` is empty in this case ON PURPOSE: no grade was assigned HERE, and copying a grade
      we did not produce is exactly the "claimed" that `EvidenceSpan.verified` refuses to become.

    A record that was regraded and FAILED is unverified whatever L1's flag said. The check we can
    repeat outranks the flag we cannot: a span whose prepared text has since been re-masked, or
    whose offsets were stamped in another frame, is a receipt that no longer resolves, and the
    flag would carry it as if it did.
    """

    source_ref: str
    quote: str
    start_offset: int
    end_offset: int
    #: ALG-08's grade, or `""` when no grading was possible at all.
    verdict: str
    verification: str
    #: `qualified_signals.signal_id` — WHICH signal carried this receipt. A quote with no signal
    #: behind it cannot be explained backwards, which is the whole use of an evidence table.
    signal_id: str

    @property
    def verified(self) -> bool:
        if self.verification == VERIFICATION_REVERIFIED:
            return self.verdict in VERIFIED_VERDICTS
        return self.verification == VERIFICATION_L1

    def as_record(self) -> dict[str, Any]:
        """The mapping the BSO carries. Plain JSON — no floats, no clocks, no objects.

        A clock is the one thing that must never appear here: `BusinessSituationObject.metadata`
        and `evidence` are both hashed by `to_semantic_dict`, and that hash is the expertise
        package's content address. A per-sweep value in a receipt mints a fresh package row per
        situation per sweep — the mechanism that put 995 MB on one tenant's database and took the
        project read-only. The quote's own timestamp is on the `qualified_signals` row
        `signal_id` names.
        """
        return {
            "source_ref": self.source_ref,
            "quote": self.quote,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "verified": self.verified,
            "verdict": self.verdict,
            "verification": self.verification,
            "signal_id": self.signal_id,
            "source": EVIDENCE_SOURCE_L1,
        }

    @classmethod
    def build(cls, *, source_ref: str, quote: str, start_offset: int, end_offset: int,
              verdict: str, verification: str, signal_id: str) -> VerifiedEvidenceSpan:
        """Construct with the two invariants a mapping cannot hold.

        `source_ref` and `quote` must be real text — a span that says neither what it points into
        nor what it says points at nothing — and the two vocabulary fields must be members of
        their vocabularies. A misspelled verification state would read as `unverified` under
        `verified` and as a valid state everywhere else, which is a receipt that silently stops
        counting.
        """
        if verification not in (VERIFICATION_REVERIFIED, VERIFICATION_L1, VERIFICATION_NONE):
            raise ValueError(f"unknown evidence verification state {verification!r}")
        return cls(source_ref=require_text(source_ref, "evidence source_ref"),
                   quote=require_text(quote, "evidence quote"),
                   start_offset=max(0, int(start_offset)),
                   end_offset=max(0, int(end_offset)),
                   verdict=str(verdict or ""),
                   verification=verification,
                   signal_id=require_identifier(signal_id, "evidence signal id"))


#: The six axes, in the order `situations.Confidence` declares them. Named once so "all 6" is a
#: length check against a declaration rather than a count of whatever keys were written.
CONFIDENCE_AXES: tuple[str, ...] = (
    "evidence", "freshness", "consistency", "identity", "coverage", "analytic")

#: `situations.COVERAGE_UNKNOWN`, restated in basis-point terms. A dimension with no basis is
#: reported as having none; a 0 would rank an unmeasured situation below every measured one,
#: which is the same error `situation_bso.UNSCORED_VERSION` exists to prevent one field up.
AXIS_UNKNOWN_BP = -1


@dataclass(frozen=True, slots=True)
class SituationConfidenceVector:
    """The six confidence axes, in basis points, as one object rather than six loose keys.

    **Never collapsed to a scalar** — doc 09's "what must not regress" row 3. `confidence_bp` on
    the BSO is the MINIMUM of the axes that apply, and a reader who needs to know WHICH dimension
    is weak has to be able to ask. That is what this record is for.

    Every axis accepts `AXIS_UNKNOWN_BP` and nothing else outside 0..10000: an axis that was not
    assessed is a third state, and squeezing it into the same range as an assessed one is how
    "we did not look" becomes "we looked and it was terrible".
    """

    evidence: int
    freshness: int
    consistency: int
    identity: int
    coverage: int
    analytic: int

    def __post_init__(self) -> None:
        for axis in CONFIDENCE_AXES:
            value = getattr(self, axis)
            if value != AXIS_UNKNOWN_BP:
                require_bp(value, f"confidence axis {axis}")

    @property
    def complete(self) -> bool:
        """Every axis carries an assessed number. The group gate's row, as a property."""
        return all(getattr(self, axis) != AXIS_UNKNOWN_BP for axis in CONFIDENCE_AXES)

    def as_record(self) -> dict[str, int]:
        return {axis: int(getattr(self, axis)) for axis in CONFIDENCE_AXES}

    @classmethod
    def from_record(cls, record: Mapping[str, Any] | None) -> SituationConfidenceVector:
        """Read a vector back off a BSO's metadata. A missing axis is UNKNOWN, never 0."""
        body = dict(record or {})
        return cls(**{axis: int(body.get(axis, AXIS_UNKNOWN_BP)) for axis in CONFIDENCE_AXES})


__all__ = [
    "AXIS_UNKNOWN_BP",
    "CONFIDENCE_AXES",
    "EVIDENCE_SOURCE_L1",
    "VERDICT_INVALID_BOUNDS",
    "VERIFICATION_L1",
    "VERIFICATION_NONE",
    "VERIFICATION_REVERIFIED",
    "VERIFIED_VERDICTS",
    "SituationConfidenceVector",
    "VerifiedEvidenceSpan",
]
