"""L1.5.6 · the Schema Validator — the structural gate between the model's answer and S3.

S2 hands S3 an `ExtractionResult`. Everything after that point — span verification, date
resolution, currency normalisation, conflict detection, importance scoring — reads its fields
by name and trusts that they are the fields the schema declares, carrying values from the sets
the prompt named. This unit is what makes that trust checkable. It answers exactly one
question, in one pass: **does this extraction conform to the closed schema?**

**Why the contract's own constructor is not enough**, which is the only interesting question
about this unit:

* **The constructor deliberately does not check vocabulary.** `contracts/extraction.py` says so
  in its own words: `entity_type`, `state`, `dependency_type`, `intent`, `stance` and
  `extraction_profile` are typed `str` because the closed sets live in
  `capture/semantic/vocabulary.py`, where the promotion path (L1.4.5-U2) can extend one behind
  a schema-version bump. Presence is asserted at the boundary; **membership has to be asserted
  somewhere in the validated lane, and this is that somewhere.** Without it a model that
  answers `"stance": "optimistic"` produces a perfectly constructible result that every
  downstream rule silently fails to match — the recorded v1 failure, where rules read
  `deal.status` while the extractor wrote `status` and the rule was dead on arrival.
* **A constructor raises; S3 may not.** The stage law gives S3 one verb: it may flag, it may
  not drop. A `ValidationError` unwinding out of a publisher loop is a log line, and the next
  question a tenant asks is always about the message that produced nothing. So this unit
  returns a `SchemaReport` of named-field violations — every one of them, not the first — and
  the caller writes the row.
* **Objects reach S3 that never ran a constructor.** `model_construct()` and
  `model_copy(update=...)` both skip validation by documented design; the repair path in the
  extractor, the rehydration of a cached `l1_extraction_results` row written under an older
  schema version, and any test helper all have a route to one. `contracts/publication.py`
  names those two routes for the same reason and reads its input the same defensive way. A
  check that trusted the annotation would be a rule that only ever passes.

**What it does NOT do, and the boundary is sharp.** It does not verify a span against source
text (ALG-08, `spans.py` — that needs the prepared content). It does not resolve a date
(ALG-09, `dates.py` — that needs an `eval_time`). It does not parse an amount (ALG-10,
`money.py` — that needs a locale). It never rewrites a value: a validator that quietly repairs
its input is a validator that lets a malformed extraction reach a human with the repair
invisible. **Shape and vocabulary. Nothing else.**

One rule here is not about the object at all but about where the object came from — S-9, "the
extractor may not stamp its own receipts" — and a rule about origin needs to be told which seam
it is standing at. That is the `stage` parameter. It is the reason this unit can be run twice
over one extraction, before and after ALG-08, without the second run refusing the first one's
correctly verified output; see `ValidationStage` for the ordering it encodes and for why the
default is the arrival stage rather than the permissive one.

The vocabulary is a PARAMETER, never a constant in this file. The words belong to
`capture/semantic/vocabulary.py` (doc 04, L1.4.4-U1), which is also what the prompt generator
reads; a second copy here would be the one that drifts, and a validator disagreeing with the
prompt about what the model was allowed to say is worse than no validator — it rejects correct
extractions and it does so in the lane that is supposed to establish trust.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (FORBIDDEN_RESULT_FIELDS,
                                                MAX_UNCLASSIFIED_PER_EXTRACTION, ExtractionResult)
from genios_engine.contracts.units import DateCertainty
from genios_engine.contracts.validators import require_bp, require_non_negative, require_text

#: Absence is not the same value as `None`, and the two are different defects. A field omitted
#: by `model_construct` raises `AttributeError`; a field explicitly set to null was answered
#: with nothing. Both fail S-1, and the detail line says which — a sentinel is the only way to
#: tell them apart through one `getattr`.
_MISSING = object()

#: The closed field list, read off the contract rather than copied. Adding a field to
#: `ExtractionResult` extends this automatically, which is the whole reason it is derived: a
#: hand-maintained list is a list that silently stops covering the newest field, and the newest
#: field is exactly the one whose extractor support is least proven.
DECLARED_FIELDS: tuple[str, ...] = tuple(ExtractionResult.model_fields)

#: Result field -> the `ExtractionVocabulary` set that governs it. These three are the closed
#: sets that live directly on the result; the per-claim ones are below.
_RESULT_VOCABULARY: Mapping[str, str] = {
    "intent": "intent",
    "stance": "stance",
    "extraction_profile": "extraction_profile",
}

#: Claim attribute -> the `ExtractionVocabulary` set that governs it. Keyed by attribute name
#: rather than by claim type because the four names are unique across the claim types, so the
#: walk needs no per-type dispatch and a new claim type reusing `state` is covered on the day
#: it is written rather than on the day somebody remembers to extend a table.
_CLAIM_VOCABULARY: Mapping[str, str] = {
    "entity_type": "entity_type",
    "state": "decision_state",
    "dependency_type": "dependency_type",
}

#: How many characters of a quote a violation may echo. A violation line is read in a log or a
#: ledger row; a 400-character quote inlined there buries the field name that is the point of
#: the message.
_QUOTE_ECHO = 60


class SchemaRule(str, Enum):
    """The eight checks, by id. The value is what a diagnosis row stores.

    Ids rather than prose for the reason `PublicationRule` uses them: "S-3 on
    `entity_mentions[2].entity_type`" is joinable, sortable and countable across a week of
    extractions, which is how a bad extraction PROFILE becomes visible. "bad value" is a
    sentence somebody will rewrite next month and nobody can group by.
    """

    #: Every declared field is present and is not null. A field that never arrived is a field
    #: every downstream reader will attribute to the message rather than to the extractor.
    S1 = "S-1"
    #: Each field holds the container and element type the schema declares.
    S2 = "S-2"
    #: Every vocabulary-governed value is inside its closed set. Never coerced to a near
    #: neighbour — "optimistic" is not a mis-spelled "positive", it is a word the prompt did
    #: not offer, and silently mapping it would hide that the profile is drifting.
    S3 = "S-3"
    #: Every claim carries at least one `EvidenceSpan`. Universal rule 4: a claim with no
    #: receipt is a guess.
    S4 = "S-4"
    #: Every score is an exact integer in its stated range — basis points 0..10000, token
    #: counts non-negative.
    S5 = "S-5"
    #: Neither forbidden score appears. The model may describe; it may never score.
    S6 = "S-6"
    #: `all_evidence` contains every span the claims carry. It is the list ALG-08 walks, so a
    #: span missing from it is a claim that is never verified and never reported unverified.
    S7 = "S-7"
    #: ADVISORY, non-blocking: the open lane is over its per-extraction cap.
    S8 = "S-8"
    #: No span arrived with `verified=True`. `EvidenceSpan.verified` means "L1.5.1 opened the
    #: source and found this quote", and the contract says only the span validator may set it —
    #: but the field has an ordinary default, so the extractor can set it itself. This is the
    #: rule that makes that sentence true. An extraction is the model's testimony; it may not
    #: also be the receipt for its own testimony.
    #:
    #: The only STAGE-SCOPED rule here, and the only one that could be: it is about a value's
    #: origin, so it holds where the extraction arrives and nowhere later. See `ValidationStage`.
    S9 = "S-9"


class ValidationStage(str, Enum):
    """WHERE in the lane the extraction being validated is — the one thing S-9 needs to know.

    Every other rule here is a statement about an `ExtractionResult` at any age: a null field is
    null forever, and `"optimistic"` is outside the stance set no matter who is holding the
    object. S-9 is not like that. It says *the extractor may not stamp its own receipts*, which
    is a claim about ORIGIN, and after ALG-08 has run every grounded span legitimately wears the
    flag. Applied unconditionally the rule rejects `spans.apply_verdicts`' own output — the very
    object L1.5.1 exists to produce — and it does so with a report reading "the extractor stamped
    its own receipt", which points a reader at the one component that did nothing wrong. A
    diagnosis naming the wrong unit is worse than no diagnosis; it costs a day before anyone
    doubts it.

    So the stage is a PARAMETER, and the ordering it encodes is stated here rather than left as
    something a reader has to infer from the absence of a second caller. An extraction arrives at
    `EXTRACTOR_OUTPUT`; it is at `POST_VERIFICATION` only once `spans.apply_verdicts` has graded
    it. Re-validation is an anticipated path, not a hypothetical — a cached `l1_extraction_results`
    row read back, an extractor repair, W6 handing S3's own output to S3 again — and every one of
    those knows which of the two objects it is holding. Naming it costs a keyword.

    Scoping the rule is not weakening it, and the difference is the whole point. At
    `POST_VERIFICATION` the flag is no longer testimony: ALG-08 sets it on exactly the spans it
    grounded in the source and clears it on every other one (`spans.py::_as_unverified`), so
    there is nothing left for S-9 to protect. At `EXTRACTOR_OUTPUT` it is enforced exactly as
    before — blocking, both on the claim-carried path and on the `all_evidence` index, and still
    never repaired.
    """

    #: The model's answer as it arrives from S2, before any validator has touched it. Every rule
    #: applies, S-9 included. It is the DEFAULT because it is the fail-closed one: a caller who
    #: has not thought about the ordering is refused, not waved through, and the pre-stamped
    #: fabrication S-9 exists to catch cannot enter behind a forgotten keyword.
    EXTRACTOR_OUTPUT = "extractor_output"
    #: After `spans.apply_verdicts` (ALG-08) has graded every span in the extraction. S-9 is off:
    #: a `verified=True` here is L1.5.1's own signature, which is the thing S-9 exists to keep
    #: meaningful. Nothing else changes — all eight other rules still run.
    POST_VERIFICATION = "post_verification"


#: The rules that hold only at arrival, kept as data for the reason `NON_BLOCKING_RULES` is:
#: "which rules are stage-scoped?" should be answerable by looking at one line rather than by
#: tracing a walk. S-9 is the only rule about a value's ORIGIN; every other one is about its
#: shape or its vocabulary, and those are true of the object forever.
ARRIVAL_ONLY_RULES: frozenset[SchemaRule] = frozenset({SchemaRule.S9})


#: S-8 alone. Kept as data, exactly as `contracts/publication.py` keeps `NON_BLOCKING_RULES`,
#: so "which rules block?" has one answer a reader can see without tracing control flow.
#:
#: S-8 does not block because `MAX_UNCLASSIFIED_PER_EXTRACTION` is deliberately not a validator:
#: the contract states that the cap is enforced by instructing the model to pick the five most
#: significant observations, and that failing an extraction over it would let an over-eager
#: extractor destroy a whole message — the precise failure the open lane exists to end. But a
#: profile that keeps overrunning the cap is worth seeing, and the weekly discovery report is
#: not where a shape problem should first surface.
NON_BLOCKING_RULES: frozenset[SchemaRule] = frozenset({SchemaRule.S8})


def _enforced(rule: SchemaRule, stage: ValidationStage) -> bool:
    """Does this rule hold at this stage? False only for an arrival-only rule past arrival.

    One function so there is exactly one place the stage is consulted. A second `if stage is`
    somewhere in the walk is how the two ends up disagreeing, and a rule that fires at one seam
    and not at another is the hardest kind of validator bug to see.
    """
    return stage is ValidationStage.EXTRACTOR_OUTPUT or rule not in ARRIVAL_ONLY_RULES


#: Report order. Violations are grouped by rule so a reader sees all eight missing fields
#: together rather than interleaved with vocabulary misses, and Python's stable sort keeps
#: discovery order (and therefore list index order) inside each group.
_RULE_ORDER: Mapping[SchemaRule, int] = {rule: index for index, rule in enumerate(SchemaRule)}


class _Shape(Enum):
    """The shapes S-2 knows how to check, classified from the contract's own annotations.

    Deriving the expected shape from `ExtractionResult.model_fields` rather than restating it
    means this unit cannot fall out of agreement with the type it validates. `UNKNOWN` is the
    fail-closed branch: a field whose annotation matches none of these is a schema that grew a
    shape S3 has no rule for, and reporting that is the honest answer — passing it would be
    this unit quietly ceasing to cover the newest field.
    """

    TEXT = "text"
    COUNT = "count"
    TEXT_LIST = "text_list"
    #: ONE nested record, not a list of them. `exchange_intent` is the first: a message has
    #: exactly one reading of what kind of exchange it is, where it has many commitments and
    #: many dates. Kept separate from `MODEL_LIST` rather than folded into it because the
    #: shapes fail differently — a list arriving as an object and an object arriving as a list
    #: are opposite mistakes and a reader deserves to be told which one happened.
    MODEL = "model"
    MODEL_LIST = "model_list"
    MAPPING_LIST = "mapping_list"
    BP_MAPPING = "bp_mapping"
    UNKNOWN = "unknown"


class SchemaViolation(BaseModel):
    """One rule that did not hold, and the FIELD it did not hold on.

    The field path is the reason this type exists rather than a list of strings. "the
    extraction was rejected" is unactionable; `commitments[1].evidence` names the claim, and
    `entity_mentions[0].entity_type` names a prompt that is offering the model a word the
    vocabulary does not contain. A bad extraction profile is diagnosable only if the rejection
    says where it went wrong.

    Frozen and extra-forbidding, like every record type in `contracts/`: this is a record of a
    check that ran, and a record that can be edited afterwards is not one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Which check failed. See `SchemaRule`.
    rule: SchemaRule
    #: The dotted/indexed path to the offending value, rooted at the result: `stance`,
    #: `commitments[1].due.evidence`, `field_confidence['deal.status']`. Indexes are positions
    #: in the list as it arrived, so a reader can go straight to the claim.
    field: str
    #: WHY, in one line, naming the offending value where there is one. It stands alone: by the
    #: time anyone reads it the extraction is a row in a different table.
    detail: str

    @property
    def blocking(self) -> bool:
        """False only for S-8. A non-blocking violation is still recorded — it is a fact about
        this extraction that somebody will want to count."""
        return self.rule not in NON_BLOCKING_RULES

    def __str__(self) -> str:
        return f"{self.rule.value} {self.field}: {self.detail}"


