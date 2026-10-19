"""GeniOS-008 L2 · what a run starts from: subjects from bundles (E1/E8), the tools, the plan, the dossier.

    pytest tests/reason/l2/test_the_run_inputs.py -q
"""
from __future__ import annotations

import re
from datetime import timedelta

import pytest

from genios_engine.contracts.reasoning_result import DEPTH_DEEP, DEPTH_SHALLOW, DEPTH_STANDARD
from genios_engine.reason.l2.inputs import subjects_for
from genios_engine.reason.l2.plan import compile_plan
from genios_engine.reason.l2.tools import measured_inputs, run_tools
from tests.reason.expert.test_the_dossier import FILE, NOW
from tests.reason.l2.world import bundle, file_world, signal

pytestmark = pytest.mark.unit


# ── subjects ───────────────────────────────────────────────────────────────────────────────────

def test_a_bundle_whose_events_a_file_holds_is_that_files_run():
    sigs = {"s1": signal("s1")}
    [subject] = subjects_for([bundle("b1", ["s1"])], sigs, {"evt_005": FILE})
    assert (subject.subject_ref, subject.file_id) == (f"file:{FILE}", FILE)


def test_a_bundle_no_file_holds_is_reasoned_on_its_own_thread():
    sigs = {"s1": signal("s1", event="evt_new", thread="th_vendor")}
    [subject] = subjects_for([bundle("b1", ["s1"])], sigs, {})
    assert subject.subject_ref == "seed:thread:th_vendor" and subject.file_id is None


def test_two_bundles_of_one_subject_are_one_run():
    sigs = {"s1": signal("s1"), "s2": signal("s2", event="evt_003")}
    subjects = subjects_for([bundle("b1", ["s1"], at=NOW - timedelta(hours=3)),
                             bundle("b2", ["s2"], at=NOW - timedelta(hours=1))], sigs,
                            {"evt_005": FILE, "evt_003": FILE})
    assert len(subjects) == 1
    s = subjects[0]
    assert s.bundle_ids == ("b1", "b2") and {x.signal_id for x in s.signals} == {"s1", "s2"}
    assert s.oldest_bundle_at < s.newest_bundle_at


def test_a_bundle_whose_signals_were_not_read_is_no_run():
    """A private signal is filtered at the read (`read_signals`); a bundle left with none is not reasoned on."""
    assert subjects_for([bundle("b1", ["s_private"])], {}, {}) == []


# ── tools: arithmetic only, at eval_time ───────────────────────────────────────────────────────

def test_the_tools_say_age_turn_due_and_waiting():
    sigs = [signal("s1", due=NOW - timedelta(hours=5)),
            signal("s2", direction="outbound", ball="them", at=NOW - timedelta(hours=60))]
    by = {t.tool_id: t for t in run_tools(sigs, eval_time=NOW)}
    assert by["tool:newest_signal_age"].value == 30
    assert by["tool:whose_turn"].value == "us"
    assert by["tool:nearest_due"].value["hours"] == -5 and "past due" in by["tool:nearest_due"].says
    assert by["tool:unanswered_inbound"].value == 1


def test_an_unknown_turn_is_not_a_turn():
    by = {t.tool_id for t in run_tools([signal("s1", ball="unknown")], eval_time=NOW)}
    assert "tool:whose_turn" not in by


# ── the plan: depth from measured inputs, with why ─────────────────────────────────────────────

def test_nothing_pressing_is_shallow():
    plan = compile_plan(tools={}, file_id=None, unresolved=(), truncated=False, situations=0, importance_bp=3000)
    assert plan.depth == DEPTH_SHALLOW and plan.max_calls == 1 and len(plan.groups_skipped) == 4


def test_a_file_is_standard_and_says_why():
    plan = compile_plan(tools={}, file_id=FILE, unresolved=(), truncated=False, situations=0, importance_bp=None)
    assert plan.depth == DEPTH_STANDARD and "a file's work in motion" in plan.why


def test_past_due_important_work_is_deep():
    plan = compile_plan(tools={"nearest_due": {"hours": -10}}, file_id=None, unresolved=(), truncated=False,
                        situations=0, importance_bp=8000)
    assert plan.depth == DEPTH_DEEP and plan.max_calls == 3 and not plan.groups_skipped


def test_the_model_asking_for_depth_is_heard_and_recorded():
    plan = compile_plan(tools={}, file_id=None, unresolved=(), truncated=False, situations=0, importance_bp=None,
                        asked_deeper="two sources disagree on the date")
    assert plan.depth == DEPTH_DEEP and any("asked for more depth" in w for w in plan.why)


# ── the dossier: six blocks, every id in the catalogue ─────────────────────────────────────────

def test_the_dossier_is_six_labelled_blocks_in_order():
    *_, dossier = file_world()
    heads = [line for line in dossier.text.splitlines() if line.startswith("# ")]
    assert [h[2] for h in heads] == ["A", "B", "C", "D", "E", "F"]


def test_every_printed_id_can_be_cited_and_the_files_ids_are_kept():
    *_, dossier = file_world()
    printed = set(re.findall(r"\[([^\[\]\s]+)\]", dossier.text))
    assert printed <= dossier.catalogue.evidence_ids
    assert {"sig:s1", "case:node_other", f"node:{FILE}", "tool:newest_signal_age", "evt_005",
            "num:days_quiet"} <= dossier.catalogue.evidence_ids


def test_the_signals_carry_what_l1_computed_and_the_mails_words():
    *_, dossier = file_world()
    block = dossier.text.split("# B ·")[0]
    assert "turn with: us" in block and "thread th_1" in block
    assert "  “Thanks Kunal, I will book it again tonight”" in block


def test_the_dossier_is_the_same_bytes_for_the_same_parts():
    assert file_world()[-1].digest == file_world()[-1].digest


def test_every_number_in_the_dossier_is_in_its_catalogue():
    *_, dossier = file_world()
    assert {"30", "41"} <= dossier.catalogue.numbers           # the tool's hours, the snapshot revision
