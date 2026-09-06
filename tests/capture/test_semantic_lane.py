"""D6b · the S2 seam — Wave W9.

Eleven modules under `capture/semantic/` were built and none of them was ever reached: no call
site in `genios_engine/` named `extractor.extract`, so the whole Semantic Extraction Engine was
dead weight that every test in `tests/capture/semantic/` proved correct and nothing ran.

    pytest tests/capture/test_semantic_lane.py -q

Three properties, and the middle one is the expensive half:

* an unstructured event with a lane makes the model call and comes back with an extraction;
* a STRUCTURED event makes **ZERO** calls — `capture/gate/gate.py`'s short-circuit routes a typed
  object around the model, and a lane that ignored it would put an LLM bill on every CRM row;
* a lane that is not supplied changes nothing at all, which is what makes this wiring safe to
  land before any tenant is activated.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture import pipeline as P

WAVE = "W9"
GATE = "D6b"

OWNER = "founder@genios.ai"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

#: The smallest answer that is a valid extraction — a message that said nothing structured still
#: has an intent and a stance, and `tests/capture/semantic/test_extractor.py` pins that shape.
MINIMAL_ANSWER = {"intent": "inform", "stance": "neutral"}


def _email(**over) -> RawObject:
    kwargs = dict(
        source="gmail", object_type="email_message", source_object_id="m_s2_1",
        occurred_at=NOW, actor_email="buyer@acme.com", recipients=(OWNER,),
        raw={"subject": "Contract", "body": "We can move forward with the annual contract."})
    kwargs.update(over)
    return RawObject(**kwargs)


def _crm_deal() -> RawObject:
    """A typed CRM object — the structured bypass lane. gate.py:60-65 short-circuits it."""
    return RawObject(source="hubspot", object_type="deal", source_object_id="deal_1",
                     occurred_at=NOW, actor_email=OWNER, content_version="v1",
                     raw={"dealname": "Acme", "dealstage": "contractsent", "amount": "84000"})


def _lane(llm, **over):
    kwargs = dict(llm=llm, eval_time=NOW)
    kwargs.update(over)
    return P.SemanticLane(**kwargs)


def _capture(raw, *, lane=None, repo=None, **over):
    kwargs = dict(org_id="org_s2", connection_id="con_s2",
                  repo=repo if repo is not None else InMemorySourceEventRepository(),
                  mailbox_owner=OWNER)
    kwargs.update(over)
    if lane is not None:
        kwargs["semantic"] = lane
    return P.capture_event(raw, **kwargs)


@pytest.mark.gate
def test_an_emitted_event_reaches_the_extractor_and_carries_its_extraction(fake_llm):
    """The whole defect in one assertion: `extract()` runs, and its answer survives the seam."""
    llm = fake_llm(MINIMAL_ANSWER)
    res = _capture(_email(), lane=_lane(llm))

    assert res.outcome == "emitted"
    assert llm.call_count == 1, "S2 was wired but never called — the seam is still dead"
    assert res.extraction is not None
    assert res.extraction.intent == "inform"
    assert res.extraction_parked is None
    stages = [r.stage for r in res.trace.records]
    assert "s2_semantic_extraction" in stages, "an extraction that leaves no trace is unauditable"


@pytest.mark.gate
def test_a_structured_object_makes_zero_model_calls(fake_llm):
    """The bypass at gate.py:60-65 must still cost nothing. A FakeLLM with no canned answers
    raises on its first call, so this fails loudly rather than by an off-by-one count."""
    llm = fake_llm()
    res = _capture(_crm_deal(), lane=_lane(llm))

    assert res.outcome == "emitted"
    assert res.gated is not None and res.gated.route == "structured"
    assert llm.call_count == 0, "the structured lane paid for a model call it is defined to avoid"
    assert res.extraction is None


def test_no_lane_means_no_change_at_all(fake_llm):
    """Wiring a seam must not activate it. Without a lane the pipeline behaves exactly as before."""
    res = _capture(_email())
    assert res.outcome == "emitted"
    assert res.extraction is None
    assert [r.stage for r in res.trace.records] == [
        "landing", "preprocess", "S0", "S1", "S2", "triage", "s4_esqe", "emit"]


def test_an_unresolvable_direction_skips_the_model_rather_than_guessing(fake_llm):
    """Doc 04: *"without it an outbound offer reads as an inbound request"*. With no mailbox
    owner there is no identity to compare a sender against, so the honest answer is not to call
    the model at all — a guessed direction is the bug the envelope exists to prevent."""
    llm = fake_llm()
    res = _capture(_email(), lane=_lane(llm), mailbox_owner=None)

    assert res.outcome == "emitted"
    assert llm.call_count == 0
    assert res.extraction is None
    skip = [r for r in res.trace.records if r.stage == "s2_semantic_extraction"]
    assert skip and skip[-1].reason_code == "direction_unknown"


def test_the_owners_own_message_is_outbound_and_a_counterpartys_is_inbound(fake_llm):
    """The envelope the model is shown, read back off the prompt it was sent."""
    out = fake_llm(MINIMAL_ANSWER)
    _capture(_email(actor_email=OWNER, source_object_id="m_out"), lane=_lane(out))
    assert "outbound" in out.prompts[0]

    inn = fake_llm(MINIMAL_ANSWER)
    _capture(_email(actor_email="buyer@acme.com", source_object_id="m_in"), lane=_lane(inn))
    assert "inbound" in inn.prompts[0]


def test_a_model_that_cannot_be_repaired_parks_instead_of_dropping(fake_llm):
    """Park-never-drop reaches the pipeline: the extraction failed, the EVENT still emitted, and
    the park row travels so a drain can retry it."""
    llm = fake_llm("not json at all", "still not json")
    res = _capture(_email(), lane=_lane(llm))

    assert res.outcome == "emitted", "a failed extraction must not delete the event"
    assert res.extraction is None
    assert res.extraction_parked is not None
    assert res.extraction_parked.reason_code == "extraction_parse_failed"


def test_a_second_identical_message_is_served_from_the_cache_without_a_call(fake_llm):
    """The cache is the reason heavy L1 extraction is affordable, and it only pays if the
    pipeline hands the store down. One canned answer, two captures, one call."""
    from genios_engine.capture.semantic.cache import InMemoryExtractionCache

    cache = InMemoryExtractionCache()
    llm = fake_llm(MINIMAL_ANSWER)
    first = _capture(_email(source_object_id="m_a"), lane=_lane(llm, cache=cache))
    second = _capture(_email(source_object_id="m_b"), lane=_lane(llm, cache=cache))

    assert first.extraction is not None and second.extraction is not None
    assert llm.call_count == 1, "identical content re-read the model instead of the cache"