class SchemaReport(BaseModel):
    """The verdict: does this extraction conform, and if not, which fields broke it.

    Deliberately not a bool and deliberately not an exception. A bool cannot name a field, and
    a field name is the entire diagnostic value of this unit. An exception cannot become a row
    without the caller re-deriving from a message string what the validator already knew, and
    S3 is forbidden to drop an event — a refusal here must be recorded and reviewable, not
    thrown.

    Read `conforms`, never `not report.violations`: an advisory S-8 is a violation that still
    conforms, and reading the list instead of the property is how the one non-blocking rule
    quietly becomes blocking.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Every rule that did not hold, grouped by rule and in discovery order within a rule.
    #: All of them, not the first: an extraction missing a field AND carrying an out-of-set
    #: stance has two different upstream bugs, and fixing one would otherwise reveal the other
    #: a release later.
    violations: tuple[SchemaViolation, ...] = ()

    @property
    def conforms(self) -> bool:
        """The single question a caller asks. True when nothing blocking failed."""
        return not any(violation.blocking for violation in self.violations)

    @property
    def blocking_violations(self) -> tuple[SchemaViolation, ...]:
        """The violations that actually refused the extraction. Distinct from `violations` by
        the advisory rules."""
        return tuple(violation for violation in self.violations if violation.blocking)

    @property
    def failed_fields(self) -> tuple[str, ...]:
        """The field paths that failed a blocking rule, deduplicated, in report order — what a
        diagnosis row stores, and what a weekly rollup groups by to find a bad profile."""
        seen: dict[str, None] = {}
        for violation in self.blocking_violations:
            seen.setdefault(violation.field, None)
        return tuple(seen)

    @property
    def failed_rules(self) -> tuple[SchemaRule, ...]:
        """The distinct rules that failed, in report order."""
        seen: dict[SchemaRule, None] = {}
        for violation in self.violations:
            seen.setdefault(violation.rule, None)
        return tuple(seen)


class ExtractionVocabulary(BaseModel):
    """The six closed sets S-3 checks against, supplied by the caller.

    There is no default and there will not be one. The words live in
    `capture/semantic/vocabulary.py` (doc 04, L1.4.4-U1) because that module is also what the
    prompt generator and the promotion path read; a default baked in here would be a second
    copy, and the day somebody promotes a discovered kind into the vocabulary the two would
    disagree — with this unit rejecting extractions the prompt explicitly asked for. Passing
    the sets in costs one line at the call site and removes the entire class of drift.

    Every set is required and must be non-empty, which is the fail-closed reading of a
    misconfigured caller: an empty set would reject every extraction that has that field, and a
    pipeline producing nothing looks like a broken extractor for as long as it takes somebody
    to find the empty frozenset. Raising at construction points at the caller instead.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: inform | request | commit | decide | escalate | schedule | negotiate | approve | reject |
    #: question | acknowledge | introduce
    intent: frozenset[str]
    #: person | organization | vendor | product | document | project
    entity_type: frozenset[str]
    #: pending | made | blocked | deferred | abandoned
    decision_state: frozenset[str]
    #: approval | information | delivery | decision
    dependency_type: frozenset[str]
    #: positive | neutral | cautious | negative | mixed
    stance: frozenset[str]
    #: email | chat | transcript | document | crm_note. Which profile ran decides what the
    #: extractor was even looking for, so a replay that cannot name it is not a replay.
    extraction_profile: frozenset[str]

    @field_validator("*")
    @classmethod
    def _non_empty_set(cls, value: frozenset[str], info: ValidationInfo) -> frozenset[str]:
        label = info.field_name or "vocabulary set"
        if not value:
            raise ValueError(f"{label} is empty — a closed set with no members rejects every "
                             "extraction, which reads as a broken extractor rather than a "
                             "misconfigured validator")
        for member in value:
            require_text(member, f"{label} member")
        return value

    def members(self, name: str) -> frozenset[str]:
        """The set governing one field, by the name used in the two maps above."""
        return getattr(self, name)


