from __future__ import annotations

import json

from genios_engine.capture.structured.apply import apply_mapping
from genios_engine.capture.structured.registry import (_REGISTRY, get_mapping, has_mapping,
                                                       load_mappings_from_config, mapping_from_dict)

# Structured mappings are DATA: a client can map their own DB table / CRM object with a JSON file
# instead of editing Python (LAYER1_CAPTURE_FIXES #12). This is how an unmapped client table stops
# parking — you describe it in config and it flows through the structured lane.


def test_mapping_from_dict_round_trips_fields_and_relations():
    m = mapping_from_dict({
        "mapping_id": "acme.order.v1", "source": "postgres", "object_type": "public.acme_orders_cfg",
        "identity_field": "id", "node_type": "order", "intent": "pipeline_update",
        "name_field": "order.ref", "tags": ["order_change"], "emit_on_change": ["status"],
        "fields": [{"source_field": "status", "target": "order.status", "value_type": "enum"},
                   {"source_field": "ref", "target": "order.ref", "value_type": "string"}],
        "relations": [{"source_field": "buyer_email", "related_node_type": "person",
                       "edge_type": "placed_by", "direction": "in", "identity": "email"}],
    })
    assert m.source == "postgres" and m.object_type == "public.acme_orders_cfg"
    assert m.fields[0].target == "order.status" and m.relations[0].edge_type == "placed_by"


def test_load_from_config_registers_and_applies(tmp_path):
    cfg = [{"mapping_id": "acme.order.v1", "source": "postgres", "object_type": "public.acme_orders_cfg",
            "identity_field": "id", "node_type": "order", "intent": "pipeline_update",
            "fields": [{"source_field": "status", "target": "order.status", "value_type": "enum"}],
            "emit_on_change": ["status"]}]
    p = tmp_path / "mappings.json"
    p.write_text(json.dumps(cfg))
    try:
        assert load_mappings_from_config(str(p)) == 1
        assert has_mapping("postgres", "public.acme_orders_cfg")
        fields = apply_mapping(get_mapping("postgres", "public.acme_orders_cfg"), {"status": "shipped"})
        assert fields.get("order.status") == "shipped"
    finally:
        _REGISTRY.pop(("postgres", "public.acme_orders_cfg"), None)   # don't pollute the global registry


def test_missing_config_file_is_a_noop_not_an_error():
    assert load_mappings_from_config("/no/such/mappings.json") == 0
    assert load_mappings_from_config("") == 0
