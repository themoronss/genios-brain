"""The production probes are read-only, and every one of them runs.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_production_probes_are_read_only.py -q

`speedrun008/YC-II W27/baseline/production_state.sql` is what Rohit or Harsh runs against production
(`08` §4), never Claude: a production read needs their hands. So the file has to be safe to run as
written and right the first time. `yc2_w27_align` M34.C2.L-data.V0.U09 adds STEP-02's two production
measures — a DEFER expiring a card, and the gate re-deciding the same fingerprint — and `03` F148's two
counts of dates a late read framed; each is held here:

  * every block is ONE statement that reads (a `select`, or a `with` that selects) — no write, no DDL;
  * every block runs, under `default_transaction_read_only`, on a migrated scratch database;
  * every block names the one org it is about, and the STEP-02 and F148 blocks are present.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

PROBES = (Path(__file__).resolve().parents[1] / "speedrun008" / "YC-II W27" / "baseline"
          / "production_state.sql")
ORG = "org_e97e86f858ad48b2bbf64b8a"
GLOBAL = {"latest_migration", "database"}           # facts about the server, not about the org
WRITES = re.compile(r"\b(insert|update|delete|merge|truncate|create|alter|drop|grant|revoke|"
                    r"copy|vacuum|call|do)\b", re.I)


def blocks() -> dict[str, str]:
    """`-- @name` → the statement under it, comments stripped."""
    out: dict[str, str] = {}
    name = None
    for line in PROBES.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^-- @(\w+)\s*$", line)
        if m:
            name = m.group(1)
            out[name] = ""
        elif name and not line.lstrip().startswith("--"):
            out[name] += line + "\n"
    return {k: v.strip() for k, v in out.items()}


def test_the_alignment_blocks_are_there():
    assert {"cards_expired_while_deferred", "gate_redecided_unchanged", "dates_framed_late",
            "promises_framed_late"} <= set(blocks())


def test_the_thinking_blocks_are_there():
    """`yc2_w27_s18` M50.C5.L-data.V0.U17 (STEP-18 §9): Claude 5 thinks by default — every lane's calls at
    their ceiling, parsed or not, the R-site receipts, the Sonnet 5 lanes by day, the models in use, and
    the two reads for after the speedrun008 deploy."""
    assert {"thinking_lanes", "thinking_r_sites", "thinking_sonnet_by_day", "thinking_models_in_use",
            "thinking_expert_after_deploy", "thinking_brief_after_deploy"} <= set(blocks())


@pytest.mark.parametrize("name", sorted(blocks()))
def test_a_probe_is_one_read(name):
    statement = blocks()[name]
    assert statement.rstrip(";").count(";") == 0, f"@{name} holds more than one statement"
    assert re.match(r"^(select|with)\b", statement, re.I), f"@{name} does not start by reading"
    assert not WRITES.search(re.sub(r"'[^']*'", "''", statement)), f"@{name} writes"
    if name not in GLOBAL:
        assert ORG in statement, f"@{name} names no org"


@pytest.mark.pg
@pytest.mark.parametrize("name", sorted(blocks()))
def test_a_probe_runs_in_a_read_only_transaction(name):
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))
        conn.execute(text(blocks()[name])).fetchall()
        conn.rollback()
