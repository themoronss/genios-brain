"""L1.3.9-U4 · THE STRUCTURED LANE'S KEY CLOSURE — the residual hole in the typed sink.

`capture/semantic/sink_guard.py` closed the semantic lane: an extraction whose `roles` entry
read `{"deal_stage": "negotiation"}` used to cache permanently under a name no consumer reads,
and now it is refused into the open lane. That guard sits inside `extractor._run_calls`, which
is the SEMANTIC lane's parse, so it closes the semantic lane and nothing else.

THE HOLE IT DID NOT CLOSE
-------------------------
The structured lane is a second producer of an extraction and a second path into storage, and
no part of it ever asked what its field NAMES were:

* `apply_mapping` returns a bare `dict[str, Any]` keyed by `FieldMap.target` — an untyped dict
  crossing two module boundaries;
* `capture/pipeline.py` puts it on `GatedEvent.structured_fields`, and `context/runner.py` hands
  it to `context/structured.py::commit_structured`, which calls
  ``store.write_fact(..., field=<target>, ...)``. **The mapping's target string becomes the fact
  field name in the graph**, verbatim, forever;
* the targets are TENANT DATA. `registry.mapping_from_dict` builds a `StructuredMapping` out of a
  JSON file named by `GENIOS_STRUCTURED_MAPPINGS`, so `FieldMap.target` is a string a customer
  types. Nothing between that file and `graph_facts` looked at it.

`capture/semantic/vocabulary.py` records where that ends, in the words of the failure it was
built after: *"rules read `deal.status` while the extractor, never told the name, wrote `status`
— so the rule was dead on arrival"*. A mapping that writes `status`, `Deal.Stage` or
`crm.deal_stage` produces facts that are perfectly stored, perfectly confident, and unreadable
by every rule that will ever be written — which is the 268-distinct-field-names failure with a
config file in place of a model.

THE CLOSURE, AND WHY IT IS A SHAPE PLUS A NAMESPACE RATHER THAN A WORD LIST
---------------------------------------------------------------------------
A fixed list of permitted target names cannot be right here: the lane's whole reason to exist is
that a client maps their OWN table by dropping in config, and a closed list would make every new
customer a code change. What IS closed is the FORM a name must take to be addressable:

* a target is ``<namespace>.<attribute>`` — exactly two dot-separated lowercase snake_case
  segments. `deal.stage`, `meeting.title`, `product_usage.event`: every target every shipping
  mapping declares, and every name a rule is written against. A bare `status` has no namespace
  and collides with every other source's `status`; `Deal.Stage` is a different string from the
  one the rule matches; `crm.deal.stage` is three segments and reads as neither;
* and the namespace is the mapping's OWN, `StructuredMapping.namespace` — `target_namespace`
  when it is declared and `node_type` when it is not. A mapping for a deal that writes
  `subscription.status` is writing a fact about a node it is not describing.

Both halves are checkable, neither invents a vocabulary, and together they catch the two ways a
mapping actually drifts: a field renamed to the raw provider spelling, and a field pasted in
from another mapping.

WHAT HAPPENS TO A REFUSED NAME — the open lane, and nowhere else
----------------------------------------------------------------
Exactly what happens to a refused lane key in `sink_guard`: it is removed from the dict, and it
is re-expressed as a typed `UnclassifiedObservation` carrying a real receipt into the object it
came from. So the name survives in the one place an unpromoted name is allowed to live, where
no rule may read it and a human may promote it — and it reaches `graph_facts`, the extraction
and `mapped_field_confidence` nowhere at all.

A refused target whose field is ABSENT from this object produces no observation: there is
nothing to cite, and `UnclassifiedObservation` refuses a receiptless observation. It is still
removed, and still named in `SiftedTargets.refused`.

RELATIONS TOO. `RelationMap.edge_type` and `related_node_type` are the same kind of string one
step over — `commit_structured` writes them as the edge type and the related node's type — so
they are held to the single-segment half of the same rule. They carry no namespace because they
name a KIND rather than an attribute of one node.

THE ONE NAME THIS UNIT DOES NOT CLOSE, stated rather than left to be discovered:
`StructuredMapping.node_type`. It is not a per-object name, it is the mapping's identity, and
refusing it would silently empty an object rather than one of its fields. It belongs with
registration — `route_structured`/`gate.py` already own "is this mapping usable at all?" — and
this unit would be the wrong place to decide that a customer's whole table is unreadable.

PURE. No clock, no model, no database, no network, no float. The same value in the same mapping
sifts to the same answer on every machine and every replay, which is what lets `apply_mapping`
call it on the ingestion path without changing what that path costs.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import UnclassifiedObservation

from .registry import StructuredMapping

log = logging.getLogger(__name__)

#: How many dot-separated segments an addressable target name has. Two: the node it describes
#: and the attribute of it. Named rather than written as `2` in a comparison so the error
#: message and the check cannot disagree about the number.
TARGET_SEGMENTS = 2

#: One segment: lowercase snake_case, starting with a letter. The same shape
#: `capture/semantic/open_lane.py::_VOCABULARY_MEMBER` requires of a promoted vocabulary member,
#: and for the same reason — the name is what a rule will be written against, and `Deal Stage`
#: is not a name a rule can match.
_SEGMENT = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")

#: What a salvaged target name is worth, in integer basis points. Identical to
#: `sink_guard.REFUSED_KEY_CONFIDENCE_BP` and identical in its reasoning: the lane is certain the
#: name was refused and has NO opinion about the world, and a guard that scored its own
#: bookkeeping at full confidence would evict the model's real noticing from the open lane's cap.
REFUSED_TARGET_CONFIDENCE_BP = 5000

#: How much of a refused value the description echoes, for the same reason `sink_guard` clips
#: one: the description is read in a weekly report beside four others.
_VALUE_ECHO = 80


class _Absent:
    """The sentinel for "this object did not carry that field at all".

    A class rather than `None`, because a structured source distinguishes the two: a JSON `null`
    in a column is a stated absence and a missing key is an unstated one, and `_render` has to
    give the same answer to both without the caller having to pre-flatten them.
    """

    __slots__ = ()

    def __repr__(self) -> str:                      # pragma: no cover - diagnostic only
        return "<absent>"


#: The singleton every caller compares against. `mapper.py` imports it under its own name.
ABSENT: Any = _Absent()


def render_field(value: Any) -> str | None:
    """One typed value -> the source text its receipt quotes, or None when there is nothing.

    THE lane's rendering, and the reason it lives in this leaf module rather than in `mapper.py`:
    the receipt builder and the key sifter must agree about what a field's text IS, and two
    renderings would put a span's offsets in a coordinate system nobody else can reproduce.
    `mapper.py` imports this function; `structured_source_index` publishes its results; the open
    lane's probes are measured against it.

    None for absent, for null, and for a value whose rendering is blank: a field holding `""` or
    three spaces asserts nothing, and a span quoting whitespace is a receipt a human cannot check
    (`EvidenceSpan` refuses it outright).

    Deterministic and total: the same value renders the same way on every machine and every
    replay, or the stored offsets stop describing the text they were measured in. That is why
    containers go through `json.dumps(..., sort_keys=True)` rather than `str()`, whose dict order
    is insertion order and therefore a property of the connector's parser rather than of the data.

    `bool` is handled before `int` on purpose — `isinstance(True, int)` is True in Python, so the
    obvious ordering renders a boolean column as "1" and loses the only two words that column
    ever says.
    """
    if value is ABSENT or value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float)):
        # `repr` for a float, which is the shortest string that round-trips back to the same
        # binary value — so the rendering is stable across runs. The float itself is never
        # arithmetic here: a money field's literal is handed to ALG-10 as a STRING and every
        # sum downstream is in integer minor units.
        text = repr(value) if isinstance(value, float) else str(value)
    elif isinstance(value, (list, tuple)):
        parts = [rendered for rendered in (render_field(item) for item in value)
                 if rendered is not None]
        text = ", ".join(parts)
    elif isinstance(value, Mapping):
        text = json.dumps(dict(value), sort_keys=True, default=str, ensure_ascii=False)
    else:
        text = str(value)
    return text if text.strip() else None


def object_text(raw_fields: Mapping[str, Any]) -> str:
    """The whole source object as ONE canonical string — the open lane's coordinate system.

    `capture_unclassified` re-grades every receipt it stores against a single `source_text`, so
    a refused name's probe has to point into something that holds every field's value at once.
    The object's own canonical rendering is that something, and it is `render_field` applied to
    the object rather than a second serialisation, so a field's text is a literal substring of it
    and ALG-08 relocates the probe onto real offsets instead of grading it a fabrication.

    An object with no fields renders as `{}` — the canonical rendering of an empty mapping, not
    a special case. Nothing can be cited against it, so any probe measured in it grades
    unresolved and is stored flagged, which is the documented behaviour of the lane for a receipt
    that did not resolve.
    """
    return render_field(dict(raw_fields)) or ""


def target_namespace(target: str) -> str | None:
    """`deal.amount` -> `deal`; any name that is not addressable -> None.

    Addressable means exactly `TARGET_SEGMENTS` dot-separated lowercase snake_case segments. The
    negative cases are the ones that matter and each is a real drift: `status` (no namespace, so
    it collides with every other source's `status`), `Deal.Stage` (a different string from the
    one the rule matches), `crm.deal.stage` (three segments, addressable as neither), `deal.`
    (an empty attribute), `deal stage` (not a name at all).
    """
    segments = target.split(".")
    if len(segments) != TARGET_SEGMENTS:
        return None
    if not all(_SEGMENT.fullmatch(segment) for segment in segments):
        return None
    return segments[0]


@dataclass(frozen=True)
class RefusedTarget:
    """One name the structured lane would not write, and why.

    A typed record rather than a string for the same reason `sink_guard.RefusedKey` is one: "the
    mapping had a bad field" is unactionable, and `hubspot.deal.v1: dealstage -> status` names
    the mapping, the column and the drift in one line a reviewer can act on.
    """

    #: The mapping that declared it, so a reviewer edits the right config file.
    mapping_id: str
    #: The provider's own column, which is what the reviewer sees in the source system.
    source_field: str
    #: The name as the mapping spelled it, verbatim.
    target: str
    #: WHY, in one line. It stands alone in a log row.
    reason: str

    @property
    def path(self) -> str:
        """`hubspot.deal.v1#dealstage -> status` — the one string a reader greps for."""
        return f"{self.mapping_id}#{self.source_field} -> {self.target}"


@dataclass(frozen=True)
class SiftedTargets:
    """A mapping restricted to the names this lane may write, plus everything it took out.

    `mapping` is the object every later step uses — `map_to_extraction`, `mapped_field_confidence`,
    `absent_fields`, `structured_source_index`, `apply_relations`. Passing the SIFTED mapping on
    rather than filtering each output separately is what makes "the refused name lands in the open
    lane and nowhere else" a structural fact instead of five places that each had to remember.
    """

    mapping: StructuredMapping
    #: `target -> raw value`, for accepted targets whose field this object carried. What
    #: `apply_mapping` returns and what `commit_structured` writes as facts.
    fields: Mapping[str, Any]
    refused: tuple[RefusedTarget, ...] = ()
    #: One per refused name that had a value to cite. Ready for `capture_unclassified`.
    observations: tuple[UnclassifiedObservation, ...] = ()


def _echo(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= _VALUE_ECHO else f"{text[:_VALUE_ECHO]}…"


def _probe(source_ref: str, rendered: str) -> EvidenceSpan:
    """A receipt for a refused name: the field's own text, at offsets ALG-08 will correct.

    A PROBE, not a claim about position — offsets 0..len and `verified=False`, exactly as
    `sink_guard._probe` and `extractor._spans_from_payload` do. `capture_unclassified` re-grades
    it against `object_text`, where the value really does appear, and stores the CORRECTED
    offsets with the verdict ALG-08 gave. Nothing here asserts its own salvage was checked.
    """
    quote = rendered[:MAX_QUOTE_CHARS]
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=0,
                        end_offset=len(quote), verified=False)


def _observation(refused: RefusedTarget, rendered: str, span: EvidenceSpan,
                 ) -> UnclassifiedObservation:
    """One refused name -> one open-lane observation.

    `proposed_kind` is the target AS THE MAPPING SPELLED IT. That is the string a human either
    corrects in the config or promotes into the vocabulary, and `hubspot_deal_v1_status` is not a
    name anybody would do either to. It also means the same drifted name arriving from two
    mappings groups as one candidate, which is what `canonical_kind` exists for.
    """
    return UnclassifiedObservation(
        proposed_kind=refused.target,
        description=(f"the mapping {refused.mapping_id} maps the column "
                     f"{refused.source_field!r} to {refused.target!r}, which is not a name any "
                     f"consumer can address: {refused.reason}; the value was {_echo(rendered)}"),
        evidence=[span], confidence_bp=REFUSED_TARGET_CONFIDENCE_BP)


def _refuse(mapping: StructuredMapping, source_field: str, target: str,
            reason: str) -> RefusedTarget:
    return RefusedTarget(mapping_id=mapping.mapping_id, source_field=source_field,
                         target=target, reason=reason)


def _target_refusal(mapping: StructuredMapping, source_field: str,
                    target: str) -> RefusedTarget | None:
    """Why this target may not be written, or None when it may be."""
    namespace = target_namespace(target)
    if namespace is None:
        return _refuse(mapping, source_field, target,
                       f"a target is <namespace>.<attribute> in lowercase snake_case and this "
                       f"is {len(target.split('.'))} segment(s) — a fact written under it is "
                       "addressable by no rule")
    if namespace != mapping.namespace:
        return _refuse(mapping, source_field, target,
                       f"its namespace is {namespace!r} and this mapping describes "
                       f"{mapping.namespace!r} — the fact would be filed against a node this "
                       "mapping is not about")
    return None


def _relation_refusal(mapping: StructuredMapping, relation: Any) -> RefusedTarget | None:
    """Why this relation may not be written. Edge and node KINDS, so one segment, no namespace."""
    for name, value in (("edge_type", relation.edge_type),
                        ("related_node_type", relation.related_node_type)):
        if not _SEGMENT.fullmatch(value or ""):
            return _refuse(mapping, relation.source_field, value or "",
                           f"{name} is written as an edge or node kind in the graph and must be "
                           "one lowercase snake_case word")
    return None


def sift_mapping_targets(mapping: StructuredMapping,
                         raw_fields: Mapping[str, Any]) -> SiftedTargets:
    """L1.3.9-U4 · close the structured lane's field names. Pure: no clock, no store, no DB.

    Every declared target outside the mapping's own addressable namespace is removed from the
    mapping and re-expressed as an `UnclassifiedObservation` — typed, receipted, and in the one
    place an unpromoted name is allowed to live. Every accepted target whose field this object
    carried a value for appears in `fields`, which is exactly what `apply_mapping` has always
    returned.

    Idempotent by construction: a sifted mapping carries no refusable target, so a second pass
    changes nothing and returns no observations. That matters at the seam it is called from —
    `apply_mapping` runs on the ingestion path, `run_structured_lane` runs on the same object,
    and a replay runs both again.

    `raw_fields` may be any mapping; a non-mapping is a caller bug and raises, because a lane
    that quietly returned no fields for a malformed object would report a quiet CRM record.
    """
    if not isinstance(raw_fields, Mapping):
        raise TypeError("raw_fields must be a mapping of source field name to value")

    kept_fields = []
    kept_relations = []
    fields: dict[str, Any] = {}
    refused: list[RefusedTarget] = []
    observations: list[UnclassifiedObservation] = []
    text_of = object_text(raw_fields)

    def salvage(record: RefusedTarget, rendered: str | None) -> None:
        """Record the refusal, and cite it when this object actually carried the value."""
        refused.append(record)
        if rendered is None:
            # Nothing to cite. `UnclassifiedObservation` refuses a receiptless observation —
            # "the one thing this lane must not accumulate" — so a name whose column is absent
            # from this object is removed and named, and does not become a row asserting
            # evidence that does not exist.
            return
        observations.append(_observation(record, rendered,
                                         _probe(_lane_source_ref(record), rendered)))

    for field_map in mapping.fields:
        record = _target_refusal(mapping, field_map.source_field, field_map.target)
        rendered = render_field(raw_fields.get(field_map.source_field, ABSENT))
        if record is not None:
            salvage(record, rendered)
            continue
        kept_fields.append(field_map)
        if field_map.source_field in raw_fields:
            fields[field_map.target] = raw_fields[field_map.source_field]

    for relation in mapping.relations:
        record = _relation_refusal(mapping, relation)
        if record is not None:
            salvage(record, render_field(raw_fields.get(relation.source_field, ABSENT)))
            continue
        kept_relations.append(relation)

    if not refused:
        return SiftedTargets(mapping=mapping, fields=fields)

    log.info("structured lane: refused %d name(s) from %s into the open lane (%s)",
             len(refused), mapping.mapping_id, ", ".join(record.path for record in refused))
    return SiftedTargets(mapping=replace(mapping, fields=kept_fields, relations=kept_relations),
                         fields=fields, refused=tuple(refused),
                         observations=tuple(observations))


def _lane_source_ref(refused: RefusedTarget) -> str:
    """``structured:<mapping_id>#<source_field>`` — doc 03 L1.3.9 step 4's ref, for a refusal.

    Spelled here rather than imported from `mapper.source_ref_for` because `mapper` imports THIS
    module: a leaf that reached back up for one f-string would make the lane's two halves
    mutually dependent for no gain. `test_targets.py` asserts the two spellings are identical,
    which is the check that keeps one string one string.
    """
    return f"structured:{refused.mapping_id}#{refused.source_field}"


def refused_targets_of(sifted: SiftedTargets) -> Sequence[str]:
    """Just the names, in mapping order — for a log line, a metric, or a config diff.

    A separate accessor rather than a comprehension at four call sites, because "which names is
    this mapping losing?" is the question an operator asks and it should have one answer.
    """
    return tuple(record.target for record in sifted.refused)


__all__ = ["ABSENT", "REFUSED_TARGET_CONFIDENCE_BP", "TARGET_SEGMENTS", "RefusedTarget",
           "SiftedTargets", "object_text", "refused_targets_of", "render_field",
           "sift_mapping_targets", "target_namespace"]
