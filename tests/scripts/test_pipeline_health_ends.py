"""STEP-06 · the health check: every situation and every card says how it ended.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_ends.py -q

`scripts/pipeline_health.check_every_situation_and_card_says_how_it_ended` (tree `yc2_w27_s06 ·
M24.C4.L-interface.V4.U01`). It fails on a live situation nothing explains and on a card expired with
no reason; it names, without failing, every live situation type with no open card (`06` D25).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

ORG = "org_s06_health_ends"
NOW = datetime.now(timezone.utc)


def _health():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


def test_the_check_runs_in_every_audit():
    assert _health().check_every_situation_and_card_says_how_it_ended in _health().CHECKS


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the check needs real Postgres")
    from genios_engine.platform.db import get_engine
    from genios_engine.platform.l3_activation import activate
    eng = get_engine(live_db_url)
    _clear(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'f@health.test')"),
                  {"o": ORG})
        for sid, kind, outcome in [("s_held", "awaiting_response", "hold"),
                                   ("s_silent", "reply_owed", "admit")]:
            c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, "
                           "anchor_node_id, situation_type, domain) "
                           "values (:s, :o, :c, 'n1', :t, 'admin')"),
                      {"s": sid, "o": ORG, "c": f"corr_{sid}", "t": kind})
            c.execute(text(
                "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
                "candidate_hash, outcome, reasons, candidate, schema_version, decided_at, "
                "reevaluate_after) values (:d, :o, :s, :h, :out, cast(:r as jsonb), "
                "cast('{}' as jsonb), 'v1', :at, :retry)"),
                {"d": f"dec_{sid}", "o": ORG, "s": sid, "h": f"h_{sid}", "out": outcome,
                 "r": '["verified_evidence_required"]', "at": NOW,
                 "retry": NOW + timedelta(hours=1) if outcome == "hold" else None})
        c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
                       "reason_code, eval_time) values ('sig_h', :o, 'r1', 'n1', 50, 'rc', :t)"),
                  {"o": ORG, "t": NOW})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, why, actions, artifact, state, expires_at) values "
            "('c_raw', 'sig_h', :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), "
            "cast('[]' as jsonb), cast('{}' as jsonb), 'expired', :exp)"),
            {"o": ORG, "exp": NOW + timedelta(days=3)})
    activate(eng, ORG, domain="admin", by="test_pipeline_health_ends")
    yield eng
    _clear(eng)


def _clear(eng):
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals", "context_situations"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_it_fails_on_an_unrecorded_situation_and_a_silent_expiry_then_passes(engine):
    check = _health().check_every_situation_and_card_says_how_it_ended
    with engine.connect() as c:
        first = check(c, ORG)
    assert not first.ok
    assert first.measured.startswith("1 live situation(s) with no recorded end, 1 card(s)")
    assert "unrecorded: s_silent" in first.detail
    assert "no open card — admin:awaiting_response: held 1" in first.detail
    with engine.begin() as c:
        c.execute(text("insert into situation_outcomes (org_id, decision_id, situation_id, outcome, "
                       "recorded_at, last_seen_at) values (:o, 'dec_s_silent', 's_silent', "
                       "'no_route', :t, :t)"), {"o": ORG, "t": NOW})
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id) "
                       "values ('cev_x', 'c_raw', :o, 'card.expired', 'replaced', 'system')"),
                  {"o": ORG})
    with engine.connect() as c:
        second = check(c, ORG)
    assert second.ok, second.measured
    assert "no open card — admin:reply_owed: stopped 1" in second.detail
