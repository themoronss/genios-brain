"""STEP-02 · the two fingerprint inputs that sit outside a decision's request, read once per sweep.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_fingerprint_inputs.py -q

`reason/fingerprint_inputs.read_inputs` (tree `yc2_w27_s02/M20.C1.L-data.V1.U02`): every pack's
`authority_revision`, and every human verdict on a card, keyed by the subject it is about — the
legacy (rule, node) a signal names, or the compiled (situation, capability). A verdict that lands, or
a new version of one, changes its subject's inputs and so its fingerprint; nothing else's.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_defaults, make_registry
from genios_engine.reason.fingerprint import MaterialInputs, verdict_key
from genios_engine.reason.fingerprint_inputs import read_inputs
from genios_engine.reason.runner import run_all

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ORG = "fp_inputs_org"
NODE = "fpi_p1"


def _seed(store) -> tuple[str, dict]:
    """A real open signal (the legacy lane's `unanswered_email` on one person) and its card."""
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as conn:
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        conn.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fpi@example.test')"),
                     {"o": ORG})
        _wipe(conn, ORG)
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values (:n, :o, 'person', 'Ada Buyer', 'ada@acme.test')"), {"n": NODE, "o": ORG})
        stale = NOW - timedelta(days=5)
        for i, (field, value) in enumerate((("thread.ball_in_court", "us"),
                                            ("thread.last_inbound", stale.isoformat()))):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, :n, :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"fpi_fv{i}", "f": f"fpi_f{i}", "o": ORG, "n": NODE, "field": field,
                 "v": json.dumps(value), "t": stale})
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    run_all(org_id=ORG, store=store, eval_time=NOW, registry=registry)
    with store.engine.begin() as conn:
        signal = conn.execute(text(
            "select signal_id, pack_id, pack_version, authority_pack_revision from signals "
            "where org_id=:o and rule_id='unanswered_email' and subject_node_id=:n "
            "and status='open'"), {"o": ORG, "n": NODE}).mappings().first()
        assert signal, "the legacy lane wrote no signal to hang a card on"
        conn.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, expires_at, state) values ('fpi_card', :s, :o, 'prescriptive', "
            "'high', 'Reply to Ada', 'Ada is waiting on us', 7000, :e, 'surfaced')"),
            {"s": signal["signal_id"], "o": ORG, "e": NOW + timedelta(days=3)})
    return signal["signal_id"], dict(signal)


def _verdict(store, signal: dict, *, feedback_id: str, version: int) -> None:
    with store.engine.begin() as conn:
        conn.execute(text(
            "insert into card_feedback_verdicts (feedback_id, org_id, card_id, pack_id, pack_version, "
            "authority_pack_revision, capability_id, capability_version, rule_id, cause, reason, "
            "detail, actor_id, verdict_version, occurred_at) values (:f, :o, 'fpi_card', :p, :pv, "
            ":rev, 'legacy.unanswered_email', '1', 'unanswered_email', 'wrong', 'bad_timing', "
            "'{}'::jsonb, 'founder', :v, :t) on conflict (org_id, card_id) do update set "
            "verdict_version = excluded.verdict_version"),
            {"f": feedback_id, "o": ORG, "p": signal["pack_id"], "pv": signal["pack_version"],
             "rev": signal["authority_pack_revision"], "v": version, "t": NOW})


def test_no_verdict_yet_is_the_packs_revision_and_nothing_else(pg_store):
    _seed(pg_store)
    with pg_store.engine.connect() as conn:
        index = read_inputs(conn, ORG)
        revision = conn.execute(text("select authority_revision from tenant_packs where "
                                     "org_id=:o and pack_id='general'"), {"o": ORG}).scalar()
    inputs = index.for_rule("general", "unanswered_email", NODE)
    assert inputs == MaterialInputs(authority_revision=revision, verdicts=())


def test_a_verdict_reaches_its_subject_and_no_other(pg_store):
    _, signal = _seed(pg_store)
    _verdict(pg_store, signal, feedback_id="fpi_fb1", version=1)
    with pg_store.engine.connect() as conn:
        index = read_inputs(conn, ORG)
    assert index.for_rule(signal["pack_id"], "unanswered_email", NODE).verdicts == (
        verdict_key("fpi_fb1", 1),)
    assert index.for_rule(signal["pack_id"], "unanswered_email", "someone_else").verdicts == ()
    assert index.for_rule(signal["pack_id"], "another_rule", NODE).verdicts == ()


def test_a_new_version_of_the_verdict_is_a_new_input(pg_store):
    _, signal = _seed(pg_store)
    _verdict(pg_store, signal, feedback_id="fpi_fb1", version=1)
    with pg_store.engine.connect() as conn:
        first = read_inputs(conn, ORG).for_rule(signal["pack_id"], "unanswered_email", NODE)
    _verdict(pg_store, signal, feedback_id="fpi_fb1", version=2)
    with pg_store.engine.connect() as conn:
        second = read_inputs(conn, ORG).for_rule(signal["pack_id"], "unanswered_email", NODE)
    assert first != second and second.verdicts == (verdict_key("fpi_fb1", 2),)


def test_a_compiled_subject_is_found_by_its_situation_and_capability(pg_store):
    signal_id, signal = _seed(pg_store)
    with pg_store.engine.begin() as conn:      # the signal as the compiled lane writes it
        conn.execute(text("update signals set situation_id='sit_fpi', "
                          "capability_id='expertise.account_admin' where org_id=:o and "
                          "signal_id=:s"), {"o": ORG, "s": signal_id})
    _verdict(pg_store, signal, feedback_id="fpi_fb2", version=1)
    with pg_store.engine.connect() as conn:
        index = read_inputs(conn, ORG)
    assert index.for_situation(signal["pack_id"], "sit_fpi", "expertise.account_admin").verdicts \
        == (verdict_key("fpi_fb2", 1),)
    assert index.for_situation(signal["pack_id"], "sit_other", "expertise.account_admin") \
        .verdicts == ()


def test_a_pack_the_tenant_does_not_hold_has_no_revision(pg_store):
    _seed(pg_store)
    with pg_store.engine.connect() as conn:
        index = read_inputs(conn, ORG)
    assert index.for_rule("no_such_pack", "r", NODE).authority_revision is None
