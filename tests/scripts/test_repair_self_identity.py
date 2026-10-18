"""STEP-04 · the repair undoes what the engine did before it knew who "us" is — and only that.

    pytest tests/scripts/test_repair_self_identity.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_repair_self_identity.py -q

`scripts/repair_self_identity.py` (tree `yc2_w27_s04/M22.C4.L-interface.V4.U01`), written by Claude, run
by Harsh after the deploy, applied after Rohit reads its dry run (`06` D14). Production holds threads
named after the founder (a label the engine never renames) and open cards and signals whose subject is
the founder himself (`speedrun008/YC-II W27/` STEP-04 §8.2). The repair renames each such thread after
its other side, expires each such signal, retires each such card with a `card_event` saying why — and
lists, without touching, the situations anchored on us and nothing of the tenant node's own.
"""
from __future__ import annotations

import ast
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "repair_self_identity.py"
ORG = "repair_identity_org"


def _module():
    # Imported as a module, not loaded from its path: the script holds a dataclass, and a module
    # loaded by path is not in `sys.modules`, which dataclasses read to resolve annotations.
    import importlib
    return importlib.import_module("scripts.repair_self_identity")


def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called and "get_settings" not in called


def test_the_org_is_required():
    with pytest.raises(SystemExit):
        _module().parse_args([])


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    eng = create_engine(url)
    _reset(eng)
    at = datetime.now(timezone.utc)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email, first_name, last_name) values "
                       "(:o, 'Kitebird', 'meera.iyer@gmail.com', 'Meera', 'Iyer')"), {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', 'ceo@kitebird.test', 'D6'), (:o, 'domain', 'kitebird.test', 'D6')"),
                  {"o": ORG})
        for node_id, kind, key, name in [
                ("n_me", "person", "meera.iyer@gmail.com", "Meera Iyer"),
                ("n_ceo", "service", "ceo@kitebird.test", "ceo@kitebird.test"),
                ("n_co", "company", "kitebird.test", "kitebird.test"),
                ("n_manav", "person", "manav@lumenvc.test", "Manav Rao"),
                ("n_thread", "thread", "thread:t1", "Meera Iyer — seed round pitch to Lumen"),
                ("n_thread_ok", "thread", "thread:t2", "Manav Rao — the data room"),
                ("n_tenant", "tenant", f"tenant:{ORG}", "Kitebird")]:
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                           "display_name) values (:n, :o, :t, :k, :d)"),
                      {"n": node_id, "o": ORG, "t": kind, "k": key, "d": name})
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                       "from_node_id, to_node_id) values ('ev1', 'e1', :o, 'corresponded_with', "
                       "'n_manav', 'n_thread'), ('ev2', 'e2', :o, 'corresponded_with', 'n_me', 'n_thread')"),
                  {"o": ORG})
        for sid, anchor, kind in [("sit_ceo", "n_ceo", "awaiting_response"),
                                  ("sit_period", "n_tenant", "admin_period_review"),
                                  ("sit_manav", "n_manav", "investor_relationship")]:
            c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, "
                           "anchor_node_id, situation_type, domain) values (:s, :o, :c, :a, :t, 'admin')"),
                      {"s": sid, "o": ORG, "c": f"corr_{sid}", "a": anchor, "t": kind})
        for sig, node, rule in [("sig_ceo", "n_ceo", "r1"), ("sig_manav", "n_manav", "r1"),
                                ("sig_name", "n_manav", "r2")]:
            c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
                           "reason_code, eval_time) values (:s, :o, :r, :n, 50, 'unanswered_email', :t)"),
                      {"s": sig, "o": ORG, "r": rule, "n": node, "t": at})
        for card, sig, subject in [("c_self", "sig_ceo", "ceo@kitebird.test — awaiting reply"),
                                   ("c_name", "sig_name", "Meera Iyer"),
                                   ("c_manav", "sig_manav", "Manav Rao")]:
            c.execute(text(
                "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                "score, why, actions, artifact, state, expires_at, business_subject) values "
                "(:c, :s, :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), cast('[]' as jsonb), "
                "cast('{}' as jsonb), 'queued', :exp, :subj)"),
                {"c": card, "s": sig, "o": ORG, "exp": at + timedelta(days=3), "subj": subject})
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    from sqlalchemy import text
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals", "context_situations", "graph_edges",
                      "graph_nodes"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.mark.pg
def test_the_dry_run_lists_exactly_what_is_about_us(engine):
    mod = _module()
    with engine.connect() as c:
        plan = mod.plan(c, ORG)
    assert plan.threads == [("n_thread", "Meera Iyer — seed round pitch to Lumen",
                             "Manav Rao — seed round pitch to Lumen")]
    assert plan.signals == [("sig_ceo", "n_ceo")]
    assert sorted(card for card, _ in plan.cards) == ["c_name", "c_self"]
    assert plan.situations == [("sit_ceo", "awaiting_response", "n_ceo")], (
        "the tenant node's own period situation is never listed")


@pytest.mark.pg
def test_apply_writes_it_once_with_a_card_event_per_retired_card(engine):
    from sqlalchemy import text
    mod = _module()
    with engine.connect() as c:
        plan = mod.plan(c, ORG)
    assert mod.apply(engine, plan) == {"threads": 1, "signals": 1, "cards": 2}
    with engine.connect() as c:
        state = dict(c.execute(text("select card_id, state from cards where org_id = :o"), {"o": ORG}).fetchall())
        events = c.execute(text("select card_id, kind, cause from card_events where org_id = :o "
                                "order by card_id"), {"o": ORG}).fetchall()
        thread = c.execute(text("select display_name from graph_nodes where node_id = 'n_thread'")).scalar()
        signal = dict(c.execute(text("select signal_id, status from signals where org_id = :o"), {"o": ORG}).fetchall())
        situations = c.execute(text("select count(*) from context_situations where org_id = :o "
                                    "and status = 'active'"), {"o": ORG}).scalar()
        replan = mod.plan(c, ORG)
    assert state == {"c_self": "expired", "c_name": "expired", "c_manav": "queued"}
    assert [tuple(e) for e in events] == [("c_name", "card.retired", "subject_is_us"),
                                          ("c_self", "card.retired", "subject_is_us")]
    assert thread == "Manav Rao — seed round pitch to Lumen"
    assert signal == {"sig_ceo": "expired", "sig_manav": "open", "sig_name": "open"}
    assert situations == 3, "situations are listed, never changed"
    assert (replan.threads, replan.signals, replan.cards) == ([], [], [])
    assert mod.apply(engine, plan) == {"threads": 0, "signals": 0, "cards": 0}, "a second run wrote"
