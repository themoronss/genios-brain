"""STEP-18 B3 · every "wrong because" reason a card offers is kept — none of them is a 500.

    GENIOS_TEST_DATABASE_URL=… pytest tests/feedback/test_every_wrong_reason_is_kept.py -q

`yc2_w27_s18` M48.C1.L-contract.V0.U01 (L6 Learning, `feedback/`).

⛔ WHAT WAS WRONG. The card offers eleven reasons (`deliver/card_builder`, from
`contracts/learning_attribution.ALL_REASONS`), `POST /v1/intelligence/feedback` accepts all eleven
(`api/intelligence_routes._FB_WRONG_REASONS`) — and `card_feedback_verdicts` and
`card_feedback_revisions` still carried `0034`'s CHECK, which allows three. Eight of the eleven
reached the INSERT inside the founder's own write and the database refused them: a 500, and the
verdict lost. `migrations/0210` widens both CHECKs to the vocabulary the contract declares.

The first half runs on Postgres, through the real route over HTTP, against a card the route's own
authority SELECT accepts (`scripts/brain_pilot_seed.seed_audited_card`). The second half reads the
migration and holds it to the contract, so a twelfth reason cannot be added to one and not the other.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.contracts.learning_attribution import ALL_REASONS, LEGACY_REASONS

ORG = "org_s18_every_wrong_reason"
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0210_every_wrong_reason_is_kept.sql"


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the CHECK is Postgres's")
    from genios_engine.platform.db import get_engine

    eng = get_engine(live_db_url)
    _wipe(eng)
    yield eng
    _wipe(eng)


def _wipe(engine) -> None:
    """This test's own tenant only — its cards, their audit chain and its verdicts."""
    with engine.begin() as conn:
        for table in ("card_feedback_revisions", "card_feedback_verdicts", "card_events", "cards",
                      "signals", "reasoning_reasoner_results", "reasoning_run_outputs",
                      "reasoning_candidates", "reasoning_runs", "reasoning_context_snapshots",
                      "reasoning_capability_snapshots", "config_snapshots", "temporary_memories",
                      "learning_transitions", "learning_object_evaluations", "learning_objects",
                      "learning_runs", "tenant_packs"):
            savepoint = conn.begin_nested()
            try:
                conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
                savepoint.commit()
            except Exception:                                  # noqa: BLE001 — a table not here
                savepoint.rollback()
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _cards(engine, n: int) -> list[str]:
    from scripts.brain_pilot_seed import ensure_org, seed_audited_card

    at = datetime.now(timezone.utc)
    ensure_org(engine, ORG, at=at)
    with engine.begin() as conn:
        return [seed_audited_card(conn, org_id=ORG, index=i, at=at, node_id=f"node_s18_{i}")
                for i in range(n)]


def test_each_of_the_eleven_reasons_is_kept_through_the_route(engine):
    from scripts.brain_pilot_seed import feedback_client

    reasons = list(ALL_REASONS)
    assert len(reasons) == 11
    cards = _cards(engine, len(reasons))
    statuses = {}
    with feedback_client(engine, org_id=ORG, actor_id="actor_s18") as client:
        for reason, card_id in zip(reasons, cards):
            response = client.post("/v1/intelligence/feedback",
                                   json={"action": "thumbs_down", "insight_id": card_id,
                                         "reason": reason})
            statuses[reason] = response.status_code
    assert statuses == {r: 200 for r in reasons}, statuses
    with engine.connect() as conn:
        kept = dict(conn.execute(text(
            "select card_id, reason from card_feedback_verdicts "
            "where org_id = :o and cause = 'wrong'"), {"o": ORG}).all())
        revised = dict(conn.execute(text(
            "select card_id, reason from card_feedback_revisions "
            "where org_id = :o and cause = 'wrong'"), {"o": ORG}).all())
    assert kept == dict(zip(cards, reasons))
    assert revised == dict(zip(cards, reasons)), "the revision ledger holds the same verdicts"


def test_a_founder_may_change_a_reason_to_a_new_one(engine):
    """The UPDATE half of the route (`verdict_version + 1`) meets the same CHECK."""
    from scripts.brain_pilot_seed import feedback_client

    (card_id,) = _cards(engine, 1)
    with feedback_client(engine, org_id=ORG, actor_id="actor_s18") as client:
        first = client.post("/v1/intelligence/feedback",
                            json={"action": "thumbs_down", "insight_id": card_id,
                                  "reason": "not_relevant"})
        second = client.post("/v1/intelligence/feedback",
                             json={"action": "thumbs_down", "insight_id": card_id,
                                   "reason": "wrong_person"})
    assert (first.status_code, second.status_code) == (200, 200), second.text
    with engine.connect() as conn:
        row = conn.execute(text(
            "select reason, verdict_version from card_feedback_verdicts "
            "where org_id = :o and card_id = :c"), {"o": ORG, "c": card_id}).one()
        history = [r[0] for r in conn.execute(text(
            "select reason from card_feedback_revisions where org_id = :o and card_id = :c "
            "order by verdict_version"), {"o": ORG, "c": card_id})]
    assert (row.reason, row.verdict_version) == ("wrong_person", 2)
    assert history == ["not_relevant", "wrong_person"]


@pytest.mark.parametrize("table", ["card_feedback_verdicts", "card_feedback_revisions"])
def test_a_wrong_verdict_still_needs_a_reason_and_an_unknown_one_is_still_refused(engine, table):
    """The CHECK was widened, not dropped: a `wrong` with no reason, or with a word outside the
    contract, is refused by the database as before."""
    with engine.connect() as conn:
        definitions = [r[0] for r in conn.execute(text(
            "select pg_get_constraintdef(c.oid) from pg_constraint c "
            "where c.conrelid = cast(:t as regclass) and c.contype = 'c'"), {"t": table})]
    rules = [d for d in definitions if "reason" in d]
    assert len(rules) == 1, definitions
    rule = rules[0]
    assert set(re.findall(r"'([a-z_]+)'::text", rule)) == set(ALL_REASONS) | {"wrong"}, rule
    assert "reason IS NOT NULL" in rule, rule


# --------------------------------------------------------------- the migration, against the contract

def _reasons_in(sql: str) -> list[set[str]]:
    """Every `reason in (…)` list the migration writes, as a set of words."""
    return [set(re.findall(r"'([a-z_]+)'", body))
            for body in re.findall(r"reason\s+in\s*\(([^)]*)\)", sql, re.I)]


def test_the_migration_names_exactly_the_contracts_reasons():
    sql = MIGRATION.read_text(encoding="utf-8")
    lists = _reasons_in("\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")))
    assert len(lists) == 2, "one CHECK per table: the verdicts and their revisions"
    assert all(found == set(ALL_REASONS) for found in lists), lists


def test_the_three_old_reasons_are_still_among_them():
    """Renaming one would silently re-score every judgment already recorded
    (`contracts/learning_attribution.WrongReason`'s own warning)."""
    assert LEGACY_REASONS <= set(ALL_REASONS)