def _echo(value: Any) -> str:
    """A value rendered short enough to belong in a one-line diagnosis."""
    text = repr(value)
    return text if len(text) <= _QUOTE_ECHO else f"{text[:_QUOTE_ECHO]}..."


def _shape_of(annotation: Any) -> tuple[_Shape, Any]:
    """Classify a declared annotation into the shape S-2 checks, plus its element type.

    Reads `get_origin`/`get_args` rather than matching on strings so that `list[Commitment]`
    and `list[EvidenceSpan]` are one rule with two element types instead of two rules that will
    be maintained to different standards.
    """
    if annotation is str:
        return (_Shape.TEXT, None)
    if annotation is int:
        return (_Shape.COUNT, None)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (_Shape.MODEL, annotation)
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        if len(args) != 1:
            return (_Shape.UNKNOWN, None)
        element = args[0]
        if element is str:
            return (_Shape.TEXT_LIST, None)
        if isinstance(element, type) and issubclass(element, BaseModel):
            return (_Shape.MODEL_LIST, element)
        if get_origin(element) is dict:
            return (_Shape.MAPPING_LIST, None)
        return (_Shape.UNKNOWN, None)
    if origin is dict:
        args = get_args(annotation)
        if args == (str, int):
            return (_Shape.BP_MAPPING, None)
    return (_Shape.UNKNOWN, None)


