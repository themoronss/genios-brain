"""L6 render validators reject FIELDS, not whole renders.

Both used to discard everything the model produced the moment any one field failed.
"""
from genios_engine.deliver.render import HEADLINE_CAP, render_copy

# ── validators reject FIELDS, not whole renders ─────────────────────────────────
def test_an_overlong_headline_does_not_destroy_a_good_situation_line():
    """39 of 43 live renders were rejected — 27 V-02, 12 V-01 — and every rejection returned the
    whole template plus an empty artifact body. A headline three characters over the cap says
    nothing about whether the situation line is sound, and ~91% of the layer's LLM spend was
    paid for and thrown away on that reasoning."""
    template = {"fallback": {"headline": "{entity}", "situation": "{stage}"},
                "artifact_kind": "draft"}
    facts = {"company": {"value": "Acme"}}
    slots = {"entity": "Acme", "stage": "negotiation"}

    class _LLM:
        def call(self, prompt, max_tokens=600):
            class R:
                ok, model, input_tokens, output_tokens = True, "m", 1, 1
                parsed = {"headline": "A" * (HEADLINE_CAP + 5),
                          "situation": "Acme is in negotiation",
                          "artifact": "Acme"}
            return R()

    out = render_copy(reason_code="stalled_deal", template=template, facts=facts,
                      slots=slots, llm=_LLM())
    assert out["headline"] == "Acme"                       # the one bad field fell back …
    assert out["situation"] == "Acme is in negotiation"     # … its sibling survived
    assert out["reject_code"] == "V-01"
    assert "headline" in out["reject_detail"]


def test_an_invented_name_in_the_draft_does_not_destroy_the_copy():
    """The artifact is the longest chunk and the likeliest to name something ungrounded, so an
    invented surname in a draft body was routinely destroying a perfectly grounded headline and
    situation alongside it."""
    template = {"fallback": {"headline": "{entity}", "situation": "{stage}"},
                "artifact_kind": "draft"}
    facts = {"company": {"value": "Acme"}}
    slots = {"entity": "Acme", "stage": "negotiation"}

    class _LLM:
        def call(self, prompt, max_tokens=600):
            class R:
                ok, model, input_tokens, output_tokens = True, "m", 1, 1
                parsed = {"headline": "Acme stalled",
                          "situation": "Acme is in negotiation",
                          "artifact": "Hi Bartholomew, following up on Acme"}
            return R()

    out = render_copy(reason_code="stalled_deal", template=template, facts=facts,
                      slots=slots, llm=_LLM())
    assert out["headline"] == "Acme stalled"
    assert out["situation"] == "Acme is in negotiation"
    assert out["artifact"]["body"] == ""                   # the unusable field, and only it
    assert out["reject_code"] == "V-02"
    # A card whose copy survived is an LLM render even when the attachment did not — calling it
    # raw_slot conflated "we could not write the copy" with "we could not write the draft".
    assert out["render_mode"] == "llm"


def test_a_clean_render_still_reports_no_rejection():
    template = {"fallback": {"headline": "{entity}", "situation": "{stage}"},
                "artifact_kind": "draft"}
    facts = {"company": {"value": "Acme"}}
    slots = {"entity": "Acme", "stage": "negotiation"}

    class _LLM:
        def call(self, prompt, max_tokens=600):
            class R:
                ok, model, input_tokens, output_tokens = True, "m", 1, 1
                parsed = {"headline": "Acme stalled", "situation": "Acme in negotiation",
                          "artifact": "Acme negotiation"}
            return R()

    out = render_copy(reason_code="stalled_deal", template=template, facts=facts,
                      slots=slots, llm=_LLM())
    assert out["reject_code"] is None
    assert out["reject_detail"] is None
    assert out["render_mode"] == "llm"
