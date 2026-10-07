"""STEP-09 · the health check: every counterparty the company brief names that has mail has a file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_files.py -q

`scripts/pipeline_health.check_every_named_counterparty_has_a_file` (tree `yc2_w27_s09 ·
M27.C4.L-interface.V2.U03`). It reads the same answer `GET /v1/workstreams` serves
(`context/workstreams.files_for`), through the audit's read-only connection: it fails while a
connector, a person or a watched portal the brief names has mail memory read and nothing filed, and
names each; it passes when all of it is filed; a brief that names no counterparty measures nothing,
and says so.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from tests.context.workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, WATCHED, later,
                                            mention, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_health_files"
RAHUL = "rahul@kestrelcap.test"
LATE = "otherportal.gov.test"


def _health():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


def test_the_check_runs_in_every_audit():
    assert _health().check_every_named_counterparty_has_a_file in _health().CHECKS


def test_it_reads_the_one_answer_the_file_list_serves():
    tree = ast.parse(inspect.getsource(_health().check_every_named_counterparty_has_a_file))
    called = {getattr(n.func, "id", getattr(n.func, "attr", None)) for n in ast.walk(tree)
              if isinstance(n, ast.Call)}
    assert "files_for" in called


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)
    from genios_engine.platform import company_brief
    company_brief.invalidate(ORG)


def _accept(store, section, **kw):
    from genios_engine.platform import company_brief_store
    with store.engine.begin() as c:
        company_brief_store.add(c, org_id=ORG, section=section, decided_by="founder", at=T0,
                                words=f"{section}: {kw.get('address') or kw.get('domain')}", **kw)


def _check(store):
    from scripts._gate import read_only_connection
    conn = read_only_connection(store.engine)
    try:
        return _health().check_every_named_counterparty_has_a_file(conn, ORG)
    finally:
        conn.close()


def _brief(store):
    from genios_engine.platform import company_brief
    company_brief.invalidate(ORG)
    return company_brief.current(store, ORG)


def test_it_passes_when_every_named_counterpartys_mail_is_filed(store):
    _accept(store, "connectors", address=CONNECTOR)
    _accept(store, "watchlist", domain=WATCHED)
    b = _brief(store)
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL),
            thread="t_intro", headers=UNSUBSCRIBE, mentions=(mention("Rahul Menon"),),
            company_brief=b)
    process(store, ORG, event_id="evt_notice", sender=f"updates@{WATCHED}", company_brief=b,
            at=later(1))
    check = _check(store)
    assert check.ok, check
    assert check.measured.startswith("0 of 2 named counterparties with mail have no file; 2 of 2")


def test_it_fails_on_a_portal_read_before_it_was_named_and_names_it(store):
    process(store, ORG, event_id="evt_old", sender=f"updates@{LATE}", company_brief=None)
    _accept(store, "watchlist", domain=LATE)
    check = _check(store)
    assert not check.ok
    assert check.detail == [f"watchlist:{LATE} — \"watchlist: {LATE}\": 1 mail read, none filed"]
    assert "rebuild_graph.py" in check.fix


def test_it_fails_on_introductions_filed_under_the_connector_and_names_them(store):
    """Introly's introduction read before the founder named Introly sits in Introly's file."""
    process(store, ORG, event_id="evt_old", sender=CONNECTOR, recipients=(FOUNDER, RAHUL),
            thread="t_old", headers=UNSUBSCRIBE, company_brief=None)
    _accept(store, "connectors", address=CONNECTOR)
    check = _check(store)
    assert not check.ok and "1 introduction(s) are filed under the connector" in check.measured
    assert check.detail == [f"connector:{CONNECTOR} — \"connectors: {CONNECTOR}\": 1 "
                            "introduction(s) filed under the connector, not under the people "
                            "introduced"]


def test_mail_outside_its_file_is_said_beside_a_pass(store):
    process(store, ORG, event_id="evt_old", sender=f"updates@{LATE}", company_brief=None)
    _accept(store, "watchlist", domain=LATE)
    process(store, ORG, event_id="evt_new", sender=f"updates@{LATE}", company_brief=_brief(store),
            at=later(1))
    check = _check(store)
    assert check.ok and "some of the mail of 1 is outside its file" in check.measured
    assert check.detail[-1] == f"watchlist:{LATE}: 1 of 2 filed"


def test_a_mailing_is_never_counted(store):
    _accept(store, "watchlist", domain=LATE)
    process(store, ORG, event_id="evt_news", sender=f"news@{LATE}",
            headers={"List-Id": "<news.otherportal.gov.test>"}, company_brief=_brief(store))
    check = _check(store)
    assert check.ok and check.measured.startswith("not exercised")


def test_a_brief_that_names_no_counterparty_measures_nothing_and_says_so(store):
    process(store, ORG, event_id="evt_any", sender=RAHUL, thread="t_any", company_brief=None)
    check = _check(store)
    assert check.ok and check.measured.startswith("not exercised")
