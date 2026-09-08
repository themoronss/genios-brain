"""R-4 · the expected effect, framed — where every number is the engine's and none is the model's.

Doc 04 E4 settles the division of labour in one line: *"the LLM may FRAME it (R-4), never compute
it"*. `decision_maker.do_nothing_record` computes `{cost_bp, horizon, statement, source}` and
foresight computes base rates; this site turns them into a sentence. The tests are therefore about
two things only: that the model cannot introduce a number, and that an UNMEASURED number never
becomes a rendered zero.
"""

from __future__ import annotations

from genios_engine.contracts.reasoning import ReasoningBundle, bare_numbers
from genios_engine.reason import narration as N
from genios_engine.reason.bundle.gate import force_failed
from genios_engine.reason.llm_sites import (
    OUTCOME_CACHED,
    OUTCOME_PRECONDITION,
    OUTCOME_RAN,
    InMemorySiteCache,
    make_gate,
)

COMPUTED = {"cost_bp": 2800, "source": "computed", "statement": "computed sentence"}
MANIFEST = {"cost_bp": 0, "source": "manifest_fallback",
            "statement": "Leaving this unaddressed carries risk."}


class Client:
    model = "claude-haiku-4-5"

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = 0
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=600):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        self.prompts.append(prompt)
        body = self.texts[min(self.calls - 1, len(self.texts) - 1)]
        return LLMResult(parsed={"expected_effect": body}, raw="", ok=True, model=self.model,
                         input_tokens=700, output_tokens=180)


def gate(client=None, *, activated=frozenset({"bundle"})):
    """The ONE C5 gate, wired for a test — never a stand-in for it."""
    return make_gate(org_id="org_1", client=client, activated=activated)


def frame(inputs, client=None, site_gate=None, **kwargs):
    return N.frame_expected_effect(org_id="org_1", decision_hash="dh_1", inputs=inputs,
                                   gate=(site_gate or gate(client)), **kwargs)


def inputs(**kwargs):
    base = {"do_nothing": COMPUTED, "horizon_days": 11, "close_probability_bp": 3400,
            "action_label": "renewal outreach"}
    base.update(kwargs)
    return N.EffectInputs(**base)


# ── which numbers exist at all ───────────────────────────────────────────────────────────────

def test_only_numbers_something_actually_computed_become_placeholders():
    assert N.effect_numbers(inputs()) == {"do_nothing_cost_bp": 2800, "days_to_horizon": 11,
                                          "close_probability_bp": 3400}


def test_a_manifest_fallback_contributes_no_cost_number():
    """E4's `source` is the honesty of the other three: an uncomputed cost must never render as a
    measurement, and `manifest_fallback` carries `cost_bp: 0` — the exact number that would read as
    "inaction is free"."""
    numbers = N.effect_numbers(inputs(do_nothing=MANIFEST))
    assert "do_nothing_cost_bp" not in numbers


def test_an_unmeasured_base_rate_is_absent_rather_than_zero():
    numbers = N.effect_numbers(inputs(close_probability_bp=None, play_win_rate_bp=None))
    assert "close_probability_bp" not in numbers and "play_win_rate_bp" not in numbers


def test_with_nothing_computed_and_nothing_stated_the_site_does_not_run():
    client = Client("anything")
    result = frame(N.EffectInputs(do_nothing={}), client=client)
    assert result.receipt.outcome == OUTCOME_PRECONDITION and client.calls == 0


# ── what the model may say ───────────────────────────────────────────────────────────────────

def test_a_framing_with_placeholders_only_is_accepted_and_rendered_by_code():
    client = Client("Acting now closes this {days_to_horizon} days before the date; "
                    "inaction costs {do_nothing_cost_bp} basis points.")
    result = frame(inputs(), client=client)
    assert result.receipt.outcome == OUTCOME_RAN
    assert result.numbers_used == {"days_to_horizon": 11, "do_nothing_cost_bp": 2800}
    assert result.rendered.startswith("Acting now closes this 11 days")


def test_a_generated_number_is_refused():
    client = Client("Acting today saves $84,000 of exposure.")
    result = frame(inputs(), client=client)
    assert result.fell_back and "bare_number" in result.receipt.reason_codes


def test_a_framing_that_uses_no_computed_number_is_refused_when_numbers_exist():
    """A framing that ignores every measurement is prose about nothing, and the measurements are
    the only reason this site is allowed to speak."""
    client = Client("Acting now would be better than not acting.")
    result = frame(inputs(), client=client)
    assert result.fell_back and "no_number_referenced" in result.receipt.reason_codes


