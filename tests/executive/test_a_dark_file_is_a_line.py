"""STEP-15 · a file decided on the shadow lane is a line in your brief, labelled — never a card.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_a_dark_file_is_a_line.py

`executive/morning_day.read_day` (tree `yc2_w27_s15` M45.C4.L-logic.V0.U01, s15-D2 = yes). A file whose domain is
not switched on is still reviewed, and the review still decides it — on the shadow lane (`reason/expert/store.
SHADOW_LANE`) — and until this unit the brief read `continue` and said nothing of it (`03` s15-F6's sibling for
F30 and F55's Dev). Now it is a line: the SAME item the live lane would have built, its headline (or question)
ending in `morning_day.SHADOW_LABEL` — `06` D2 still governs the CARD, so `card_id` is always `None` and no
`SOURCE_CARD` ever appears among its sources, whatever `reason/brief_ranking.open_decisions` would otherwise
have ranked it. F55's Dev (an `act`) and F30's own file (an `act`) are the golden set's two; both replayed from
their cassettes, no spend.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_day as M

pytestmark = pytest.mark.pg

CASES = ("F30", "F55")


@pytest.fixture(scope="module")
def days():
    import os
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the day is read from golden tenants on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    out, orgs = {}, []
    try:
        for cid in CASES:
            case = cases[cid]
            run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
            orgs.append(run.org_id)
            with engine.connect() as c:
                out[cid] = M.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        yield out
    finally:
        for org in orgs:
            engine_runner.remove_tenant(engine, org)


def _shadow(day):
    return [i for i in day.items if i.kind == B.DECISION and i.lane == "shadow"]


def test_f30_the_shadow_file_is_one_decision_line(days):
    (d,) = _shadow(days["F30"])
    assert d.subject == "Stackfield"
    assert d.material.word("headline") and d.material.word("headline").endswith(M.SHADOW_LABEL)


def test_f55_the_shadow_file_is_one_decision_line_beside_the_two_live_ones(days):
    shadow = _shadow(days["F55"])
    assert len(shadow) == 1 and shadow[0].subject == "Tanglewood"
    assert "Dev" in shadow[0].material.word("headline")
    live = [i for i in days["F55"].items if i.kind == B.DECISION and i.lane == "live"]
    assert len(live) == 2


@pytest.mark.parametrize("case_id", CASES)
def test_the_shadow_line_never_carries_a_card(days, case_id):
    (d,) = _shadow(days[case_id])
    assert d.card_id is None
    assert d.book_score_bp is None
    assert B.SOURCE_CARD not in {s.kind for s in d.sources}


@pytest.mark.parametrize("case_id", CASES)
def test_the_shadow_line_still_names_you_the_same_way_any_file_does(days, case_id):
    (d,) = _shadow(days[case_id])
    assert d.our_move is True
    assert B.SOURCE_REVIEW in {s.kind for s in d.sources}
    assert d.material.word("name")


# ── the negative control: even where a card source WOULD otherwise be found, a shadow file's never is ──────────

def test_a_card_the_book_rerank_would_otherwise_find_is_still_refused(monkeypatch):
    """`06` D2 governs the CARD, and today's card pipeline never builds one for a shadow decision at all — so a
    guard that read `carded.get(file_id)` alone would never be exercised by any real tenant. Forced here: a fake
    `carded` entry for F30's own shadow file, as if `reason/brief_ranking.open_decisions` had somehow ranked it,
    proves the guard — not the absence of data — is what refuses the card."""
    import os
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the day is read from a golden tenant on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    case = {c.case_id: c for c in load_cases()}["F30"]
    run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    try:
        with engine.connect() as c:
            before = M.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        (file_id,) = [i.about for i in before.items if i.kind == B.DECISION and i.lane == "shadow"]
        real_carded = M._carded

        def _faked(conn, org_id, now):
            # F30's own shadow file — faked as if `open_decisions` had somehow ranked it.
            return {**real_carded(conn, org_id, now), file_id: (9999, "card_fake_forced")}
        monkeypatch.setattr(M, "_carded", _faked)
        with engine.connect() as c:
            day = M.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        (d,) = _shadow(day)
        assert d.card_id is None, "a shadow file's card_id must stay None even when carded() claims one"
        assert B.SOURCE_CARD not in {s.kind for s in d.sources}
    finally:
        engine_runner.remove_tenant(engine, run.org_id)


def test_a_question_card_is_refused_the_same_way(monkeypatch):
    """The same guard, on the OTHER path a card could reach a shadow file by: a found question whose own card
    (STEP-13's) is forced here, the way a real `find_out` review on a shadow file would hand it one — F30's and
    F55's own shadow files are both `act`, so this forces the `q is not None` branch the golden set does not
    reach today."""
    import os
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the day is read from a golden tenant on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    from genios_engine.context.your_desk import OpenQuestion
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    case = {c.case_id: c for c in load_cases()}["F30"]
    run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    try:
        with engine.connect() as c:
            before = M.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        (file_id,) = [i.about for i in before.items if i.kind == B.DECISION and i.lane == "shadow"]
        real_open_questions = M.open_questions

        def _faked(conn, org_id, *, now):
            fake = OpenQuestion(question_id="q_fake", file_id=file_id, fingerprint="fp_fake", run_id=None,
                               question="Is this still the plan?", asked_at=now, card_id="card_fake_forced2")
            return (*real_open_questions(conn, org_id, now=now), fake)
        monkeypatch.setattr(M, "open_questions", _faked)
        with engine.connect() as c:
            day = M.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        asked = next(i for i in day.items if i.kind == B.QUESTION and i.about == file_id)
        assert asked.card_id is None, "a shadow file's question card_id must stay None too"
        assert B.SOURCE_CARD not in {s.kind for s in asked.sources}
        assert asked.material.word("question").endswith(M.SHADOW_LABEL)
    finally:
        engine_runner.remove_tenant(engine, run.org_id)
