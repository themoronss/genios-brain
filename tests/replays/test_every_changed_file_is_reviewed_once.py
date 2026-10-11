"""STEP-12 · M32's acceptance — every changed file reviewed once and valid; an unchanged sweep asks nothing.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_every_changed_file_is_reviewed_once.py -q

Tree `yc2_w27_s12` M32.C5.L-integration.V3.U05. Every founder case of the golden set runs through the REAL
chain with the expert switched on (`engine_runner.switch_on_the_expert`) and the ideal reader answering
(`06` D49 — no spend), with one more sweep 15 minutes after its last, bringing nothing new:

  * the files its sweeps review are exactly the files measured (`expert_files.json`), each reviewed once
    per fingerprint, every review VALID against its dossier — no refusal, no failure, no repair;
  * one model call per review, and the unchanged sweep asks the expert nothing;
  * every stored review reads back — the review the expert wrote — with no model call;
  * shadow: the case is marked exactly as its recording is — the expert moves no verdict on the board.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
from pathlib import Path

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.harness import identify_site
from tests.replays.marking import judge

CASES = load_cases()
FILES = json.loads((Path(__file__).parent / "expert_files.json").read_text())


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


class _Tagged:
    """The model the case is run with, every call tagged with the sweep it was made in."""

    def __init__(self, inner, sweep: dict) -> None:
        self.inner, self.sweep = inner, sweep
        self.model = getattr(inner, "model", "")
        self.calls: list[tuple[int, str]] = []

    def content_hash(self, material: str) -> str:
        return self.inner.content_hash(material)

    def call(self, prompt: str, **kw):
        self.calls.append((self.sweep["n"], identify_site(prompt)))
        return self.inner.call(prompt, **kw)


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_changed_file_is_reviewed_once_and_an_unchanged_sweep_asks_nothing(case, monkeypatch):
    _scratch_db()
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.contracts.expert_review import ExpertReview
    from genios_engine.reason.expert import store as reviews
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader

    extended = dataclasses.replace(
        case, sweeps=case.sweeps + (case.sweeps[-1] + dt.timedelta(minutes=15),))
    last = len(extended.sweeps) - 1
    sweep = {"n": -1}
    original = routes._run_l2_chain

    def chain(org_id, *, eval_time=None):
        sweep["n"] += 1
        return original(org_id, eval_time=eval_time)

    monkeypatch.setattr(routes, "_run_l2_chain", chain)
    model = _Tagged(CassetteRecorder(IdealReader(extended)), sweep)
    run = run_case(extended, model, keep=True)
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            rows = c.execute(text(
                "select r.file_id, r.fingerprint, r.status, r.reason, n.canonical_key "
                "  from expert_reviews r left join graph_nodes n on n.org_id = r.org_id "
                "       and n.node_id = r.file_id and n.valid_to is null "
                " where r.org_id = :o order by r.reviewed_at, r.file_id"), {"o": run.org_id}).fetchall()
            calls_before = len(model.calls)
            stored = [reviews.read_review(c, run.org_id, r.file_id, r.fingerprint) for r in rows]
        expert_calls = [s for s, site in model.calls if site == "expert"]

        assert {r.canonical_key for r in rows} == set(FILES[case.case_id]), (
            f"{case.case_id}: the files reviewed are not the files measured")
        assert all(r.status == reviews.VALID and r.reason is None for r in rows), (
            f"{case.case_id}: " + "; ".join(f"{r.canonical_key} {r.status}: {r.reason}"
                                            for r in rows if r.status != reviews.VALID))
        assert len(expert_calls) == len(rows), (
            f"{case.case_id}: {len(expert_calls)} expert calls for {len(rows)} reviews — every review is "
            "one call, and no call is left without its row")
        assert last not in expert_calls, f"{case.case_id}: the unchanged sweep asked the expert again"
        assert len(model.calls) == calls_before, "reading a stored review called a model"
        assert all(s is not None and s.review == ExpertReview.from_mapping(s.raw) for s in stored)

        recorded = judge(case, cassettes.replayed(case))
        assert judge(case, run).verdict == recorded.verdict, (
            f"{case.case_id}: the expert moved the verdict from {recorded.verdict} (it is in shadow)")
    finally:
        remove_tenant(engine, run.org_id)


@pytest.mark.pg
@pytest.mark.golden
def test_without_the_fingerprint_and_the_triggers_the_same_sweep_asks_again(monkeypatch):
    """⛔ THE NEGATIVE CONTROL: the zero above is the pass's. With every fingerprint new (nothing
    standing answers it) and every file touched, F02's unchanged sweep asks the expert again — once
    for each file it reviews."""
    _scratch_db()
    import itertools

    from genios_engine.api import routes
    from genios_engine.reason.expert import sweep as expert_pass
    from genios_engine.reason.expert.triggers import FIRST_LOOK, Trigger
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader

    fresh = itertools.count()
    monkeypatch.setattr(expert_pass, "file_fingerprint", lambda *a, **kw: f"ffp-{next(fresh):024x}")
    monkeypatch.setattr(expert_pass, "triggers_for", lambda *a, **kw: [Trigger(FIRST_LOOK, "forced")])
    case = next(c for c in CASES if c.case_id == "F02")
    extended = dataclasses.replace(
        case, sweeps=case.sweeps + (case.sweeps[-1] + dt.timedelta(minutes=15),))
    sweep = {"n": -1}
    original = routes._run_l2_chain

    def chain(org_id, *, eval_time=None):
        sweep["n"] += 1
        return original(org_id, eval_time=eval_time)

    monkeypatch.setattr(routes, "_run_l2_chain", chain)
    model = _Tagged(CassetteRecorder(IdealReader(extended)), sweep)
    run_case(extended, model)
    last = len(extended.sweeps) - 1
    asked = [site for s, site in model.calls if s == last and site == "expert"]
    assert len(asked) == len(FILES["F02"]) > 0, f"the forced sweep asked the expert {len(asked)} times"
