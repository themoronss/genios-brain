"""STEP-07 · a changed company brief re-decides each subject once — and no brief moves nothing.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_a_changed_company_brief_decides_once.py -q

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U12`. Every judging prompt carries the tenant's company brief, so
the brief can change the right answer without touching a decision's request. Its version is a fingerprint
input (`reason/fingerprint.MaterialInputs.brief`), read once per sweep where the prompts read it
(`reason/fingerprint_inputs.read_inputs` → `platform/company_brief.current`):

  * a tenant with no brief — every fingerprint is byte for byte what it was before STEP-07 (the two
    values below were recorded from the code before the input existed);
  * a brief accepted between two sweeps re-decides the subject on the next sweep, and the sweep after
    that skips it again.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.reason.fingerprint import MaterialInputs

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("material_fingerprint_cases",
                                               _HERE / "test_material_fingerprint.py")
MF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MF)

#: Recorded at `speedrun008` ba05508f, before `MaterialInputs.brief` existed.
BEFORE_STEP_07 = {
    "base": "fp_33eb47e0dc39424058bdd046837c5050df96303dc021aa38185fa8b8825e58aa",
    "every_input": "fp_25964fc8b1c8eb3205ee02146fbc9c56d0fa5fbd73fa9daeaaa1e4d16b9eec12",
}
EVERY_INPUT = dict(authority_revision=3, verdicts=("fb_1:1",),
                   decider="llm:claude-haiku-4-5-20251001+r1")


def test_a_tenant_without_a_brief_keeps_every_fingerprint_it_had():
    assert MF._fp() == BEFORE_STEP_07["base"]
    assert MF._fp(inputs=MaterialInputs(**EVERY_INPUT)) == BEFORE_STEP_07["every_input"]
    assert MF._fp(inputs=MaterialInputs(brief="")) == BEFORE_STEP_07["base"]


def test_a_brief_is_an_input_and_its_version_is_what_counts():
    one, two = MaterialInputs(brief="cb-0123456789ab"), MaterialInputs(brief="cb-ba9876543210")
    assert MF._fp(inputs=one) != BEFORE_STEP_07["base"]
    assert MF._fp(inputs=one) == MF._fp(inputs=MaterialInputs(brief="cb-0123456789ab"))
    assert MF._fp(inputs=one) != MF._fp(inputs=two)


# ── the legacy lane, end to end ──────────────────────────────────────────────────────────────────

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ORG = "s07_brief_gate_org"
NODE = "s07bg_p1"
RULE = "unanswered_email"


def _setup(store):
    from genios_engine.api.account_routes import _wipe
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.platform import company_brief
    from genios_engine.reason.runner import run_all

    stale = NOW - timedelta(days=5)
    with store.engine.begin() as conn:
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        conn.execute(text("insert into orgs (id, name, company, email) "
                          "values (:o, 'Arjun Rao', 'Nimbus Labs', 's07bg@example.test')"), {"o": ORG})
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
                {"fv": f"s07bg_fv{i}", "f": f"s07bg_f{i}", "o": ORG, "n": NODE, "field": field,
                 "v": json.dumps(value), "t": stale})
    company_brief.invalidate(ORG)
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    run_all(org_id=ORG, store=store, eval_time=NOW, registry=registry)
    with store.engine.begin() as conn:            # a card showing — else the gate regenerates it
        signal_id = conn.execute(text(
            "select signal_id from signals where org_id=:o and rule_id=:r and subject_node_id=:n "
            "and status='open'"), {"o": ORG, "r": RULE, "n": NODE}).scalar()
        assert signal_id, "the legacy lane wrote no signal"
        conn.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, expires_at, state) values ('s07bg_card', :s, :o, 'prescriptive', "
            "'high', 'Reply to Ada', 'Ada is waiting on us', 7000, :e, 'surfaced')"),
            {"s": signal_id, "o": ORG, "e": NOW + timedelta(days=3)})
    return registry


def _sweep(store, registry, monkeypatch, at):
    """One more sweep, and whether the rule was reasoned in it."""
    from genios_engine.reason import runner as runner_module

    reasoned = []
    original = runner_module.reason_legacy_rule

    def spy(**kw):
        if kw["rule"].id == RULE and kw["context"].node_id == NODE:
            reasoned.append(kw["evaluation_time"])
        return original(**kw)

    monkeypatch.setattr(runner_module, "reason_legacy_rule", spy)
    runner_module.run_all(org_id=ORG, store=store, eval_time=at, registry=registry)
    monkeypatch.setattr(runner_module, "reason_legacy_rule", original)
    return reasoned


def test_the_sweep_reads_the_brief_version_where_the_prompts_read_it(pg_store):
    from genios_engine.platform import company_brief, company_brief_store as store
    from genios_engine.reason.fingerprint_inputs import read_inputs

    _setup(pg_store)
    with pg_store.engine.connect() as conn:
        assert read_inputs(conn, ORG).brief == ""
    with pg_store.engine.begin() as conn:
        store.add(conn, org_id=ORG, section="goals", words="raise the pre-seed round",
                  decided_by="founder", at=NOW)
    with pg_store.engine.connect() as conn:
        version = company_brief.brief_for(conn, ORG).version
        assert version.startswith("cb-") and read_inputs(conn, ORG).brief == version
        index = read_inputs(conn, ORG)
    assert index.for_rule("p", RULE, NODE).brief == version
    assert index.for_situation("p", "s", "c", interpreted=True).brief == version


def test_a_brief_accepted_between_sweeps_re_decides_once_then_skips(pg_store, monkeypatch):
    from genios_engine.platform import company_brief_store as store

    registry = _setup(pg_store)
    later = NOW + timedelta(minutes=15)
    assert _sweep(pg_store, registry, monkeypatch, later) == [], "nothing changed, yet reasoned"
    with pg_store.engine.begin() as conn:
        store.add(conn, org_id=ORG, section="goals", words="raise the pre-seed round",
                  decided_by="founder", at=later)
    assert _sweep(pg_store, registry, monkeypatch, later + timedelta(minutes=15)) == [
        later + timedelta(minutes=15)], "the brief changed and the subject was not decided again"
    assert _sweep(pg_store, registry, monkeypatch, later + timedelta(minutes=30)) == [], (
        "decided again under the same brief")
