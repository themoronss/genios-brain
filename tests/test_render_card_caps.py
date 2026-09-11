"""A group briefing may declare more prose than a one-line nudge."""
import pytest

from genios_engine.deliver.render import _prompt, render_copy
from tests.test_render_compiled_copy import _llm

BODY = "The request is still open. " * 7
BODY = BODY.strip()


def test_a_card_declared_cap_reaches_model_validation_prompt_and_authored_fallback():
    template = {"situation_cap": 240, "fallback": {"headline": "Review", "situation": BODY}}
    assert "HARD LIMIT 240 characters" in _prompt("campaign", template, {}, {})
    kwargs = dict(reason_code="campaign", template=template, facts={"text": {"value": BODY}}, slots={})
    assert render_copy(**kwargs)["situation"] == BODY
    rendered = render_copy(**kwargs, llm=_llm("Review", BODY, ""))
    assert rendered["situation"] == BODY
    assert rendered["reject_code"] is None


@pytest.mark.parametrize("cap", [None, 0, -1, True, "240", 140.5])
def test_an_absent_or_invalid_card_cap_keeps_the_140_character_default(cap):
    template = {"situation_cap": cap, "fallback": {"headline": "Review", "situation": BODY}}
    assert "HARD LIMIT 140 characters" in _prompt("campaign", template, {}, {})
    assert len(render_copy(reason_code="campaign", template=template, facts={}, slots={})["situation"]) <= 140