def _is_sequence(value: Any) -> bool:
    """A real ordered collection — not a string, which is a `Sequence` and would otherwise pass
    a list check one character at a time."""
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _check_presence(result: ExtractionResult, out: list[SchemaViolation]) -> frozenset[str]:
    """S-1 · every declared field arrived, and none of them arrived as null.

    Returns the names that did NOT, so the walk below can skip them. Without that skip a single
    absent `commitments` would also fail S-2 (not a list), and a reader would be reading two
    violations about one defect — which is how a report with forty lines gets skimmed instead
    of read.
    """
    absent: list[str] = []
    for name in DECLARED_FIELDS:
        value = getattr(result, name, _MISSING)
        if value is _MISSING:
            absent.append(name)
            out.append(SchemaViolation(
                rule=SchemaRule.S1, field=name,
                detail="field is absent from the extraction — every reader downstream would "
                       "attribute the gap to the message rather than to the extractor"))
        elif value is None:
            absent.append(name)
            out.append(SchemaViolation(
                rule=SchemaRule.S1, field=name,
                detail="field is null; the schema declares no nullable field, and an empty "
                       "list or an empty mapping is how 'nothing was found' is said here"))
    return frozenset(absent)


def _check_forbidden(result: ExtractionResult, out: list[SchemaViolation]) -> None:
    """S-6 · neither forbidden score is present.

    `FORBIDDEN_RESULT_FIELDS` is the contract's own data, reused rather than restated. The
    constructor already refuses both names, so the only way one arrives is a construction that
    skipped it — `model_copy(update=...)` writes straight into the instance — and that is
    exactly the route a well-meaning caller takes when a prompt starts emitting a score. The
    stage law is unambiguous: the model describes, S4 scores, and a score carried this far is
    derived from unvalidated input and does not reproduce on replay.
    """
    for name, reason in FORBIDDEN_RESULT_FIELDS.items():
        if getattr(result, name, _MISSING) is not _MISSING:
            out.append(SchemaViolation(
                rule=SchemaRule.S6, field=name,
                detail=f"{name} may never appear on an ExtractionResult: {reason}"))


