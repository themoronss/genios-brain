"""L1.3.9-U1 · ALG-21 — a registered field mapping into an `ExtractionResult`. The S2 bypass.

A HubSpot deal already has `amount`, `dealstage` and `closedate` as typed columns. A Stripe
subscription already has `status` and `current_period_end`. A row in the client's own database
already has `plan` and `seats_used`. Rendering those into prose and asking a language model to
read the numbers back out is the most expensive available way to be *less* certain: the model
can get a number wrong, and the column cannot.

So this module is the lane that never calls a model. It takes the mapping (data —
`registry.py`) and the source object's raw fields, and produces the SAME `ExtractionResult`
the semantic lane produces, so that from S3 onward nothing can tell the two apart. That
sameness is the whole point. A CRM-sourced fact and an email-sourced fact have to be
comparable — validated by the same validators, conflict-resolved against each other, scored by
the same importance formula — or they are two parallel pipelines that drift, and the customer's
churn question gets answered from whichever half happened to be wired that quarter.

WHAT A VERIFIED SPAN MEANS FOR A TYPED FIELD
--------------------------------------------
This is the one genuinely new question the lane asks, and it deserves a stated answer rather
than a convention.

For prose, `EvidenceSpan.verified` means "ALG-08 opened the prepared text and found this quote
at these offsets". For a typed field there is no prose to open — so the temptation is to stamp
`verified=True` on a synthesized span and call a typed field its own receipt. **This module does
not do that**, and refusing to is what keeps the flag worth reading.

Instead the lane defines its own coordinate system and then submits to the ordinary check:

* the SOURCE TEXT of a mapped field is the field's own value, rendered to a canonical string
  by `_render` — deterministic, no clock, no locale, no model;
* the `source_ref` is ``structured:<mapping_id>#<source_field>`` (doc 03 L1.3.9 step 4, and the
  prefix `authority.py` already ranks at STRUCTURED_SOURCE);
* the span quotes that text at real offsets into it;
* and the span is then handed to **`spans.verify_span` (ALG-08, L1.5.1)** — the same function,
  unmodified — which slices the source at the stated offsets, compares, and returns the span
  with `verified=True`. Nothing here constructs a span carrying the flag.

`structured_source_index` publishes the map from `source_ref` to that source text, so the check
is repeatable by anyone, forever: a replay, a card renderer, an auditor. A receipt nobody else
can re-check is an assertion, and an assertion is what this whole layer exists to avoid.

Two consequences worth naming:

* The grade is always `SpanVerdict.VERIFIED` — the strongest one — because the quote is a
  literal slice of the text it points into. It is exact by CONSTRUCTION, not by luck, and a
  grade below it means the renderer and the span builder have fallen out of agreement, which is
  a defect and is raised rather than downgraded.
* Schema rule **S-9** ("no span arrived already wearing the checkmark", `validate/schema.py`)
  is therefore satisfied honestly, not worked around: the extraction this module returns must be
  validated at `ValidationStage.POST_VERIFICATION`, and that stage is exactly true of it —
  ALG-08 has run on every span it carries. `structured_validation_stage()` names that so no
  caller has to remember. There is no cross-wave conflict here; the stage parameter W1 already
  built is the seam this lane needs.

PURITY — the decision logic in this module is pure. No clock (`eval_time` is a parameter, and
it is what `ResolvedDate.resolved_against` records so a replay of a March event resolves against
March), no model, no database, no network. No float in any score: every confidence is integer
basis points and every money amount is integer minor units, because ALG-10 owns the arithmetic
and this module owns none of it.

WHAT THIS LANE DOES *NOT* CARRY, stated because the boundary is easy to misread. `string`,
`enum` and `number` fields contribute a receipt but no claim object: `ExtractionResult` has
typed lanes for amounts, dates, commitments, decisions, dependencies and entities, and none for
"a scalar column's value". Those values already travel as `GatedEvent.structured_fields`
(`apply_mapping`, the shipped path L2's `commit_structured` reads), and re-encoding them into
one of the untyped open lanes would create a second copy that drifts from the first. What the
extraction says about them is complete where it counts: their receipt is in `all_evidence`, and
`mapped_field_confidence` states each one at 10000.

CROSS-WAVE CONFLICT — `field_confidence`, doc 03 step 5 vs W1's schema rule S-3
-------------------------------------------------------------------------------
Reported rather than worked around, because the two waves genuinely disagree and only one of
them can be right about what the dict's KEYS are.

* Doc 03 L1.3.9 step 5 says "field_confidence = 10000 for every **mapped field**", and a mapped
  field is a mapping TARGET — `deal.amount`, `deal.stage`. `contracts/extraction.py` echoes it:
  "The structured lane sets every mapped field to 10000." `validate/schema.py`'s own
  `SchemaViolation.field` docstring even uses ``field_confidence['deal.status']`` as its worked
  example of a path, which is a mapping target and nothing else.
* W1's S-3, as built, refuses any `field_confidence` key that is not a field of
  `ExtractionResult` (`schema.py`, `_Shape.BP_MAPPING`, `key not in DECLARED_FIELDS`). Under
  that rule `deal.amount` is a violation and the whole extraction is rejected.

Both readings cannot hold. This module takes W1's, because the alternative is a lane whose every
output fails the layer's own schema validator — and doc 03's own routing sentence is that from S3
onward the two lanes must be validated identically. So `ExtractionResult.field_confidence` is
keyed by RESULT field, and the per-target view doc 03 asks for is published beside it by
`mapped_field_confidence`, which is what G2's "every mapped field carries field_confidence ==
10000" is asserted against. Resolving it properly is one line in whichever wave owns the
disagreement: either S-3 admits dotted target names, or doc 03 step 5 is restated in terms of
result fields. It is not resolvable inside this module, and pretending otherwise by emitting keys
that fail validation would ship a lane that cannot pass S3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo

from genios_engine.capture.validate.authority import (Authority, AuthorityWeight, Provenance,
                                                      weigh_authority)
from genios_engine.capture.validate.dates import resolve_date
from genios_engine.capture.validate.money import parse_money_outcome
from genios_engine.capture.validate.schema import ValidationStage
from genios_engine.capture.validate.spans import SpanVerdict, verify_span
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import (EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.units import Money
from genios_engine.platform.identity import norm_email

from .apply import apply_mapping
from .registry import FieldMap, RelationMap, StructuredMapping, get_mapping
from .targets import ABSENT, render_field as _render, sift_mapping_targets

#: `ExtractionResult.extraction_profile` for this lane, verbatim from doc 03 L1.3.9's STORAGE
#: line ("writes `l1_extraction_results` with `profile_id="structured"`"), so a stored row says
#: which lane produced it and a replay reads it back the same way.
#:
#: GAP FLAG (cross-doc): doc 04's closed profile set is `email | chat | transcript | document |
#: crm_note` and contains no `structured` member, so an extraction from this lane fails S-3
#: against a vocabulary built strictly from that list. Doc 03 states this literal and doc 04
#: does not know about the bypass. The name is kept as doc 03 wrote it — the alternative is
#: filing a CRM row under `crm_note`, which is a lie about a typed column, and filing a
#: database row or a calendar event under it is not even a plausible lie. The caller supplies
#: the vocabulary (`ExtractionVocabulary` has no default, deliberately), so the fix is one
#: member in `capture/semantic/vocabulary.py` when doc 04's module lands.
STRUCTURED_PROFILE = "structured"

#: `prompt_version`. No prompt ran, and the field is required because a replay cannot proceed
#: without knowing what produced the row — so it names the absence rather than borrowing a
#: version from a prompt this lane never used. What actually determines this lane's output is
#: the MAPPING, and that is versioned in `model_snapshot` below.
STRUCTURED_PROMPT_VERSION = "structured-no-prompt"

#: `schema_version`. The shape of `ExtractionResult` itself, which W0 froze at 1. It is part of
#: the `l1_extraction_results` cache key: bump it only when the contract's shape changes, so
#: rows written by older code stay valid for the code that wrote them.
STRUCTURED_SCHEMA_VERSION = "1"

#: Doc 03 L1.3.9 step 5, in the unit the contract uses. A typed field is not a guess.
STRUCTURED_FIELD_CONFIDENCE_BP = 10_000

#: Doc 03 L1.3.9 step 6 — "authority_rank = 4 (structured source of record)". Named as the
#: `Authority` CLASS rather than the integer, because `authority.py` owns the class-to-rank
#: table and a second copy of the digit 4 is a second thing to re-tune. `structured_authority`
#: below is what a caller reads, and it goes through `weigh_authority` so the answer comes from
#: the same cascade every other piece of evidence is ranked by.
STRUCTURED_AUTHORITY = Authority.STRUCTURED_SOURCE

#: A typed column has no attitude. `stance` is required and the closed set is
#: `positive | neutral | cautious | negative | mixed`; anything but neutral would be this lane
#: inventing a sentiment the source never expressed, which is precisely the hallucination the
#: bypass exists to avoid.
STRUCTURED_STANCE = "neutral"

#: `StructuredMapping.intent` -> doc 04's closed intent set. The registry's intent is the
#: EMISSION intent Layer 2 keys on ("pipeline_update", "invoice_event"); the contract's is the
#: illocutionary one ("what is this message doing?"). They are different vocabularies and the
#: translation belongs in exactly one table.
#:
#: The default is `inform`, and it is the right default rather than a shrug: a system of record
#: STATES things. A row changed; the row is telling you so. `schedule` is the one genuine
#: exception — a calendar event is an act of scheduling, and reading it as a bare statement of
#: fact would cost the scheduling lane every calendar move.
STRUCTURED_INTENT: Mapping[str, str] = MappingProxyType({
    "scheduling_move": "schedule",
})
DEFAULT_STRUCTURED_INTENT = "inform"

#: The `related_node_type` values this lane will emit as an `EntityMention`, mapped to doc 04's
#: closed `entity_type` set. A relation to a node type with no entry produces a receipt-bearing
#: edge for L2 (via `apply_relations`, untouched) and no entity mention, rather than a mention
#: carrying a word the vocabulary does not contain — S-3 would reject the whole extraction for
#: it, destroying a good CRM deal over a node type nobody has typed yet.
RELATION_ENTITY_TYPE: Mapping[str, str] = MappingProxyType({
    "person": "person",
    "organization": "organization",
    "company": "organization",
    "vendor": "vendor",
    "product": "product",
})

#: Epoch values at or above this are MILLISECONDS. 10^11 seconds is the year 5138 and 10^11
#: milliseconds is 1973-03-03, so no real timestamp is ambiguous between the two readings —
#: which is what makes a threshold honest here instead of a guess. HubSpot states `closedate`
#: in milliseconds and most SQL drivers hand back seconds; both have to land on the same day.
_EPOCH_MILLISECOND_FLOOR = 10 ** 11

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

#: Re-exported under this module's own name so every `raw_fields.get(field, _ABSENT)` below reads
#: as it always did. THE sentinel, defined once in `targets.py`; two sentinels would each be
#: absent to one half of the lane and present to the other.
_ABSENT = ABSENT


class StructuredMappingError(ValueError):
    """A mapped field arrived and could not be turned into the value the mapping declares.

    Raised rather than written as a null, which is doc 03 L1.3.9's own instruction ("a field
    that maps to nothing raises rather than writing null") and is the difference between a
    mapping that has drifted from the provider's schema and a deal that genuinely has no close
    date. A silent null makes those two indistinguishable, and the first one then hides for as
    long as it takes somebody to notice that a column stopped arriving.

    An ABSENT field is not this. A HubSpot deal omits every property it has no value for, and
    an open deal legitimately has no `closedate`; refusing the whole object over it would drop
    the pipeline this lane exists to carry. Absence is reported by `absent_fields` on the
    coverage side and is not an error here.
    """


@dataclass(frozen=True, slots=True)
class StructuredRoute:
    """L1.3.9-U1 step 1 (LOOKUP) — the routing answer for one structured object, as data.

    A typed record rather than a bare `StructuredMapping | None`, because the interesting half
    of the answer is the NEGATIVE one and it has to be countable. Doc 03's failure table:
    "A structured source is *not* registered -> falls to `needs_extraction`, model runs on JSON
    -> acceptable fallback, but counted — `unmapped_structured` metric". A `None` return cannot
    be counted without every call site remembering to count it, which is how a metric ends up
    reading zero forever.
    """

    source: str
    object_type: str
    mapping: StructuredMapping | None

    @property
    def mapped(self) -> bool:
        """True when the structured lane can carry this object with no model call."""
        return self.mapping is not None

    @property
    def unmapped_structured(self) -> int:
        """Doc 03's metric, per object: 1 when a structured source had no registered mapping.

        An integer rather than a bool so a caller sums it over a sync without a second
        conversion, and so "how many objects paid for an LLM call they did not need?" is one
        `sum(...)` over the routes rather than a filter plus a len.
        """
        return 0 if self.mapped else 1


def structured_authority(source: str, object_type: str) -> AuthorityWeight:
    """Doc 03 L1.3.9 step 6 — the authority of a structured object, from ALG-14's own cascade.

    Not a hardcoded 4. `weigh_authority` is the single ranking function and its tables already
    place `hubspot`, `gcal`, `postgres` and the `structured:` ref prefix at STRUCTURED_SOURCE;
    returning the digit directly here would be a second copy of a table that exists to be
    re-tuned in one place. The returned weight also carries its `basis`, so "why is this a 4?"
    is answerable from the record.
    """
    return weigh_authority(Provenance(
        source=source, object_type=object_type,
        source_ref=f"structured:{source}.{object_type}"))


def structured_validation_stage() -> ValidationStage:
    """Which `ValidationStage` an extraction from this lane must be validated at.

    `POST_VERIFICATION`, and the reason is a statement about this lane rather than a convenience:
    S-9 refuses spans that arrive already carrying `verified=True`, because for the semantic lane
    such a span is the extractor asserting the conclusion ALG-08 exists to reach. Every span this
    module returns was set by `verify_span` — ALG-08 itself, called on a real slice of real source
    text — so the flag here is L1.5.1's signature, which is exactly the condition `POST_VERIFICATION`
    names. Validating at the arrival stage would reject a correctly verified extraction and blame
    the one component that did nothing wrong.

    A function rather than a constant so the answer is impossible to import as a default and then
    apply to an object that has not been through this module.
    """
    return ValidationStage.POST_VERIFICATION


def source_ref_for(mapping_id: str, source_field: str) -> str:
    """``structured:<mapping_id>#<source_field>`` — doc 03 L1.3.9 step 4, verbatim.

    One function so the string is built in exactly one place: the ref is the join key a card
    renderer, an audit row and `authority.py`'s prefix table all read, and two spellings of it
    would silently split one field's evidence into two.
    """
    return f"structured:{mapping_id}#{source_field}"


def structured_source_index(mapping: StructuredMapping,
                            raw_fields: Mapping[str, Any]) -> Mapping[str, str]:
    """`source_ref` -> the source text its spans point into. The lane's coordinate system.

    This is what makes `verified=True` mean something for a typed field: prose spans resolve
    against `PreparedContent.clean_text`, and these resolve against the rendered field value
    published here. Anyone holding an extraction from this lane and the raw object can re-run
    `verify_span` and get the same verdict — which is the definition of a receipt, as opposed
    to an assertion.

    Every declared field and every declared relation gets an entry, and fields that are absent
    or blank get none: a key mapping to an empty string would be a coordinate system for a
    receipt that cannot exist. Read-only, because a caller that edits it has moved the
    coordinates the stored spans were measured in.
    """
    index: dict[str, str] = {}
    for field_map in mapping.fields:
        text = _render(raw_fields.get(field_map.source_field, _ABSENT))
        if text is not None:
            index[source_ref_for(mapping.mapping_id, field_map.source_field)] = text
    for relation in mapping.relations:
        text = _render(raw_fields.get(relation.source_field, _ABSENT))
        if text is not None:
            index[source_ref_for(mapping.mapping_id, relation.source_field)] = text
    return MappingProxyType(index)


def route_structured(source: str, object_type: str) -> StructuredRoute:
    """L1.3.9-U1 step 1 — is this structured object carried by a registered mapping?

    The registry lookup and the metric in one answer. `gate.py` S1.5 already short-circuits on
    `has_mapping`; this is the same question asked in a form that can also be counted, so
    `unmapped_structured` is a field on a returned value rather than a global counter somebody
    has to remember to bump.
    """
    return StructuredRoute(source=source, object_type=object_type,
                           mapping=get_mapping(source, object_type))


def map_to_extraction(mapping: StructuredMapping, raw_fields: Mapping[str, Any], *,
                      eval_time: datetime, tz: str = "UTC", locale: str | None = None,
                      unclassified: Sequence[UnclassifiedObservation] = ()) -> ExtractionResult:
    """ALG-21 · a registered mapping plus one source object -> an `ExtractionResult`. No model.

    The steps are doc 03 L1.3.9's, in its order:

    2. APPLY      every declared field whose source field is present and non-blank is mapped.
    3. NORMALIZE  `money` goes through ALG-10 (`validate/money.py`) and `timestamp` through
                  ALG-09 (`validate/dates.py`) — the SAME normalizers the extracted path uses.
                  There is no second implementation of either in this file, and a re-read that
                  finds one has found a bug.
    4. EVIDENCE   one span per mapped field, graded by ALG-08 against the field's own rendered
                  value. See the module docstring for what that means and why it is not a stamp.
    5. CONFIDENCE `field_confidence[target] = 10000` for every mapped field.
    6. AUTHORITY  STRUCTURED_SOURCE (rank 4), from `weigh_authority` rather than a literal.

    `eval_time` is required and has no default. It is the clock `resolve_date` resolves against
    and is copied onto every `ResolvedDate` as `resolved_against`, so replaying a March object
    resolves its dates against March instead of against today — and so this module reads no
    clock of its own, which is what makes two runs over the same object byte-identical.

    `tz` is the ORG's timezone and it decides which CALENDAR DAY a typed instant falls on:
    a `closedate` of 2026-11-30T19:30:00Z is 30 November in London and 1 December in Delhi, and
    a deadline on the wrong day is a card that fires late. `locale` is ALG-10's, for amounts
    whose literal carries a symbol and an ambiguous separator.

    Raises `StructuredMappingError` when a field ARRIVED and could not be normalised, and when a
    non-empty object matches none of the mapping's declared fields at all — the shape of schema
    drift. It never raises for a field that is simply absent.

    `input_tokens` and `output_tokens` are 0, which is not bookkeeping: `is_structured_lane`
    reads exactly those two, and a mapping that reported tokens it never spent would make the
    bypass look as expensive as the thing it exists to avoid.

    `unclassified` is what `capture/structured/targets.py` refused — the mapping's own target
    names that no consumer can address. They ride on the extraction rather than beside it because
    `ExtractionResult.unclassified_observations` IS the typed open lane, and
    `capture_unclassified` reads that field and no other; a refused name handed back in a second
    return value is a name every caller has to remember to persist. Their spans are indexed into
    `all_evidence` for the same reason every other span is: S-7 refuses a claim whose receipt is
    not in the list ALG-08 walks.
    """
    if not isinstance(raw_fields, Mapping):
        raise TypeError("raw_fields must be a mapping of source field name to value")

    amounts: list[Money] = []
    dates: list[Any] = []
    entity_mentions: list[EntityMention] = []
    all_evidence: list[EvidenceSpan] = []
    mapped_any = False

    for field_map in mapping.fields:
        raw_value = raw_fields.get(field_map.source_field, _ABSENT)
        text = _render(raw_value)
        if text is None:
            continue
        mapped_any = True
        span = _grounded_span(source_ref_for(mapping.mapping_id, field_map.source_field), text)
        all_evidence.append(span)
        if field_map.value_type == "money":
            amounts.append(_money_of(field_map, raw_fields, text, locale=locale))
        elif field_map.value_type == "timestamp":
            dates.append(resolve_date(_calendar_day(field_map, raw_value, tz=tz),
                                      eval_time=eval_time, tz=tz, evidence=[span]))

    for relation in mapping.relations:
        for mention in _mentions_of(mapping, relation, raw_fields):
            mapped_any = True
            entity_mentions.append(mention)
            all_evidence.extend(mention.evidence)

    for observation in unclassified:
        all_evidence.extend(span for span in observation.evidence if span not in all_evidence)

    if raw_fields and not mapped_any:
        raise StructuredMappingError(
            f"{mapping.mapping_id}: none of the {len(mapping.fields)} declared fields and "
            f"{len(mapping.relations)} declared relations matched this object's "
            f"{len(raw_fields)} keys — the mapping has drifted from the provider's schema, and "
            "emitting an extraction with no fields would report that as a quiet object")

    return ExtractionResult(
        intent=STRUCTURED_INTENT.get(mapping.intent, DEFAULT_STRUCTURED_INTENT),
        topics=list(mapping.tags),
        stance=STRUCTURED_STANCE,
        entity_mentions=entity_mentions,
        amounts=amounts,
        dates_mentioned=dates,
        field_confidence=_result_field_confidence(mapping, amounts, dates, entity_mentions),
        all_evidence=all_evidence,
        model_snapshot=f"mapping:{mapping.mapping_id}",
        prompt_version=STRUCTURED_PROMPT_VERSION,
        schema_version=STRUCTURED_SCHEMA_VERSION,
        extraction_profile=STRUCTURED_PROFILE,
        input_tokens=0,
        output_tokens=0,
        unclassified_observations=list(unclassified),
    )


def mapped_field_confidence(mapping: StructuredMapping,
                            raw_fields: Mapping[str, Any]) -> Mapping[str, int]:
    """Doc 03 L1.3.9 step 5, in the keys doc 03 states: mapping TARGET -> 10000 basis points.

    "A typed field is not a guess." Every field this object actually carried a value for is at
    full confidence, and there is no gradient: a column either arrived or it did not, and a CRM
    stage that arrived is not 8700 confident. Marking one at anything below 10000 would let a
    model's opinion about the same fact outrank the column it was read out of, which is the
    whole failure the bypass exists to end.

    This lives beside `ExtractionResult.field_confidence` rather than inside it because W1's
    schema rule S-3 refuses keys that are not fields of `ExtractionResult` — see the module
    docstring's CROSS-WAVE CONFLICT section for the disagreement and why it is reported instead
    of patched. Read-only, and derived rather than stored, so it can never drift from the
    mapping and the object it describes.

    Absent and blank fields are omitted, not zeroed. Zero basis points is a statement that we
    looked and found nothing worth believing; a column that did not arrive is a statement about
    the payload, and `absent_fields` is where that is said.
    """
    stated: dict[str, int] = {}
    # The SIFTED fields. This is the one function besides `apply_mapping` that publishes TARGET
    # names, and a refused name stating full confidence in itself here would be the same hole
    # reopened one function over — see `capture/structured/targets.py`.
    for field_map in sift_mapping_targets(mapping, raw_fields).mapping.fields:
        if _render(raw_fields.get(field_map.source_field, _ABSENT)) is not None:
            stated[field_map.target] = STRUCTURED_FIELD_CONFIDENCE_BP
    return MappingProxyType(stated)


def _result_field_confidence(mapping: StructuredMapping, amounts: list[Money],
                             dates: list[Any],
                             entity_mentions: list[EntityMention]) -> dict[str, int]:
    """`ExtractionResult.field_confidence`, keyed by RESULT field so it passes S-3.

    A result field is stated at 10000 exactly when everything in it came from a typed column or
    from the mapping's own versioned declaration:

    * `amounts`, `dates_mentioned`, `entity_mentions` — read out of typed columns;
    * `intent` and `topics` — the mapping's declared `intent` and `tags`, which are versioned
      configuration a human wrote, not something inferred from this object.

    `stance` is deliberately ABSENT even though this lane always emits `neutral`. That value is
    OUR reading of what a typed record expresses, not something the source stated, and claiming
    full confidence in our own convention is the one place this function could quietly become a
    lie. An empty result field is omitted for the same reason: a confidence about nothing is a
    number a reader would take as a claim.
    """
    stated: dict[str, int] = {"intent": STRUCTURED_FIELD_CONFIDENCE_BP}
    if mapping.tags:
        stated["topics"] = STRUCTURED_FIELD_CONFIDENCE_BP
    if amounts:
        stated["amounts"] = STRUCTURED_FIELD_CONFIDENCE_BP
    if dates:
        stated["dates_mentioned"] = STRUCTURED_FIELD_CONFIDENCE_BP
    if entity_mentions:
        stated["entity_mentions"] = STRUCTURED_FIELD_CONFIDENCE_BP
    return stated


def absent_fields(mapping: StructuredMapping,
                  raw_fields: Mapping[str, Any]) -> tuple[str, ...]:
    """The declared source fields this object carried no usable value for, in mapping order.

    Doc 03's first failure mode is "a mapping drifts from the provider's schema -> silently
    empty fields". `map_to_extraction` refuses the total case (nothing matched) and tolerates
    the partial one, because a partly-populated object is the normal state of a CRM record.
    This is how the partial case stops being silent: a column that disappears shows up here on
    every object from that source, which is a pattern, while an open deal with no close date
    shows up on some and is not.

    Blank and whitespace-only values count as absent — a typed field holding `""` states
    nothing, and treating it as present would put an unquotable receipt in the extraction.

    EVERY declared source column, not only the ones in `mapping.fields`. A mapping declares
    three kinds of column and depends on all three: a field's `source_field`, a money field's
    `currency_field`, and a relation's `source_field`. Walking only the first left this function
    blind in precisely the case it exists for — a HubSpot deal whose `deal_currency_code` column
    went away raises `StructuredMappingError` and loses the WHOLE extraction (`FieldMap` refuses
    to default a currency, correctly), and `absent_fields` answered `()`. The one column
    responsible for the failure was the one column this could not name, so an operator reading
    the trace saw an empty absence list beside a lane that had just refused the object.

    Order is mapping order and each name appears ONCE: a currency column shared by two money
    fields is one missing column, not two, and a caller counting names would otherwise read one
    drift as two.

    ALTERNATE RELATION SHAPES ARE NOT ABSENCES. A mapping may declare the same edge twice to
    accept either of a provider's two payload shapes — `hubspot.deal.v1` names both
    `contact_email` and `contacts` for one `person -involves-> deal` edge, and a real deal
    carries exactly one of them. Reporting the unused alternate would put a name in this tuple
    on EVERY object of that source, which is the exact signature this function uses to mean
    "drift", so the one thing it is read for would be noise from the first row. A relation
    column is therefore absent only when no sibling declaring the SAME edge arrived either.
    """
    missing: list[str] = []
    seen: set[str] = set()

    def _present(source_field: str | None) -> bool:
        return bool(source_field) and _render(raw_fields.get(source_field, _ABSENT)) is not None

    def _note(source_field: str | None) -> None:
        if not source_field or source_field in seen:
            return
        if not _present(source_field):
            seen.add(source_field)
            missing.append(source_field)

    for field_map in mapping.fields:
        _note(field_map.source_field)
        # A fixed `currency` needs no column and cannot be absent; `currency_field` names one.
        _note(field_map.currency_field)

    def _edge(relation) -> tuple[str, str, str, str]:
        return (relation.related_node_type, relation.edge_type,
                relation.direction, relation.identity)

    satisfied = {_edge(r) for r in mapping.relations if _present(r.source_field)}
    for relation in mapping.relations:
        if _edge(relation) not in satisfied:
            _note(relation.source_field)
    return tuple(missing)


# ---------------------------------------------------------------------------------------------
# Rendering — a typed value into the canonical string its span quotes.
#
# `_render` and `_ABSENT` live in `targets.py` and are imported at the top of this module under
# their old names. They had to move: `targets.sift_mapping_targets` mints the receipt for a
# REFUSED target name and this module mints it for an accepted one, and two renderings of the
# same value would put those two spans in coordinate systems that do not agree — which is the
# one failure `structured_source_index` exists to make impossible. `targets.py` is the leaf (it
# imports the registry and nothing else in this package), so the dependency runs one way and
# `apply_mapping` can sift without importing the mapper.
#
# What it guarantees is unchanged and is asserted in `tests/capture/structured/test_targets.py`:
# deterministic and total, so the same value renders the same way on every machine and every
# replay, or the stored offsets stop describing the text they were measured in.
# ---------------------------------------------------------------------------------------------


def _grounded_span(source_ref: str, source_text: str) -> EvidenceSpan:
    """Build a span into `source_text` and have ALG-08 grade it. Nothing here sets `verified`.

    The window starts at the first non-whitespace character and runs at most `MAX_QUOTE_CHARS`,
    which is the contract's cap and exists so that a receipt is something a human checks in a
    glance rather than a wall they skip. A value longer than the cap is quoted at its first 400
    characters — a real, exactly-resolving pointer into a real region of the real value, with
    the whole value still published by `structured_source_index` for anyone who wants the rest.

    The verdict is asserted, not tolerated: the quote is a literal slice of the text it points
    into, so `VERIFIED` is the only grade this can produce. Anything weaker means `_render` and
    this function disagree about the text, and a receipt measured in a coordinate system nobody
    else can reproduce is the exact failure this lane is built to avoid.
    """
    start = len(source_text) - len(source_text.lstrip())
    end = min(len(source_text), start + MAX_QUOTE_CHARS)
    probe = EvidenceSpan(source_ref=source_ref, quote=source_text[start:end],
                         start_offset=start, end_offset=end)
    verdict, graded = verify_span(probe, source_text)
    if verdict is not SpanVerdict.VERIFIED:
        raise StructuredMappingError(
            f"{source_ref}: the synthesized span graded {verdict.value}, not verified — the "
            "field rendering and the span offsets have fallen out of agreement, and a receipt "
            "that does not resolve against its own source text is not a receipt")
    return graded


# ---------------------------------------------------------------------------------------------
# Normalization — ALG-10 for money, ALG-09 for dates. Neither algorithm is reimplemented here;
# this section only puts a typed value into the form those two functions read.
# ---------------------------------------------------------------------------------------------


def _money_of(field_map: FieldMap, raw_fields: Mapping[str, Any], literal: str, *,
              locale: str | None) -> Money:
    """A typed amount -> `Money`, through ALG-10, with the currency the MAPPING declares.

    The mapping states the currency (a column, or a fixed code — `FieldMap.__post_init__`
    refuses a money field that states neither), and ALG-10 reads a currency from the string it
    is given. So the declared code is prefixed onto the literal — `"800000"` becomes
    `"USD 800000"`, which is exactly the `"USD 84,000"` form `contracts/units.py` documents —
    and ALG-10 does all of the arithmetic: the minor-unit exponent, the grouping separators,
    the decimals. This file multiplies nothing.

    When the literal ALREADY carries its own currency (a formatted `"$84,000"` in a text
    column), that reading wins and is CHECKED against the declaration. A disagreement raises: a
    column labelled EUR holding "$84,000" is either a mapping pointing at the wrong currency
    column or a source that has changed under us, and resolving it silently in either direction
    produces a confidently wrong number on the one field that most deserves not to be.

    `as_written` is rebuilt as the source's own literal. The prefixed form is OUR declaration,
    not the source's bytes, and `as_written` exists so a human can see what was actually written
    next to what we made of it.
    """
    declared = field_map.currency
    if field_map.currency_field is not None:
        code = _render(raw_fields.get(field_map.currency_field, _ABSENT))
        if code is None:
            raise StructuredMappingError(
                f"{field_map.source_field} -> {field_map.target}: the mapping names "
                f"{field_map.currency_field!r} as the currency column and this object carries "
                "no value in it. An amount with no currency is not a smaller fact than an "
                "amount with one, it is a different fact, and defaulting it is how a rupee "
                "figure is read as dollars at full confidence")
        declared = code.strip().upper()

    own = parse_money_outcome(literal, locale=locale).money
    if own is not None and own.currency_known:
        if own.currency != declared:
            raise StructuredMappingError(
                f"{field_map.source_field} -> {field_map.target}: the value {literal!r} states "
                f"{own.currency} and the mapping declares {declared} — one of the two is wrong "
                "and neither may quietly win")
        return own

    parsed = parse_money_outcome(f"{declared} {literal}", locale=locale)
    if parsed.money is None:
        raise StructuredMappingError(
            f"{field_map.source_field} -> {field_map.target}: ALG-10 refused "
            f"{literal!r} as {declared} ({parsed.failure.value if parsed.failure else 'unknown'})"
            " — a typed amount that will not normalise is schema drift, and writing null here "
            "would empty the field silently")
    return Money(minor_units=parsed.money.minor_units, currency=parsed.money.currency,
                 as_written=literal)


def _calendar_day(field_map: FieldMap, raw_value: Any, *, tz: str) -> str:
    """A typed timestamp -> the ISO calendar day ALG-09 resolves, in the ORG's timezone.

    Doc 03 L1.3.9 step 3 is explicit that date fields go through L1.5.2 "exactly like extracted
    ones", so this function does no resolving: it renders, and `resolve_date` runs its cascade
    over the result exactly as it does over a phrase a human typed. Row 1 (explicit date) fires,
    the certainty comes back EXACT, and `resolved_against` records the caller's `eval_time` — so
    a structured date and a prose date are the same kind of object, produced by the same code,
    and ALG-17 cannot tell which lane a deadline came from.

    The instant's TIME OF DAY is not carried into the window, because ALG-09's grain is the
    calendar day and this module may not add a second resolver beside it. It is not lost: the
    span's quote is the raw literal, `structured_source_index` publishes it, and a consumer that
    needs the exact minute reads the source object it already has. What matters for a deadline —
    which day — is decided here, in the org's zone rather than in UTC, because 2026-11-30T19:30Z
    is 30 November in London and 1 December in Delhi.

    Formats accepted are the ones real structured sources emit: an aware `datetime`, a `date`,
    epoch seconds or milliseconds (HubSpot states `closedate` in milliseconds), an ISO-8601
    string, and Google Calendar's `{"dateTime": ...}` / `{"date": ...}` envelope. A naive
    `datetime` is refused for the reason `require_aware` refuses one everywhere else: the
    unanswered timezone question expresses itself later as a reminder on the wrong day.
    """
    zone = _zone(field_map, tz)
    moment = _as_instant(field_map, raw_value)
    if isinstance(moment, date) and not isinstance(moment, datetime):
        return moment.isoformat()
    return moment.astimezone(zone).date().isoformat()


def _zone(field_map: FieldMap, tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception as exc:                       # noqa: BLE001 — any zone lookup failure
        raise StructuredMappingError(
            f"{field_map.source_field} -> {field_map.target}: unknown timezone {tz!r}; a typed "
            "instant cannot be placed on a calendar day without one") from exc


def _as_instant(field_map: FieldMap, raw_value: Any) -> datetime | date:
    """The typed timestamp as an aware `datetime`, or a bare `date` when that is all it said."""
    value = raw_value
    if isinstance(value, Mapping):
        # Google Calendar states a timed event as {"dateTime": ..., "timeZone": ...} and an
        # all-day one as {"date": ...}. Reading `str(dict)` here would hand ALG-09 a brace and
        # get UNRESOLVED on every meeting in the calendar.
        value = value.get("dateTime", value.get("date", _ABSENT))
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise StructuredMappingError(
                f"{field_map.source_field} -> {field_map.target}: naive datetime {value!r} — "
                "the offset it silently carries becomes a deadline on the wrong day")
        return value
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise StructuredMappingError(
            f"{field_map.source_field} -> {field_map.target}: {value!r} is not a timestamp")
    if isinstance(value, int):
        return _from_epoch(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return _from_epoch(int(text))
        # A BARE DATE is tried first, and the order is the whole of the fix.
        # `datetime.fromisoformat("2026-09-04")` succeeds and returns a NAIVE datetime at
        # midnight — so testing for a datetime first made every date-only column ("2026-09-04",
        # the shape a SQL `date` column and Google Calendar's all-day envelope both hand back)
        # look like a timestamp that had forgotten its timezone, and the offset guard below
        # refused it. A date genuinely carries no zone and needs none: it already names the
        # calendar day, which is the only thing ALG-09 is being asked for.
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass            # not a bare date — fall through to the datetime reading below
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StructuredMappingError(
                f"{field_map.source_field} -> {field_map.target}: {value!r} is not an "
                "ISO-8601 timestamp, a date, or an epoch — a declared timestamp field that "
                "will not parse is schema drift, not a missing value") from exc
        if parsed.tzinfo is None:
            raise StructuredMappingError(
                f"{field_map.source_field} -> {field_map.target}: {value!r} states no offset; "
                "a timestamp without a zone is an unanswered question, not a UTC one")
        return parsed
    raise StructuredMappingError(
        f"{field_map.source_field} -> {field_map.target}: cannot read a timestamp out of "
        f"{type(value).__name__}")


def _from_epoch(value: int) -> datetime:
    """Epoch seconds or milliseconds -> an aware UTC datetime, in integer arithmetic only.

    `datetime.fromtimestamp` takes a float and would put a binary rounding step between a
    millisecond column and a calendar day. `timedelta` accepts the two integers directly, so the
    conversion is exact and this module keeps its no-float property on the path that decides a
    deadline.
    """
    if abs(value) >= _EPOCH_MILLISECOND_FLOOR:
        return _EPOCH + timedelta(milliseconds=value)
    return _EPOCH + timedelta(seconds=value)


# ---------------------------------------------------------------------------------------------
# Relations -> entity mentions. The cross-tool bridge, as claims.
# ---------------------------------------------------------------------------------------------


def _mentions_of(mapping: StructuredMapping, relation: RelationMap,
                 raw_fields: Mapping[str, Any]) -> list[EntityMention]:
    """A declared relation's people -> `EntityMention`s carrying real spans.

    `apply_relations` already turns these into graph edges for L2 and is untouched; this is the
    same declared data expressed as the claim type S3 onward reads, so a person named by a CRM
    deal and a person named in an email arrive at conflict detection and importance scoring as
    the same kind of object.

    The span points at the person's own email WHERE IT SITS inside the rendered relation field,
    not at a re-quoted copy: an attendee list renders once, and each attendee's receipt is a
    real offset into that one rendering. `canonical_hint` is `norm_email`, THE person-identity
    function, so a CRM contact and a calendar attendee merge instead of becoming two people.
    """
    entity_type = RELATION_ENTITY_TYPE.get(relation.related_node_type)
    if entity_type is None or relation.identity != "email":
        return []
    text = _render(raw_fields.get(relation.source_field, _ABSENT))
    if text is None:
        return []
    source_ref = source_ref_for(mapping.mapping_id, relation.source_field)
    mentions: list[EntityMention] = []
    seen: set[str] = set()
    for surface in _email_literals(raw_fields.get(relation.source_field)):
        canonical = norm_email(surface)
        if canonical is None or canonical in seen:
            continue
        start = text.find(surface)
        if start < 0:
            continue
        seen.add(canonical)
        mentions.append(EntityMention(
            surface_form=surface, entity_type=entity_type, canonical_hint=canonical,
            evidence=[_span_at(source_ref, text, start, start + len(surface))],
            confidence_bp=STRUCTURED_FIELD_CONFIDENCE_BP))
    return mentions


def _email_literals(value: Any) -> list[str]:
    """The email strings a relation field carries, VERBATIM — never lowercased.

    `apply_relations` canonicalises for graph identity, which is right for a key and wrong for a
    receipt: the span has to quote what the source actually wrote, so `Priya@Chat360.io` is
    found in the rendering as it was written and `norm_email` supplies the merge key separately.
    """
    items = value if isinstance(value, (list, tuple)) else [value]
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            candidate: Any = item
        elif isinstance(item, Mapping):
            candidate = item.get("email") or item.get("address")
        else:
            continue
        if isinstance(candidate, str) and "@" in candidate and candidate.strip():
            out.append(candidate.strip())
    return out


def _span_at(source_ref: str, source_text: str, start: int, end: int) -> EvidenceSpan:
    """A span at a KNOWN region of the source text, graded by ALG-08 like every other one."""
    if end - start > MAX_QUOTE_CHARS:
        end = start + MAX_QUOTE_CHARS
    probe = EvidenceSpan(source_ref=source_ref, quote=source_text[start:end],
                         start_offset=start, end_offset=end)
    verdict, graded = verify_span(probe, source_text)
    if verdict is not SpanVerdict.VERIFIED:
        raise StructuredMappingError(
            f"{source_ref}: span at [{start}, {end}) graded {verdict.value}, not verified")
    return graded


def structured_fields_of(mapping: StructuredMapping,
                         raw_fields: Mapping[str, Any]) -> Mapping[str, Any]:
    """The shipped `target -> raw value` projection, unchanged, as a read-only view.

    `apply_mapping` is the projection L2's `commit_structured` and the gated event already read,
    and this lane does not replace it — the two are complementary halves of one object's
    passage: `apply_mapping` carries the VALUES, `map_to_extraction` carries the receipts, the
    confidences and the normalised dimensioned values. Re-exported here so a caller working with
    the extraction never has to reach past this module to get the other half and never has a
    reason to build a second projection.
    """
    return MappingProxyType(dict(apply_mapping(mapping, dict(raw_fields))))


__all__ = [
    "DEFAULT_STRUCTURED_INTENT",
    "RELATION_ENTITY_TYPE",
    "STRUCTURED_AUTHORITY",
    "STRUCTURED_FIELD_CONFIDENCE_BP",
    "STRUCTURED_INTENT",
    "STRUCTURED_PROFILE",
    "STRUCTURED_PROMPT_VERSION",
    "STRUCTURED_SCHEMA_VERSION",
    "STRUCTURED_STANCE",
    "StructuredMappingError",
    "StructuredRoute",
    "absent_fields",
    "map_to_extraction",
    "mapped_field_confidence",
    "route_structured",
    "source_ref_for",
    "structured_authority",
    "structured_fields_of",
    "structured_source_index",
    "structured_validation_stage",
]
