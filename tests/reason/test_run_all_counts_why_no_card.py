"""GeniOS-011 S18.U3 · why a judged file has no card — counted every sweep, read by the operator, said on the file.

    PYTHONPATH=. pytest -q tests/reason/test_run_all_counts_why_no_card.py                       # hermetic part
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest -q tests/reason/test_run_all_counts_why_no_card.py

Audit `l2-skips-invisible` (and `l2-l3-binding-no-situation-no-card`, `l2-daily-cap-formula-first`): every skip,
refusal, budget cap and shadow decision of the judgment lanes was a log line Rohit never sees, or a key of a receipt
`run_all` only returned. Three surfaces now carry them:

  1. `reason/runner.run_all` counts, per sweep, judged · held · refused · truncated · carried_budget · fell_back ·
     covered_not_carded · budget_exhausted — each read off the receipt of the pass that measured it — returns them
     (`why_no_card`, and in `outcomes` beside `no_capability`), and SAYS them in one line; and it says the L2
     pass's skip, with its reason, where it calls it;
  2. `scripts/pipeline_health.check_the_l2_judgment_says_why` reads `reasoning_results` and `l2_admissions`;
  3. `GET /v1/workstreams/{file_id}` carries `why_no_card`: one line, with its reason, or null while a card is open.
"""
from __future__ import annotations

import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.reason import runner
from genios_engine.reason.bundle.budget import REASON_PER_CALL

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


# ── 1 · the counts, read off each pass's own receipt (hermetic) ───────────────────────────────────

EXPERT = {"reviewed": {"valid": 3, "refused": 1, "truncated": 2, "over_budget": 1, "failed": 1},
          "carried": 4, "too_big": 1, "checked": {"shown": 2, "held": 1, "refused": 1}, "unchecked": 1,
          "covered": {}, "people": {}}
L2 = {"ended": {"result": 2, "refused": 1, "truncated": 1, "over_budget": 1, "failed": 2},
      "not_reached": {"feature_off": 1}, "carried": 3, "admissions": {"admit": 1, "hold": 2}}
COMPILED = {"budget_exhausted": 5, "covered_no_card": {"node_a": "expert_shadow",
                                                       "node_b": "covered_without_situation",
                                                       "node_c": "budget_exhausted"}}


def test_each_count_is_read_off_the_pass_that_measured_it():
    counts = runner.why_no_card(EXPERT, L2, COMPILED)
    assert tuple(counts) == runner.WHY_NO_CARD
    assert counts == {
        "judged": 3 + 2,                       # valid reviews + checked L2 results
        "held": 1 + 2,                         # the check held its move + L3 held the judgment
        "refused": 1 + 1,
        "truncated": 2 + 1,
        "carried_budget": 1 + 4 + 1 + 3,       # over budget (too_big among them) + carried, each pass
        "fell_back": 1 + 1 + 1 + 2 + 1,        # failed, check refused, unchecked; L2 failed, gate not reached
        "covered_not_carded": 3,
        "budget_exhausted": 5,
    }


def test_a_pass_that_failed_is_unmeasured_and_one_that_skipped_counted_nothing():
    """⛔ A zero is a number and an absence is "nobody looked" (`platform/funnel`). A pass that SKIPPED ran its
    gate and judged nothing: 0. A pass that FAILED measured nothing: None — and the compiled lane, when the sweep
    never entered it, is None too."""
    counts = runner.why_no_card({"error": True}, {"error": True}, {})
    assert {k: counts[k] for k in ("judged", "refused", "covered_not_carded", "budget_exhausted")} == {
        "judged": None, "refused": None, "covered_not_carded": None, "budget_exhausted": None}
    skipped = runner.why_no_card({"skipped": "expert_review_not_activated"},
                                 {"skipped": "l2_reasoning_not_activated"},
                                 {"covered_no_card": {}})
    assert skipped == {k: 0 for k in runner.WHY_NO_CARD}
    one_side = runner.why_no_card({"error": True}, L2, COMPILED)
    assert one_side["judged"] == 2 and one_side["refused"] == 1, "the pass that measured still counts"


