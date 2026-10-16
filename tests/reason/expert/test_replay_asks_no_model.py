"""STEP-12 M33 · an expert decision replays from its stored review — zero model calls, in a fresh process.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_replay_asks_no_model.py -q

Tree `yc2_w27_s12` M33.C1.L-logic.V1.U03 (`reason/replay.py`), `03` F139 for covered files. With the
test-mode decider on, a replay re-executes the run and the decider calls the model again — in a fresh
process its cache is empty. A covered file's decision is its review's (`reason/expert/decide`): the run
is persisted through the audit store like any other, and `replay_persisted` rebuilds its request from
the review stored in `expert_reviews` and executes it on the expert's own orchestrator. Here the replay
runs in a NEW process with every model door poisoned — the decider on and raising, R-1 raising, the
R-sites' client raising — and the caller handing it the ordinary orchestrator: it matches, and asks
nothing. A review gone, or changed, is a difference the comparison names.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.expert import decide as D
from genios_engine.reason.expert import store as R
from tests.reason.expert.checks import as_written
from genios_engine.reason.store import ReasoningStore

pytestmark = pytest.mark.pg

ORG = "org_s12_m33_replay"
NOW = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
FILE, FINGERPRINT = "node_replay_fund", "ffp-replay-review-0000000000"
REPO = Path(__file__).resolve().parents[3]
RAW = {
    "facts": [{"claim": "Neel wrote asking for a first call", "evidence": ["evt_neel_0927"]},
              {"claim": "The call is booked", "evidence": ["evt_invite_1008"]}],
    "frames": {"primary": "a first call with a fund", "rivals": ["an exploratory chat"]},
    "expected_vs_actual": {"stage": None, "expected": "a pre-read", "actual": "nothing sent"},
    "scenarios": {"do_nothing": "the call runs cold", "act": "a pre-read frames it", "best": "a meeting",
                  "worst": "a pass", "signals_to_watch": ["a reply"]},
    "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible", "reasons": ["close"]},
    "mode": "act",
    "next_move": {"who": "the founder", "what": "Send Neel a pre-read", "for_whom": "Neel", "by_when": None},
    "alternative": "send it after", "wait_or_stop": "raise it on the call", "done_when": "the call happens"}

#: The fresh process: every model door poisoned, the ordinary orchestrator handed to the replay.
_REPLAY = r"""
import json, sys
from genios_engine.platform.db import get_engine
from genios_engine.reason import llm_decision_maker, llm_interpretation, llm_sites
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.replay import replay_persisted
from genios_engine.reason.store import ReasoningStore

asked = []
def _poisoned(*a, **kw):
    asked.append("model")
    raise RuntimeError("a model was asked during a replay")
llm_decision_maker.enabled_for = lambda org_id: True
llm_decision_maker.decide_with_llm = _poisoned
llm_decision_maker.client = _poisoned
llm_interpretation.interpret_request = _poisoned
llm_sites.make_site_client = _poisoned
org, run_id, url = sys.argv[1:4]
_execution, comparison = replay_persisted(
    store=ReasoningStore(engine=get_engine(url)), org_id=org, run_id=run_id,
    orchestrator=ReasoningOrchestrator(default_registry()))
print(json.dumps({"matches": comparison.matches, "review_matches": comparison.review_matches,
                  "differences": list(comparison.differences), "asked": asked}))
"""


@pytest.fixture
def persisted(pg_store):
    """A tenant whose fund file was decided from its stored review, the run in the audit store."""
    from tests.test_admin_support_packs import _erase_tenant, _seed_org
    _seed_org(pg_store, ORG)
    _erase_tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        c.execute(text("delete from expert_reviews where org_id = :o"), {"o": ORG})
        # STEP-13: decided through its check — the check of a review that stands whole (`checks.as_written`).
        assert R.write_review(c, org_id=ORG, file_id=FILE, fingerprint=FINGERPRINT,
                              model="claude-sonnet-5", prompt_version="expert-review.v2",
                              dossier_digest="d" * 64, status=R.VALID, reason=None,
                              review=ExpertReview.from_mapping(RAW), input_tokens=10, output_tokens=10,
                              cost_micro_usd=1, at=NOW, inputs={"events": ["evt_neel_0927"]},
                              triggers=[{"kind": "first_look", "says": "never judged"}],
                              checked=as_written(ExpertReview.from_mapping(RAW)))
        row = R.read_review(c, ORG, FILE, FINGERPRINT)
    request = D.request_for(row, org_id=ORG, root_entity_type="company", domain="founder_office",
                            eval_time=NOW, graph_version=3)
    bundle = persist_execution(store=ReasoningStore(engine=pg_store.engine), execution=D.decide(request))
    try:
        yield pg_store, bundle["run"]["run_id"]
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from expert_reviews where org_id = :o"), {"o": ORG})
        _erase_tenant(pg_store, ORG)


def _replay(store, run_id: str) -> dict:
    url = store.engine.url.render_as_string(hide_password=False)
    out = subprocess.run([sys.executable, "-c", _REPLAY, ORG, run_id, url], cwd=REPO,
                         capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                         timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_the_run_is_audited_like_any_other(persisted):
    store, run_id = persisted
    with store.engine.connect() as c:
        run = c.execute(text("select capability_id, input_manifest->>'original_trigger_kind', trigger_ref, "
                             "       mode from reasoning_runs where org_id = :o and run_id = :r"),
                        {"o": ORG, "r": run_id}).one()
    # ⛔ RESTATED by yc2_w27_s13/M35.C3.L-integration.V1.U06 (X12): the run is keyed on the review and its check.
    assert tuple(run[:2]) + (D.fingerprint_of(run[2]), run[3]) == (D.CAPABILITY_ID, D.TRIGGER_KIND, FINGERPRINT, "live")
    assert D.check_version_of(run[2]) is not None


def test_a_fresh_process_replays_it_from_the_stored_review_asking_no_model(persisted):
    store, run_id = persisted
    seen = _replay(store, run_id)
    assert seen == {"matches": True, "review_matches": True, "differences": [], "asked": []}


def test_a_review_that_is_gone_is_a_difference_the_replay_names(persisted):
    store, run_id = persisted
    with store.engine.begin() as c:
        c.execute(text("delete from expert_reviews where org_id = :o"), {"o": ORG})
    seen = _replay(store, run_id)
    assert (seen["matches"], seen["review_matches"]) == (False, False)
    assert "expert_review_missing" in seen["differences"] and seen["asked"] == []


def test_a_review_changed_since_is_a_difference_the_replay_names(persisted):
    store, run_id = persisted
    changed = dict(RAW, appraisal=dict(RAW["appraisal"], urgency="low"))
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set review = cast(:r as jsonb) where org_id = :o"),
                  {"o": ORG, "r": json.dumps(changed)})
    seen = _replay(store, run_id)
    assert seen["review_matches"] is False and "expert_review" in seen["differences"]
    assert seen["matches"] is False and seen["asked"] == []


def test_a_review_that_is_no_longer_valid_rebuilds_nothing(persisted):
    """Only a valid review may be read for a decision (`migrations/0197`): a row that is not one is
    no review to rebuild from — the stored request is replayed, and the comparison says so."""
    store, run_id = persisted
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set status = 'refused', reason = 'uncited_fact', review = null "
                       " where org_id = :o"), {"o": ORG})
    seen = _replay(store, run_id)
    assert seen["review_matches"] is False and "expert_review_missing" in seen["differences"]
