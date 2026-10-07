"""STEP-06 · the acceptance: on every founder case, nothing ends silently.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_nothing_ends_silently.py -q

Tree `yc2_w27_s06 · M24.C6.L-integration.V5.U01`. Every founder case is replayed from its cassette
through the REAL chain (`engine_runner.run_case`, the recorded model — no spend), and the tenant's rows
are read before it is removed:

  * every event names its end (`capture/journey.event_journey` — never `none`);
  * every active situation names its end (`reason/situation_end` — never `unrecorded`). On the golden
    set before STEP-06, 126 of 227 had no record anywhere of how they ended (`speedrun008/YC-II W27/`
    STEP-06 §8.1);
  * every expired card carries an event saying why (`platform/card_lifecycle.KINDS`). ⛔ No founder
    case expires a card (§8.1: 25 cards, 0 expired), so on the golden set this holds over nothing;
    the twelve sites are held one by one (`tests/reason/test_every_card_expiry_says_why.py`), and the
    control below proves the check can fail.

STEP-06 changes no decision, so the golden board must not move: the QA run holds it
(`scripts/golden_score.py --assert-recorded`). The controls plant one miss of each kind into a real
run and require the check to name it.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = load_cases()


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def violations(engine, org: str) -> dict[str, list]:
    """The three promises, read off the tenant's rows. Every list empty is a pass."""
    from genios_engine.capture.journey import event_journey
    from genios_engine.platform.card_lifecycle import KINDS
    from genios_engine.reason.situation_end import UNRECORDED, situation_ends

    with engine.connect() as c:
        events = [r[0] for r in c.execute(text(
            "select event_id from source_events where org_id = :o order by event_id"), {"o": org})]
        unrecorded = [e.situation_id for e in situation_ends(c, org) if e.end == UNRECORDED]
        silent = [r[0] for r in c.execute(text(
            "select c.card_id from cards c where c.org_id = :o and c.state = 'expired' "
            "   and not exists (select 1 from card_events e where e.org_id = c.org_id "
            "                   and e.card_id = c.card_id and e.kind = any(:kinds))"),
            {"o": org, "kinds": sorted(KINDS)})]
    no_end = [e for e in events
              if event_journey(engine, org_id=org, event_id=e)["end"]["end"] == "none"]
    return {"event with no end": no_end, "situation with no recorded end": unrecorded,
            "card expired with no reason": silent}


def _run(case):
    from genios_engine.api import routes
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM

    return routes._graph.engine, run_case(case, RecordedLLM(cassettes.load(case)), keep=True)


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_nothing_ends_silently(case):
    _scratch_db()
    from tests.replays.engine_runner import remove_tenant

    engine, run = _run(case)
    try:
        found = violations(engine, run.org_id)
    finally:
        remove_tenant(engine, run.org_id)
    assert not run.misses, f"{case.case_id}: the replay missed its cassette at {run.misses[:3]}"
    assert not any(found.values()), f"{case.case_id}: {found}"


def _plant(engine, org: str, kind: str) -> None:
    """One miss of `kind`, planted into a real run's rows."""
    with engine.begin() as c:
        if kind == "event with no end":
            # captured, stopped by nothing anyone wrote down, and in no ledger
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at, outcome) values ('evt_plant', "
                ":o, 'con_plant', 'gmail', 'email_message', 'm_plant', 'd_plant', "
                "cast('{\"email\": \"x@plant.test\"}' as jsonb), now(), 'dropped')"), {"o": org})
        elif kind == "situation with no recorded end":
            # a live situation the gate held, admitted again — and nothing recorded what came of it
            held = c.execute(text(
                "select d.situation_id, max(d.decided_at) as at from situation_admission_decisions d "
                "  join context_situations s on s.org_id = d.org_id "
                "       and s.situation_id = d.situation_id and s.status in ('active', 'partial') "
                " where d.org_id = :o and d.outcome = 'hold' group by d.situation_id "
                " order by d.situation_id limit 1"), {"o": org}).first()
            c.execute(text(
                "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
                "candidate_hash, outcome, candidate, schema_version, decided_at) values "
                "('dec_plant', :o, :s, 'h_plant', 'admit', cast('{}' as jsonb), 'v1', :at)"),
                {"o": org, "s": held.situation_id, "at": held.at + timedelta(seconds=1)})
        elif kind == "card expired with no reason":
            c.execute(text("update cards set state = 'expired' where org_id = :o"), {"o": org})


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id, kind", [
    ("F04", "event with no end"), ("F04", "card expired with no reason"),
    ("F12", "situation with no recorded end")])
def test_a_planted_miss_of_each_kind_is_named(case_id, kind):
    """The negative control: each check, handed a real run with one miss planted, names it."""
    _scratch_db()
    from tests.replays.engine_runner import remove_tenant

    case = next(c for c in CASES if c.case_id == case_id)
    engine, run = _run(case)
    try:
        assert not violations(engine, run.org_id)[kind], "dirty before the plant"
        _plant(engine, run.org_id, kind)
        found = violations(engine, run.org_id)
    finally:
        remove_tenant(engine, run.org_id)
    assert found[kind], f"{case_id}: a planted '{kind}' was not named"
