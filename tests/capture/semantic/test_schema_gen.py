"""L1.4.4-U2 · the JSON schema generator — Wave W3, gate G3.

    pytest tests/capture/semantic/test_schema_gen.py -q

Doc 04's acceptance is two lines — *adding a field to `ExtractionResult` changes the generated
block* and *the generated block parses as a valid JSON template* — and the first of the two is
the whole unit, so it is asserted the only way that proves anything: by CONSTRUCTING a variant
model with an extra field and generating from it. An assertion that greps this repository's
source for a field name would pass just as happily against a hand-written block, which is the
thing this unit exists to replace.

The rows beyond those two all guard one failure mode, the one the doc records in its own words:

    rules read `deal.status` while the extractor, never told the name, wrote `status` —
    so the rule was dead on arrival

Every way the block can quietly stop describing the type is a re-run of that failure. So: the
top-level keys are the contract's fields exactly, in order (a filter is where a new field goes
to be dropped); each enum-shaped field carries its closed set inline, from `vocabulary.py`, so
the SCHEMA block cannot disagree with the VOCAB block; the two forbidden score names appear
nowhere; and an annotation the walk has no rule for RAISES instead of emitting a shapeless
placeholder that would take a new field to the model with no shape at all.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import pytest
from pydantic import BaseModel, create_model

from genios_engine.capture.semantic.schema_gen import SchemaGenerationError, generate_schema_block
from genios_engine.capture.semantic.vocabulary import (FIELD_TO_SET, untyped_lane_sets,
                                                       vocabulary_sets)
from genios_engine.contracts.extraction import FORBIDDEN_RESULT_FIELDS, ExtractionResult

WAVE = "W3"
GATE = "G3"

#: Fields whose value in the block must say "omit": the extractor stamps them, the evidence
#: binder assembles them, or ALG-08 alone may set them (S-9 — the extractor may not stamp its own
#: receipts). They are SHOWN rather than filtered out, so that "every declared field appears in
#: the block" stays an unconditional property.
CALLER_FILLED = ("model_snapshot", "prompt_version", "schema_version", "extraction_profile",
                 "input_tokens", "output_tokens", "all_evidence", "source_ref", "verified")


def _block() -> dict[str, Any]:
    return json.loads(generate_schema_block())


def _walk(node: Any):
    """Every (key, value) pair anywhere in the template, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


@pytest.mark.gate
def test_generated_block_parses_as_a_json_template():
    """Doc 04 assert 2. It is pasted into a prompt as an object the model must mirror; prose
    about a shape is not a shape, and a block that does not parse is one the model will not
    reproduce."""
    block = generate_schema_block()
    parsed = json.loads(block)
    assert isinstance(parsed, dict) and parsed


@pytest.mark.gate
def test_adding_a_field_to_the_result_changes_the_block():
    """Doc 04 assert 1, by construction rather than by inspection.

    A variant of the real contract with one extra field must produce a different block that
    mentions the new field — and the original's block must be unchanged, because the generator is
    cached and a cache keyed on anything but the type would serve the variant's block to the
    contract or the other way round.
    """
    before = generate_schema_block(ExtractionResult)
    variant = create_model("VariantResult", __base__=ExtractionResult,
                           renewal_window=(str, ...))
    after = generate_schema_block(variant)

    assert after != before
    assert "renewal_window" in json.loads(after)
    assert "renewal_window" not in json.loads(before)
    assert generate_schema_block(ExtractionResult) == before


@pytest.mark.gate
def test_block_keys_are_every_declared_field_in_declaration_order():
    """Not a subset and not a superset. A field the block omits is a field the model is never
    asked for and every reader downstream attributes to the message rather than to the prompt;
    order is pinned too, because the block is part of the prompt and the prompt is part of the
    extraction cache key."""
    assert list(_block()) == list(ExtractionResult.model_fields)


@pytest.mark.gate
@pytest.mark.parametrize("field,set_name", sorted(FIELD_TO_SET.items()))
def test_every_governed_field_inlines_its_closed_set(field, set_name):
    """The allowed values, in the block, from `vocabulary.py` — never retyped.

    `extraction_profile` is governed and also caller-filled: the extractor stamps it, so the
    block says so instead of offering the model a list it must not choose from.
    """
    found = [value for key, value in _walk(_block()) if key == field]
    assert found, f"{field} does not appear anywhere in the block"
    if field in CALLER_FILLED:
        assert all("omit" in value for value in found)
        return
    for value in found:
        for word in vocabulary_sets()[set_name]:
            assert word in value, f"{field} placeholder omits the allowed value {word!r}"


@pytest.mark.gate
@pytest.mark.parametrize("field", CALLER_FILLED)
def test_fields_the_model_may_not_answer_say_so(field):
    """Shown, and marked. `verified` is the sharpest of them: S-9 refuses an extraction that
    arrives with a span already verified, so a block that invited the model to set it would be
    asking for the one answer the next stage rejects."""
    found = [value for key, value in _walk(_block()) if key == field]
    assert found, f"{field} is missing from the block"
    assert all(isinstance(value, str) and "omit" in value for value in found), found


@pytest.mark.gate
@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_RESULT_FIELDS))
def test_no_score_field_is_ever_offered_to_the_model(forbidden):
    """The model DESCRIBES; it never SCORES. The type refuses both names at construction, and the
    prompt must not name them either — a block that mentions `importance_bp` teaches the model to
    emit one, and the refusal then destroys the whole extraction."""
    assert forbidden not in generate_schema_block()


