"""STEP-17 §3.2 · every SQL statement the engine and its scripts hold is planned by Postgres.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q tests/platform/test_every_statement_plans.py

`yc2_w27_s17` M40.C1.L-integration.V2.U04. ⛔ THE BUG THIS EXISTS FOR: the weekly calibration raised
`UndefinedColumn card_level` on every run from 2026-09-10 to 2026-10-05 (STEP-18 B1) while every
test passed — no test ran that statement on Postgres, and nothing asked Postgres whether it was SQL.
The first run of this test found a script that had never run (`scripts/slice_weight.py`, S17-F1).

Every statement `platform/statement_plans.statements()` renders WHOLE — its constants resolved,
across modules — is prepared and explained on the migrated scratch database. What it cannot render
is assembled at run time; the database suite is its only check, and its number is held here so it
cannot grow in silence. Strings that look like SQL and are not are named one by one, both ways.
"""
from __future__ import annotations

import pytest

from genios_engine.platform import statement_plans as sp

#: ⛔⛔ STRINGS SHAPED LIKE SQL THAT ARE NOT SQL — `{(path, text): why}`. Named one by one, never
#: guessed by a heuristic: a rule that skips "prose" would skip a broken statement too. Checked both
#: ways — a declaration whose string is gone, or now plans, is a lie and fails.
NOT_SQL: dict[tuple[str, str], str] = {
    ("genios_engine/context/support_situations.py", "delete my data"):
        "a phrase a support ticket is matched on (the `data_request` intent)",
    ("genios_engine/deliver/units.py",
     "select SMTP/API provider, verified domain, bounce/unsubscribe handling"):
        "the email unit's description of what it still needs",
    ("genios_engine/executive/planning.py", "update the crm"):
        "a phrase that makes an action a RECORD",
    ("genios_engine/executive/planning.py", "update crm"):
        "a phrase that makes an action a RECORD",
    ("genios_engine/platform/receipts.py",
     "with no reporting line, rung 7 of the ladder (escalate -> manager) climbs into nothing and "
     "a stalled item is never escalated"):
        "a receipt's sentence: what it means when the receipt fails",
    ("genios_engine/platform/table_coverage.py", "insert into ([a-z_][a-z_0-9]*)"):
        "table_coverage's own regex (`_VERBS`), declared there as SELF_MEASURED_PATTERNS",
    ("genios_engine/platform/table_coverage.py", "update ([a-z_][a-z_0-9]*) set"):
        "table_coverage's own regex (`_VERBS`), declared there as SELF_MEASURED_PATTERNS",
    ("genios_engine/platform/table_coverage.py", "delete from ([a-z_][a-z_0-9]*)"):
        "table_coverage's own regex (`_VERBS`), declared there as SELF_MEASURED_PATTERNS",
    ("genios_engine/reason/situation_binding.py", "insert into signals"):
        "the marker the binding guard searches source text for — a substring, not a statement",
    ("scripts/composio_triggers.py",
     "with --apply: delete + recreate the subscription to get a new secret"):
        "an argparse help text",
    ("scripts/pipeline_health.py",
     "UPDATE them to route='needs_extraction'; the writers are capture/parked/drain.py and "
     "capture/parked/recapture.py"):
        "a health check's advice to the operator",
}

#: ⛔⛔ THE RATCHET — statements assembled at run time (a `{where}` from a helper, a `{?}` from a
#: call, `sql += …`, a `%` format, a `.replace(…)` template). The planner cannot see them; the
#: database suite is their only check. ⛔ EXACT, AND IT MOVES IN THE SAME DIFF AS THE CODE: a new one
#: is +1 and fails until it is made static (a constant the census can resolve) or this number is
#: raised deliberately; one made static is -1 and fails until the number is lowered — a ceiling only
#: ratchets while it sits on the actual.
#: ⛔ MOVED 270 → 272 at the merge of STEP-17 with STEP-13 (12 Oct; crosscheck S17X-B1), both STEP-13's: the
#: question card's door in `deliver/actions.ingest_action` (`QUESTION_CARD_SQL`, imported inside the function
#: as the situation door's is) and the queue's third door in `deliver/store.CardStore.queue` (`qq += …`).
#: ⛔ MOVED 272 → 274 at the merge of speedrun008 onto harsh/mvp (18 Oct): both are operator scripts
#: that branch carried — `scripts/screen_cost_report.py` (75d08481) picks its `device_id` column at
#: run time because migration 0212 may not be applied yet, and `scripts/purge_reasoning_now.py`
#: (b9a21d91). Read-only reports and a manual purge, not engine paths.
#: ⛔ MOVED 274 → 273 by GeniOS-011 S36.U2 (23 Oct): Ask's recall read (`reason/moments/recall.read`, its fragments
#: imported inside the function) is now `deliver/store._LIVE_CARDS_ABOUT`, a module constant the census resolves.
ASSEMBLED_AT_RUN_TIME = 273

