"""STEP-16 · the golden set's acceptance — what you tell GeniOS changes its next judgment, and a verified close is proved.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q tests/replays/test_learning_from_you.py

Tree `yc2_w27_s16` M47.C4.L-integration.V6.U08. On the recorded runs, through the real chain and the real doors:

  * F57 — the signed NDA answered the ask its card named: the card ends `verified`, BY that mail;
  * F65 — you call the investor's card wrong with your words: the next sweep reviews the file again
    (`founder_corrected`), the review cites your correction, and the decision moves (act → wait);
  * F66 — one correction for every investor file: both files are reviewed again, both cite it, both wait;
  * F67 — one click is never a pattern: a bare wrong brings back that file only, writes no correction, and the
    other programme keeps its card.

Negative controls, each caught: the trigger off — F65's file is never reviewed again and its decision never moves;
the dashboard's door unwired — F65's next dossier never shows your reason; resolution off — F57's card ends
`rule_cleared`, proving nothing. The board (every must-abstain case holds, must-detect never moves backwards) is
`scripts/golden_score.py --assert-recorded` over the whole set, in the golden lane beside this file.
"""
from __future__ import annotations

import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.marking import PASS, judge

pytestmark = [pytest.mark.pg, pytest.mark.golden]

CASES = {c.case_id: c for c in load_cases()}


@pytest.fixture(autouse=True)
def _scratch():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
            pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the golden set runs on a scratch database")


def _run(case_id: str, *, recorded: bool = True):
    """Run a case — on its recording, or (for a control that changes what the chain asks) on the ideal reader —
    and keep its tenant for the reads below."""
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteRecorder, RecordedLLM
    from tests.replays.ideal_reader import IdealReader
    case = CASES[case_id]
    llm = RecordedLLM(cassettes.load(case)) if recorded else CassetteRecorder(IdealReader(case))
    return case, run_case(case, llm, keep=True)


def _reviews(org: str):
    from sqlalchemy import text

    from genios_engine.api import routes
    with routes._graph.engine.connect() as c:
        return c.execute(text(
            "select r.file_id, n.canonical_key, r.reviewed_at, r.review ->> 'mode' as mode, r.triggers, "
            "       r.inputs -> 'corrections' as corrections "
            "  from expert_reviews r left join graph_nodes n on n.org_id = r.org_id and n.node_id = r.file_id "
            "       and n.valid_to is null where r.org_id = :o and r.status = 'valid' order by r.reviewed_at, n.canonical_key"),
            {"o": org}).fetchall()


def _corrections(org: str):
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.context import founder_corrections as fc
    with routes._graph.engine.connect() as c:
        ids = [r[0] for r in c.execute(text("select correction_id from founder_corrections where org_id = :o "
                                            "order by corrected_at"), {"o": org})]
        return [fc.by_id(c, org, i) for i in ids]


def _delta(org: str, correction):
    from genios_engine.api import routes
    from genios_engine.reason.expert.correction_delta import delta_for
    with routes._graph.engine.connect() as c:
        return delta_for(c, org, correction)


def _gone(run) -> None:
    from genios_engine.api import routes
    from tests.replays.engine_runner import remove_tenant
    remove_tenant(routes._graph.engine, run.org_id)


def _founder_corrected(row) -> bool:
    return any(t.get("kind") == "founder_corrected" for t in (row.triggers or ()))


# =================================================================================================
# the four cases, on their recordings
# =================================================================================================
def test_f57_ends_verified_by_the_signed_mail():
    case, run = _run("F57")
    try:
        assert judge(case, run).verdict == PASS
        [card] = [c for c in run.cards if c.app_sweeps]
        assert (card.state, card.ended, card.ended_by) == ("resolved", "verified", "signed")
    finally:
        _gone(run)


def test_f65_your_wrong_with_words_changes_the_next_judgment_and_is_cited():
    case, run = _run("F65")
    try:
        assert judge(case, run).verdict == PASS and [a.ok for a in run.acts] == [True]
        first, second = _reviews(run.org_id)
        assert (first.mode, second.mode) == ("act", "wait") and _founder_corrected(second)
        [correction] = _corrections(run.org_id)
        assert second.corrections == [f"corr:{correction.correction_id}"]
        [file] = _delta(run.org_id, correction).files
        assert file.changed and file.after.cited and file.before.mode == "act" and file.after.mode == "wait"
        [card] = run.cards
        assert card.ended == "called_wrong", "no second card: the review that read your words waits"
    finally:
        _gone(run)


def test_f66_one_correction_for_the_kind_changes_both_files():
    case, run = _run("F66")
    try:
        assert judge(case, run).verdict == PASS
        [correction] = _corrections(run.org_id)
        assert (correction.scope, correction.kind) == ("kind", "investor")
        delta = _delta(run.org_id, correction)
        assert (delta.reviewed, delta.changed, delta.cited) == (2, 2, 2), delta
        later = [r for r in _reviews(run.org_id) if _founder_corrected(r)]
        assert sorted(r.canonical_key for r in later) == ["harborpoint.test", "northfieldvc.test"]
        assert {c.ended for c in run.cards} == {"cleared"}, "both decisions stood down: the file waits"
    finally:
        _gone(run)


def test_f67_a_bare_wrong_changes_only_its_own_file_and_writes_no_correction():
    case, run = _run("F67")
    try:
        assert judge(case, run).verdict == PASS
        assert _corrections(run.org_id) == [], "one click generalises nothing: no correction is written"
        again = [r.canonical_key for r in _reviews(run.org_id) if _founder_corrected(r)]
        assert again == ["techbridge.test"], again
        awadh = next(c for c in run.cards if "Awadh" in c.text or "interview" in c.text)
        assert awadh.state in ("queued", "surfaced", "delivered") and awadh.ended is None, "the other file keeps its card"
    finally:
        _gone(run)


# =================================================================================================
# the negative controls — each one is caught
# =================================================================================================
def test_control_the_trigger_off_f65_is_never_reviewed_again(monkeypatch):
    from genios_engine.reason.expert import triggers
    monkeypatch.setattr(triggers, "_corrected", lambda now, then: [])
    _case, run = _run("F65")
    try:
        rows = _reviews(run.org_id)
        assert [r.mode for r in rows] == ["act"], "with nothing to bring it back, the decision never moves"
    finally:
        _gone(run)


def test_control_the_dashboard_door_unwired_f65s_dossier_never_shows_your_reason(monkeypatch):
    from genios_engine.api import routes
    from genios_engine.deliver import verdicts
    from genios_engine.reason.expert.dossier import dossier_for
    monkeypatch.setattr(verdicts, "record", lambda *a, **k: None)
    case, run = _run("F65", recorded=False)
    try:
        [row, *_rest] = _reviews(run.org_id)
        with routes._graph.engine.connect() as c:
            said = dossier_for(c, run.org_id, row.file_id, now=case.sweeps[-1]).text
        assert "the founder's verdict: wrong" not in said, "unwired, your reason never reaches the expert"
    finally:
        _gone(run)


def test_control_resolution_off_f57_ends_rule_cleared(monkeypatch):
    from genios_engine.reason import domain_shadow
    monkeypatch.setattr(domain_shadow, "CLOSED_ANSWERED", "no basis is this")
    _case, run = _run("F57", recorded=False)
    try:
        [card] = [c for c in run.cards if c.app_sweeps]
        assert card.ended != "verified" and card.state == "expired", (card.state, card.ended)
        assert any(kind == "card.expired" and cause == "rule_cleared" for kind, cause, *_ in card.events)
    finally:
        _gone(run)
