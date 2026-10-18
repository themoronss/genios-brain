"""B1 — the weekly calibration EXECUTES on PostgreSQL, and `card_level` reaches its denominator.

`feedback/calibrate._PRECISION_SQL` filters `card_level` on the `canonical_judgments` CTE that
`reason/authority.AUDITED_CARD_JUDGMENTS_CTES` builds. Commit cd7f85d7 carried `card_level` into
`audited_cards` and `judgment_events` but not into `canonical_judgments`, so from 2026-09-10 every
call raised `UndefinedColumn: column "card_level" does not exist` — for every org with an active
pack, on every heartbeat — and the heartbeat's per-org `except` swallowed it.

Every test that covered this statement grepped its TEXT (`tests/test_learning_authority.py`,
`tests/contracts/test_the_outcome_vocabulary_is_wired.py`); none executed it. These do, on a real
Postgres, through the production lanes. They assert the MEASUREMENT (`precision_28d`) and the run
claim, never a mute: whether a mute is applied unattended is a product decision (06-DECISIONS
D13), and `test_calibration_is_shadow_until_armed.py` holds the shadow default.

Real Postgres only; skips without GENIOS_TEST_DATABASE_URL.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.feedback.calibrate import precision_28d, run_calibration

pytestmark = pytest.mark.pg


def _org(store, n_people: int = 0) -> str:
    """A fresh tenant; with `n_people`, people we owe a reply (general pack `unanswered_email`)."""
    org = f"b1cal_{uuid.uuid4().hex[:10]}"
    stale = datetime.now(timezone.utc) - timedelta(days=5)
    with store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": org})
        for i in range(n_people):
            node = f"{org}_p{i}"
            c.execute(text(
                "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
                "values (:n, :o, 'person', :d, :k)"),
                {"n": node, "o": org, "d": f"Person {i}", "k": f"p{i}@acme.test"})
            for j, (field, value) in enumerate((("thread.ball_in_court", "us"),
                                                ("thread.last_inbound", stale.isoformat()))):
                c.execute(text(
                    "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                    "field, value, value_type, status, occurred_at) values "
                    "(:fv, :f, :o, :n, :field, cast(:v as jsonb), 'string', 'active', :t)"),
                    {"fv": f"{node}_fv{j}", "f": f"{node}_f{j}", "o": org, "n": node,
                     "field": field, "v": json.dumps(value), "t": stale})
    return org


def _drop(store, org: str) -> None:
    with store.engine.begin() as c:
        c.execute(text("delete from orgs where id=:o"), {"o": org})


def test_the_weekly_calibration_completes_for_an_org_with_an_active_pack(pg_store):
    """The heartbeat's exact call (`api/routes.run_maintenance_sweep`), on an empty tenant. The
    error is raised while Postgres PLANS the statement, so no data is needed to reach it."""
    org = _org(pg_store)
    try:
        with pg_store.engine.begin() as c:
            c.execute(text("insert into tenant_packs (org_id, pack_id, version, state) "
                           "values (:o, 'general', '1.5.0', 'active')"), {"o": org})
        now = datetime.now(timezone.utc)

        result = run_calibration(pg_store, org, pack_id="general", eval_time=now)

        # The heartbeat's call is SHADOW unless the tenant armed `calibration_apply` (D13): it runs
        # to completion and claims the week, and applies nothing.
        assert result["mode"] == "shadow" and result["applied"] is False, result
        assert result["already_ran"] is False, result
        with pg_store.engine.connect() as c:
            status = c.execute(text("select status from calibration_runs where org_id=:o"),
                               {"o": org}).scalars().all()
        assert status == ["completed"]
        # The week is claimed: the next heartbeat in the same UTC week is a no-op, not a re-run.
        again = run_calibration(pg_store, org, pack_id="general", eval_time=now)
        assert again["already_ran"] is True and again["applied"] is False
    finally:
        _drop(pg_store, org)


def test_a_wrong_counts_against_a_rule_only_on_a_card_that_prescribed(pg_store):
    """Through the production lanes: reasoning sweep -> cards -> the founder's `wrong` button.

    The builder levels these cards `review` (no quotable evidence), so 13 `wrong:not_relevant`
    verdicts must NOT enter the denominator. Re-levelled `prescriptive` — what a grounded card
    carries — the same 13 verdicts must. Both halves need `card_level` to reach
    `canonical_judgments`; before the fix neither can run at all.
    """
    from genios_engine.deliver.actions import ingest_action
    from genios_engine.deliver.pipeline import build_cards_for_org
    from genios_engine.deliver.store import CardStore
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.runner import run_all

    url = pg_store.engine.url.render_as_string(hide_password=False)
    org = _org(pg_store, n_people=13)
    try:
        registry = make_registry(url)
        ensure_defaults(registry, org)
        now = datetime.now(timezone.utc)
        run_all(org_id=org, store=pg_store, eval_time=now, registry=registry)
        build_cards_for_org(graph=pg_store, card_store=CardStore(url), org_id=org, llm=None,
                            registry=registry, eval_time=now)
        with pg_store.engine.connect() as c:
            cards = c.execute(text(
                "select k.card_id, k.level from cards k join signals s on s.signal_id=k.signal_id "
                "and s.org_id=k.org_id where k.org_id=:o and s.rule_id='unanswered_email'"),
                {"o": org}).fetchall()
        assert len(cards) == 13 and {c.level for c in cards} == {"review"}, cards
        for card in cards:
            pressed = ingest_action(card_store=None, graph=pg_store, org_id=org,
                                    card_id=card.card_id, actor="founder", action="wrong",
                                    reason="not_relevant", eval_time=datetime.now(timezone.utc))
            assert pressed.get("ok"), pressed

        def unanswered_email() -> dict:
            stats = precision_28d(pg_store, org, pack_id="general",
                                  eval_time=datetime.now(timezone.utc))
            rows = [v for v in stats.values() if v["rule_id"] == "unanswered_email"]
            assert len(rows) == 1, stats
            return rows[0]

        answered = unanswered_email()
        assert (answered["judgments"], answered["rel_wrong"]) == (0, 0), answered

        with pg_store.engine.begin() as c:
            c.execute(text("update cards set level='prescriptive' where org_id=:o"), {"o": org})
        prescribed = unanswered_email()
        assert (prescribed["judgments"], prescribed["rel_wrong"]) == (13, 13), prescribed
        assert prescribed["precision"] == 0.0
    finally:
        _drop(pg_store, org)
