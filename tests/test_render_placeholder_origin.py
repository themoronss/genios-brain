"""Current-path probes, NOT a reproduction of unavailable historical render inputs.

The two rejection tokens alone do not identify a producer. Never allowlist them to hide
the failure. Exact live source/prompt/model output is still needed to attribute that bug.
"""
import json

import pytest

from genios_engine.capture.documents.native import _html_to_text
from genios_engine.deliver.render import _prompt, render_copy
from tests.test_render_compiled_copy import _llm


def test_html_signature_boundaries_do_not_concatenate_the_name_and_company():
    source = _html_to_text("<p>Rohit Swerashi<br>GeniOS</p>")
    assert source == "Rohit Swerashi GeniOS"
    assert "SwerashiGeniOS" not in _prompt("campaign", {}, {"signature": {"value": source}}, {})


@pytest.mark.parametrize("token", ["Insert", "SwerashiGeniOS"])
def test_the_renderer_does_not_generate_or_allowlist_the_historical_rejection_tokens(token):
    template = {"fallback": {"headline": "Review the send", "situation": "The send awaits a reply."}}
    prompt = _prompt("campaign", template, {}, {})
    assert token not in prompt
    out = render_copy(reason_code="campaign", template=template, facts={}, slots={},
        llm=_llm("Review the send", f"{token} approved the send.", ""))
    assert json.loads(out["reject_detail"])["situation"] == f"V-02:name:{token}"
    assert token not in out["situation"]
    assert out["situation"] == template["fallback"]["situation"]