def _check_vocabulary(value: Any, path: str, set_name: str,
                      vocabulary: ExtractionVocabulary, out: list[SchemaViolation]) -> None:
    """S-3 · one value against one closed set. Membership, never a coercion.

    A value outside the set is reported with the set beside it, because the useful question is
    never "is this word wrong" but "what was the model offered instead" — and the answer is
    usually that the prompt and the vocabulary have drifted apart.
    """
    if not isinstance(value, str):
        return                                       # S-2 already said it is not text
    members = vocabulary.members(set_name)
    if value not in members:
        out.append(SchemaViolation(
            rule=SchemaRule.S3, field=path,
            detail=f"{value!r} is not in the closed {set_name} set "
                   f"({', '.join(sorted(members))}) — a value outside the set is never mapped "
                   "to a near neighbour, because that would hide the drift that produced it"))


def _check_evidence(claim: Any, path: str, out: list[SchemaViolation], *,
                    stage: ValidationStage) -> list[EvidenceSpan]:
    """S-4 · the claim carries at least one well-formed receipt. Returns the spans it carries.

    Universal rule 4, re-asserted where a constructor may not have run. The spans are returned
    rather than only counted so that S-7 can ask whether `all_evidence` — the list ALG-08
    actually walks — contains them.
    """
    spans = getattr(claim, "evidence", _MISSING)
    if spans is _MISSING or spans is None or not _is_sequence(spans) or not spans:
        out.append(SchemaViolation(
            rule=SchemaRule.S4, field=f"{path}.evidence",
            detail="claim carries no evidence span — a claim with no receipt is a guess, and "
                   "it would render in the same typography as a checked fact"))
        return []
    carried: list[EvidenceSpan] = []
    for index, span in enumerate(spans):
        if isinstance(span, EvidenceSpan):
            carried.append(span)
            _check_unstamped(span, f"{path}.evidence[{index}]", out, stage=stage)
        else:
            out.append(SchemaViolation(
                rule=SchemaRule.S2, field=f"{path}.evidence[{index}]",
                detail=f"expected an EvidenceSpan, got {type(span).__name__} — an unresolvable "
                       "receipt cannot be verified by ALG-08 and cannot be shown to a reader"))
    if not carried:
        out.append(SchemaViolation(
            rule=SchemaRule.S4, field=f"{path}.evidence",
            detail="claim carries no usable evidence span — every entry was the wrong type"))
    return carried


def _check_unstamped(span: EvidenceSpan, path: str, out: list[SchemaViolation], *,
                     stage: ValidationStage) -> None:
    """S-9 · one span did not arrive already wearing the checkmark. AT ARRIVAL ONLY.

    `contracts/evidence.py` documents the invariant and cannot enforce it: `verified` is a
    plain field with a plain default, so the single bit that separates a checked citation from
    a claimed one is writable by the extractor whose claims ALG-08 exists to check. Nothing
    downstream can tell the difference — V-5 reads the flag as a receipt and downgrades what
    lacks it — so a pre-stamped fabrication passes the entire anti-hallucination mechanism by
    asserting its own conclusion.

    BLOCKING, and it is worth saying why rather than repairing the flag quietly: an extraction
    that stamps its own receipts is not a well-shaped extraction with one bad field, it is a
    profile doing something no prompt asked it to do. Silently clearing the bit would let that
    ship for a year with nobody able to name the day it started. ALG-08 clears the bit anyway on
    every span it grades (`spans.py::_as_unverified`) — belt and braces, at two different seams,
    because this is the one bit in the system that cannot be reconstructed after the fact.

    The rule is about ORIGIN, so it is the one rule here that a `stage` can switch off — and
    `POST_VERIFICATION` is the only thing that switches it off. Past ALG-08 a set flag is
    L1.5.1's signature rather than the extractor's, so enforcing it there would reject the
    graded extraction and blame the component that produced the clean one. See
    `ValidationStage`. Off is not repaired: nothing clears the bit here at either stage.
    """
    if not _enforced(SchemaRule.S9, stage):
        return
    if span.verified:
        out.append(SchemaViolation(
            rule=SchemaRule.S9, field=f"{path}.verified",
            detail=f"span {_echo(span.quote)} arrived with verified=True — only L1.5.1 may set "
                   "that flag, after opening the source and finding the quote. An extractor "
                   "that stamps its own receipt has asserted the conclusion the validator "
                   "exists to reach"))


