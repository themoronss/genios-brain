"""STEP-16 · your door on a file — a correction in your words, with its scope, and taking it back.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_correcting_a_file.py -q

Tree `yc2_w27_s16 · M46.C3.L-interface.V2.U03` (S16-D1, `06` D27's rule). `POST /v1/workstreams/{file_id}/corrections`
keeps your words with their scope — `file`, `kind` (every file of this kind of work, the kind the brief gives
the file) or `company` (your preferences line of the brief) — and, optionally, the card it is about;
`…/corrections/{id}/withdraw` takes one back; `GET /v1/workstreams/{file_id}` lists the file's standing
corrections. A file correction is the owner's, or the seat a card of that file is routed to; a kind or a
company correction is the owner's alone; a `kind` on a file the brief names no kind for is refused, saying so.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import workstream_routes as routes
from genios_engine.context import founder_corrections as C
from genios_engine.platform import auth
from genios_engine.platform.auth import MEMBER_SCOPES, AuthCtx, get_auth_ctx
from tests.context.workstream_world import FOUNDER, T0, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s16_correct_route"
PRIYA = "priya@northwind.test"
NOW = T0 + timedelta(days=30)
OWNER = AuthCtx(org_id=ORG, actor_id="seat_owner", seat_id="seat_owner", role="owner", source="jwt")
ADMIN = AuthCtx(org_id=ORG, actor_id="seat_admin", seat_id="seat_admin", role="admin", source="jwt")
MEMBER = AuthCtx(org_id=ORG, actor_id="seat_member", seat_id="seat_member", role="member", source="jwt",
                 scopes=sorted(MEMBER_SCOPES))
WORDS = "Priya asked for updates only with real news — don't push me."


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    for i in range(2):
        asked = T0 + timedelta(days=5 * i)
        process(pg_store, ORG, event_id=f"{ORG}_ask_{i}", sender=FOUNDER, recipients=(PRIYA,), thread=f"t_{i}",
                at=asked)
        process(pg_store, ORG, event_id=f"{ORG}_her_{i}", sender=PRIYA, thread=f"t_{i}",
                at=asked + timedelta(days=1))
    yield pg_store
    reset(pg_store, ORG)


def _client(monkeypatch, store, ctx: AuthCtx) -> TestClient:
    monkeypatch.setattr(routes, "_graph", _Graph(store.engine))
    monkeypatch.setattr(routes, "_now", lambda: NOW)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def _file_id(store) -> str:
    with store.engine.connect() as c:
        return c.execute(text(
            "select k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id and m.correlation_id = k.correlation_id "
            "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            " where k.org_id = :o and lower(se.actor->>'email') = :k limit 1"), {"o": ORG, "k": PRIYA}).scalar()


def _work_kind(store, kind="investor") -> None:
    from genios_engine.platform import company_brief_store as brief
    with store.engine.begin() as c:
        brief.add(c, org_id=ORG, section="in_motion", words="Raising from Northwind — the seed round",
                  decided_by="seat_owner", at=T0, domain="northwind.test", kind=kind)


def _card(store, card_id: str, *, subject: str, assignee: str | None) -> str:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, subject_node_id, score, "
            "reason_code, eval_time) values (:s, :o, 'general', '1.0.0', 'unanswered_email', :n, 10, "
            "'unanswered_email', :at)"), {"s": f"sig_{card_id}", "o": ORG, "n": subject, "at": NOW})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
            "expires_at, assignee) values (:c, :s, :o, 'prescriptive', 'standard', 'h', 's', 10, :exp, :a)"),
            {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "exp": NOW + timedelta(days=7), "a": assignee})
    return card_id


def _post(client, file_id, **body):
    return client.post(f"/v1/workstreams/{file_id}/corrections", json=body)


def test_the_owner_corrects_a_file_and_it_is_listed_with_it(monkeypatch, store):
    file_id = _file_id(store)
    client = _client(monkeypatch, store, OWNER)
    answer = _post(client, file_id, words=WORDS)
    assert answer.status_code == 200, answer.text
    kept = answer.json()["correction"]
    assert (kept["words"], kept["scope"], kept["kind"], kept["state"], kept["corrected_by"]) == (
        WORDS, "file", None, "standing", "seat_owner")
    assert kept["correction_id"] == C.correction_id_for(ORG, file_id, WORDS, "file")
    again = _post(client, file_id, words=WORDS).json()["correction"]
    assert again["correction_id"] == kept["correction_id"], "the same words again are the same correction"
    listed = client.get(f"/v1/workstreams/{file_id}").json()["corrections"]
    assert [c["correction_id"] for c in listed["standing"]] == [kept["correction_id"]] and listed["cut"] == 0


def test_a_kind_correction_reaches_the_kind_the_brief_gives_the_file(monkeypatch, store):
    file_id = _file_id(store)
    client = _client(monkeypatch, store, OWNER)
    refused = _post(client, file_id, words="Investors get nothing before a milestone.", scope="kind")
    assert refused.status_code == 422 and "names no kind of work" in refused.json()["detail"]
    _work_kind(store)
    kept = _post(client, file_id, words="Investors get nothing before a milestone.", scope="kind")
    assert kept.status_code == 200, kept.text
    assert (kept.json()["correction"]["scope"], kept.json()["correction"]["kind"]) == ("kind", "investor")


def test_a_company_correction_is_your_line_of_the_brief_and_not_the_files(monkeypatch, store):
    file_id = _file_id(store)
    client = _client(monkeypatch, store, OWNER)
    kept = _post(client, file_id, words="Never push a follow-up on a Friday.", scope="company").json()["correction"]
    assert kept["scope"] == "company" and kept["brief_line_id"]
    with store.engine.connect() as c:
        line = c.execute(text("select section, text, status from company_brief_lines where org_id = :o and "
                              "line_id = :l"), {"o": ORG, "l": kept["brief_line_id"]}).one()
    assert tuple(line) == ("preferences", "Never push a follow-up on a Friday.", "accepted")
    assert client.get(f"/v1/workstreams/{file_id}").json()["corrections"]["standing"] == []


@pytest.mark.parametrize("scope", ["kind", "company"])
def test_a_kind_or_company_correction_is_the_owners_alone(monkeypatch, store, scope):
    file_id = _file_id(store)
    _work_kind(store)
    card = _card(store, "card_s16_admin", subject=file_id, assignee="seat_admin")
    for ctx in (ADMIN, MEMBER):
        answer = _post(_client(monkeypatch, store, ctx), file_id, words="Not yours to say.", scope=scope,
                       card_id=card)
        assert answer.status_code == 403, (ctx.role, answer.text)


def test_a_seat_corrects_a_file_through_a_card_of_it_routed_to_them(monkeypatch, store):
    file_id = _file_id(store)
    priya = node(store, ORG, PRIYA).node_id
    mine = _card(store, "card_s16_mine", subject=priya, assignee="seat_member")
    theirs = _card(store, "card_s16_theirs", subject=file_id, assignee="seat_someone_else")
    elsewhere = _card(store, "card_s16_elsewhere", subject="node_another_file", assignee="seat_member")
    client = _client(monkeypatch, store, MEMBER)
    assert _post(client, file_id, words=WORDS).status_code == 403, "no card, no door"
    assert _post(client, file_id, words=WORDS, card_id=theirs).status_code == 403, "not routed to this seat"
    assert _post(client, file_id, words=WORDS, card_id=elsewhere).status_code == 403, "a card of another file"
    kept = _post(client, file_id, words=WORDS, card_id=mine)
    assert kept.status_code == 200, kept.text
    assert (kept.json()["correction"]["card_id"], kept.json()["correction"]["corrected_by"]) == (
        mine, "seat_member")


@pytest.mark.parametrize("body", [{"words": "  "}, {"words": "two\nlines"}, {"words": WORDS, "scope": "team"}])
def test_what_is_not_a_correction_is_422(monkeypatch, store, body):
    answer = _post(_client(monkeypatch, store, OWNER), _file_id(store), **body)
    assert answer.status_code == 422


def test_an_unknown_file_is_404(monkeypatch, store):
    assert _post(_client(monkeypatch, store, OWNER), "node_nope", words=WORDS).status_code == 404


def test_a_correction_is_taken_back_and_kept(monkeypatch, store):
    file_id = _file_id(store)
    owner = _client(monkeypatch, store, OWNER)
    kept = _post(owner, file_id, words=WORDS).json()["correction"]
    url = f"/v1/workstreams/{file_id}/corrections/{kept['correction_id']}/withdraw"
    assert _client(monkeypatch, store, MEMBER).post(url).status_code == 403, "not the seat that wrote it"
    gone = _client(monkeypatch, store, OWNER).post(url)
    assert gone.status_code == 200 and gone.json()["correction"]["state"] == "withdrawn"
    assert gone.json()["correction"]["withdrawn_by"] == "seat_owner"
    assert owner.post(url).status_code == 409, "already withdrawn"
    assert owner.post(f"/v1/workstreams/{file_id}/corrections/fc_nope/withdraw").status_code == 404
    assert owner.get(f"/v1/workstreams/{file_id}").json()["corrections"]["standing"] == []
    with store.engine.connect() as c:
        assert c.execute(text("select state from founder_corrections where org_id = :o"), {"o": ORG}).scalar() \
            == "withdrawn", "kept, never deleted"


def test_a_seat_takes_back_its_own_file_correction(monkeypatch, store):
    file_id = _file_id(store)
    mine = _card(store, "card_s16_mine2", subject=file_id, assignee="seat_member")
    member = _client(monkeypatch, store, MEMBER)
    kept = _post(member, file_id, words=WORDS, card_id=mine).json()["correction"]
    gone = member.post(f"/v1/workstreams/{file_id}/corrections/{kept['correction_id']}/withdraw")
    assert gone.status_code == 200 and gone.json()["correction"]["withdrawn_by"] == "seat_member"


def test_a_kind_correction_records_the_kind_the_brief_gives_whatever_it_is(monkeypatch, store):
    file_id = _file_id(store)
    _work_kind(store, "program")
    kept = _post(_client(monkeypatch, store, OWNER), file_id, words="Programmes reply in their own time.",
                 scope="kind").json()["correction"]
    assert kept["kind"] == "program"


def test_a_correction_is_taken_back_only_through_its_own_file(monkeypatch, store):
    file_id = _file_id(store)
    owner = _client(monkeypatch, store, OWNER)
    kept = _post(owner, file_id, words=WORDS).json()["correction"]
    other = "node_not_this_file"
    with store.engine.begin() as c:
        C.correct(c, org_id=ORG, file_id=other, words="Another file's correction.", scope="file", by="seat_owner",
                  at=NOW)
    elsewhere = owner.post(f"/v1/workstreams/{other}/corrections/{kept['correction_id']}/withdraw")
    assert elsewhere.status_code == 404, "no such file holds it"
    theirs = C.correction_id_for(ORG, other, "Another file's correction.", "file")
    assert owner.post(f"/v1/workstreams/{file_id}/corrections/{theirs}/withdraw").status_code == 404, (
        "a correction of another file is not this file's to take back")
    with store.engine.connect() as c:
        assert {r[0] for r in c.execute(text("select state from founder_corrections where org_id = :o"),
                                        {"o": ORG})} == {"standing"}
