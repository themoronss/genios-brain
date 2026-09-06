"""L1.1-U1 · the coverage declaration, row by row.

`compute_coverage` was always correct (`tests/test_domain_coverage.py` proves it). What did not
exist was anything that ASKED it on behalf of an org: the two inputs it needs — which capabilities
this tenant's connections satisfy, and how much canon they have written — lived as private helpers
of `api/routes.py`, so the only way to obtain a coverage answer was to make an HTTP request.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.coverage.declaration import (FRESH, STALE, CoverageDeclaration,
                                                        connected_capabilities, declare_coverage)
from genios_engine.contracts.connection import Connection

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


def _conn(source: str, *, org: str = "org_a", status: str = "connected") -> Connection:
    return Connection(org_id=org, source_type=source, status=status,
                      connection_id=f"con_{org}_{source}_{status}")


# ---------------------------------------------------------------------------------------------
# connected_capabilities — the half absorbed out of api/routes.py:_connected_capabilities
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("sources,expected", [
    pytest.param(["gmail"], {"communication": FRESH}, id="one mailbox"),
    pytest.param(["gmail", "hubspot"], {"communication": FRESH, "crm": FRESH}, id="mail + crm"),
    # An ALIAS must resolve. A connection stored as `google_calendar` counted for nothing while
    # the capability list was hand-written against the canonical id alone.
    pytest.param(["google_calendar"], {"calendar": FRESH}, id="alias resolves"),
    # A source with no declared capability contributes nothing rather than an empty-string key.
    pytest.param(["nothing_like_this"], {}, id="unknown source"),
    pytest.param([], {}, id="nothing connected"),
])
def test_capabilities_are_derived_from_the_connection_set(sources, expected):
    assert connected_capabilities([_conn(s) for s in sources], org_id="org_a") == expected


def test_another_tenants_connections_are_not_this_tenants_coverage():
    """`list_active()` returns EVERY org's connections. The filter is the tenant boundary, and a
    coverage answer computed across it would license negative inferences about one company from
    another company's CRM."""
    conns = [_conn("gmail", org="org_a"), _conn("hubspot", org="org_b")]
    assert connected_capabilities(conns, org_id="org_a") == {"communication": FRESH}
    assert connected_capabilities(conns, org_id="org_b") == {"crm": FRESH}


def test_a_paused_connection_is_stale_and_withdraws_the_licence():
    """A paused connector returns the same empty result set as a connected one with nothing in
    it. Calling that `fresh` is how "they never replied" gets said about a channel we stopped
    reading."""
    declared = connected_capabilities([_conn("gmail", status="paused")], org_id="org_a")
    assert declared == {"communication": STALE}
    cov = declare_coverage(org_id="org_a", connections=[_conn("gmail", status="paused")],
                           computed_at=NOW).for_domain("fundraising")
    assert cov["coverage_ready"] is False


def test_a_disconnected_connection_contributes_nothing():
    assert connected_capabilities([_conn("gmail", status="disconnected")], org_id="org_a") == {}


def test_fresh_wins_over_stale_for_the_same_capability():
    """Two mailboxes, one live and one paused, in either iteration order. Coverage must not
    depend on which row the loop happened to reach last."""
    live, paused = _conn("gmail"), _conn("gmail", status="paused")
    assert connected_capabilities([live, paused], org_id="org_a") == {"communication": FRESH}
    assert connected_capabilities([paused, live], org_id="org_a") == {"communication": FRESH}


# ---------------------------------------------------------------------------------------------
# declare_coverage — every registered domain, once
# ---------------------------------------------------------------------------------------------

def test_one_declaration_answers_for_every_registered_domain():
    """The reason a sweep pays for this once: the expensive inputs are shared and the per-domain
    arithmetic is free, so `for_domain` is a lookup rather than a query."""
    declaration = declare_coverage(org_id="org_a", connections=[_conn("gmail"), _conn("hubspot")],
                                   computed_at=NOW)
    assert isinstance(declaration, CoverageDeclaration)
    assert set(declaration.domains) == {"sales", "support", "admin", "fundraising"}
    assert declaration.for_domain("sales")["coverage_ready"] is True
    assert declaration.for_domain("support")["coverage_ready"] is False
    assert declaration.ready("fundraising") is True


def test_an_unregistered_domain_fails_closed_instead_of_missing_the_lookup():
    """A domain nobody has written requirements for is not a KeyError and not a default `True`.
    It is `unknown_domain` with every readiness predicate False — "we have never defined what a
    complete picture looks like here, so no negative inference is licensed"."""
    declaration = declare_coverage(org_id="org_a", connections=[_conn("gmail")], computed_at=NOW)
    verdict = declaration.for_domain("astrology")
    assert verdict["coverage_state"] == "unknown_domain"
    assert verdict["coverage_ready"] is False
    assert all(v is False for k, v in verdict["readiness"].items() if k != "has_company_canon")


def test_written_canon_is_visible_without_ever_licensing_a_negative_inference():
    """A refund policy is real context and no amount of it is email data. It must show up as its
    own dimension and must NOT move `coverage_ready` — the dashboard used to report a tenant with
    forty written documents as flatly 'not connected'."""
    declaration = declare_coverage(org_id="org_a", connections=[], computed_at=NOW,
                                   company_knowledge_count=40)
    sales = declaration.for_domain("sales")
    assert sales["company_knowledge"] == {"present": True, "count": 40}
    assert sales["readiness"]["has_company_canon"] is True
    assert sales["coverage_ready"] is False


def test_the_declaration_is_stamped_with_the_instant_it_was_given():
    """`computed_at` is a PARAMETER. A declaration that read a clock would make every replay of a
    March sweep a different row, and 'what did we believe we could see when we decided this'
    would stop being answerable."""
    assert declare_coverage(org_id="org_a", connections=[], computed_at=NOW).computed_at == NOW


def test_the_same_inputs_declare_the_same_coverage_twice():
    a = declare_coverage(org_id="org_a", connections=[_conn("gmail")], computed_at=NOW)
    b = declare_coverage(org_id="org_a", connections=[_conn("gmail")], computed_at=NOW)
    assert a == b


def test_a_missing_engine_counts_no_canon_rather_than_raising():
    """A deployment with no database is a legitimate state, and coverage is a hint on the
    ingestion path — a hint that can abort a capture is worse than a conservative one."""
    from genios_engine.capture.coverage.declaration import company_knowledge_count
    assert company_knowledge_count(None, "org_a") == 0
