"""L2 rebuild C1 — with `l2_cards`, an ADMITTED Layer 2 judgment of a file IS that file's review (real Postgres).

The road a card takes from a review is the expert's (`expert_reviews` → `covered` → the compiled lane decides
the file once → the card in the review's checked words). The L2 judgment now walks it: its admitted result of a
file is written as the file's review, keyed the way the expert pass keys one, so

  * the pass covers the file in the same sweep (`receipt["covered"]`), and
  * the next expert pass reads it as the file's STANDING review — covered, and NO R-7 call is made: one judgment
    per file, one spend.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_an_admitted_judgment_reviews_its_file_pg.py -q
"""
from __future__ import annotations

import os
import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe.bundle import build_bundles
from genios_engine.capture.esqe.bundle_store import PostgresBundleStore
from genios_engine.capture.esqe.signal_store import PostgresSignalStore, QualifiedSignalRow
from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.reasoning_result import CONFIDENCE_DIMENSIONS
from genios_engine.reason.expert import store as R
from genios_engine.reason.expert import sweep as EXPERT
from genios_engine.reason.l2.prompt import PROMPT_VERSION as L2_PROMPT
from genios_engine.reason.l2.sweep import l2_pass

pytestmark = pytest.mark.pg

ORG = "org_l2c1_cards"
KUNAL = "kunal@meridianvc.test"


class _Sig:
    def __init__(self):
        self.signal_id, self.thread_key, self.subject_key = "sig_c1", "t_k", None
        self.trace_id, self.extraction = "tr_c1", None
        self.coverage = {"sources": [{"source": "gmail", "completeness_bp": 9000}]}


class _R9:
    """R-9 answering validly, citing the first event its dossier prints."""
    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400, **_):
        self.prompts.append(prompt)
        evt = re.search(r"\[(evt_[^\]\s]+)\]", prompt).group(1)
        return LLMResult(parsed={
            "facts": [{"claim": "Kunal wrote to us", "evidence": [evt]}],
            "inferences": [], "patterns": [], "hypotheses": [], "unknowns": [],
            "frames": {"primary": "a fund getting to know us", "rivals": ["a cold intro"]},
            "expected_vs_actual": {"stage": None, "expected": "a reply", "actual": "a reply came"},
            "scenarios": {"do_nothing": "it cools", "act": "it moves", "best": "a meeting", "worst": "silence",
                          "signals_to_watch": ["a reply"]},
            "appraisal": {"stakes": "medium", "urgency": "low", "reversibility": "reversible", "reasons": ["early"]},
            "mode": "wait", "wait_or_stop": "wait for their reply", "done_when": "they reply",
            "intervention_mode": "monitor",
            "confidence": {d: {"level": "medium", "reason": "one mail", "evidence": [evt]}
                           for d in CONFIDENCE_DIMENSIONS},
            "options": [], "decision_need": {"needed": False}, "proposed_mutations": [], "evidence_needs": [],
            "coverage_limitations": [], "open_conflict": None, "deeper": None},
            raw="{}", ok=True, model=self.model, input_tokens=9000, output_tokens=900)


class _NoCall:
    model = "claude-sonnet-5"

    def call(self, *a, **k):
        raise AssertionError("with l2_cards the expert makes no call")


