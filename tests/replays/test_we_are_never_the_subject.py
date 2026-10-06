"""STEP-04 · the acceptance: on every founder case, we are never the subject.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_we_are_never_the_subject.py -q

Tree `yc2_w27_s04 · M22.C5.L-integration.V4.U10`. Every founder case is replayed from its cassette
through the REAL chain (`engine_runner.run_case`, the recorded model — no spend), as production
runs it: the tenant seated as signup seats it, its own addresses and domains declared. After the last
sweep the heartbeat's naming pass runs (`context/backfill.name_thread_nodes`, which the golden runner
does not call on its own), and the tenant's rows are read before it is removed:

  * no open card's subject is one of us — the production receipt itself
    (`platform/receipts` "no open card's subject is one of us"), so the instrument is tested too;
  * no open card's words name one of us as somebody waiting or owed — `platform/self_identity.
    names_us` over its headline and situation, the test the card builder refuses by;
  * no live situation is anchored on a node of ours (the tenant node's own period situations are
    ours by design and are not this question);
  * no thread is named after one of us.

The four cases STEP-04 added are held to their marking on the board (`03-FINDINGS` §F.1) by
`tests/replays/test_founder_cases.py`; this file holds the property on all of them.
"""
from __future__ import annotations

import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = load_cases()
_DASH = " — "


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_we_are_never_the_subject(case):
    _scratch_db()
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.context.backfill import name_thread_nodes
    from genios_engine.platform.receipts import receipts
    from genios_engine.platform.self_identity import identity_for, names_us
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    engine = routes._graph.engine
    org = run.org_id
    try:
        name_thread_nodes(routes._graph, org)          # the heartbeat's pass, after the last sweep
        receipt = next(r for r in receipts(org) if r.claim == "no open card's subject is one of us")
        with engine.connect() as c:
            us = identity_for(c, org)
            row = c.execute(text("select name, first_name, last_name, company from orgs "
                                 "where id = :o"), {"o": org}).first()
            names = (row.name, row.company,
                     f"{row.first_name} {row.last_name}" if row.first_name and row.last_name
                     else None)
            about_us = int(c.execute(text(receipt.sql), {"org": org}).scalar())
            cards = c.execute(text(
                "select card_id, headline, situation from cards where org_id = :o "
                "   and state in ('queued', 'surfaced', 'snoozed', 'claimed', 'delivered')"),
                {"o": org}).fetchall()
            anchors = c.execute(text(
                "select s.situation_id, n.node_type, n.canonical_key from context_situations s "
                "  join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id "
                "       and n.valid_to is null "
                " where s.org_id = :o and s.status in ('active', 'dormant', 'partial') "
                "   and n.node_type <> 'tenant'"), {"o": org}).fetchall()
            threads = c.execute(text(
                "select node_id, display_name from graph_nodes where org_id = :o "
                "   and valid_to is null and node_type = 'thread'"), {"o": org}).fetchall()
    finally:
        remove_tenant(engine, org)

    assert not run.misses, f"{case.case_id}: the replay missed its cassette at {run.misses[:3]}"
    assert about_us == 0, f"{case.case_id}: {about_us} open card(s) whose subject is one of us"
    worded = [(r.card_id, r.headline) for r in cards
              if any(names_us(f"{part}", us, names) for part in _parties(r.headline, r.situation))]
    assert not worded, f"{case.case_id}: a card's words name one of us as a party: {worded}"
    ours = [(r.situation_id, r.canonical_key) for r in anchors
            if us.is_us_node(r.node_type, r.canonical_key)]
    assert not ours, f"{case.case_id}: situations anchored on us: {ours}"
    named = [(r.node_id, r.display_name) for r in threads
             if _DASH in str(r.display_name or "")
             and names_us(str(r.display_name).partition(_DASH)[0], us, names)]
    assert not named, f"{case.case_id}: threads named after us: {named}"


def _parties(*texts: str | None) -> list[str]:
    """The phrases of a card's words that name a party: each clause split at the separators a
    headline and a situation use between who and what (" — ", ",", " and ")."""
    out: list[str] = []
    for value in texts:
        for clause in str(value or "").replace(_DASH, ",").split(","):
            out.extend(part.strip() for part in clause.split(" and ") if part.strip())
    return out