def _check_score(value: Any, path: str, rule: SchemaRule, out: list[SchemaViolation],
                 *, basis_points: bool) -> None:
    """S-5 · one number, through the shared `require_*` helper rather than a second copy.

    Reusing the helper the constructor uses is the point: two range checks written twice are
    two range checks that disagree the day either is edited, and both sides would still
    typecheck. The helper raises by design; this is the single place that turns that grammar
    into a row.
    """
    label = path.rsplit(".", 1)[-1]
    try:
        require_bp(value, label) if basis_points else require_non_negative(value, label)
    except (TypeError, ValueError) as exc:
        out.append(SchemaViolation(rule=rule, field=path, detail=f"{exc} (got {_echo(value)})"))


def _check_claim(claim: Any, path: str, vocabulary: ExtractionVocabulary,
                 out: list[SchemaViolation], *,
                 stage: ValidationStage) -> list[EvidenceSpan]:
    """Every rule that applies to one embedded object, driven by what it declares.

    The applicable checks are derived from the claim type's own `model_fields` — carries
    `evidence` so S-4 applies, carries `confidence_bp` so S-5 applies, carries `entity_type` so
    S-3 applies. That is why `Money` (which declares no evidence) is not falsely accused of
    missing a receipt, and why a claim type added at W3 is covered by the checks it earns
    rather than by a table somebody has to remember to extend.
    """
    fields = type(claim).model_fields
    spans: list[EvidenceSpan] = []

    if "evidence" in fields:
        spans.extend(_check_evidence(claim, path, out, stage=stage))

    if "confidence_bp" in fields:
        _check_score(getattr(claim, "confidence_bp", _MISSING), f"{path}.confidence_bp",
                     SchemaRule.S5, out, basis_points=True)

    for attribute, set_name in _CLAIM_VOCABULARY.items():
        if attribute in fields:
            _check_vocabulary(getattr(claim, attribute, _MISSING), f"{path}.{attribute}",
                              set_name, vocabulary, out)

    if "certainty" in fields:
        allowed = {member.value for member in DateCertainty}
        certainty = getattr(claim, "certainty", _MISSING)
        if certainty is not _MISSING and not isinstance(certainty, DateCertainty) \
                and certainty not in allowed:
            out.append(SchemaViolation(
                rule=SchemaRule.S3, field=f"{path}.certainty",
                detail=f"{certainty!r} is not a DateCertainty "
                       f"({', '.join(sorted(allowed))})"))

    if "is_conditional" in fields:
        flag = getattr(claim, "is_conditional", _MISSING)
        if not isinstance(flag, bool):
            out.append(SchemaViolation(
                rule=SchemaRule.S2, field=f"{path}.is_conditional",
                detail=f"expected a literal bool, got {type(flag).__name__} — truthiness "
                       "coercion is how a conditional promise becomes a false overdue"))

    due = getattr(claim, "due", _MISSING) if "due" in fields else _MISSING
    if due is not _MISSING and due is not None and not isinstance(due, BaseModel):
        out.append(SchemaViolation(
            rule=SchemaRule.S2, field=f"{path}.due",
            detail=f"expected a ResolvedDate or nothing, got {type(due).__name__} — a bare "
                   "timestamp cannot say whether it came from a stated date or from "
                   "'pretty soon', and the proximity term reads the two the same way"))
    elif due is not _MISSING and due is not None:
        #: A nested `ResolvedDate` earns exactly the checks its own fields declare — a receipt
        #: and a readable certainty band — so it recurses through this same function rather
        #: than through a second copy that would be maintained to a different standard.
        spans.extend(_check_claim(due, f"{path}.due", vocabulary, out, stage=stage))

    return spans