def test_only_numbers_the_prose_references_come_back():
    """The bundle refuses a `numbers_used` entry no sentence shows — so the site returns the
    referenced subset, not everything it offered."""
    client = Client("Inaction costs {do_nothing_cost_bp} basis points.")
    result = frame(inputs(), client=client)
    assert result.numbers_used == {"do_nothing_cost_bp": 2800}


def test_the_prompt_never_shows_the_model_a_digit_it_could_copy():
    client = Client("Inaction costs {do_nothing_cost_bp} basis points.")
    frame(inputs(action_label="Renewal at risk 84,000 · 11 days"), client=client)
    prompt = client.prompts[0]
    assert "84,000" not in prompt
    assert "2800" not in prompt and "3400" not in prompt


def test_the_model_is_told_not_to_promise_an_outcome():
    client = Client("Inaction costs {do_nothing_cost_bp} basis points.")
    frame(inputs(), client=client)
    assert "Do not promise an outcome" in client.prompts[0]


# ── the deterministic fallback ───────────────────────────────────────────────────────────────

def test_the_template_states_the_same_two_facts_with_the_same_placeholders():
    result = frame(inputs(), client=None)
    assert result.generation == "template_fallback"
    assert result.numbers_used == {"days_to_horizon": 11, "do_nothing_cost_bp": 2800,
                                   "close_probability_bp": 3400}
    assert bare_numbers(result.text) == ()
    assert "11 days" in result.rendered and "2800 basis points" in result.rendered


def test_a_stored_manifest_sentence_carrying_digits_never_reaches_prose():
    """It is TRUE and it is still refused: a digit in prose is a digit the bundle will not carry."""
    stated = {"source": "manifest_fallback",
              "statement": "Leaving this unaddressed costs about 2800 basis points a day."}
    result = frame(N.EffectInputs(do_nothing=stated, action_label="renewal outreach"),
                   client=None)
    assert bare_numbers(result.text) == ()
    assert "2800" not in result.text


def test_a_headline_carrying_a_number_is_replaced_rather_than_repaired():
    assert N.EffectInputs(action_label="Renewal · 84,000 · 11 days").safe_action_label == (
        "the recommended action")
    assert N.EffectInputs(action_label="renewal outreach").safe_action_label == (
        "renewal outreach")


def test_both_the_generation_and_the_template_fit_inside_a_real_bundle():
    for client in (None, Client("Inaction costs {do_nothing_cost_bp} basis points.")):
        result = frame(inputs(), client=client)
        bundle = ReasoningBundle(
            decision_id="decision_1", action_id="outreach", headline="Renewal at risk",
            situation_summary="s", why_it_matters="w", root_cause="r",
            recommendation_rationale="rr", expected_effect=result.text,
            numbers_used=dict(result.numbers_used), evidence_refs=("ev_1",))
        rendered = bundle.render()["expected_effect"]
        assert "{" not in rendered


# ── the standing guards ──────────────────────────────────────────────────────────────────────

def test_the_same_decision_framed_twice_is_framed_once():
    cache = InMemorySiteCache()
    client = Client("Inaction costs {do_nothing_cost_bp} basis points.")
    site_gate = gate(client)
    first = frame(inputs(), site_gate=site_gate, cache=cache)
    second = frame(inputs(), site_gate=site_gate, cache=cache)
    assert client.calls == 1 and second.receipt.outcome == OUTCOME_CACHED
    assert second.text == first.text and second.numbers_used == first.numbers_used


def test_a_different_measurement_is_a_different_framing():
    cache = InMemorySiteCache()
    client = Client("Inaction costs {do_nothing_cost_bp} basis points.")
    site_gate = gate(client)
    frame(inputs(), site_gate=site_gate, cache=cache)
    frame(inputs(do_nothing={**COMPUTED, "cost_bp": 3900}), site_gate=site_gate, cache=cache)
    assert client.calls == 2


def test_the_site_is_failable_and_the_card_still_says_the_true_thing():
    """Through the SHIPPED switch — one flip turns every R-site off, this one included."""
    client = Client("Inaction costs {do_nothing_cost_bp} basis points.")
    with force_failed():
        result = frame(inputs(), client=client)
    assert result.receipt.outcome == "force_failed" and client.calls == 0
    assert "2800 basis points" in result.rendered