class _Rows:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **k):
        return iter(())


def _sweep(monkeypatch, *, expert, l2, compiled):
    """`run_all` over a store whose tenant holds no pack, the three judgment lanes stubbed to the receipts given."""
    from genios_engine.platform import l3_activation
    from genios_engine.reason import bundle
    from genios_engine.reason import domain_shadow
    from genios_engine.reason.expert import sweep as expert_sweep
    from genios_engine.reason.l2 import sweep as l2_sweep
    handed: dict = {}

    def _l2(**kw):
        handed["files_due"] = kw.get("files_due")
        return l2
    monkeypatch.setattr(expert_sweep, "expert_pass", lambda **kw: expert)
    monkeypatch.setattr(l2_sweep, "l2_pass", _l2)
    monkeypatch.setattr(domain_shadow, "shadow_compile", lambda **kw: compiled)
    monkeypatch.setattr(runner, "ensure_defaults", lambda registry, org_id: None)
    monkeypatch.setattr(runner, "l1_seam_enabled", lambda engine, org_id: True)
    monkeypatch.setattr(l3_activation, "activated_domains", lambda engine, org_id: frozenset())
    monkeypatch.setattr(bundle, "narrate_published", lambda **kw: {})
    store = SimpleNamespace(engine=SimpleNamespace(connect=_Rows))
    return runner.run_all(org_id="org_s18u3", store=store, eval_time=NOW, registry=object())


def test_run_all_returns_the_counts_and_puts_them_beside_no_capability(monkeypatch):
    result = _sweep(monkeypatch, expert=EXPERT, l2=L2, compiled=COMPILED)
    assert result["why_no_card"] == runner.why_no_card(EXPERT, L2, COMPILED)
    for key in runner.WHY_NO_CARD:
        assert result["outcomes"][key] == result["why_no_card"][key], key
    assert result["why_no_card_files"] == COMPILED["covered_no_card"]


def test_an_unmeasured_count_writes_nothing_into_the_outcomes(monkeypatch):
    result = _sweep(monkeypatch, expert={"error": True}, l2={"error": True}, compiled={})
    assert result["why_no_card"]["judged"] is None
    assert not set(runner.WHY_NO_CARD) & set(result["outcomes"]), "None is not a count: no key, not a zero"


def test_the_sweep_says_its_counts_at_warning_when_a_judged_file_is_lost(monkeypatch, caplog):
    with caplog.at_level(logging.INFO, logger=runner.logger.name):
        _sweep(monkeypatch, expert=EXPERT, l2=L2, compiled=COMPILED)
    [line] = [r for r in caplog.records if "why no card" in r.getMessage()]
    assert line.levelno == logging.WARNING
    said = line.getMessage()
    for key in runner.WHY_NO_CARD:
        assert f"{key}=" in said, key
    assert "expert_shadow=1" in said and "covered_without_situation=1" in said


def test_a_sweep_that_lost_nothing_says_its_counts_at_info(monkeypatch, caplog):
    quiet = {"reviewed": {"valid": 1}, "checked": {"shown": 1}, "covered": {}, "people": {}}
    with caplog.at_level(logging.INFO, logger=runner.logger.name):
        _sweep(monkeypatch, expert=quiet, l2={"skipped": "l2_reasoning_not_activated"},
               compiled={"covered_no_card": {}})
    [line] = [r for r in caplog.records if "why no card" in r.getMessage()]
    assert line.levelno == logging.INFO and "judged=1" in line.getMessage()


def _skip_lines(caplog):
    return [r for r in caplog.records if "the L2 pass skipped" in r.getMessage()]


def test_the_l2_pass_skip_is_said_at_warning_when_it_cannot_run(monkeypatch, caplog):
    with caplog.at_level(logging.INFO, logger=runner.logger.name):
        _sweep(monkeypatch, expert={"covered": {}}, l2={"skipped": "no_model_configured"},
               compiled={"covered_no_card": {}})
    [line] = _skip_lines(caplog)
    assert line.levelno == logging.WARNING and "no_model_configured" in line.getMessage()


