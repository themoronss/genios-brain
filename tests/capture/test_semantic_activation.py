"""The strangler fig's switch — Wave W9.

Doc 04 forbids a config boolean here by name, and gives the reason: `use_domain_compiler=False`
is set in no environment and has left 152 capabilities dark. A global flag has two states and
both are wrong mid-migration — off means the new path is never exercised by anything real, on
means every tenant's bill changes on one deploy.

So the gate is a ROW, and the two properties that matter are: nothing runs until somebody adds
one, and the lookup fails closed when it cannot be read.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from genios_engine.platform import activation as A

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


class _BrokenEngine:
    """An engine whose every connection raises — a dropped table, a dead pool, a bad password."""

    def connect(self):
        raise RuntimeError("the database is not answering")

    def begin(self):
        raise RuntimeError("the database is not answering")


# ---------------------------------------------------------------------------------------------
# fail-closed
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("engine", [None, _BrokenEngine()],
                         ids=["no database at all", "a database that will not answer"])
def test_an_unreadable_switch_is_an_off_switch(engine):
    """The failure mode of this lookup must be a tenant who does not get the new extraction —
    the state every tenant is in today. The opposite default is an unbudgeted model call on
    every message of every sweep, discovered on an invoice."""
    assert A.semantic_activated_orgs(engine) == frozenset()
    assert A.is_semantic_activated(engine, "org_a") is False


def test_no_lane_is_built_for_a_tenant_nobody_switched_on():
    """The wiring's own gate, with the activation set stated outright so no database is needed."""
    from genios_engine.platform.wiring import make_semantic_lane
    assert make_semantic_lane("org_a", engine=None, llm=object(),
                              activated=frozenset()) is None


def test_no_lane_is_built_without_a_model_however_activated_the_tenant_is():
    """Condition 1 of 3. A lane around a None client would fail every event of every sweep, so an
    activated tenant on a deployment with no Anthropic key still gets the old path."""
    from genios_engine.platform.wiring import make_semantic_lane
    assert make_semantic_lane("org_a", engine=None, llm=None,
                              activated=frozenset({"org_a"})) is None


# ---------------------------------------------------------------------------------------------
# the real table
# ---------------------------------------------------------------------------------------------

@pytest.mark.pg
def test_activation_is_a_row_that_can_be_added_read_and_taken_away():
    """A migration you cannot reverse is a cutover with extra steps, so the OFF path is tested
    exactly as hard as the ON path."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the activation table is not exercised")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    org = "org_scratch_tests"                      # seeded by tests/conftest.py; FK-satisfying

    A.deactivate_semantic(engine, org)
    assert A.is_semantic_activated(engine, org) is False
    assert org not in A.semantic_activated_orgs(engine)

    record = A.activate_semantic(engine, org, by="harsh@genios.ai", at=NOW)
    assert record.org_id == org
    assert record.enabled_by == "harsh@genios.ai"
    assert A.is_semantic_activated(engine, org) is True
    assert org in A.semantic_activated_orgs(engine)

    # idempotent, and it keeps the ORIGINAL enabling record — "since when has this tenant been on
    # the new lane" is the question a two-path diff is read against, and an upsert that refreshed
    # the timestamp would answer it with the date of the last click
    again = A.activate_semantic(engine, org, by="someone.else@genios.ai")
    assert again.enabled_by == "harsh@genios.ai"
    assert again.enabled_at == record.enabled_at

    assert A.deactivate_semantic(engine, org) is True
    assert A.deactivate_semantic(engine, org) is False, "a second removal removed nothing"
    assert A.is_semantic_activated(engine, org) is False
