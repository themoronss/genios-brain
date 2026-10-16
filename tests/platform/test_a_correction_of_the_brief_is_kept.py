"""STEP-16 · the brief keeps what you corrected — the drafter's kind beside yours, and a line replaced in one act.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_a_correction_of_the_brief_is_kept.py -q

Tree `yc2_w27_s16 · M46.C5.L-data.V1.U02` (`platform/company_brief_store`, migration 0242; `03` F126, F157).
Accepting a proposal as another kind of work keeps the proposal's kind in `proposed_kind`. A proposal may
replace an accepted line (`propose(replaces=…)`) — the line it corrects does not count as already saying
it — and accepting it removes that line in the same act, at the same instant, so the brief never holds
both and still says, at any earlier instant, what it said then. `pending` shows the replacing proposal
beside the line it would replace, and the confirm route returns it as is.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import company_brief_routes as routes
from genios_engine.platform import auth
from genios_engine.platform import company_brief_store as store
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

pytestmark = pytest.mark.pg

ORG = "org_s16_brief_corrected"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
SURGE = "surge.peakxv.test"


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company, email) values (:o, 'Arjun Rao', 'Nimbus Labs', "
                       "'arjun@s16brief.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _row(eng, line_id):
    with eng.connect() as c:
        return c.execute(text("select status, kind, proposed_kind, replaces, removed_at, accepted_at from "
                              "company_brief_lines where org_id = :o and line_id = :l"),
                         {"o": ORG, "l": line_id}).mappings().one()


def _program(c, at=AT):
    return store.add(c, org_id=ORG, section="in_motion", words="Surge — the programme we applied to",
                     decided_by="founder", at=at, domain=SURGE, kind="program")


def test_accepting_another_kind_keeps_the_drafters(engine):
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="in_motion", words="Surge — the programme we applied to",
                             proposed_by="drafter", at=AT, domain=SURGE, kind="program")
        store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT, kind="investor")
    row = _row(engine, line)
    assert (row["status"], row["kind"], row["proposed_kind"]) == ("accepted", "investor", "program")


@pytest.mark.parametrize("edit", [{}, {"kind": "program"}, {"words": "Surge — Peak XV's programme"}])
def test_a_kind_accepted_as_proposed_keeps_no_other(engine, edit):
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="in_motion", words="Surge — the programme we applied to",
                             proposed_by="drafter", at=AT, domain=SURGE, kind="program")
        store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT, **edit)
    assert _row(engine, line)["proposed_kind"] is None


def test_clearing_the_drafters_kind_keeps_it_and_a_proposal_with_none_keeps_nothing(engine):
    with engine.begin() as c:
        named = store.propose(c, org_id=ORG, section="in_motion", words="Surge — the programme we applied to",
                              proposed_by="drafter", at=AT, domain=SURGE, kind="program")
        store.accept(c, org_id=ORG, line_id=named, decided_by="founder", at=AT, kind=None)
        bare = store.propose(c, org_id=ORG, section="in_motion", words="Antler — the residency",
                             proposed_by="drafter", at=AT, domain="antler.test")
        store.accept(c, org_id=ORG, line_id=bare, decided_by="founder", at=AT, kind="program")
    assert (_row(engine, named)["kind"], _row(engine, named)["proposed_kind"]) == (None, "program")
    assert (_row(engine, bare)["kind"], _row(engine, bare)["proposed_kind"]) == ("program", None)


def test_a_proposal_may_correct_an_accepted_line_and_accepting_it_replaces_that_line(engine):
    later = AT + timedelta(days=3)
    with engine.begin() as c:
        old = _program(c)
        plain = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund behind it",
                              proposed_by="expert_review", at=later, domain=SURGE, kind="investor")
        assert plain is None, "without `replaces`, the accepted line already says it"
        new = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund behind it",
                            proposed_by="expert_review", at=later, domain=SURGE, kind="investor", replaces=old)
        assert new is not None
        [waiting] = store.pending(c, ORG)
        assert [ln.line_id for ln in store.accepted(c, ORG)] == [old], "nothing applied until you accept"
        store.accept(c, org_id=ORG, line_id=new, decided_by="founder", at=later + timedelta(hours=1))
        now = [(ln.line_id, ln.kind) for ln in store.accepted(c, ORG)]
        before = [(ln.line_id, ln.kind) for ln in store.accepted(c, ORG, at=later)]
    assert waiting["replaces"] == {"line_id": old, "text": "Surge — the programme we applied to",
                                   "kind": "program", "address": None, "domain": SURGE, "status": "accepted"}
    assert now == [(new, "investor")] and before == [(old, "program")]
    assert (_row(engine, old)["status"], _row(engine, old)["removed_at"]) == ("removed", later + timedelta(hours=1))
    assert _row(engine, new)["replaces"] == old


def test_a_replacing_proposal_is_not_written_twice_nor_after_you_rejected_one(engine):
    with engine.begin() as c:
        old = _program(c)
        first = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund",
                              proposed_by="expert_review", at=AT, domain=SURGE, kind="investor", replaces=old)
        again = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund",
                              proposed_by="expert_review", at=AT, domain=SURGE, kind="investor", replaces=old)
        store.reject(c, org_id=ORG, line_id=first, decided_by="founder", at=AT + timedelta(hours=1))
        nag = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund",
                            proposed_by="expert_review", at=AT + timedelta(days=2), domain=SURGE, kind="investor",
                            replaces=old)
    assert first is not None and again is None and nag is None
    assert _row(engine, old)["status"] == "accepted", "a rejected replacement replaces nothing"


@pytest.mark.parametrize("target", ["missing", "pending", "removed", "other_section"])
def test_only_an_accepted_line_of_the_section_can_be_replaced(engine, target):
    with engine.begin() as c:
        lines = {
            "missing": "cbl_nope",
            "pending": store.propose(c, org_id=ORG, section="in_motion", words="Antler — the residency",
                                     proposed_by="drafter", at=AT, domain="antler.test", kind="program"),
            "removed": _program(c),
            "other_section": store.add(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                                       decided_by="founder", at=AT),
        }
        store.remove(c, org_id=ORG, line_id=lines["removed"], decided_by="founder", at=AT)
    with pytest.raises(store.CompanyBriefError) as refused:
        with engine.begin() as c:
            store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund",
                          proposed_by="expert_review", at=AT, domain=SURGE, kind="investor",
                          replaces=lines[target])
    assert refused.value.code == "not_accepted"


def test_a_replacement_whose_line_you_removed_meanwhile_is_simply_accepted(engine):
    with engine.begin() as c:
        old = _program(c)
        new = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund",
                            proposed_by="expert_review", at=AT, domain=SURGE, kind="investor", replaces=old)
        store.remove(c, org_id=ORG, line_id=old, decided_by="founder", at=AT + timedelta(hours=1))
        store.accept(c, org_id=ORG, line_id=new, decided_by="founder", at=AT + timedelta(hours=2))
    assert _row(engine, old)["removed_at"] == AT + timedelta(hours=1), "removed once, when you removed it"
    assert _row(engine, new)["status"] == "accepted"


def test_the_confirm_route_returns_the_replacing_proposal_as_it_is(monkeypatch, engine):
    with engine.begin() as c:
        old = _program(c)
        new = store.propose(c, org_id=ORG, section="in_motion", words="Surge behaves like the fund",
                            proposed_by="expert_review", at=AT, domain=SURGE, kind="investor", replaces=old)
        expected = store.pending(c, ORG)

    monkeypatch.setattr(routes, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_owner", role="owner",
                                                             source="jwt")
    body = TestClient(app).get("/v1/company-brief").json()
    assert body["proposals"] == expected and body["proposals"][0]["line_id"] == new
    assert body["proposals"][0]["replaces"]["line_id"] == old
