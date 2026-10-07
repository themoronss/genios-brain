"""STEP-06 · the operator's read of how every situation ended — read-only, through the guard.

    pytest tests/scripts/test_situation_ends.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_situation_ends.py -q

`scripts/situation_ends.py` (tree `yc2_w27_s06 · M24.C2.L-interface.V3.U01`): per situation type, how
many ended which way, from `reason/situation_end`; exit 1 while any live situation is `unrecorded`.
"""
from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "situation_ends.py"
ORG = "sit_ends_script_org"
AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def _module():
    import importlib
    return importlib.import_module("scripts.situation_ends")


def test_the_target_is_resolved_through_the_guard_and_read_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert {"resolve_database_url", "read_only_connection"} <= called
    assert "get_settings" not in called


def test_the_org_is_required():
    with pytest.raises(SystemExit):
        _module().parse_args([])


def test_the_histogram_is_per_type_and_sorted():
    from genios_engine.reason.situation_end import SituationEnd
    hist = _module().histogram([SituationEnd("a", "admin", "x", "held"),
                                SituationEnd("b", "admin", "x", "decided"),
                                SituationEnd("c", "admin", "x", "held"),
                                SituationEnd("d", "sales", "y", "not_live")])
    assert hist == {"admin:x": {"decided": 1, "held": 2}, "sales:y": {"not_live": 1}}
    assert list(hist["admin:x"]) == ["decided", "held"]


@pytest.fixture
def scratch():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from context_situations where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 's@ends.test')"),
                  {"o": ORG})
        for sid, domain in [("s1", "sales"), ("s2", "fundraising")]:
            c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, "
                           "anchor_node_id, situation_type, domain) "
                           "values (:s, :o, :c, 'n1', 'kind', :d)"),
                      {"s": sid, "o": ORG, "c": f"corr_{sid}", "d": domain})
    yield url
    with eng.begin() as c:
        c.execute(text("delete from context_situations where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_it_reads_the_tenant_and_exits_0_when_nothing_is_unrecorded(scratch, capsys):
    rc = _module().main(["--org", ORG, "--database-url", scratch, "--json", "--verbose"])
    out = capsys.readouterr().out.splitlines()
    body = json.loads(out[-1])
    assert rc == 0 and body["unrecorded"] == 0 and body["situations"] == 2
    assert body["by_type"] == {"fundraising:kind": {"no_corpus": 1},
                               "sales:kind": {"not_live": 1}}
