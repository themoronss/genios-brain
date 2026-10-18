"""STEP-02 · a DEFER keeps the card it found — and a shadow run still keeps nothing alive.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_a_defer_keeps_the_card.py -q

Tree `yc2_w27_s02/M20.C5.L-logic.V0.U01`. ⛔ WHAT WAS WRONG: a live, deliverable run whose decision
was DEFER — the model's, the formula's, or an unavailable model's (`llm_decision_unavailable:*`,
the daily cap included) — fails `authorizes_delivery`, so the legacy lane suppressed it as
`shadow` and left the subject out of `fired` and `indeterminate`; the lifecycle pass then resolved
its open signal and expired the card. "I cannot decide this time" deleted what the founder had
already been shown (`speedrun008/YC-II W27/` STEP-02 §8.2). A DEFER is now indeterminate: the
card stands, the suppression says `deferred`, and the sweep counts it apart from `shadow`.

The negative control is the rule the runner states beside it — *"a shadow or non-deliverable run
must not keep a prior live signal alive"*: a pack switched to shadow still retires its cards.

Real Postgres (the lifecycle UPDATE is the behaviour under test).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_defaults, make_registry
from genios_engine.reason import llm_decision_maker
from genios_engine.reason.runner import run_all

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ORG = "defer_keeps_card"
NODE = "dkc_p1"


def _seed_org(store) -> None:
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": ORG}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else "dkc@x.test" if "email" in r.column_name else ORG)
        conn.execute(text(f"insert into orgs ({','.join(cols)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


def _fresh_graph(store) -> None:
    """One person we owe a reply to: the ball is in our court, their last message five days old —
    `unanswered_email` matches, and nothing about them changes between the sweeps."""
    from genios_engine.api.account_routes import _wipe

    stale = NOW - timedelta(days=5)
    with store.engine.begin() as conn:
        _wipe(conn, ORG)
        conn.execute(text("delete from signals where org_id=:o"), {"o": ORG})
        conn.execute(text("delete from reasoning_publication_watermarks where org_id=:o"),
                     {"o": ORG})
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values (:n, :o, 'person', 'Ada Buyer', 'ada@acme.test')"), {"n": NODE, "o": ORG})
        for i, (field, value) in enumerate((("thread.ball_in_court", "us"),
                                            ("thread.last_inbound", stale.isoformat()))):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, :n, :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"dkc_fv{i}", "f": f"dkc_f{i}", "o": ORG, "n": NODE, "field": field,
                 "v": json.dumps(value), "t": stale})


def _first_sweep_with_a_card(store, registry) -> str:
    """The formula decides (the decider is off): one open signal, and the card the founder sees."""
    first = run_all(org_id=ORG, store=store, eval_time=NOW, registry=registry)
    with store.engine.begin() as conn:
        signal_id = conn.execute(text(
            "select signal_id from signals where org_id=:o and rule_id='unanswered_email' "
            "and subject_node_id=:n and status='open'"), {"o": ORG, "n": NODE}).scalar()
        assert signal_id, first
        conn.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, expires_at, state) values (:c, :s, :o, 'prescriptive', 'high', "
            "'Reply to Ada', 'Ada is waiting on us', 7000, :e, 'surfaced')"),
            {"c": "dkc_card", "s": signal_id, "o": ORG, "e": NOW + timedelta(days=3)})
    return signal_id


def _state(store, signal_id: str) -> tuple[str, str]:
    with store.engine.connect() as conn:
        signal = conn.execute(text("select status from signals where org_id=:o and signal_id=:s"),
                              {"o": ORG, "s": signal_id}).scalar()
        card = conn.execute(text("select state from cards where org_id=:o and card_id='dkc_card'"),
                            {"o": ORG}).scalar()
    return signal, card


def _setup(store):
    _seed_org(store)
    _fresh_graph(store)
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    # The tenant reset keeps a tenant's pack configuration, so a shadow state left by the negative
    # control below would make every later run of this file start in shadow.
    with store.engine.begin() as conn:
        conn.execute(text("update tenant_packs set state='active', updated_at=now() "
                          "where org_id=:o and state <> 'active'"), {"o": ORG})
    return registry


def test_a_defer_from_an_unavailable_model_keeps_the_card(pg_store, monkeypatch):
    registry = _setup(pg_store)
    signal_id = _first_sweep_with_a_card(pg_store, registry)

    # The decider is switched on and cannot be reached (the tests carry no key): every decision of
    # the next sweep is `DEFER` with `llm_decision_unavailable:no_client`.
    monkeypatch.setattr(llm_decision_maker, "enabled_for", lambda org_id: True)
    llm_decision_maker._cache.clear()
    second = run_all(org_id=ORG, store=pg_store, eval_time=NOW + timedelta(hours=6),
                     registry=registry)

    assert second["outcomes"].get("deferred", 0) >= 1, second
    assert second["outcomes"].get("resolved", 0) == 0, second
    assert _state(pg_store, signal_id) == ("open", "surfaced"), second
    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select reason_code, detail from signal_suppression_log where org_id=:o and "
            "rule_id='unanswered_email' and subject_node_id=:n and eval_time=:t"),
            {"o": ORG, "n": NODE, "t": NOW + timedelta(hours=6)}).all()
    assert [r.reason_code for r in rows] == ["deferred"], rows
    assert any("llm_decision_unavailable" in u for u in rows[0].detail.get("uncertainty", ())), rows


def test_a_shadow_pack_still_keeps_nothing_alive(pg_store):
    """⛔ THE NEGATIVE CONTROL. A pack switched to shadow may not deliver, so its run must not hold a
    live card open — the lifecycle retires it, exactly as before this unit."""
    registry = _setup(pg_store)
    signal_id = _first_sweep_with_a_card(pg_store, registry)
    with pg_store.engine.begin() as conn:
        conn.execute(text("update tenant_packs set state='shadow', updated_at=now() "
                          "where org_id=:o"), {"o": ORG})
    try:
        second = run_all(org_id=ORG, store=pg_store, eval_time=NOW + timedelta(hours=6),
                         registry=registry)
        assert second["outcomes"].get("deferred", 0) == 0, second
        assert _state(pg_store, signal_id) != ("open", "surfaced"), second
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(text("update tenant_packs set state='active', updated_at=now() "
                              "where org_id=:o"), {"o": ORG})
