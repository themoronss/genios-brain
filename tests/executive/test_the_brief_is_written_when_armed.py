"""STEP-15 · compose writes through the writer when `morning_brief` is armed, the template otherwise.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_the_brief_is_written_when_armed.py

Tree `yc2_w27_s15` M45.C3.L-integration.V0.U01. `executive/morning.compose` no longer calls
`morning_template.template_brief` directly — it calls `executive/morning_writer.write_brief`, which
degrades to that same template on its own (not activated, no client, both attempts fail) and is the
real writer (checked, with its receipt) once a tenant arms the switch. This file pins the WIRING:
that `compose` is the caller now, that it hands `write_brief` the founder's own name (`orgs.name`,
the same column `morning_day._SEAT` already reads it from), and that the two-transaction split
(`compose`'s own docstring) still gives one brief a day.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning as MB
from genios_engine.executive import morning_store
from genios_engine.platform.l4_activation import FEATURE_MORNING_BRIEF, activate

pytestmark = pytest.mark.pg

ORG = "org_s15_armed"
AT = datetime(2026, 10, 14, 3, 0, tzinfo=timezone.utc)      # past 08:00 in Asia/Kolkata


@pytest.fixture
def engine():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — composed on Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Priya Nair', :e, "
                       "'Asia/Kolkata')"), {"o": ORG, "e": f"{ORG}@example.test"})
        from genios_engine.platform.seats import ensure_owner_seat
        ensure_owner_seat(c, ORG)
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_not_armed_still_composes_the_template_through_write_brief(engine):
    """Unchanged from before this unit: `morning_brief` is off by default (M45.C1.L-contract.V0.U03),
    so `write_brief`'s own step-1 gate degrades to the template for free."""
    brief, wrote = MB.compose(engine, ORG, "seat_owner", now=AT)
    assert wrote and brief.written_by == B.TEMPLATE_BRIEF
    assert brief.cost_micro_usd == 0 and brief.model is None


def test_armed_with_no_client_configured_still_degrades_to_the_template(engine):
    """Armed, but this test suite never holds a real Anthropic key, and this fixture's org has no
    file, question or promise of its own — so `write_brief` takes its own empty-day exit before
    ever reaching a client. Either way the result is the same template `compose` always fell back
    to; `test_compose_calls_the_writer_not_the_template_directly` below is what proves `compose`
    itself is really the caller now, for a day with content or without."""
    activate(engine, ORG, feature=FEATURE_MORNING_BRIEF, by="test", at=AT)
    brief, wrote = MB.compose(engine, ORG, "seat_owner", now=AT)
    assert wrote and brief.written_by == B.TEMPLATE_BRIEF
    assert brief.cost_micro_usd == 0 and brief.model is None and brief.tier is None


def test_compose_hands_the_writer_the_founders_own_name(engine, monkeypatch):
    """`orgs.name` ('Priya Nair' here) is the founder's own name — the same column
    `morning_day._SEAT` reads `seat.name` from for `speaks_of_you`. `compose` must pass it on."""
    seen = {}

    def _fake(engine_, **kw):
        seen.update(kw)
        from genios_engine.executive.morning_template import template_brief
        return template_brief(org_id=kw["org_id"], seat_id=kw["seat_id"], items=kw["items"],
                              now=kw["now"], tz=kw["tz"])
    monkeypatch.setattr(MB, "write_brief", _fake)
    MB.compose(engine, ORG, "seat_owner", now=AT)
    assert seen.get("founder") == ("Priya Nair",)


def test_compose_calls_the_writer_not_the_template_directly(engine, monkeypatch):
    """The wiring itself, isolated from `write_brief`'s own correctness (covered in
    `tests/executive/test_the_brief_writer.py`): a sentinel return from a monkeypatched
    `write_brief` is what `compose` keeps."""
    sentinel = {"called_with": None}

    def _fake(engine_, **kw):
        sentinel["called_with"] = kw
        from genios_engine.executive.morning_template import template_brief
        return template_brief(org_id=kw["org_id"], seat_id=kw["seat_id"], items=kw["items"],
                              now=kw["now"], tz=kw["tz"])
    monkeypatch.setattr(MB, "write_brief", _fake)
    brief, wrote = MB.compose(engine, ORG, "seat_owner", now=AT)
    assert wrote and sentinel["called_with"] is not None
    assert sentinel["called_with"]["org_id"] == ORG and sentinel["called_with"]["seat_id"] == "seat_owner"
    with engine.connect() as c:
        assert morning_store.read(c, ORG, "seat_owner", date(2026, 10, 14)) == brief


def test_a_kept_brief_is_read_back_not_rewritten(engine, monkeypatch):
    """The two-transaction split still gives one brief a day: a second compose of the same local
    day never calls the writer at all."""
    first, wrote = MB.compose(engine, ORG, "seat_owner", now=AT)
    assert wrote

    def _unreached(*_a, **_k):
        raise AssertionError("write_brief was called for an already-kept day")
    monkeypatch.setattr(MB, "write_brief", _unreached)
    again, wrote = MB.compose(engine, ORG, "seat_owner", now=AT)
    assert wrote is False and again == first