def test_the_l2_pass_skip_is_a_warning_when_files_were_handed_to_it(monkeypatch, caplog):
    """The files the expert handed over (`to_l2_files`) are judged by nobody when the L2 pass skips."""
    handed = {"covered": {}, "to_l2": 2, "to_l2_files": [("node_a", []), ("node_b", ["due"])]}
    with caplog.at_level(logging.INFO, logger=runner.logger.name):
        _sweep(monkeypatch, expert=handed, l2={"skipped": "l2_reasoning_not_activated"},
               compiled={"covered_no_card": {}})
    [line] = _skip_lines(caplog)
    assert line.levelno == logging.WARNING
    assert "l2_reasoning_not_activated" in line.getMessage() and "2 file(s)" in line.getMessage()


def test_a_tenant_without_l2_reasoning_is_said_at_info(monkeypatch, caplog):
    """The switch working, nothing handed over: said, never a warning on every tenant's every sweep."""
    with caplog.at_level(logging.INFO, logger=runner.logger.name):
        _sweep(monkeypatch, expert={"covered": {}}, l2={"skipped": "l2_reasoning_not_activated"},
               compiled={"covered_no_card": {}})
    [line] = _skip_lines(caplog)
    assert line.levelno == logging.INFO and "l2_reasoning_not_activated" in line.getMessage()


# ── 3 · the file page's one line (hermetic: the rule) ─────────────────────────────────────────────

def _routes():
    from genios_engine.api import workstream_routes
    return workstream_routes


def _standing(status="valid", *, mode="act", fate="shown", reason=None, at=NOW - timedelta(days=1),
              stakes="high"):
    from genios_engine.contracts.expert_review import ExpertReview
    from tests.reason.expert.test_the_review_store import REVIEW
    review = None
    if status == "valid":
        raw = REVIEW.as_mapping()
        raw["mode"] = mode
        raw["appraisal"] = {**raw["appraisal"], "stakes": stakes, "urgency": stakes}
        if mode not in ("act", "find_out"):
            raw["next_move"] = None
        review = ExpertReview.from_mapping(raw)
    checked = SimpleNamespace(fate=fate) if status == "valid" and fate else None
    return SimpleNamespace(status=status, reason=reason, review=review, checked=checked, reviewed_at=at)


def _explain(**facts):
    base = dict(open_card=False, last_card_state=None, standing=None, attempt=None, l2_last=None, l2_hold=None,
                gate_outcome=None, judging=True)
    base.update(facts)
    return _routes().explain_no_card(**base)


def test_a_file_with_an_open_card_has_no_why():
    assert _explain(open_card=True, standing=_standing()) is None


@pytest.mark.parametrize(("facts", "reason"), [
    (dict(judging=False), "judgment_off"),
    (dict(), "not_judged"),
    (dict(attempt=SimpleNamespace(status="failed", reason="model_call_raised", at=NOW)), "failed"),
    (dict(attempt=SimpleNamespace(status="over_budget", reason="daily_budget_exhausted", at=NOW)),
     "carried_budget"),
    (dict(attempt=SimpleNamespace(status="over_budget", reason=f"{REASON_PER_CALL}: 0.16 > 0.10", at=NOW)),
     "too_big"),
    (dict(standing=_standing("refused", reason="number_not_in_dossier: 4317")), "refused"),
    (dict(standing=_standing("truncated", reason="max_tokens")), "truncated"),
    (dict(standing=_standing(fate=None)), "unchecked"),
    (dict(standing=_standing(fate="refused")), "check_refused"),
    (dict(standing=_standing(fate="held")), "held_question"),
    (dict(standing=_standing(mode="wait")), "no_move"),
    (dict(standing=_standing(stakes="low")), "small_move"),
    (dict(standing=_standing(), gate_outcome="shadow"), "expert_shadow"),
    (dict(standing=_standing(), gate_outcome="indeterminate"), "budget_exhausted"),
    (dict(standing=_standing(), gate_outcome="emitted", last_card_state="resolved"), "card_closed"),
    (dict(standing=_standing()), "covered_not_carded"),
    (dict(l2_last=SimpleNamespace(status="result", reason=None, at=NOW), l2_hold="open_conflict: two dates"),
     "held"),
    (dict(l2_last=SimpleNamespace(status="truncated", reason="max_tokens", at=NOW)), "truncated"),
])
def test_each_way_a_file_has_no_card_is_one_line(facts, reason):
    why = _explain(**facts)
    assert why["reason"] == reason
    line = why["says"]
    assert line and "\n" not in line and line.endswith("."), line


