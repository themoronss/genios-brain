"""STEP-16 · what your correction changed — the review before it and the one after, read back with no model asked.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_what_a_correction_changed.py

Tree `yc2_w27_s16` M46.C4.L-logic.V4.U07 (`reason/expert/correction_delta`; STEP-16 §8.4 item 6). For each correction,
on each file it reached: the last valid review that did not see it and the first that did — each one's mode once
checked, its move as the check let it stand, whether it cited the correction, the check's fate — and whether the
decision moved. Read from the stored reviews and their stored checks, every model door poisoned.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.founder_corrections import Correction
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import correction_delta as CD
from genios_engine.reason.expert import store as R
from tests.reason.expert.checks import as_written

pytestmark = pytest.mark.pg

ORG = "org_s16_correction_delta"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
FILE, OTHER = "node_theresa", "node_other_fund"
CORR = Correction(correction_id="fc_" + "1" * 24, file_id=FILE, card_id="card_1", feedback_id=None,
                  reason="not_relevant", words="Theresa wants news only on real milestones.", scope="file", kind=None,
                  brief_line_id=None, corrected_by="user_arjun", corrected_at=AT, state="standing")
REF = f"corr:{CORR.correction_id}"


def _raw(*, mode: str, move: str | None, cites: tuple[str, ...] = ()) -> dict:
    raw = {
        "facts": [{"claim": "Theresa wrote for an update", "evidence": ["evt_theresa"]}],
        "inferences": [{"claim": "she wants the round's news", "based_on": ["fact:1", *cites]}],
        "frames": {"primary": "an investor waiting on news", "rivals": ["a polite brush-off"]},
        "expected_vs_actual": {"stage": None, "expected": "news", "actual": "none yet"},
        "scenarios": {"do_nothing": "she waits", "act": "she hears", "best": "a term sheet", "worst": "a pass",
                      "signals_to_watch": ["a milestone"]},
        "appraisal": {"stakes": "high", "urgency": "low", "reversibility": "reversible", "reasons": ["warm"]},
        "mode": mode, "wait_or_stop": "wait for a milestone", "done_when": "she has the news"}
    if move:
        raw["next_move"] = {"who": "you", "what": move, "for_whom": "Theresa", "by_when": None}
    return raw


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the reviews are read from Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'delta@s16.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _write(engine, fingerprint: str, raw: dict, *, at: datetime, file_id: str = FILE, saw: bool = False,
           status: str = R.VALID, reason: str | None = None):
    review = ExpertReview.from_mapping(raw)
    with engine.begin() as c:
        assert R.write_review(c, org_id=ORG, file_id=file_id, fingerprint=fingerprint, model="claude-sonnet-5",
                              prompt_version="expert-review.v4", dossier_digest="d" * 64, status=status, reason=reason,
                              review=review if status == R.VALID else None, input_tokens=10, output_tokens=10,
                              cost_micro_usd=1, at=at, inputs={"events": ["evt_theresa"],
                                                               **({"corrections": [REF]} if saw else {})},
                              triggers=[{"kind": "first_look", "says": "never judged"}],
                              checked=as_written(review) if status == R.VALID else None)


@pytest.fixture
def poisoned(monkeypatch):
    """Every model door raises: what changed is read from the store."""
    from genios_engine.reason import llm_decision_maker, llm_interpretation, llm_sites

    def _asked(*_a, **_k):
        raise AssertionError("a model was asked")
    monkeypatch.setattr(llm_sites, "make_site_client", _asked)
    monkeypatch.setattr(llm_decision_maker, "decide_with_llm", _asked)
    monkeypatch.setattr(llm_interpretation, "interpret_request", _asked)


def test_the_review_before_your_correction_and_the_first_after_it(engine, poisoned):
    _write(engine, "ffp-before-0", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=3))
    _write(engine, "ffp-before-1", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=1))
    _write(engine, "ffp-after-00", _raw(mode="wait", move=None, cites=(REF,)), at=AT + timedelta(hours=1), saw=True)
    _write(engine, "ffp-after-01", _raw(mode="wait", move=None, cites=(REF,)), at=AT + timedelta(days=2), saw=True)
    with engine.connect() as c:
        delta = CD.delta_for(c, ORG, CORR)
    [file] = delta.files
    assert (file.file_id, file.before.fingerprint, file.after.fingerprint) == (FILE, "ffp-before-1", "ffp-after-00")
    assert (file.before.mode, file.before.move, file.before.cited) == ("act", "Send Theresa the August update", False)
    assert (file.after.mode, file.after.move, file.after.cited, file.after.fate) == (
        "wait", "an investor waiting on news", True, "shown")
    assert file.changed and (delta.reviewed, delta.changed, delta.cited) == (1, 1, 1)


def test_a_correction_no_review_saw_yet_changed_nothing(engine, poisoned):
    _write(engine, "ffp-before-0", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=1))
    with engine.connect() as c:
        delta = CD.delta_for(c, ORG, CORR)
    [file] = delta.files
    assert file.before.fingerprint == "ffp-before-0" and file.after is None and not file.changed
    assert (delta.reviewed, delta.changed, delta.cited) == (0, 0, 0), "no review saw it: none counted"


def test_a_review_that_saw_it_and_cited_nothing_is_said_so(engine, poisoned):
    _write(engine, "ffp-before-0", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=1))
    _write(engine, "ffp-after-00", _raw(mode="act", move="Send Theresa the August update"), at=AT + timedelta(hours=1),
           saw=True)
    with engine.connect() as c:
        delta = CD.delta_for(c, ORG, CORR)
    [file] = delta.files
    assert not file.after.cited and not file.changed and (delta.reviewed, delta.cited) == (1, 0)


def test_a_correction_for_the_kind_is_read_on_every_file_that_saw_it(engine, poisoned):
    kind = Correction(**{**{f: getattr(CORR, f) for f in CORR.__slots__}, "scope": "kind", "kind": "investor"})
    _write(engine, "ffp-before-0", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=1))
    _write(engine, "ffp-after-00", _raw(mode="wait", move=None, cites=(REF,)), at=AT + timedelta(hours=1), saw=True)
    _write(engine, "ffp-other-00", _raw(mode="act", move="Send the fund the deck"), at=AT - timedelta(days=1),
           file_id=OTHER)
    _write(engine, "ffp-other-01", _raw(mode="wait", move=None, cites=(REF,)), at=AT + timedelta(hours=2),
           file_id=OTHER, saw=True)
    with engine.connect() as c:
        delta = CD.delta_for(c, ORG, kind)
    assert [f.file_id for f in delta.files] == sorted([FILE, OTHER])
    assert delta.changed == 2 and delta.scope == "kind"


def test_the_same_mode_with_another_move_is_a_change(engine, poisoned):
    _write(engine, "ffp-before-0", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=1))
    _write(engine, "ffp-after-00", _raw(mode="act", move="Ask Theresa which milestone she waits for", cites=(REF,)),
           at=AT + timedelta(hours=1), saw=True)
    with engine.connect() as c:
        [file] = CD.delta_for(c, ORG, CORR).files
    assert (file.before.mode, file.after.mode) == ("act", "act") and file.changed, "the move moved"


def test_a_review_that_is_no_decision_is_no_part_of_it(engine, poisoned):
    _write(engine, "ffp-before-0", _raw(mode="act", move="Send Theresa the August update"), at=AT - timedelta(days=1))
    _write(engine, "ffp-failed-0", _raw(mode="wait", move=None), at=AT + timedelta(hours=1), saw=True, status=R.FAILED,
           reason="network")
    with engine.connect() as c:
        [file] = CD.delta_for(c, ORG, CORR).files
    assert file.after is None, "a failed call judged nothing"


def test_every_correction_of_a_list_is_read_in_its_order(engine, poisoned):
    other = Correction(**{**{f: getattr(CORR, f) for f in CORR.__slots__}, "correction_id": "fc_" + "2" * 24})
    with engine.connect() as c:
        deltas = CD.deltas_for(c, ORG, (CORR, other))
    assert [d.correction_id for d in deltas] == [CORR.correction_id, other.correction_id]