@pytest.mark.gate
def test_confidence_placeholders_ask_for_basis_points_not_a_ratio():
    """Every `confidence_bp` in the tree, at every depth. A model told only "integer" writes 1
    for 0.87, and 1 basis point is not a rounding error — it is a claim the pipeline reads as
    noise."""
    found = [value for key, value in _walk(_block()) if key == "confidence_bp"]
    assert len(found) >= 4, "the claim types each carry a confidence; none was rendered"
    assert all("basis points 0..10000" in value for value in found), found


@pytest.mark.gate
def test_generation_is_cached_and_byte_identical():
    """It is deterministic — sorted vocabularies, declaration-ordered fields, no clock — and it
    runs on the per-message prompt-build path."""
    assert generate_schema_block() == generate_schema_block()
    assert generate_schema_block(ExtractionResult) is generate_schema_block(ExtractionResult)


class _SelfReferential(BaseModel):
    """A claim type that contains itself. There is no finite JSON template for one."""

    child: Optional["_SelfReferential"] = None


_SelfReferential.model_rebuild()


@pytest.mark.gate
@pytest.mark.parametrize("label,model", [
    ("a float score", create_model("FloatModel", __base__=BaseModel, score=(float, ...))),
    ("a Decimal amount", create_model("DecimalModel", __base__=BaseModel, total=(Decimal, ...))),
    ("a set-typed field", create_model("SetModel", __base__=BaseModel, tags=(set[str], ...))),
    ("a two-type union", create_model("UnionModel", __base__=BaseModel, thing=(str | int, ...))),
    ("a non-string mapping key",
     create_model("KeyModel", __base__=BaseModel, by_id=(dict[int, str], ...))),
    ("a model with no fields", create_model("EmptyModel", __base__=BaseModel)),
    ("a self-referential model", _SelfReferential),
    ("a type that is not a model", datetime),
])
def test_an_annotation_with_no_rendering_rule_raises(label, model):
    """A vague `"<value>"` would be worse than a crash: the prompt keeps generating, the new field
    reaches the model with no shape, and what comes back is whatever the name suggested. `float`
    and `Decimal` are refused by their own rule — every score here is integer basis points."""
    with pytest.raises(SchemaGenerationError):
        generate_schema_block(model)


@pytest.mark.gate
def test_a_governed_field_retyped_off_string_is_refused():
    """`intent` holds a word from a closed set. If the contract ever retypes it — to an int code,
    say — the prompt cannot offer a word list for it, and generating a block that quietly stopped
    showing the vocabulary is how the extractor and the S-3 validator start disagreeing."""
    variant = create_model("RetypedIntent", __base__=BaseModel, intent=(int, ...))
    with pytest.raises(SchemaGenerationError, match="intent"):
        generate_schema_block(variant)


@pytest.mark.gate
@pytest.mark.parametrize("lane, keys", sorted(untyped_lane_sets().items()))
def test_an_untyped_lane_is_shown_as_its_closed_key_set(lane, keys):
    """The three untyped lanes name every key they may carry, and no others.

    THIS TEST REPLACES ONE THAT ENCODED THE DEFECT. It read, verbatim:

        def test_open_lane_dicts_are_shown_as_open_objects_not_as_invented_fields():
            \"\"\"`roles`, `relationships` and `scheduling_proposals` are untyped by design. A
            realistic example key there (`"deal_stage"`) reads as a required field — which is the
            268-invented-names failure arriving through the example instead of through the
            schema.\"\"\"
            block = _block()
            for field in ("roles", "relationships", "scheduling_proposals"):
                assert block[field] == [{"<key>": "<any JSON value>"}], block[field]

    Half of that reasoning is right and the conclusion does not follow. Showing ONE realistic
    invented key would indeed read as a required field — but the answer to "do not show one
    invented name" is not "invite any name at all". `[{"<key>": "<any JSON value>"}]` was an
    explicit licence to make a field name up, issued to the two profiles (`chat`, `transcript`)
    that emphasise these very lanes, and nothing between the model and `l1_extraction_results`
    refused what came back: S-2 checks that a mapping's keys are strings, S-3 is never applied to
    a mapping's keys at all. So the old assertion pinned the 268-invented-names failure in place
    while its docstring explained why that failure must not happen.

    The third option is the correct one and is what `vocabulary.UNTYPED_LANE_KEYS` now provides:
    enumerate the real keys — the ones `context/pipeline.py` actually reads off these lanes — so
    the model is shown a closed set rather than an example or a blank cheque. Anything it wants
    to say outside them goes to `unclassified_observations`, which the VOCAB block tells it in
    the same breath and `capture/semantic/sink_guard.py` enforces at the sink.
    """
    block = _block()
    assert block[lane] == [{key: "<string, or omit this key>" for key in sorted(keys)}], block[lane]


@pytest.mark.gate
def test_no_untyped_lane_still_invites_an_invented_field_name():
    """The negative form, over the WHOLE block rather than the three fields by name.

    A fourth `list[dict[str, Any]]` field added to `ExtractionResult` would render through the
    open-mapping branch and re-open the hole one field over — with the parametrised test above
    still green, because it only iterates the lanes that are already closed.
    """
    block = _block()
    open_objects = [name for name, value in block.items()
                    if value == [{"<key>": "<any JSON value>"}]]
    assert not open_objects, (f"{open_objects} ask the model for an object with any key it likes; "
                              "close them in vocabulary.UNTYPED_LANE_KEYS so the sink guard can "
                              "route what it refuses into the open lane")
