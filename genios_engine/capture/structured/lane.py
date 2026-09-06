"""L1.3.9-U5 · THE STRUCTURED LANE, end to end — one call, no model, S-1..S-9 for real.

`mapper.py` builds an `ExtractionResult` out of a typed CRM/DB/calendar row (ALG-21) and
`targets.py` closes its field names. Neither had a production caller, and the mapper's own
module docstring recorded the reason it could not have one:

    GAP FLAG (cross-doc): doc 04's closed profile set is `email | chat | transcript | document |
    crm_note` and contains no `structured` member, so an extraction from this lane fails S-3
    against a vocabulary built strictly from that list.

That gap is closed — `capture/semantic/vocabulary.py::EXTRACTION_PROFILE` now admits
`structured`, which is where the mapper's comment said the fix belonged — and this module is
what turns that from a fact about a frozenset into a lane that runs. Before it, the only thing
validating a structured extraction was a test that hand-wrote the six closed sets beside the
real ones: a lane asserted against an INVENTED vocabulary passes forever and proves nothing,
because the copy in the test is the copy that gets updated.

WHAT THIS UNIT IS
-----------------
One public callable, `run_structured_lane`, and it is the whole passage of one structured
object:

1. **sift** — `targets.sift_mapping_targets`. Every declared name the graph cannot be queried by
   is removed and re-expressed as a typed `UnclassifiedObservation`;
2. **map** — `mapper.map_to_extraction` over the SIFTED mapping, carrying those observations, so
   a refused name appears in the extraction's open lane and in none of its typed fields;
3. **validate** — `validate_extraction_schema` at `structured_validation_stage()`
   (`POST_VERIFICATION`: every span this lane carries was set by ALG-08 itself, which is exactly
   what that stage names) against `structured_vocabulary()` — `ExtractionVocabulary` built from
   `capture/semantic/vocabulary.py::vocabulary_sets()`, THE closed set, with no second copy;
4. **persist the discoveries** — `capture_unclassified`, the open lane's one entry point, when a
   store is wired. `None` still closes the names; it only means they are not kept for review.

ZERO LLM, STRUCTURALLY
----------------------
There is no client parameter on this function and no import of one anywhere beneath it. That is
the guarantee in its strongest available form: a lane that took a client and promised not to use
it could break the promise in a later edit and nothing would fail. `tests/capture/structured/`
proves it the other way round too, by driving the pipeline with a client that RAISES on contact
— stricter than a fake with no canned answers, because there is no count to be off by and no way
for a swallowed exception to look like a zero.

WHY A FAILURE HERE IS A RETURN VALUE AND NOT AN EXCEPTION
---------------------------------------------------------
`map_to_extraction` raises `StructuredMappingError` when a mapping has drifted from the
provider's schema, and doc 03 is right that it should: writing a null would make schema drift
and a genuinely empty column indistinguishable. But this function runs on the INGESTION path,
where L1's rule is park-never-drop — `capture/pipeline.py` already applies it to the semantic
lane, where "an extraction that failed does NOT fail the capture". So the drift is caught here
and returned as `failure`, and `fields` — the shipped projection L2 commits — is produced by the
sift and is therefore unaffected by whether an extraction could be built beside it. A CRM object
never stops landing because its close-date column changed shape.

A schema violation is the same shape of answer for a different reason: this lane builds every
field of the result itself, so a blocking violation is a defect in `mapper.py` or in this file
and never in the customer's data. It is logged at ERROR, the extraction is withheld rather than
published (an invalid extraction reaching S3 is worse than none), and `schema` carries the exact
rule and field path. `tests/capture/structured/test_lane.py` asserts `conforms` over every
registered mapping, so that defect is caught in CI rather than in a log.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from genios_engine.capture.semantic.open_lane import (OpenLaneCapture, OpenLaneStore,
                                                      capture_unclassified)
from genios_engine.capture.semantic.vocabulary import vocabulary_sets
from genios_engine.capture.validate.schema import (ExtractionVocabulary, SchemaReport,
                                                   validate_extraction_schema)
from genios_engine.contracts.extraction import ExtractionResult

from genios_engine.capture.validate.authority import AuthorityWeight

from .mapper import (StructuredMappingError, absent_fields, map_to_extraction,
                     mapped_field_confidence, structured_authority,
                     structured_source_index, structured_validation_stage)
from .registry import StructuredMapping
from .targets import (RefusedTarget, object_text, refused_targets_of, sift_mapping_targets)

log = logging.getLogger(__name__)


def structured_vocabulary() -> ExtractionVocabulary:
    """The closed sets S-3 checks this lane against — the real ones, from `vocabulary.py`.

    `ExtractionVocabulary` has no default and will not get one, so SOMEBODY has to name the sets;
    this is the one place the structured lane does it. A function rather than a module constant
    because the frozensets are curated by a human and promoted with a version bump: building the
    object per call costs six attribute reads and means a promotion cannot be shadowed by a value
    captured at import time.

    `vocabulary_sets()`' keys are exactly `ExtractionVocabulary`'s six field names — asserted in
    `tests/capture/semantic/test_vocabulary.py` — so the `**` is a pairing that cannot silently
    mis-associate two frozensets of strings that no type checker can tell apart.
    """
    return ExtractionVocabulary(**vocabulary_sets())


@dataclass(frozen=True)
class StructuredLaneOutcome:
    """What the lane did with one object: what L2 commits, what S3 reads, and what was refused.

    `fields` is never None and never depends on the extraction succeeding. It is the shipped
    projection — the one `commit_structured` writes as facts — and separating it from `result` is
    what keeps a drifted close-date column from costing a customer their whole deal record.
    """

    #: `target -> raw value` for every accepted name this object carried. What L2 commits.
    fields: Mapping[str, Any]
    #: The extraction, or None when the mapping drifted or the result did not conform.
    result: ExtractionResult | None
    #: S-1..S-9 over `result`. Empty and conforming when there is no result to validate.
    schema: SchemaReport
    #: Names the lane would not write, each naming its mapping and its column.
    refused: tuple[RefusedTarget, ...] = ()
    #: What the open lane stored. Empty when no store was wired, which is the default.
    capture: OpenLaneCapture = OpenLaneCapture()
    #: Why there is no `result`, in one line. None when there is one.
    failure: str | None = None
    #: ALG-08's coordinate system for this object: `source_ref -> the text its spans quote`.
    #: Published rather than recomputed because a consumer that rebuilds it from the raw object
    #: has to re-derive `_render`, and two renderings put one field's spans in two coordinate
    #: systems — which is the one failure `structured_source_index` exists to make impossible.
    source_index: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    #: Doc 03 L1.3.9 step 5: mapping TARGET -> 10000bp. A typed field is not a guess. Beside the
    #: extraction rather than inside it because S-3 refuses keys that are not `ExtractionResult`
    #: fields — see `mapper.mapped_field_confidence`.
    field_confidence: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    #: The declared source columns this object carried NO usable value for, in mapping order.
    #: Doc 03's first failure mode is a mapping drifting from the provider's schema into
    #: silently-empty fields; a column that shows up here on EVERY object is that drift, and
    #: before this was published nothing on the request path could see it.
    absent: tuple[str, ...] = ()
    #: ALG-14's authority for this object, carrying its own basis — never a hardcoded 4.
    authority: AuthorityWeight | None = None

    @property
    def extracted(self) -> bool:
        """True when a conforming extraction came out of this object."""
        return self.result is not None

    #: Just the refused NAMES, in mapping order — `targets.refused_targets_of`'s answer, which
    #: is the form a log line, a metric and a config diff all want. Carried rather than
    #: recomputed at each of those call sites, which is the reason that accessor exists.
    refused_targets: tuple[str, ...] = ()


def run_structured_lane(mapping: StructuredMapping, raw_fields: Mapping[str, Any], *,
                        org_id: str, event_id: str, eval_time: datetime, tz: str = "UTC",
                        locale: str | None = None,
                        open_lane: OpenLaneStore | None = None) -> StructuredLaneOutcome:
    """L1.3.9-U5 · one registered mapping plus one source object -> everything downstream needs.

    `eval_time` is required and has no default: it is the clock ALG-09 resolves every typed date
    against and the clock the open lane stamps its rows with, and a wall-clock read inside this
    function would make a replay of a March object a different extraction from the original.
    `tz` is the ORG's timezone, which decides which calendar day a typed instant falls on; both
    are handed straight to `map_to_extraction`, which is the only thing here that uses them.

    `open_lane` is optional and behaves exactly as the semantic lane's does: absent, the refused
    names are still removed and still ride on the extraction's typed open lane, they are simply
    not persisted for review — so the vocabulary cannot grow from evidence, but nothing invented
    reaches storage either way.

    Raises nothing that the ingestion path has to catch. See the module docstring for why.
    """
    sifted = sift_mapping_targets(mapping, raw_fields)
    # The four descriptions of this object that do not depend on the extraction succeeding, and
    # therefore must be produced BEFORE the two early returns below. A drifted close-date column
    # is exactly when `absent` matters most, and a lane that only published it on the happy path
    # would go blind in the one case it was built to explain.
    refused_names = tuple(refused_targets_of(sifted))
    absent = absent_fields(mapping, raw_fields)
    confidence = mapped_field_confidence(mapping, raw_fields)
    source_index = structured_source_index(mapping, raw_fields)
    authority = structured_authority(mapping.source, mapping.object_type)

    try:
        result: ExtractionResult | None = map_to_extraction(
            sifted.mapping, raw_fields, eval_time=eval_time, tz=tz, locale=locale,
            unclassified=sifted.observations)
    except StructuredMappingError as exc:
        log.warning("structured lane: %s did not map %s (%s)",
                    mapping.mapping_id, event_id, exc)
        return StructuredLaneOutcome(fields=sifted.fields, result=None, schema=SchemaReport(),
                                     refused=sifted.refused, failure=str(exc),
                                     source_index=source_index, field_confidence=confidence,
                                     absent=absent, authority=authority,
                                     refused_targets=refused_names)

    report = validate_extraction_schema(result, vocabulary=structured_vocabulary(),
                                        stage=structured_validation_stage())
    if not report.conforms:
        # A defect in this lane, never in the customer's row: every field of `result` was built
        # by code in this package. Withheld rather than published, and named precisely enough
        # that the failing rule and field are in the log line that reports it.
        detail = "; ".join(f"{violation.rule.value} on {violation.field}"
                           for violation in report.blocking_violations)
        log.error("structured lane: %s produced a non-conforming extraction for %s (%s)",
                  mapping.mapping_id, event_id, detail)
        return StructuredLaneOutcome(fields=sifted.fields, result=None, schema=report,
                                     refused=sifted.refused, failure=detail,
                                     source_index=source_index, field_confidence=confidence,
                                     absent=absent, authority=authority,
                                     refused_targets=refused_names)

    capture = OpenLaneCapture()
    if open_lane is not None:
        capture = capture_unclassified(result, org_id=org_id, event_id=event_id,
                                       source_text=object_text(raw_fields),
                                       eval_time=eval_time, store=open_lane)
    return StructuredLaneOutcome(fields=sifted.fields, result=result, schema=report,
                                 refused=sifted.refused, capture=capture,
                                 source_index=source_index, field_confidence=confidence,
                                 absent=absent, authority=authority,
                                 refused_targets=refused_names)


__all__ = ["StructuredLaneOutcome", "run_structured_lane", "structured_vocabulary"]