def test_a_newer_failed_attempt_is_said_over_the_review_that_stands():
    why = _explain(standing=_standing(), attempt=SimpleNamespace(status="failed", reason="x", at=NOW))
    assert why["reason"] == "failed"
    older = _explain(standing=_standing(at=NOW), gate_outcome="shadow",
                     attempt=SimpleNamespace(status="failed", reason="x", at=NOW - timedelta(days=3)))
    assert older["reason"] == "expert_shadow", "an older attempt is not what happened last"


def test_the_refusal_says_its_reason():
    why = _explain(standing=_standing("refused", reason="number_not_in_dossier: 4317"))
    assert "number_not_in_dossier: 4317" in why["says"]


# ── PG: the route, and the operator's check ──────────────────────────────────────────────────────

ORG = "org_g011_s18u3_why"


@pytest.fixture
def world(pg_store):
    from genios_engine.context.periodic import _ensure_tenant_node
    from genios_engine.context.waiting import compute_waiting
    from tests.context.workstream_world import FOUNDER
    from tests.context.workstream_world import T0
    from tests.context.workstream_world import process
    from tests.context.workstream_world import reset
    from tests.context.workstream_world import tenant
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        _ensure_tenant_node(pg_store, c, ORG)
    for i in range(3):
        asked = T0 + timedelta(days=5 * i)
        process(pg_store, ORG, event_id=f"{ORG}_ask_{i}", sender=FOUNDER, recipients=("priya@northwind.test",),
                thread=f"t_{i}", at=asked)
        process(pg_store, ORG, event_id=f"{ORG}_her_{i}", sender="priya@northwind.test", thread=f"t_{i}",
                at=asked + timedelta(days=2))
    compute_waiting(pg_store, ORG, now=T0 + timedelta(days=60))
    try:
        yield pg_store
    finally:
        with pg_store.engine.begin() as c:
            for table in ("reasoning_results", "l2_admissions", "expert_reviews", "reasoning_fingerprints",
                          "l4_r_site_calls"):
                c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        reset(pg_store, ORG)


def _read(monkeypatch, store, file_id):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from genios_engine.platform import auth
    from genios_engine.platform.auth import AuthCtx
    from genios_engine.platform.auth import get_auth_ctx
    from tests.context.workstream_world import T0
    routes = _routes()

    class _Graph:
        engine = store.engine
    monkeypatch.setattr(routes, "_graph", _Graph())
    monkeypatch.setattr(routes, "_now", lambda: T0 + timedelta(days=60))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_admin", role="admin",
                                                            source="jwt")
    answer = TestClient(app).get(f"/v1/workstreams/{file_id}")
    assert answer.status_code == 200, answer.text
    return answer.json()


def _a_file(store) -> str:
    from genios_engine.context.workstreams import files_for
    with store.engine.connect() as c:
        files = files_for(c, ORG, now=NOW).files
    assert files, "the world filed no work"
    return str(files[0].file_id)


