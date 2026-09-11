"""Authored card budgets must pass the same closed schema that gates the corpus."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

BASE = {"render_hint": "Render the stated facts and preserve the source quote.",
        "fallback": {"headline": "Review the campaign", "situation": "The stated campaign facts."}}

@pytest.fixture
def render_validator():
    schema = json.loads(Path("Domain Expertise/_schema/situation.schema.json").read_text())
    return Draft202012Validator(schema["properties"]["render"])


@pytest.mark.parametrize("cap", [1, 140, 240])
def test_an_authored_positive_prose_budget_is_a_valid_render_property(render_validator, cap):
    assert not list(render_validator.iter_errors({**BASE, "situation_cap": cap}))


@pytest.mark.parametrize("cap", [0, -1, True, "140", None, 1.5])
def test_an_invalid_prose_budget_is_rejected_at_authoring(render_validator, cap):
    assert list(render_validator.iter_errors({**BASE, "situation_cap": cap}))


def test_default_budget_needs_no_field_and_unknown_render_keys_still_fail(render_validator):
    assert not list(render_validator.iter_errors(BASE))
    assert list(render_validator.iter_errors({**BASE, "ignore_invention_guard": True}))
