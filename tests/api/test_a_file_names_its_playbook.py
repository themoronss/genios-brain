"""STEP-11 · `GET /v1/workstreams/{file_id}` names the file's playbook and whether it was reviewed.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_a_file_names_its_playbook.py -q

Tree `yc2_w27_s11 · M30.C5.L-interface.V3.U02`. A file knows its kind of work from the in-motion line
that names it (M30.C4.L-logic.V1.U04); `packs/compiler/playbook_reader.playbook_for(kind)` answers what
the Founder Office corpus says about that work (M30.C5.L-logic.V2.U01). The one-file route now carries
that answer beside the file, its timeline and its numbers — the playbook with its stages, moves, claims
and review state, or the named reason there is none — so a reader sees what STEP-12's expert will read.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import workstream_routes as routes
from genios_engine.packs.compiler import playbook_reader
from genios_engine.platform import auth, company_brief, company_brief_store
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from tests.context.workstream_world import FOUNDER, T0, later, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s11_file_playbook"
NEHA = "neha@apply.lakshya.test"
OWNER = AuthCtx(org_id=ORG, actor_id="seat_owner", role="admin", source="jwt")


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        company_brief_store.add(c, org_id=ORG, section="in_motion", decided_by="founder", at=T0,
                                words="Lakshya — the accelerator application", kind="program",
                                domain="lakshya.test")
    brief = company_brief.current(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_lakshya", sender=NEHA, recipients=(FOUNDER,),
            thread="t_lakshya", company_brief=brief, at=later(1))
    process(pg_store, ORG, event_id="evt_plain", sender="ops@southwind.test", recipients=(FOUNDER,),
            thread="t_plain", company_brief=brief, at=later(2))
    yield pg_store
    reset(pg_store, ORG)
    company_brief.invalidate(ORG)


def _client(monkeypatch, store) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(store.engine))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: OWNER
    return TestClient(app)


def _file_id(client, key: str) -> str:
    files = client.get("/v1/workstreams").json()["files"]
    [found] = [f for f in files if f["counterparty"]["key"] == key]
    return found["file_id"]


def test_the_file_carries_the_answer_for_its_kind(monkeypatch, store):
    asked: list = []
    canned = playbook_reader.PlaybookAnswer(kind="program", playbook=None,
                                            reason="capability_not_authored")

    def fake(kind, **_kw):
        asked.append(kind)
        return canned

    monkeypatch.setattr(routes, "playbook_for", fake)
    client = _client(monkeypatch, store)
    body = client.get(f"/v1/workstreams/{_file_id(client, 'apply.lakshya.test')}").json()
    assert body["file"]["work_kind"] == "program"
    assert asked == ["program"]
    assert body["playbook"] == canned.as_dict()


def test_a_file_no_line_names_reads_no_playbook_and_says_why(monkeypatch, store):
    client = _client(monkeypatch, store)
    body = client.get(f"/v1/workstreams/{_file_id(client, 'southwind.test')}").json()
    assert body["file"]["work_kind"] is None
    assert body["playbook"] == {"kind": None, "reason": playbook_reader.NO_KIND, "playbook": None}


def test_the_real_answer_is_a_playbook_or_a_reason_never_both(monkeypatch, store):
    """Unstubbed, over the shipped corpus: whatever the programmes capability holds today."""
    client = _client(monkeypatch, store)
    answer = client.get(f"/v1/workstreams/{_file_id(client, 'apply.lakshya.test')}").json()["playbook"]
    assert answer["kind"] == "program"
    assert (answer["playbook"] is None) == (answer["reason"] is not None)
    if answer["playbook"] is not None:
        assert answer["playbook"]["review_label"] in (None, playbook_reader.REVIEW_LABEL)
        assert answer["playbook"]["stages"], "a kind's playbook is its spine — it has stages"


def test_the_list_still_carries_no_playbook(monkeypatch, store):
    """The list stays the list: the playbook rides on the one-file read, where a reader asked for it."""
    files = _client(monkeypatch, store).get("/v1/workstreams").json()["files"]
    assert all("playbook" not in f for f in files)
