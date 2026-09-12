"""Every Layer 1 model call reaches `llm_costs`, priced as the model actually called.

Two gaps, one consequence. S2's extraction and S4's relevance page called the model and wrote
nothing to `llm_costs` — the ledger the cost governor opens each day from and the admin console
reports — so their spend could not bind the daily ceiling. And the governor priced T2/T3 at
Sonnet 5 / Opus 5 rates while the deployed lane calls one Haiku client at every tier, over-stating
a T3 call 5x and refusing or demoting work the budget could afford.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


# ── pricing the model actually called ─────────────────────────────────────────────────────────

def test_the_lane_prices_every_tier_at_the_one_model_it_calls():
    from genios_engine.capture.semantic.batch import TIERS
    from genios_engine.platform.wiring import tier_prices_for_model

    haiku = tier_prices_for_model("claude-haiku-4-5-20251001")
    assert set(haiku) == set(TIERS)
    for tier in TIERS:
        assert (haiku[tier].input_per_mtok, haiku[tier].output_per_mtok) == (100, 500), tier
        assert haiku[tier].priced_against == "claude-haiku-4-5-20251001"

    sonnet = tier_prices_for_model("claude-sonnet-5")["T3"]
    assert (sonnet.input_per_mtok, sonnet.output_per_mtok) == (200, 1000)


def test_the_governor_charges_a_haiku_call_at_haiku_rates(monkeypatch):
    from genios_engine.capture.semantic.batch import ExtractionRequest
    from genios_engine.platform import wiring

    monkeypatch.setattr(wiring, "get_settings", lambda: SimpleNamespace(
        daily_llm_usd_cap=25.0, daily_t3_llm_usd_cap=0))
    monkeypatch.setattr(wiring, "_org_tier", lambda *_a: "startup")
    # Large enough that the estimate is well above the one-cent rounding floor.
    request = ExtractionRequest(event_id="e1", profile_id="email",
                                content="Budget approved for the renewal. " * 1_500,
                                requested_tier="T2", envelope_chars=0)

    as_called = wiring.make_cost_governor(
        "org_1", engine=None, prices=wiring.tier_prices_for_model("claude-haiku-4-5"))
    as_routed = wiring.make_cost_governor("org_1", engine=None)          # Sonnet 5 rates for T2
    assert as_called.decide(request).admitted and as_routed.decide(request).admitted

    assert 0 < as_called.ledger.spent_minor < as_routed.ledger.spent_minor


def test_the_semantic_lane_is_wired_with_the_called_models_prices_and_a_cost_sink():
    from genios_engine.platform import wiring

    source = inspect.getsource(wiring.make_semantic_lane)
    assert "tier_prices_for_model(" in source
    assert "cost_sink=cost_sink" in source
    assert "RelevancePage(llm=llm, governor=governor,\n" in source


# ── S2 extraction ─────────────────────────────────────────────────────────────────────────────

def _lane(sink):
    from genios_engine.capture.pipeline import SemanticLane
    return SemanticLane(llm=SimpleNamespace(model="claude-haiku-4-5"), eval_time=NOW,
                        cost_sink=lambda **row: sink.append(row))


def _outcome(**kw):
    base = dict(cache_hit=False, model_calls=1, input_tokens=1_200, output_tokens=300, ok=True,
                parked=None)
    return SimpleNamespace(**{**base, **kw})


def test_an_extraction_call_is_written_to_llm_costs():
    from genios_engine.capture.pipeline import L1_EXTRACT_COST_PURPOSE, _record_extraction_cost

    rows = []
    _record_extraction_cost(_lane(rows), SimpleNamespace(org_id="org_1", event_id="evt_1"),
                            _outcome())

    assert rows == [{"org_id": "org_1", "model": "claude-haiku-4-5",
                     "purpose": L1_EXTRACT_COST_PURPOSE, "input_tokens": 1_200,
                     "output_tokens": 300, "success": True, "error": None,
                     "subject_ref": "event:evt_1"}]


def test_a_parked_extraction_still_records_what_it_spent():
    from genios_engine.capture.pipeline import _record_extraction_cost

    rows = []
    _record_extraction_cost(_lane(rows), SimpleNamespace(org_id="org_1", event_id="evt_1"),
                            _outcome(ok=False, parked=SimpleNamespace(reason_code="unparseable")))
    assert rows[0]["success"] is False and rows[0]["error"] == "unparseable"


def test_a_cache_hit_made_no_call_and_files_nothing():
    from genios_engine.capture.pipeline import _record_extraction_cost

    rows = []
    event = SimpleNamespace(org_id="org_1", event_id="evt_1")
    _record_extraction_cost(_lane(rows), event, _outcome(cache_hit=True))
    _record_extraction_cost(_lane(rows), event, _outcome(model_calls=0))
    assert rows == []


def test_a_broken_cost_sink_never_stops_capture():
    from genios_engine.capture.pipeline import SemanticLane, _record_extraction_cost

    def boom(**_row):
        raise RuntimeError("db down")

    lane = SemanticLane(llm=SimpleNamespace(model="m"), eval_time=NOW, cost_sink=boom)
    _record_extraction_cost(lane, SimpleNamespace(org_id="o", event_id="e"), _outcome())


def test_the_extraction_seam_records_the_cost():
    from genios_engine.capture import pipeline

    assert "_record_extraction_cost(lane, event, outcome)" in inspect.getsource(
        pipeline.run_semantic_lane)


# ── S4 relevance page ─────────────────────────────────────────────────────────────────────────

class _FakeLLM:
    model = "claude-haiku-4-5"

    def __init__(self):
        self.calls = 0

    def call(self, _prompt, *, max_tokens=1024):
        self.calls += 1
        return SimpleNamespace(ok=True, parsed={"items": []}, raw="{}", model=self.model,
                               input_tokens=640, output_tokens=40, error=None)


def test_a_relevance_call_is_written_to_llm_costs():
    from genios_engine.capture.esqe.relevance import COST_PURPOSE, RelevancePage, _judge_batch

    rows = []
    llm = _FakeLLM()
    page = RelevancePage(llm=llm, cost_sink=lambda **row: rows.append(row), org_id="org_1")
    _judge_batch([], llm, page._record)

    assert llm.calls == 1
    assert rows == [{"org_id": "org_1", "model": "claude-haiku-4-5", "purpose": COST_PURPOSE,
                     "input_tokens": 640, "output_tokens": 40, "success": True, "error": None}]


def test_a_page_with_no_sink_or_no_org_records_nothing_and_does_not_raise():
    from genios_engine.capture.esqe.relevance import RelevancePage

    response = SimpleNamespace(ok=True, model="m", input_tokens=1, output_tokens=1, error=None)
    RelevancePage(llm=_FakeLLM())._record(response)
    rows = []
    RelevancePage(llm=_FakeLLM(), cost_sink=lambda **row: rows.append(row))._record(response)
    assert rows == []


def test_both_page_call_sites_pass_the_recorder():
    from genios_engine.capture.esqe import relevance

    source = inspect.getsource(relevance.RelevancePage)
    assert source.count("_judge_batch(") == 2
    assert source.count("self._record)") == 2


# ── the store seam the sink is built on ───────────────────────────────────────────────────────

def test_a_graph_store_can_be_bound_to_an_existing_engine():
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.wiring import _llm_cost_sink

    engine = object()
    assert GraphStore(engine=engine).engine is engine
    with pytest.raises(ValueError):
        GraphStore()
    assert _llm_cost_sink(None) is None