def _check_fields(result: ExtractionResult, vocabulary: ExtractionVocabulary,
                  absent: frozenset[str], out: list[SchemaViolation], *,
                  stage: ValidationStage) -> list[EvidenceSpan]:
    """S-2, S-3, S-4 and S-5 over every present field. Returns every span the claims carry."""
    carried: list[EvidenceSpan] = []
    for name in DECLARED_FIELDS:
        if name in absent:
            continue
        value = getattr(result, name)
        shape, element = _shape_of(ExtractionResult.model_fields[name].annotation)

        if shape is _Shape.TEXT:
            if not isinstance(value, str) or not value.strip():
                out.append(SchemaViolation(
                    rule=SchemaRule.S2, field=name,
                    detail=f"expected non-empty text, got {_echo(value)}"))
            elif name in _RESULT_VOCABULARY:
                _check_vocabulary(value, name, _RESULT_VOCABULARY[name], vocabulary, out)

        elif shape is _Shape.COUNT:
            _check_score(value, name, SchemaRule.S5, out, basis_points=False)

        elif shape is _Shape.TEXT_LIST:
            if not _is_sequence(value):
                out.append(SchemaViolation(
                    rule=SchemaRule.S2, field=name,
                    detail=f"expected a list of strings, got {type(value).__name__}"))
                continue
            for index, entry in enumerate(value):
                if not isinstance(entry, str) or not entry.strip():
                    out.append(SchemaViolation(
                        rule=SchemaRule.S2, field=f"{name}[{index}]",
                        detail=f"expected non-empty text, got {_echo(entry)} — a blank entry "
                               "renders as a blank line and counts in every tally above"))

        elif shape is _Shape.MODEL:
            # Pydantic has already coerced a conforming mapping into the model by the time this
            # runs, so anything still un-coerced is a shape the contract refused — reported
            # here rather than swallowed, because S-2's whole job is to say WHICH field broke.
            if not isinstance(value, element):
                out.append(SchemaViolation(
                    rule=SchemaRule.S2, field=name,
                    detail=f"expected a {element.__name__} object, got "
                           f"{type(value).__name__}"))

        elif shape is _Shape.MODEL_LIST:
            if not _is_sequence(value):
                out.append(SchemaViolation(
                    rule=SchemaRule.S2, field=name,
                    detail=f"expected a list of {element.__name__}, got "
                           f"{type(value).__name__}"))
                continue
            for index, entry in enumerate(value):
                path = f"{name}[{index}]"
                if not isinstance(entry, element):
                    out.append(SchemaViolation(
                        rule=SchemaRule.S2, field=path,
                        detail=f"expected {element.__name__}, got {type(entry).__name__}"))
                    continue
                carried.extend(_check_claim(entry, path, vocabulary, out, stage=stage))

        elif shape is _Shape.MAPPING_LIST:
            if not _is_sequence(value):
                out.append(SchemaViolation(
                    rule=SchemaRule.S2, field=name,
                    detail=f"expected a list of objects, got {type(value).__name__}"))
                continue
            for index, entry in enumerate(value):
                if not isinstance(entry, Mapping):
                    out.append(SchemaViolation(
                        rule=SchemaRule.S2, field=f"{name}[{index}]",
                        detail=f"expected an object, got {type(entry).__name__}"))
                    continue
                for key in entry:
                    if not isinstance(key, str):
                        out.append(SchemaViolation(
                            rule=SchemaRule.S2, field=f"{name}[{index}]",
                            detail=f"key {_echo(key)} is not a string — a non-string key makes "
                                   "the JSON round-trip and any content address unstable"))

        elif shape is _Shape.BP_MAPPING:
            if not isinstance(value, Mapping):
                out.append(SchemaViolation(
                    rule=SchemaRule.S2, field=name,
                    detail=f"expected a mapping of field name to basis points, got "
                           f"{type(value).__name__}"))
                continue
            for key, score in value.items():
                if not isinstance(key, str) or not key.strip():
                    out.append(SchemaViolation(
                        rule=SchemaRule.S2, field=name,
                        detail=f"key {_echo(key)} is not a field name"))
                    continue
                if key not in DECLARED_FIELDS:
                    out.append(SchemaViolation(
                        rule=SchemaRule.S3, field=f"{name}[{key!r}]",
                        detail=f"{key!r} is not a field of ExtractionResult — a confidence "
                               "keyed on a name the schema does not carry is the "
                               "extractor-writes-one-name-reader-reads-another failure, and "
                               "nothing downstream would ever read it"))
                    continue
                _check_score(score, f"{name}[{key!r}]", SchemaRule.S5, out, basis_points=True)

        else:
            out.append(SchemaViolation(
                rule=SchemaRule.S2, field=name,
                detail=f"the schema declares {ExtractionResult.model_fields[name].annotation!r}, "
                       "a shape L1.5.6 has no rule for — extend the validator with the field "
                       "rather than letting the newest field be the unchecked one"))

    return carried


def _check_evidence_index(result: ExtractionResult, carried: Sequence[EvidenceSpan],
                          absent: frozenset[str], out: list[SchemaViolation], *,
                          stage: ValidationStage) -> None:
    """S-7 · `all_evidence` contains every span the claims carry.

    `all_evidence` is not a summary — it is the list ALG-08 (L1.5.1) walks to verify spans in
    one pass. A span attached to a claim but missing from it is therefore never checked against
    source text, so the claim ships with `verified=False` and NOTHING reports it: V-5 counts
    unverified spans in `evidence_refs`, and this one was never a candidate. That is a
    fabricated quote surviving the entire anti-hallucination mechanism by being left out of an
    index, which is why the check is here and not left to a reviewer.

    The reverse direction is deliberately allowed. `ExtractionResult.evidence_from_claims` says
    it in its own docstring: comparing the two is how you find spans an extractor asserted but
    attached to no claim, and such a span is unattributed rather than invalid.
    """
    if "all_evidence" in absent:
        return
    index = getattr(result, "all_evidence")
    if not _is_sequence(index):
        return                                       # S-2 already reported the shape
    known = {span for span in index if isinstance(span, EvidenceSpan)}
    for position, span in enumerate(index):
        if isinstance(span, EvidenceSpan):
            _check_unstamped(span, f"all_evidence[{position}]", out, stage=stage)
    missing = [span for span in carried if span not in known]
    if not missing:
        return
    out.append(SchemaViolation(
        rule=SchemaRule.S7, field="all_evidence",
        detail=f"{len(missing)} span(s) carried by a claim are not in all_evidence, starting "
               f"with {_echo(missing[0].quote)} at {missing[0].source_ref} — ALG-08 walks this "
               "list, so a span left out of it is never verified and never reported unverified"))


