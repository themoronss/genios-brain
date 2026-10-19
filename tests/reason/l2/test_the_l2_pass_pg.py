"""GeniOS-008 L2 · the pass on real Postgres: bundle in → one checked result + receipt kept → a need filed →
the watermark moved → the same inputs again cost no call. Shadow: nothing else is written.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_the_l2_pass_pg.py -q
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe.bundle import build_bundles
from genios_engine.capture.esqe.bundle_store import PostgresBundleStore
from genios_engine.capture.esqe.signal_store import PostgresSignalStore, QualifiedSignalRow
from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.reasoning_result import CONFIDENCE_DIMENSIONS
from genios_engine.platform.l4_activation import FEATURE_L2_REASONING, activate
from genios_engine.reason.l2 import store as ST
from genios_engine.reason.l2.sweep import l2_pass

pytestmark = pytest.mark.pg

ORG = "org_g008_l2_pass"
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
QUOTE = "Please send the signed renewal before Friday"


@pytest.fixture
def store():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L2 tests skipped")
    from genios_engine.context.graph_store import GraphStore
    gs = GraphStore(url)
    with gs.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Nimbus', 'l2pass@example.test')"), {"o": ORG})
    activate(gs.engine, ORG, feature=FEATURE_L2_REASONING, by="test")
    yield gs
    with gs.engine.begin() as c:
        for table in ("reasoning_results", "evidence_needs", "signal_bundles", "qualified_signals",
                      "post_pass_watermarks", "l4_r_site_calls", "l4_activation", "l2_admissions",
                      "l1_extraction_results"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


class _Sig:
    def __init__(self):
        self.signal_id = "sig_g008_1"
        self.thread_key = "th_vendor"
        self.subject_key = "vendor:acme"
        self.trace_id = "tr_g008"
        self.occurred_at = NOW - timedelta(hours=20)
        self.extraction = None
        self.coverage = {"sources": [{"source": "gmail", "completeness_bp": 9000}]}


def _seed(store):
    row = QualifiedSignalRow(
        signal_id="sig_g008_1", org_id=ORG, subject_key="vendor:acme", event_id="evt_g008_1", trace_id="tr_g008",
        signal_type="contract_renewal", importance_bp=7000, importance_version="v", confidence_bp=8000,
        extraction_ref="struct:evt_g008_1", state="active", occurred_at=NOW - timedelta(hours=20),
        due_at=NOW + timedelta(hours=30), thread_key="th_vendor", direction="inbound", ball_in_court="us",
        evidence_refs=({"source_ref": "evt_g008_1", "quote": QUOTE, "start_offset": 0,
                        "end_offset": len(QUOTE)},))
    assert PostgresSignalStore(os.environ["GENIOS_TEST_DATABASE_URL"]).put([row]) == 1
    PostgresBundleStore(engine=store.engine).put(build_bundles(ORG, "tr_g008", [_Sig()]))


def _answer():
    return {
        "facts": [{"claim": "the vendor asked for the signed renewal", "evidence": ["evt_g008_1", "sig:sig_g008_1"],
                   "quote": QUOTE}],
        "inferences": [{"claim": "the renewal waits on us", "based_on": ["fact:1"]}],
        "patterns": [], "hypotheses": [], "unknowns": [],
        "frames": {"primary": "a vendor renewal waiting on us", "rivals": ["a reminder already handled"]},
        "expected_vs_actual": {"stage": None, "expected": "a signed renewal", "actual": "not sent"},
        "scenarios": {"do_nothing": "the service lapses", "act": "it renews", "best": "renewed",
                      "worst": "lapsed", "signals_to_watch": ["a countersigned copy"]},
        "appraisal": {"stakes": "medium", "urgency": "high", "reversibility": "costly_to_reverse",
                      "reasons": ["due before Friday"]},
        "mode": "act",
        "next_move": {"who": "you", "what": "send the signed renewal", "for_whom": "Acme", "by_when": "2026-10-19",
                      "rests_on": ["fact:1"]},
        "alternative": "", "wait_or_stop": "stop if it was already sent", "done_when": "Acme confirms",
        "intervention_mode": "prepare_decision",
        "confidence": {d: {"level": "medium", "reason": "one mail", "evidence": ["sig:sig_g008_1"]}
                       for d in CONFIDENCE_DIMENSIONS},
        "options": [{"option": "send it today", "benefit": "no lapse", "downside": "none",
                     "reversibility": "reversible", "affects": "Acme", "would_change": "it was already sent"}],
        "decision_need": {"needed": False},
        "proposed_mutations": [{"op": "create", "situation": "Acme renewal", "why": "a renewal is due",
                                "evidence": ["sig:sig_g008_1"]}],
        "evidence_needs": [{"question": "was the renewal already sent?", "why_it_matters": "then nothing is owed",
                            "decision_changing": True, "subject_ref": "thread:th_vendor",
                            "acceptable_sources": ["gmail"], "unacceptable_sources": []}],
        "coverage_limitations": [], "open_conflict": None, "deeper": None}


class _Client:
    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts = []

    def call(self, prompt, *, max_tokens=400, **_):
        self.prompts.append(prompt)
        return LLMResult(parsed=_answer(), raw="{}", ok=True, model=self.model, input_tokens=12000,
                         output_tokens=2500)


def test_a_bundle_becomes_one_kept_result_one_need_and_a_moved_watermark(store):
    _seed(store)
    client = _Client()
    receipt = l2_pass(store=store, org_id=ORG, now=NOW, llm=client)
    with store.engine.connect() as c:
        why = c.execute(text("select reason from reasoning_results where org_id = :o"), {"o": ORG}).scalar()
    assert receipt["ended"] == {"result": 1}, (receipt, why)
    assert receipt["needs_filed"] == 1 and receipt["written"] == 1 and len(client.prompts) == 1
    assert QUOTE in client.prompts[0]
    with store.engine.connect() as c:
        row = c.execute(text("select subject_ref, status, lane, depth, receipt, result from reasoning_results "
                             "where org_id = :o"), {"o": ORG}).one()
        assert row.subject_ref == "seed:thread:th_vendor" and row.status == "result"
        assert row.lane == "decision" and row.depth in ("standard", "deep")
        assert row.receipt["needs_raised"] and row.receipt["termination"] == "result"
        assert row.receipt["output_hash"] and row.result["judgment"]["intervention_mode"] == "prepare_decision"
        assert ST.read_watermark(c, ORG) is not None
        need = c.execute(text("select subject_ref, state from evidence_needs where org_id = :o"), {"o": ORG}).one()
        assert (need.subject_ref, need.state) == ("thread:th_vendor", "open")


def test_nothing_new_costs_no_call(store):
    _seed(store)
    l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client())
    again = _Client()
    receipt = l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=10), llm=again)
    assert again.prompts == [] and receipt["subjects"] == 0


def test_a_met_need_reasons_the_subject_again_once(store):
    _seed(store)
    l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client())
    with store.engine.begin() as c:
        c.execute(text("update evidence_needs set state = 'met', closed_at = now() where org_id = :o"), {"o": ORG})
    second = _Client()
    receipt = l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=10), llm=second)
    assert receipt["reentries"] == 1 and len(second.prompts) == 1
    third = _Client()
    l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=20), llm=third)
    assert third.prompts == []                       # once: the answered need is now part of the fingerprint


def test_switched_off_reads_nothing(store):
    _seed(store)
    with store.engine.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})
    assert l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client()) == {"skipped": "l2_reasoning_not_activated"}


class _Sig2(_Sig):
    def __init__(self):
        super().__init__()
        self.signal_id = "sig_g008_2"
        self.thread_key = "th_other"


def test_a_carried_subject_holds_the_watermark_and_is_reasoned_next_pass(store):
    _seed(store)
    row = QualifiedSignalRow(
        signal_id="sig_g008_2", org_id=ORG, subject_key="vendor:acme", event_id="evt_g008_2", trace_id="tr_g008",
        signal_type="contract_renewal", importance_bp=5000, importance_version="v", confidence_bp=8000,
        extraction_ref="struct:evt_g008_2", state="active", occurred_at=NOW - timedelta(hours=10),
        thread_key="th_other", direction="inbound", ball_in_court="us",
        evidence_refs=({"source_ref": "evt_g008_2", "quote": QUOTE, "start_offset": 0, "end_offset": len(QUOTE)},))
    PostgresSignalStore(os.environ["GENIOS_TEST_DATABASE_URL"]).put([row])
    PostgresBundleStore(engine=store.engine).put(build_bundles(ORG, "tr_g008", [_Sig2()]))
    first = l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client(), max_per_pass=1)
    assert first["carried"] == 1 and first["written"] == 1
    second = _Client()
    again = l2_pass(store=store, org_id=ORG, now=NOW + timedelta(minutes=5), llm=second, max_per_pass=1)
    # Only the carried one is read again: the watermark sits just before its bundle, after the one reasoned.
    assert len(second.prompts) == 1 and again["subjects"] == 1, again
    with store.engine.connect() as c:
        assert c.execute(text("select count(*) from reasoning_results where org_id = :o"), {"o": ORG}).scalar() == 2


def test_the_shadow_report_reads_what_the_pass_kept(store):
    """`scripts/l2_shadow_report.py` — every query it runs, against what the pass wrote (and a file subject,
    so the TODAY side's card and review reads run too)."""
    from scripts.l2_shadow_report import report
    _seed(store)
    l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client())
    with store.engine.begin() as c:
        ST.write_sweep(c, [ST.L2Row(org_id=ORG, subject_ref="file:node_g008", fingerprint="l2fp:f",
                                    request_id="l2req:f", trigger="bundle", status="failed", depth="standard",
                                    prompt_version="p", reasoned_at=datetime.now(timezone.utc),
                                    reason="the call failed")], org_id=ORG, watermark=None)
    rows = {r["subject"]: r for r in report(store.engine, ORG, days=36500)}
    seed = rows["seed:thread:th_vendor"]
    assert seed["lane"] == "decision" and seed["intervention"] == "prepare_decision"
    assert seed["needs"] == ["was the renewal already sent?"]
    assert rows["file:node_g008"]["today"] == {"cards": [], "expert": None}


