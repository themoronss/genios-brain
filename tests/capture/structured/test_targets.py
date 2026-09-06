"""L1.3.9-U4 · the structured lane's key closure — W2's residual sink hole.

The hole this file pins shut, in one sentence: **`apply_mapping` returned an untyped
`dict[str, Any]` whose keys were tenant-typed strings, and `context/structured.py` wrote every
one of them into the graph as a fact field name** — ``write_fact(..., field=<target>, ...)`` —
with nothing between the config file and `graph_facts` ever asking what the name was.

`capture/semantic/vocabulary.py` records what that costs, in the words of the failure it was
built after: *"rules read `deal.status` while the extractor, never told the name, wrote `status`
— so the rule was dead on arrival"*. The sink guard closed that door for the model's dicts and
left it open for the mapping's, which is the same door one lane over.

Two properties are asserted here and they are the whole unit:

* a name the graph cannot be queried by never reaches `fields`, and
* it lands in the open lane instead — as a typed, receipted `UnclassifiedObservation`, carrying
  the name the mapping actually spelled.
"""

from __future__ import annotations

from typing import Any

import pytest

from genios_engine.capture.structured.apply import apply_mapping, apply_relations
from genios_engine.capture.structured.mapper import source_ref_for
from genios_engine.capture.structured.registry import (FieldMap, RelationMap, StructuredMapping,
                                                       all_mappings, mapping_from_dict)
from genios_engine.capture.structured.targets import (REFUSED_TARGET_CONFIDENCE_BP,
                                                      TARGET_SEGMENTS, object_text,
                                                      refused_targets_of, render_field,
                                                      sift_mapping_targets, target_namespace)

WAVE = "W2"

#: The tenant-config door the hole came through: `GENIOS_STRUCTURED_MAPPINGS` names a JSON file,
#: `mapping_from_dict` turns it into a mapping, and `FieldMap.target` is a string a customer
#: typed. Every mapping below is built through it for that reason.
DEAL_CONFIG: dict[str, Any] = {
    "mapping_id": "client.deal.v1", "source": "postgres", "object_type": "public.deals",
    "identity_field": "id", "node_type": "deal", "intent": "pipeline_update",
    "fields": [{"source_field": "stage_name", "target": "deal.stage", "value_type": "enum"}],
}


def _mapping(*fields: dict[str, Any], **over: Any) -> StructuredMapping:
    config = dict(DEAL_CONFIG, fields=list(fields) or DEAL_CONFIG["fields"])
    config.update(over)
    return mapping_from_dict(config)


# ── the shape rule ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("target, namespace", [
    ("deal.stage",              "deal"),      # the form every shipping mapping declares
    ("product_usage.event",     "product_usage"),
    ("deal.close_date",         "deal"),      # snake_case attribute
    ("a.b",                     "a"),         # minimal, and still addressable
    # ── refusals, each one a way a mapping actually drifts ──
    ("status",                  None),        # THE recorded failure: no namespace at all
    ("Deal.Stage",              None),        # a different string from the one the rule matches
    ("deal.Stage",              None),
    ("crm.deal.stage",          None),        # three segments, addressable as neither
    ("deal.",                   None),        # an empty attribute
    (".stage",                  None),
    ("deal stage",              None),        # not a name a query can carry
    ("deal.close-date",         None),        # kebab, not snake
    ("",                        None),
    ("2deal.stage",             None),        # a segment must start with a letter
])
def test_a_target_is_addressable_or_it_is_not_a_name(target, namespace):
    """One row per shape. `target_namespace` is the whole rule and it returns the namespace it
    accepted, so a caller cannot check the shape and then read the prefix a different way."""
    assert target_namespace(target) == namespace


def test_the_segment_count_is_stated_once_and_the_rule_reads_it():
    """A two in a comparison and a two in a message are two numbers that can disagree."""
    assert TARGET_SEGMENTS == 2
    assert target_namespace(".".join(["a"] * TARGET_SEGMENTS)) == "a"
    assert target_namespace(".".join(["a"] * (TARGET_SEGMENTS + 1))) is None


# ── the sift ──────────────────────────────────────────────────────────────────────────────────

def test_an_addressable_target_is_kept_and_its_value_carried():
    sifted = sift_mapping_targets(_mapping(), {"stage_name": "negotiation", "junk": "x"})
    assert dict(sifted.fields) == {"deal.stage": "negotiation"}
    assert sifted.refused == () and sifted.observations == ()
    assert sifted.mapping is not None