def _check_open_lane_cap(result: ExtractionResult, absent: frozenset[str],
                         out: list[SchemaViolation]) -> None:
    """S-8 · ADVISORY. The open lane ran over its per-extraction cap.

    Advisory rather than blocking on the contract's own reasoning: enforcing the cap by
    refusing the extraction would let one over-eager extractor destroy an entire message, which
    is the failure the open lane was built to end. Reported anyway, because a profile that
    consistently overruns it is a prompt problem, and the weekly discovery report is far too
    late a place to notice a shape.
    """
    if "unclassified_observations" in absent:
        return
    observations = getattr(result, "unclassified_observations")
    if not _is_sequence(observations) or len(observations) <= MAX_UNCLASSIFIED_PER_EXTRACTION:
        return
    out.append(SchemaViolation(
        rule=SchemaRule.S8, field="unclassified_observations",
        detail=f"{len(observations)} observations exceed the per-extraction cap of "
               f"{MAX_UNCLASSIFIED_PER_EXTRACTION} — advisory only: the cap is a prompt "
               "instruction, and failing the extraction over it would destroy the message"))


def validate_extraction_schema(
        result: ExtractionResult, *, vocabulary: ExtractionVocabulary,
        stage: ValidationStage = ValidationStage.EXTRACTOR_OUTPUT) -> SchemaReport:
    """L1.5.6 · does this extraction conform to the closed schema? Returns a report, never raises.

    Runs all eight checks and reports EVERY violation, each naming the field path that broke
    it. Nothing is repaired, nothing is coerced and the argument is never mutated: a caller
    that logs the extraction after a refusal must log what it actually validated.

    `vocabulary` has no default on purpose — see `ExtractionVocabulary`. It is the caller's job
    to pass the one true set from `capture/semantic/vocabulary.py`, so that this unit and the
    prompt that produced the extraction can never disagree about what the model was allowed to
    say.

    Order is presence first and everything else afterwards, with fields that failed S-1 skipped
    by the later checks: a missing `commitments` is one defect, and reporting it four times
    turns a diagnosis into a wall.

    S-9 is the one rule here that is about a span's CONTENT rather than its shape, and it is
    here because this is the seam an extraction crosses before anything reads it: `verified` is
    the only field an extractor can fill in that asserts a downstream unit's conclusion, so the
    place to refuse it is the place the extraction arrives.

    `stage` is what tells S-9 which seam it is standing at, and it is the only rule the value
    changes. It defaults to `EXTRACTOR_OUTPUT` — the fail-closed reading, because an object
    whose provenance a caller has not thought about is an unchecked one far more often than a
    graded one, and a forgotten keyword must not be a way past the anti-hallucination lock. Pass
    `POST_VERIFICATION` for exactly one kind of object: the `ExtractionResult` that
    `spans.apply_verdicts` returned. That result legitimately carries `verified=True` on every
    span ALG-08 grounded, so validating it at the arrival stage rejects a CORRECTLY verified
    extraction and reports it as an extractor stamping its own receipts — the right rule blaming
    the wrong unit. The ordering is one-way and is stated on `ValidationStage`: arrival, then
    ALG-08, then post-verification. Nothing here repairs the flag at either stage.

    What this does NOT establish, stated because the boundary is the point: that a quote
    appears in the source (ALG-08, `spans.py`), that a date window is right (ALG-09,
    `dates.py`), that an amount was parsed correctly (ALG-10, `money.py`), or that no
    fractional number is hiding in the untyped open lanes (V-7 at the publication gate, which
    scans the SERIALIZED signal — the one place that can see the whole object). A conforming
    extraction is well-shaped, not yet true.
    """
    violations: list[SchemaViolation] = []
    absent = _check_presence(result, violations)
    _check_forbidden(result, violations)
    carried = _check_fields(result, vocabulary, absent, violations, stage=stage)
    _check_evidence_index(result, carried, absent, violations, stage=stage)
    _check_open_lane_cap(result, absent, violations)
    violations.sort(key=lambda violation: _RULE_ORDER[violation.rule])
    return SchemaReport(violations=tuple(violations))


__all__ = ["ARRIVAL_ONLY_RULES", "DECLARED_FIELDS", "NON_BLOCKING_RULES",
           "ExtractionVocabulary", "SchemaReport", "SchemaRule", "SchemaViolation",
           "ValidationStage", "validate_extraction_schema"]
