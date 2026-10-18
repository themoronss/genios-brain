"""STEP-02 · the legacy lane skips a rule whose decision inputs did not move — and replays what the
skipped decision did.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_legacy_lane_skips_an_unchanged_subject.py -q

Tree `yc2_w27_s02/M20.C4.L-integration.V3.U01`. One person we owe a reply (`unanswered_email`
matches), a first sweep that emits the signal and a card that is showing, then a second sweep.

  * nothing changed → the rule is not reasoned at all, and its signal stays open (a skip replays the
    `fired` the decision would have added);
  * the ball moved to their court → reasoned again, and the signal is retired — no stale skip;
  * the card expired from view while the ask is open → reasoned again: the regeneration path that
    re-surfaces an unanswered ask is the gate's to preserve, not to skip;
  * a stored DEFER verdict replays as indeterminate (the card stands); a stored suppression replays
    nothing (it kept nothing alive when it was decided).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.packs.wiring import ensure_defaults, make_registry
from genios_engine.reason import runner as runner_module
from genios_engine.reason.runner import run_all

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=15)
ORG = "legacy_gate_org"
NODE = "lg_p1"
RULE = "unanswered_email"


def _setup(store):
    from genios_engine.api.account_routes import _wipe

    stale = NOW - timedelta(days=5)
    with store.engine.begin() as conn:
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        conn.execute(text("insert into orgs (id, name, email) values (:o, :o, 'lg@example.test')"),
                     {"o": ORG})
        _wipe(conn, ORG)
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values (:n, :o, 'person', 'Ada Buyer', 'ada@acme.test')"), {"n": NODE, "o": ORG})
        for i, (field, value) in enumerate((("thread.ball_in_court", "us"),
                                            ("thread.last_inbound", stale.isoformat()))):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, :n, :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"lg_fv{i}", "f": f"lg_f{i}", "o": ORG, "n": NODE, "field": field,
                 "v": json.dumps(value), "t": stale})
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    first = run_all(org_id=ORG, store=store, eval_time=NOW, registry=registry)
    with store.engine.begin() as conn:
        signal_id = conn.execute(text(
            "select signal_id from signals where org_id=:o and rule_id=:r and subject_node_id=:n "
            "and status='open'"), {"o": ORG, "r": RULE, "n": NODE}).scalar()
        assert signal_id, first
        conn.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, expires_at, state) values ('lg_card', :s, :o, 'prescriptive', "
            "'high', 'Reply to Ada', 'Ada is waiting on us', 7000, :e, 'surfaced')"),
            {"s": signal_id, "o": ORG, "e": NOW + timedelta(days=3)})
    return registry, signal_id


def _second(store, registry, monkeypatch):
    """The second sweep, and how often the rule was reasoned in it."""
    reasoned = []
    original = runner_module.reason_legacy_rule

    def spy(**kw):
        if kw["rule"].id == RULE and kw["context"].node_id == NODE:
            reasoned.append(kw["evaluation_time"])
        return original(**kw)

    monkeypatch.setattr(runner_module, "reason_legacy_rule", spy)
    result = run_all(org_id=ORG, store=store, eval_time=LATER, registry=registry)
    return result, reasoned


def _signal(store, signal_id):
    with store.engine.connect() as conn:
        return conn.execute(text("select status from signals where org_id=:o and signal_id=:s"),
                            {"o": ORG, "s": signal_id}).scalar()


def _row(store):
    with store.engine.connect() as conn:
        return conn.execute(text(
            "select outcome, skips from reasoning_fingerprints where org_id=:o and "
            "subject_key like :k"), {"o": ORG, "k": f"legacy|%|{RULE}|{NODE}"}).first()


def test_an_unchanged_subject_is_not_reasoned_and_keeps_its_signal(pg_store, monkeypatch):
    registry, signal_id = _setup(pg_store)
    result, reasoned = _second(pg_store, registry, monkeypatch)
    assert reasoned == [], "re-reasoned a subject nothing about had changed"
    assert result["outcomes"].get("skipped_unchanged", 0) >= 1, result
    assert _signal(pg_store, signal_id) == "open", result
    assert _row(pg_store).skips == 1


def test_a_moved_fact_is_reasoned_again_and_the_signal_retired(pg_store, monkeypatch):
    registry, signal_id = _setup(pg_store)
    with pg_store.engine.begin() as conn:
        conn.execute(text("update graph_facts set value = cast(:v as jsonb) where org_id=:o and "
                          "fact_version_id='lg_fv0'"), {"o": ORG, "v": json.dumps("them")})
    result, reasoned = _second(pg_store, registry, monkeypatch)
    assert reasoned == [LATER], result
    assert _signal(pg_store, signal_id) == "resolved", result


def test_a_card_no_longer_showing_is_reasoned_again(pg_store, monkeypatch):
    """The regeneration path — an open ask whose card expired from view — must run, not skip."""
    registry, signal_id = _setup(pg_store)
    with pg_store.engine.begin() as conn:
        conn.execute(text("update cards set state='expired' where org_id=:o and card_id='lg_card'"),
                     {"o": ORG})
    _, reasoned = _second(pg_store, registry, monkeypatch)
    assert reasoned == [LATER]


def test_a_stored_defer_replays_as_indeterminate(pg_store, monkeypatch):
    registry, signal_id = _setup(pg_store)
    with pg_store.engine.begin() as conn:      # as if the last decision had been the decider's DEFER
        conn.execute(text("update reasoning_fingerprints set outcome='deferred' where org_id=:o "
                          "and subject_key like :k"), {"o": ORG, "k": f"legacy|%|{RULE}|{NODE}"})
    result, reasoned = _second(pg_store, registry, monkeypatch)
    assert reasoned == [] and _signal(pg_store, signal_id) == "open", result


def test_a_stored_suppression_replays_nothing(pg_store, monkeypatch):
    """⛔ THE NEGATIVE CONTROL for the replay: a skipped suppression does not hold a card open."""
    registry, signal_id = _setup(pg_store)
    with pg_store.engine.begin() as conn:
        conn.execute(text("update reasoning_fingerprints set outcome='suppressed' where org_id=:o "
                          "and subject_key like :k"), {"o": ORG, "k": f"legacy|%|{RULE}|{NODE}"})
    result, reasoned = _second(pg_store, registry, monkeypatch)
    assert reasoned == [] and _signal(pg_store, signal_id) == "resolved", result