def test_the_file_page_says_why_it_has_no_card(monkeypatch, world):
    file_id = _a_file(world)
    assert _read(monkeypatch, world, file_id)["why_no_card"]["reason"] in ("judgment_off", "not_judged")
    from genios_engine.reason.expert import store as R
    with world.engine.begin() as c:
        R.write_review(c, org_id=ORG, file_id=file_id, fingerprint="ffp-s18u3", model="claude-sonnet-5",
                       prompt_version="expert-review.v2", dossier_digest="sha256:d", status=R.REFUSED,
                       reason="number_not_in_dossier: 4317", review=None, input_tokens=1, output_tokens=1,
                       cost_micro_usd=1, at=NOW - timedelta(days=1), inputs={"events": []}, triggers=[])
    why = _read(monkeypatch, world, file_id)["why_no_card"]
    assert why["reason"] == "refused" and "number_not_in_dossier: 4317" in why["says"]


def _result(c, subject, fp, status, *, reason=None, hours_ago=1.0):
    c.execute(text(
        "insert into reasoning_results (org_id, subject_ref, fingerprint, request_id, trigger, status, reason, "
        " depth, prompt_version, reasoned_at) values (:o, :s, :fp, :fp, 'bundle', :st, :r, 'standard', 'l2.v1', "
        " now() - make_interval(secs => :secs))"),
        {"o": ORG, "s": subject, "fp": fp, "st": status, "r": reason, "secs": hours_ago * 3600})


def _admission(c, subject, situation, decision, *, reason=None):
    c.execute(text(
        "insert into l2_admissions (org_id, subject_ref, situation_id, decision, op, reason, result_fingerprint, "
        " decided_at) values (:o, :s, :sit, :d, 'none', :r, 'rfp', now())"),
        {"o": ORG, "s": subject, "sit": situation, "d": decision, "r": reason})


def _health():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


def test_the_operator_check_reads_reasoning_results_and_l2_admissions(world):
    ph = _health()
    assert ph.check_the_l2_judgment_says_why in ph.CHECKS
    with world.engine.connect() as c:
        empty = ph.check_the_l2_judgment_says_why(c, ORG)
        assert empty.verdict == ph.NO_DATA, empty.measured
        _result(c, "file:node_a", "rfp-1", "result")
        _result(c, "file:node_b", "rfp-2", "refused", reason="nothing_stands: f1 uncited")
        _result(c, "file:node_c", "rfp-3", "over_budget", reason="daily_budget_exhausted")
        _result(c, "file:node_d", "rfp-4", "result", hours_ago=30)          # outside the window
        _admission(c, "file:node_a", "sit_1", "admit")
        _admission(c, "file:node_a", "sit_2", "hold", reason="open_conflict: two dates")
        check = ph.check_the_l2_judgment_says_why(c, ORG)
        assert check.verdict == ph.PASS, check
        assert check.measured.startswith("3 judgments in 24 h — over_budget 1, refused 1, result 1"), check.measured
        assert "L3 admitted 1, held 1" in check.measured and "spent today $0.00 of $2.00" in check.measured
        assert "refused × 1: nothing_stands: f1 uncited" in check.detail
        assert "hold × 1: open_conflict: two dates" in check.detail
        c.rollback()


def test_the_operator_check_fails_when_most_judgments_are_cut(world):
    ph = _health()
    with world.engine.connect() as c:
        _result(c, "file:node_a", "rfp-1", "truncated", reason="max_tokens")
        _result(c, "file:node_b", "rfp-2", "truncated", reason="max_tokens")
        _result(c, "file:node_c", "rfp-3", "result")
        check = ph.check_the_l2_judgment_says_why(c, ORG)
        assert check.verdict == ph.FAIL and "2 of 3 truncated" in check.measured
        c.rollback()


def test_the_operator_check_fails_over_r9s_day(world):
    ph = _health()
    with world.engine.connect() as c:
        for _ in range(3):
            c.execute(text(
                "insert into l4_r_site_calls (org_id, site, outcome, tier, cache_key, cost_micro_usd, created_at) "
                "values (:o, 'R-9', 'ran', 'T2', 'k', 700000, now())"), {"o": ORG})
        check = ph.check_the_l2_judgment_says_why(c, ORG)
        assert check.verdict == ph.FAIL and "spent today $2.10 of $2.00" in check.measured
        c.rollback()