@pytest.fixture
def world(pg_store):
    from tests.context.workstream_world import process, reset, tenant
    from tests.reason.expert.test_the_dossier import NOW
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    tenant(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_k_in", sender=KUNAL, thread="t_k", at=NOW - timedelta(days=3))
    with pg_store.engine.begin() as c:
        for feature in ("expert_review", "l2_reasoning", "l2_cards"):
            c.execute(text("insert into l4_activation (org_id, feature, enabled_by) values (:o, :f, 'test')"),
                      {"o": ORG, "f": feature})
        cor = c.execute(text("select k.correlation_id, k.anchor_node_id from context_correlations k "
                             " join context_correlation_members m on m.org_id = k.org_id "
                             "  and m.correlation_id = k.correlation_id "
                             " where k.org_id = :o and m.event_id = 'evt_k_in'"), {"o": ORG}).first()
        # The SEED today's joins file for the work (`context/situations`): live, anchored on the file.
        c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
                       " situation_type, domain, status, last_seen_at) values ('sit_c1', :o, :c, :a, "
                       " 'investor_relationship', 'admin', 'active', :at)"),
                  {"o": ORG, "c": cor.correlation_id, "a": cor.anchor_node_id, "at": NOW - timedelta(days=3)})
    assert PostgresSignalStore(url).put([QualifiedSignalRow(
        signal_id="sig_c1", org_id=ORG, subject_key=None, event_id="evt_k_in", trace_id="tr_c1",
        signal_type="relationship_change", importance_bp=6000, importance_version="v", confidence_bp=8000,
        extraction_ref="struct:evt_k_in", state="active", occurred_at=NOW - timedelta(days=3), thread_key="t_k",
        direction="inbound", ball_in_court="us",
        evidence_refs=({"source_ref": "evt_k_in", "quote": "Kunal", "start_offset": 0, "end_offset": 5},))]) == 1
    PostgresBundleStore(engine=pg_store.engine).put(build_bundles(ORG, "tr_c1", [_Sig()]))
    try:
        yield pg_store, NOW, cor.anchor_node_id
    finally:
        with pg_store.engine.begin() as c:
            for table in ("reasoning_results", "evidence_needs", "signal_bundles", "qualified_signals",
                          "post_pass_watermarks", "l4_r_site_calls", "l2_admissions", "expert_reviews"):
                c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        reset(pg_store, ORG)


def test_an_admitted_judgment_is_the_files_review_and_the_expert_then_covers_it_with_no_call(world):
    store, now, file_id = world
    r9 = _R9()
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=r9)
    assert receipt.get("admissions") == {"admit": 1}, str(receipt)
    assert list(receipt["covered"]) == [file_id] and len(r9.prompts) == 1
    with store.engine.connect() as c:
        row = R.latest_valid(c, ORG, file_id)
        admitted = c.execute(text("select situation_id, decision, op from l2_admissions where org_id = :o"),
                             {"o": ORG}).one()
    assert (admitted.situation_id, admitted.decision, admitted.op) == ("sit_c1", "admit", "unchanged")
    assert row is not None and row.status == R.VALID and row.prompt_version == L2_PROMPT
    assert row.checked is not None and row.card_lines is not None and row.review.mode == "wait"
    assert receipt["covered"][file_id] == row.fingerprint

    expert = EXPERT.expert_pass(store=store, org_id=ORG, now=now + timedelta(minutes=15), llm=_NoCall())
    assert expert["covered"].get(file_id) == row.fingerprint, expert
    assert expert["unchanged"] == 1 and expert.get("to_l2", 0) == 0


def test_without_l2_cards_the_judgment_stays_in_shadow(world):
    store, now, file_id = world
    with store.engine.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o and feature = 'l2_cards'"), {"o": ORG})
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=_R9())
    assert receipt["covered"] == {} and receipt["admissions"] == {"admit": 1}
    with store.engine.connect() as c:
        assert R.latest_valid(c, ORG, file_id) is None, "no review is written in shadow"


def test_with_l2_cards_a_file_that_moved_is_left_to_the_l2_pass_and_the_expert_makes_no_call(world):
    store, now, file_id = world
    receipt = EXPERT.expert_pass(store=store, org_id=ORG, now=now, llm=_NoCall())
    assert receipt["to_l2"] == 1 and receipt["covered"] == {}, receipt
    assert receipt["reviewed"] == {} and receipt["cost_micro_usd"] == 0


class _R9Nothing(_R9):
    """R-9 judging the file needs nothing from the founder — `nothing` / `abstain`: Layer 3 REJECTS the seed."""

    def call(self, prompt, *, max_tokens=400, **_):
        res = super().call(prompt, max_tokens=max_tokens)
        res.parsed.update({"mode": "nothing", "intervention_mode": "abstain", "wait_or_stop": "stop: nothing is owed",
                           "done_when": "nothing is owed"})
        return res


def test_a_rejected_judgment_writes_no_review_and_covers_nothing(world):
    store, now, file_id = world
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=_R9Nothing())
    with store.engine.connect() as c:
        why = c.execute(text("select reason from reasoning_results where org_id = :o"), {"o": ORG}).scalar()
    assert receipt.get("admissions") == {"reject": 1}, why
    assert receipt["covered"] == {}
    with store.engine.connect() as c:
        assert R.latest_valid(c, ORG, file_id) is None, "a rejected judgment is no file's review"