@pytest.mark.parametrize("target, why", [
    ("deal_stage",        "no namespace — the sink guard's own worked example, one lane over"),
    ("status",            "the recorded failure: the rule reads deal.status, the lane wrote it"),
    ("subscription.status", "another mapping's namespace, pasted in"),
    ("Deal.Stage",        "the right words in a spelling no rule matches"),
])
def test_an_unaddressable_target_reaches_the_open_lane_and_nowhere_else(target, why):
    """W2·#6, the proof. The name is refused from every path to storage and appears in exactly
    one place: a typed observation on its way to the open lane."""
    mapping = _mapping({"source_field": "stage_name", "target": target, "value_type": "enum"})
    raw = {"stage_name": "negotiation"}

    sifted = sift_mapping_targets(mapping, raw)

    assert dict(sifted.fields) == {}, f"{why}: the name reached the graph anyway"
    assert apply_mapping(mapping, raw) == {}, "the shipped projection still carries it"
    assert refused_targets_of(sifted) == (target,)
    assert [o.proposed_kind for o in sifted.observations] == [target]
    assert [f.target for f in sifted.mapping.fields] == []


def test_the_refused_name_is_carried_verbatim_with_a_receipt_that_resolves():
    """A refusal that loses the name records nothing, and one that invents a quote is worse than
    losing it. The observation carries the mapping's own spelling and a receipt that ALG-08 can
    find in the object it came from."""
    mapping = _mapping({"source_field": "stage_name", "target": "Deal.Stage"})
    raw = {"id": "d1", "stage_name": "negotiation"}

    observation = sift_mapping_targets(mapping, raw).observations[0]

    assert observation.proposed_kind == "Deal.Stage"
    assert observation.confidence_bp == REFUSED_TARGET_CONFIDENCE_BP
    span = observation.evidence[0]
    assert span.quote == "negotiation"
    assert span.verified is False, "the sift graded its own receipt"
    assert span.source_ref == source_ref_for(mapping.mapping_id, "stage_name"), \
        "two spellings of one source_ref split a field's evidence in two"
    assert span.quote in object_text(raw), "the receipt cites text the object does not contain"


def test_a_refused_target_whose_column_is_absent_is_named_but_not_observed():
    """`UnclassifiedObservation` refuses a receiptless observation — "the one thing this lane
    must not accumulate". A mapping declaring a bad name for a column this object never carried
    has nothing to cite, so it is removed and named and does not become a row asserting evidence
    that does not exist."""
    mapping = _mapping({"source_field": "stage_name", "target": "status"})

    sifted = sift_mapping_targets(mapping, {"id": "d1"})

    assert refused_targets_of(sifted) == ("status",)
    assert sifted.observations == ()


def test_the_sift_is_idempotent_so_the_ingestion_path_may_run_it_twice():
    """`apply_mapping` sifts on the ingestion path and `run_structured_lane` sifts the same
    object again; a replay runs both once more. A second pass must change nothing."""
    mapping = _mapping({"source_field": "stage_name", "target": "status"},
                       {"source_field": "amount_cents", "target": "deal.amount_cents"})
    raw = {"stage_name": "negotiation", "amount_cents": 8400000}

    once = sift_mapping_targets(mapping, raw)
    twice = sift_mapping_targets(once.mapping, raw)

    assert dict(twice.fields) == dict(once.fields)
    assert twice.refused == () and twice.observations == ()


def test_a_relation_naming_an_unqueryable_edge_kind_is_refused_the_same_way():
    """`commit_structured` writes `edge_type` and `related_node_type` straight into the graph as
    an edge kind and a node kind. Same string from the same config file, same closure."""
    mapping = _mapping(relations=[{"source_field": "attendees", "related_node_type": "person",
                                   "edge_type": "Attended At", "identity": "email"}])
    raw = {"stage_name": "negotiation", "attendees": ["p@acme.com"]}

    sifted = sift_mapping_targets(mapping, raw)

    assert refused_targets_of(sifted) == ("Attended At",)
    assert sifted.mapping.relations == []
    assert apply_relations(mapping, raw) == [], "the bad edge kind reached the graph anyway"


def test_a_good_relation_still_produces_its_edge():
    """The neutralisation: the closure must not cost a working cross-tool bridge."""
    mapping = _mapping(relations=[{"source_field": "attendees", "related_node_type": "person",
                                   "edge_type": "attended", "identity": "email"}])
    edges = apply_relations(mapping, {"stage_name": "x", "attendees": ["P@Acme.com"]})
    assert edges == [{"node_type": "person", "canonical_key": "p@acme.com",
                      "display_name": "p@acme.com", "edge_type": "attended", "direction": "in"}]


