"""`06` D33 in code · a file's quiet window follows its kind of work.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_stays_open_by_its_kind.py -q

`yc2_w27_align` M34.C2.L-logic.V1.U02. D33 asked how long a file may stay quiet before it is
dormant, and STEP-11 answered it as DATA: each kind's playbook carries a stop rule — investor 90 days,
program 90 (the others with M31; until then 45). Nothing read it: every correlation still closed at
45 days (`context/correlation.CORRELATION_WINDOW_DAYS`) and every situation went dormant at 45
(`context/situations.DORMANT_AFTER_DAYS`), so a fund that answers after sixty days opened a second
file, and the first went dormant while the round was still live.

Context may not read the brief's kinds or the playbooks (they sit above it — `tests/test_layer_topology`),
so the composition root installs the reader (`platform/kind_windows`), as `DomainSpec.register` hands
down a domain's clock: the kind of the in-motion line that names the file's counterparty, and that
kind's playbook stop rule. No reader, no line, or no stop rule: the domain's clock, as before.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import correlation as C
from genios_engine.context.situations import DORMANT_AFTER_DAYS, quiet_days_for_situation

ORG = "org_scratch_tests"
T0 = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)
FUND = "fund-d33.test"
PARTNER = "partner-d33.test"
ANGEL = "angel@mail-d33.test"           # an investor the brief names by address, not by domain


# =================================================================================================
# the seam — hermetic
# =================================================================================================
@pytest.fixture
def reader():
    """The reader the composition root installs, put back as it was after each test."""
    held = C._quiet_days_for_node
    yield
    C.use_quiet_days(held)


def test_without_a_reader_a_file_has_no_window_of_its_own(reader):
    C.use_quiet_days(None)
    assert C.file_quiet_days(None, ORG, "node_x") is None


def test_the_installed_reader_names_the_files_window(reader):
    C.use_quiet_days(lambda conn, org_id, node_id: 90 if node_id == "node_fund" else None)
    assert C.file_quiet_days(None, ORG, "node_fund") == 90
    assert C.file_quiet_days(None, ORG, "node_other") is None


def test_a_reader_that_fails_loses_nothing_but_its_answer(reader):
    def broken(conn, org_id, node_id):
        raise RuntimeError("the brief could not be read")
    C.use_quiet_days(broken)
    assert C.file_quiet_days(None, ORG, "node_fund") is None


def test_a_situation_goes_quiet_on_its_files_clock_before_its_domains(reader):
    C.use_quiet_days(lambda conn, org_id, node_id: 90 if node_id == "node_fund" else None)
    assert quiet_days_for_situation(None, ORG, "node_fund", domain_days=None) == 90
    assert quiet_days_for_situation(None, ORG, "node_other", domain_days=None) is None
    assert quiet_days_for_situation(None, ORG, "node_other", domain_days=3) == 3
    assert DORMANT_AFTER_DAYS == 45, "the engine default the others keep"


# =================================================================================================
# the reader and the join — on Postgres
# =================================================================================================
def _node(store, conn, key: str, node_type: str) -> str:
    return store.find_or_create_node(conn, org_id=ORG, node_type=node_type, canonical_key=key,
                                     display_name=key, event_id=None)


@pytest.fixture
def brief(pg_store):
    """Two in-motion lines the founder accepted: a fund (investor) and a design partner."""
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform import kind_windows
    with pg_store.engine.begin() as conn:
        _forget(conn)
        store.add(conn, org_id=ORG, section="in_motion", words="Raise · the D33 fund", domain=FUND,
                  kind="investor", decided_by="test", at=T0)
        store.add(conn, org_id=ORG, section="in_motion", words="Partner · the D33 partner",
                  domain=PARTNER, kind="partner", decided_by="test", at=T0)
        store.add(conn, org_id=ORG, section="in_motion", words="Raise · the D33 angel", address=ANGEL,
                  kind="investor", decided_by="test", at=T0)
    held = C._quiet_days_for_node
    kind_windows.install()
    yield pg_store
    C.use_quiet_days(held)
    with pg_store.engine.begin() as conn:
        _forget(conn)
    store._invalidate(ORG)


def _forget(conn) -> None:
    """This file's lines and correlations, gone — before a run (an earlier one left them) and after."""
    conn.execute(text("delete from company_brief_lines where org_id = :o "
                      "and (domain = any(:d) or address = :a)"), {"o": ORG, "d": [FUND, PARTNER], "a": ANGEL})
    conn.execute(text("delete from context_correlations where org_id = :o and anchor_node_id in "
                      "(select node_id from graph_nodes where org_id = :o and canonical_key = any(:k))"),
                 {"o": ORG, "k": [f"ravi@{FUND}", FUND, f"lee@{PARTNER}", "someone@elsewhere-d33.test"]})