def test_the_pass_files_l3s_admission_of_what_it_proposed(store):
    """L2 rebuild B3, at the call site: the seed subject's `create` has no situation row behind it yet — L3
    HOLDS it at subject level, in the pass's own write."""
    _seed(store)
    receipt = l2_pass(store=store, org_id=ORG, now=NOW, llm=_Client())
    assert receipt.get("admissions") == {"hold": 1}, receipt
    with store.engine.connect() as c:
        row = c.execute(text("select subject_ref, situation_id, decision, op, result_fingerprint from l2_admissions "
                             "where org_id = :o"), {"o": ORG}).one()
        fp = c.execute(text("select fingerprint from reasoning_results where org_id = :o"), {"o": ORG}).scalar()
    assert (row.subject_ref, row.situation_id, row.decision, row.op) == ("seed:thread:th_vendor", "-", "hold", "create")
    assert row.result_fingerprint == fp


def test_the_amounts_a_signal_names_reach_the_prompt_as_the_money_tool(store):
    """L2 rebuild · the renewal's two prices are read from the signal's extraction in ONE read for the pass, and the
    model is shown the arithmetic — it never computes the 32% itself, and the check holds the number it repeats."""
    import json
    _seed(store)
    with store.engine.begin() as c:
        c.execute(text("insert into l1_extraction_results (processing_key, org_id, event_id, output) "
                       "values ('pk_g008_1', :o, 'evt_g008_1', cast(:out as jsonb))"),
                  {"o": ORG, "out": json.dumps({"amounts": [
                      {"currency": "USD", "minor_units": 100000, "as_written": "$1,000"},
                      {"currency": "USD", "minor_units": 132000, "as_written": "$1,320"}]})})
    client = _Client()
    l2_pass(store=store, org_id=ORG, now=NOW, llm=client)
    assert "[tool:amounts]" in client.prompts[0] or "tool:amounts" in client.prompts[0]
    assert "the largest is 32% above the smallest (USD 320.00 more)" in client.prompts[0]
