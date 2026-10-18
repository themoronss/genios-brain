"""STEP-18 B1 · calibration runs again, and in SHADOW until a tenant is armed (decision D13).

    pytest tests/feedback/test_calibration_is_shadow_until_armed.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q            # + the behavioural half

⛔ WHY THE SWITCH LANDS BEFORE THE FIX. The weekly calibration has raised `UndefinedColumn
card_level` on every run since 2026-09-10, so it has never muted or nudged anything. The repair is
one column — and that column ALONE would have switched on unattended muting and gate nudges for
every tenant with an active pack. On a scratch database, an applied mute or nudge then hid every
open card of its pack (STEP-18 B22-B24). So calibration records what it WOULD do, and changes
nothing, until `calibration_apply` is switched on for a tenant — and that feature is never
default-on.
"""
from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest

from genios_engine.feedback.calibrate import run_calibration
from genios_engine.platform import l4_activation as l4
from genios_engine.platform.intelligence_onboarding import L4_DEFAULT_FEATURES, NOT_DEFAULT_ON

FEATURE = "calibration_apply"
ROUTES = Path(__file__).resolve().parents[2] / "genios_engine" / "api" / "routes.py"


# =================================================================================================
# 1 · the switch exists, says what it does, and is never on by default
# =================================================================================================
def test_the_switch_is_a_registered_feature_with_a_wave_a_precondition_row_and_an_effect():
    assert l4.FEATURE_CALIBRATION_APPLY == FEATURE
    assert FEATURE in l4.L4_FEATURES
    assert FEATURE in l4.FEATURE_WAVES and FEATURE in l4.PRECONDITIONS
    assert "B22" in l4.EFFECTS[FEATURE], "the effect must say what arming it hides"


def test_no_tenant_is_armed_by_provisioning():
    assert FEATURE in NOT_DEFAULT_ON and FEATURE not in L4_DEFAULT_FEATURES
    assert "D13" in NOT_DEFAULT_ON[FEATURE]


def test_calibration_is_shadow_unless_told_otherwise():
    parameter = inspect.signature(run_calibration).parameters["apply"]
    assert parameter.default is False and parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_heartbeat_passes_the_tenants_switch_and_nothing_else():
    """The one production caller reads `is_l4_activated(…, FEATURE_CALIBRATION_APPLY)` — which
    fails closed — and hands THAT to `apply`. A literal `True` there is the defect this file
    exists for."""
    tree = ast.parse(ROUTES.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "run_calibration"]
    assert len(calls) == 1, "one production caller — re-read this test if that changed"
    apply = next((k.value for k in calls[0].keywords if k.arg == "apply"), None)
    assert isinstance(apply, ast.Name), "apply must come from the tenant's switch, not a literal"
    assigned = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == apply.id for t in n.targets)]
    assert any(isinstance(a.value, ast.Call) and getattr(a.value.func, "id", None)
               == "is_l4_activated"
               and any(isinstance(arg, ast.Name) and arg.id == "FEATURE_CALIBRATION_APPLY"
                       for arg in a.value.args) for a in assigned), (
        f"`{apply.id}` is not read from is_l4_activated(..., FEATURE_CALIBRATION_APPLY)")


# =================================================================================================
# 2 · behavioural — a harmful rule is PROPOSED in shadow, and nothing moves
# =================================================================================================
@pytest.mark.pg
@pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                    reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
def test_a_harmful_rule_is_proposed_in_shadow_and_nothing_moves(pg_store):
    """Through the production lanes: 13 people we owe a reply → 13 `unanswered_email` cards → the
    founder presses `wrong: not relevant` on each, on cards that prescribed. Precision 0 over 13
    judgments is below the mute floor — in shadow that is a PROPOSAL, recorded, and the rule, the
    pack's authority revision and every open card stay exactly as they were."""
    from datetime import datetime, timezone

    from sqlalchemy import text

    from genios_engine.deliver.actions import ingest_action
    from genios_engine.deliver.pipeline import build_cards_for_org
    from genios_engine.deliver.store import CardStore
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.runner import run_all
    from tests.feedback.test_calibration_runs_on_postgres import _drop, _org

    url = pg_store.engine.url.render_as_string(hide_password=False)
    org = _org(pg_store, n_people=13)
    try:
        registry = make_registry(url)
        ensure_defaults(registry, org)
        now = datetime.now(timezone.utc)
        run_all(org_id=org, store=pg_store, eval_time=now, registry=registry)
        build_cards_for_org(graph=pg_store, card_store=CardStore(url), org_id=org, llm=None,
                            registry=registry, eval_time=now)
        with pg_store.engine.begin() as c:
            c.execute(text("update cards set level='prescriptive' where org_id=:o"), {"o": org})
            cards = c.execute(text(
                "select k.card_id from cards k join signals s on s.signal_id=k.signal_id "
                "and s.org_id=k.org_id where k.org_id=:o and s.rule_id='unanswered_email'"),
                {"o": org}).scalars().all()
        assert len(cards) == 13, cards
        for card_id in cards:
            pressed = ingest_action(card_store=None, graph=pg_store, org_id=org, card_id=card_id,
                                    actor="founder", action="wrong", reason="not_relevant",
                                    eval_time=datetime.now(timezone.utc))
            assert pressed.get("ok"), pressed

        def snapshot():
            with pg_store.engine.connect() as c:
                return (
                    c.execute(text("select count(*) from rule_mutes where org_id=:o"),
                              {"o": org}).scalar(),
                    c.execute(text("select authority_revision, lvl3_config from tenant_packs "
                                   "where org_id=:o and pack_id='general'"), {"o": org}).one(),
                    c.execute(text("select count(*) from cards where org_id=:o and state in "
                                   "('queued','surfaced','snoozed','claimed','delivered')"),
                              {"o": org}).scalar())

        before = snapshot()
        result = run_calibration(pg_store, org, pack_id="general",
                                 eval_time=datetime.now(timezone.utc))
        assert result["mode"] == "shadow" and result["applied"] is False, result
        assert "unanswered_email" in result["would_mute"], result
        assert result["muted"] == [] and result["nudges"] == [], result
        assert snapshot() == before, "a shadow run changed a mute, the pack or a card"
        with pg_store.engine.connect() as c:
            stored = c.execute(text("select result from calibration_runs where org_id=:o "
                                    "and pack_id='general'"), {"o": org}).scalar()
        assert stored["mode"] == "shadow" and "unanswered_email" in stored["would_mute"]
    finally:
        _drop(pg_store, org)