def test_raw_fields_that_are_not_a_mapping_raise_rather_than_reporting_a_quiet_object():
    with pytest.raises(TypeError, match="mapping of source field name"):
        sift_mapping_targets(_mapping(), ["stage_name"])          # type: ignore[arg-type]


# ── every shipping mapping is already addressable ─────────────────────────────────────────────

@pytest.mark.parametrize("mapping", all_mappings(), ids=lambda m: m.mapping_id)
def test_every_registered_mapping_declares_only_addressable_names(mapping):
    """The closure is read off the shipping registry, never invented: if a built-in mapping
    failed it, the rule would be describing a system nobody has.

    `product_usage` is the one mapping whose namespace is not its `node_type` — the node is one
    usage EVENT and the facts describe the usage — and it declares `target_namespace` for exactly
    that reason. This test is what would have caught the alternative, which was to make the rule
    weaker until that mapping fitted it.
    """
    for field_map in mapping.fields:
        assert target_namespace(field_map.target) == mapping.namespace, (
            f"{mapping.mapping_id} declares {field_map.target!r}, which is not addressable "
            f"under this mapping's namespace {mapping.namespace!r}")
    assert sift_mapping_targets(mapping, {}).refused == ()


def test_the_namespace_defaults_to_the_node_type_and_is_declared_only_when_it_differs():
    assert StructuredMapping(mapping_id="m", source="s", object_type="o", identity_field="id",
                             node_type="deal", fields=[], intent="i").namespace == "deal"
    assert StructuredMapping(mapping_id="m", source="s", object_type="o", identity_field="id",
                             node_type="product_usage_event", fields=[], intent="i",
                             target_namespace="product_usage").namespace == "product_usage"


# ── the rendering, which two halves of the lane share ─────────────────────────────────────────

@pytest.mark.parametrize("value, rendered", [
    ("negotiation",                 "negotiation"),
    (84000,                         "84000"),
    (True,                          "true"),          # bool before int, or "1" loses the word
    (False,                         "false"),
    (["a@x.com", "b@x.com"],        "a@x.com, b@x.com"),
    ({"b": 2, "a": 1},              '{"a": 1, "b": 2}'),   # sorted, so a replay renders it once
    (None,                          None),
    ("",                            None),
    ("   ",                         None),
])
def test_render_field_is_the_one_canonical_rendering(value, rendered):
    """One rendering for the receipt builder and the key sifter alike. Two would put the spans
    they mint in coordinate systems that do not agree, which is the failure
    `structured_source_index` exists to make impossible."""
    assert render_field(value) == rendered


def test_object_text_contains_every_field_it_renders():
    """The open lane's coordinate system. `capture_unclassified` re-grades every probe against
    ONE source text, so each field's own rendering has to be findable inside it or a real value
    would be stored flagged as a fabrication."""
    raw = {"stage_name": "negotiation", "amount": "84000", "owner": "priya@chat360.io"}
    text = object_text(raw)
    for value in raw.values():
        assert render_field(value) in text
    assert object_text({}) == "{}", "an object with no fields is still an object"


def test_the_mappers_rendering_and_the_sifts_are_the_same_function():
    """Asserted as identity, not as agreement on a sample: a second `_render` in `mapper.py` is
    exactly the drift this move was made to prevent, and a sampled comparison would pass until
    the day the two disagreed about a type nobody thought to test."""
    from genios_engine.capture.structured import mapper

    assert mapper._render is render_field
    assert mapper._ABSENT is not None


def test_field_maps_declared_in_code_are_sifted_the_same_as_config_ones():
    """The registry's own `FieldMap`s go through the same rule. A closure that only applied to
    the config door would be closed against customers and open to us."""
    mapping = StructuredMapping(
        mapping_id="code.deal.v1", source="hubspot", object_type="deal", identity_field="id",
        node_type="deal", intent="pipeline_update",
        fields=[FieldMap("dealstage", "status", "enum"),
                FieldMap("dealname", "deal.title", "string")],
        relations=[RelationMap("contact_email", "person", "involves", "in", "email")])

    sifted = sift_mapping_targets(mapping, {"dealstage": "won", "dealname": "Acme"})

    assert dict(sifted.fields) == {"deal.title": "Acme"}
    assert refused_targets_of(sifted) == ("status",)
