"""STEP-13 · no signal without a lane (`03` F10, F186).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/test_every_signal_has_a_lane.py

Tree `yc2_w27_s13` M36.C1.L-integration.V1.U06. Five writers left `signals.output_lane` NULL, and every one
passed its tests; M36.C1.U01–U05 made each write the lane and its reason. This holds it:

  * every statement in the engine that inserts into `signals` names `output_lane` and `lane_reason` — read
    out of the AST (`reason/situation_binding.signal_insert_columns`), so a comment cannot satisfy it and a
    statement wrapped over eight lines cannot hide from it — and the writers are the six there are (the
    sixth, a held file's question, M36.C2.U03): another is added to `WRITERS` on purpose, with its lane;
  * against real data, `scripts/pipeline_health.check_every_new_signal_has_a_lane` counts the signals of
    the last day with no lane — 0 to pass, a day after the deploy.

AMENDED by the STEP-13 crosscheck (X29, X47): the scan reads `scripts/` as well as the engine — a seed script
that writes signals writes them with a lane too — and the CARD side is held the same way: every statement that
inserts into `cards` names `output_lane` and `lane_reason`, because the surface reads the card and a lane that
stops at `signals` reached nobody (0190).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from genios_engine.reason.situation_binding import signal_insert_columns

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "genios_engine"
#: Where a statement that writes signals or cards may live: the engine, and the scripts that seed tenants.
SCANNED = (ENGINE, ROOT / "scripts")
LANE = frozenset({"output_lane", "lane_reason"})

#: Every module that inserts into `signals`, and where its lane comes from.
WRITERS: dict[str, str] = {
    "reason/domain_shadow.py": "the compiled lane's decision, routed where it was made",
    "reason/runner.py": "the legacy rule lane: its decision's lane, in `_decision_payload`",
    "reason/publication.py": "the native publication: its decision's lane",
    "reason/composer.py": "the deal-health composite: its decision's lane",
    "reason/team/emit.py": "a post-pass's observation: a discrepancy is a conflict, a team situation is watched",
    # M36.C2.L-integration.V2.U03: a sixth, on purpose — the question a held file asks.
    "reason/expert/asks.py": "a held file's question: the Investigation lane of the decision that asked it",
    # X47: the scan reads scripts/ too — the pilot seed writes an audited decision, in the decision lane.
    "scripts/brain_pilot_seed.py": "a seeded pilot decision: the decision lane, said as seeded",
}

#: Every module that inserts into `cards` — each names the lane its signal carries (X29).
CARD_WRITERS: dict[str, str] = {
    "deliver/store.py": "the card pipeline's insert: the lane the draft resolved (`lane_display.describe`)",
    "reason/team/emit.py": "a post-pass's card: its signal's lane (M36.C1.L-data.V0.U07)",
    "scripts/brain_pilot_seed.py": "a seeded pilot card: its signal's decision lane",
}


def _key(path: Path) -> str:
    """A module by the name WRITERS gives it: engine-relative, or `scripts/…`."""
    return (path.relative_to(ENGINE).as_posix() if ENGINE in path.parents
            else path.relative_to(ROOT).as_posix())


def card_insert_columns(source: str) -> tuple[frozenset[str], ...]:
    """Every `insert into cards (...)` column list in `source`, out of the AST — the statement, never prose
    (the same reading `situation_binding.signal_insert_columns` gives `signals`)."""
    import ast

    out = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        text_ = node.value
        if "insert into cards" not in text_:
            continue
        tail = text_.split("insert into cards", 1)[1]
        if not (tail.lstrip().startswith("(") and "values" in tail.lower()):
            continue
        out.append(frozenset(c.strip() for c in tail.split("(", 1)[1].split(")", 1)[0].split(",")))
    return tuple(out)


def _card_inserts() -> dict[str, tuple[frozenset[str], ...]]:
    out = {}
    for root in SCANNED:
        for path in sorted(root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "insert into cards" not in source:
                continue
            found = card_insert_columns(source)
            if found:
                out[_key(path)] = found
    return out


def _inserts() -> dict[str, tuple[frozenset[str], ...]]:
    out = {}
    for root in SCANNED:
        for path in sorted(root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "insert into signals" not in source:
                continue
            found = signal_insert_columns(source)
            if found:
                out[_key(path)] = found
    return out


def unrouted(inserts: dict[str, tuple[frozenset[str], ...]]) -> list[str]:
    """Each statement that inserts a signal with no lane, by its module."""
    return [f"{module}: {sorted(LANE - columns)}" for module, statements in inserts.items()
            for columns in statements if not LANE <= columns]


def undeclared(inserts: dict[str, tuple[frozenset[str], ...]]) -> list[str]:
    """A writer of signals `WRITERS` does not name, or one it names that writes none any more."""
    return [f"+ {m}" for m in sorted(set(inserts) - set(WRITERS))] + \
        [f"- {m}" for m in sorted(set(WRITERS) - set(inserts))]


def test_every_statement_that_inserts_a_signal_writes_its_lane():
    inserts = _inserts()
    assert unrouted(inserts) == []
    assert undeclared(inserts) == [], \
        "a writer of signals came or went — add it to WRITERS with where its lane comes from"


def test_every_statement_that_inserts_a_card_writes_its_lane():
    """X29 · the card side, held as the signal side is: every card insert names the lane, and the writers are
    the ones `CARD_WRITERS` names."""
    inserts = _card_inserts()
    assert unrouted(inserts) == []
    assert sorted(inserts) == sorted(CARD_WRITERS), \
        "a writer of cards came or went — add it to CARD_WRITERS with where its lane comes from"


def test_a_card_writer_that_forgets_the_lane_is_named():
    """The negative control for the card side: a statement without the lane is named, a comment is no column."""
    source = ('# insert into cards (output_lane, lane_reason) values — a comment is no column\n'
              'SQL = ("insert into cards (card_id, signal_id, org_id) "\n'
              '       "values (:k, :s, :o)")\n')
    assert unrouted({"deliver/new.py": card_insert_columns(source)}) == [
        "deliver/new.py: ['lane_reason', 'output_lane']"]


def test_a_writer_that_forgets_the_lane_is_named():
    """The negative control: the guard reads the statement, never a comment beside it — and a sixth
    writer, or a writer gone, is named."""
    source = ('# insert into signals (output_lane, lane_reason) values — a comment is no column\n'
              'SQL = ("insert into signals (signal_id, org_id, rule_id) "\n'
              '       "values (:s, :o, :r)")\n')
    sixth = {**_inserts(), "reason/sixth.py": signal_insert_columns(source)}
    assert unrouted(sixth) == ["reason/sixth.py: ['lane_reason', 'output_lane']"]
    assert undeclared(sixth) == ["+ reason/sixth.py"]
    gone = {m: c for m, c in _inserts().items() if m != "reason/composer.py"}
    assert undeclared(gone) == ["- reason/composer.py"]


# ── the health check, on real data ──────────────────────────────────────────────────────────────
ORG = "org_s13_signal_lane"


@pytest.fixture
def conn():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from signals where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'lane@signal.test')"),
                  {"o": ORG})
    with eng.connect() as c:
        yield c
    with eng.begin() as c:
        c.execute(text("delete from signals where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _signal(c, sid: str, *, lane: str | None, hours_ago: float) -> None:
    created = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    c.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, eval_time, "
        "created_at, output_lane, lane_reason) values (:s, :o, 'r_lane', 'n1', 50, 'rc', :t, :t, :l, :lr)"),
        {"s": sid, "o": ORG, "t": created, "l": lane, "lr": "why" if lane else None})
    c.commit()


@pytest.mark.pg
def test_the_health_check_counts_the_last_days_signals_with_no_lane(conn):
    from scripts.pipeline_health import check_every_new_signal_has_a_lane as check
    quiet = check(conn, ORG)
    assert quiet.ok and quiet.measured == "no signal written in the last 24 hours"
    _signal(conn, "sig_routed", lane="decision", hours_ago=2)
    _signal(conn, "sig_before_the_deploy", lane=None, hours_ago=30)
    assert check(conn, ORG).ok, "a NULL lane before the window is history, not a writer today"
    _signal(conn, "sig_unrouted", lane=None, hours_ago=1)
    failed = check(conn, ORG)
    assert not failed.ok and failed.measured == "1 of 2 signals written in 24 h have no lane"
    assert failed.detail == ["- r_lane × 1"]