@pytest.mark.pg
def test_a_funds_file_reads_the_investor_playbooks_stop_rule(brief):
    from genios_engine.platform import kind_windows
    with brief.engine.begin() as conn:
        person, company = _node(brief, conn, f"ravi@{FUND}", "person"), _node(brief, conn, FUND, "company")
        partner = _node(brief, conn, f"lee@{PARTNER}", "person")
        stranger = _node(brief, conn, "someone@elsewhere-d33.test", "person")
        angel = _node(brief, conn, ANGEL, "person")
        assert kind_windows.quiet_days(conn, ORG, angel) == 90, "named by address"
        assert kind_windows.quiet_days(conn, ORG, person) == 90
        assert kind_windows.quiet_days(conn, ORG, company) == 90
        assert kind_windows.quiet_days(conn, ORG, partner) is None, "a partner's playbook has no stop rule yet"
        assert kind_windows.quiet_days(conn, ORG, stranger) is None, "no line names it"


@pytest.mark.pg
def test_a_fund_that_answers_after_sixty_days_is_the_same_file(brief):
    with brief.engine.begin() as conn:
        anchor = C.Anchor(node_id=_node(brief, conn, f"ravi@{FUND}", "person"), node_type="person",
                          domain="fundraising")
        first = C.find_or_open(conn, org_id=ORG, anchor=anchor, event_at=T0)
        later = C.find_or_open(conn, org_id=ORG, anchor=anchor, event_at=T0 + timedelta(days=60))
        assert later == first
        gone = C.find_or_open(conn, org_id=ORG, anchor=anchor, event_at=T0 + timedelta(days=60 + 91))
        assert gone != first, "past its own 90 days the file is a new one"


@pytest.mark.pg
def test_a_partner_that_answers_after_sixty_days_opens_a_new_file_as_before(brief):
    with brief.engine.begin() as conn:
        anchor = C.Anchor(node_id=_node(brief, conn, f"lee@{PARTNER}", "person"), node_type="person",
                          domain="general")
        first = C.find_or_open(conn, org_id=ORG, anchor=anchor, event_at=T0)
        later = C.find_or_open(conn, org_id=ORG, anchor=anchor, event_at=T0 + timedelta(days=60))
        assert later != first, "45 days, the engine default, for a kind with no stop rule"


# =================================================================================================
# the seam is wired — production's wiring installs it, and both lifecycle passes read it
# =================================================================================================
def test_the_composition_root_installs_the_reader():
    from genios_engine.platform import kind_windows, wiring  # noqa: F401 — importing wiring installs
    assert C._quiet_days_for_node is kind_windows.quiet_days


def test_every_lifecycle_decision_reads_the_files_clock():
    """Both passes that decide a situation's lifecycle — the refresh and the statement pass — read the
    file's clock, or they would disagree about a fund between 45 and 90 days and flap it."""
    import ast
    import inspect

    from genios_engine.context import situations
    from genios_engine.context.lifecycle import resolution
    for module in (situations, resolution):
        tree = ast.parse(inspect.getsource(module))
        # A name bound from `quiet_days_for_situation(...)` reads the file's clock as well as the call.
        bound = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                 and "quiet_days_for_situation" in ast.unparse(n.value)
                 for t in n.targets if isinstance(t, ast.Name)}
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "decide_lifecycle"]
        assert calls, module.__name__
        for call in calls:
            days = next((k.value for k in call.keywords if k.arg == "dormant_after_days"), None)
            assert days is not None, f"{module.__name__}: a lifecycle decided on the engine's 45 days"
            reads = ast.unparse(days)
            assert "quiet_days_for_situation" in reads or reads in bound, (module.__name__, reads)
