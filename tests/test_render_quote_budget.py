"""Evidence bytes survive the prose budget; quotation marks alone earn nothing."""
import pytest

from genios_engine.deliver.render import render_copy
from tests.test_render_compiled_copy import _llm

QUOTE = 'We sent the deck — "please review".\n  The next section stays exact. ' * 5
BODY = 'They were sent: "' + QUOTE + '"'


@pytest.mark.parametrize("use_llm", [False, True])
def test_a_verified_quote_is_not_counted_as_prose_or_normalised_inside_the_fallback(use_llm):
    rendered = render_copy(reason_code="campaign", template={"fallback": {
        "headline": "Review the send", "situation": 'They were sent: "{quote}"'}},
        facts={"campaign.quote": {"value": QUOTE}}, slots={"quote": QUOTE},
        quotes=[{"event_id": "event", "quote": QUOTE, "source_verified": True}],
        llm=_llm("Review the send", BODY, "") if use_llm else None)
    assert rendered["situation"] == BODY
    assert rendered["reject_code"] is None


@pytest.mark.parametrize("receipt", [{}, {"source_verified": False}, {"source_verified": True}])
def test_quotation_marks_or_an_unattributed_verified_flag_do_not_bypass_the_cap(receipt):
    rendered = render_copy(reason_code="campaign", template={"fallback": {
        "headline": "Review", "situation": "The send is awaiting a reply."}},
        facts={"campaign.quote": {"value": QUOTE}}, slots={},
        quotes=[{"quote": QUOTE, **receipt}], llm=_llm("Review", BODY, ""))
    assert len(rendered["situation"]) <= 140


def test_a_verified_quote_does_not_exempt_invented_names_in_the_surrounding_prose():
    rendered = render_copy(reason_code="campaign", template={"fallback": {
        "headline": "Review", "situation": 'They were sent: "{quote}"'}},
        facts={}, slots={"quote": QUOTE},
        quotes=[{"event_id": "event", "quote": QUOTE, "source_verified": True}],
        llm=_llm("Review", 'Initech approved: "' + QUOTE + '"', ""))
    assert rendered["reject_code"] == "V-02"
    assert rendered["situation"] == BODY