#: ⛔ A FLOOR UNDER WHAT IS PLANNED, so a census that stopped reading — an import that broke, a
#: resolver that regressed — fails rather than passing over less. Measured 2,053 at the build.
PLANNED_FLOOR = 2_000


@pytest.fixture(scope="module")
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — planning needs the migrated database")
    from genios_engine.platform.db import get_engine
    with get_engine(live_db_url).connect() as c:
        yield c


def _whole() -> list[sp.Statement]:
    return [s for s in sp.statements() if not s.holes]


def test_every_whole_statement_plans(conn):
    broken = []
    for stmt in _whole():
        if (stmt.path, stmt.sql) in NOT_SQL:
            continue
        error = sp.plan(conn, stmt.sql)
        if error is not None:
            broken.append(f"{stmt.path}:{stmt.line}: {error}\n      {stmt.sql[:240]}")
    assert not broken, (
        f"{len(broken)} statement(s) Postgres refuses — each would raise the first time it ran:\n  "
        + "\n  ".join(broken))


def test_every_not_sql_declaration_names_a_string_that_is_there_and_does_not_plan(conn):
    """Both ways. A declaration whose string is gone is stale; one whose string now PLANS is SQL
    after all, and the declaration is hiding a statement from the test above."""
    found = {(s.path, s.sql) for s in _whole()}
    stale = [key for key in NOT_SQL if key not in found]
    assert not stale, f"declared not-SQL strings the census no longer finds: {stale}"
    plans = [key for key in NOT_SQL if sp.plan(conn, key[1]) is None]
    assert not plans, f"declared not SQL, and Postgres plans them: {plans}"
    assert all(len(why) > 20 for why in NOT_SQL.values()), "every declaration says why"


def test_the_statements_assembled_at_run_time_cannot_grow_in_silence():
    counted = sp.census()["assembled_at_run_time"]
    assert counted == ASSEMBLED_AT_RUN_TIME, (
        f"{counted} statements are assembled at run time; the ratchet says {ASSEMBLED_AT_RUN_TIME}. "
        + ("A new one cannot be planned from the source: make its SQL a constant the census can "
           "resolve, or raise ASSEMBLED_AT_RUN_TIME in the same diff and say why."
           if counted > ASSEMBLED_AT_RUN_TIME else
           "One became plannable — lower ASSEMBLED_AT_RUN_TIME to the actual, so the ceiling keeps "
           "ratcheting."))


def test_the_planner_reads_enough_to_mean_something():
    assert len(_whole()) - len(NOT_SQL) >= PLANNED_FLOOR, sp.census()
    assert sp.import_failures() == ()


def test_the_test_would_have_caught_b1(conn):
    """⛔ THE NEGATIVE CONTROL, KEPT. STEP-18 B1 put back in memory: the calibration statement as the
    census renders it, with `card_level` dropped from the `canonical_judgments` projection — exactly
    `cd7f85d7`'s state. Postgres must refuse it, and with the column's name."""
    (calibration,) = [s for s in _whole() if s.path == "genios_engine/feedback/calibrate.py"
                      and "canonical_judgments as (" in s.sql]
    projection = "rule_id, play, card_id, card_level, cause, detail, occurred_at, id "
    assert calibration.sql.count(projection) == 1
    broken = calibration.sql.replace(projection, "rule_id, play, card_id, cause, detail, "
                                                 "occurred_at, id ")
    assert sp.plan(conn, calibration.sql) is None
    error = sp.plan(conn, broken)
    assert error is not None and 'column "card_level" does not exist' in error
