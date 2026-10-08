"""STEP-10 · the acceptance: every number on a file is traceable, exact, and says what it rests on.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_every_number_says_its_n.py -q

Tree `yc2_w27_s10 · M29.C6.L-integration.V5.U04`. STEP-10 §8 as a test, on the golden cases it is about, each
replayed from its cassette through the real chain and read through what `GET /v1/workstreams/{file_id}` serves
(`context/workstreams.files_for`, `context/workstream_timeline.timeline_for`,
`context/workstream_numbers.numbers_for`) before its tenant is removed:

  * your reply time is exact on the new case: six answers to Bluepeak at 0.5, 1, 1, 2, 3 and 6 days are
    "usually 1.5 days (n=6, person)", written as your normal with her and overall (F45) — the set held one
    such reply before (F14, n = 1);
  * one reply is never a habit: F17 and F25, which read a "tenant normal" built from one reply counted twice,
    now read "once: …" with no normal beside it (`STEP-10` §8.1);
  * F15's outreach to five funds is one wave — sent 5, none replied, none bounced, none followed up;
  * a bounce is on the fund's file and ends its wait — in the golden shape (F16) and in the shape Gmail sends
    it, its original attached and never landed as a document (F47);
  * every file names the mailbox it was read from and that mailbox's window; an answer that arrived in the
    founder's other mailbox is in the file, and the move is ours (F46);
  * the route and the health check read the same numbers: `GET /v1/workstreams/{file_id}` serves exactly what
    the read models say, and no normal anywhere rests on fewer than five.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = {c.case_id: c for c in load_cases()}
REPLAYED = ("F45", "F17", "F25", "F15", "F16", "F47", "F46")


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _route(engine, org: str, file_id: str, now) -> dict:
    """`GET /v1/workstreams/{file_id}` as the founder's dashboard calls it, at the case's instant."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import workstream_routes as routes
    from genios_engine.platform import auth
    from genios_engine.platform.auth import AuthCtx, get_auth_ctx

    class _Graph:
        def __init__(self, e) -> None:
            self.engine = e

    saved = (routes._graph, routes._now, auth.check_org_kill)
    routes._graph, routes._now = _Graph(engine), (lambda: now)
    auth.check_org_kill = lambda org_id: None
    try:
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(
            org_id=org, actor_id="seat_owner", role="owner", source="jwt")
        answer = TestClient(app).get(f"/v1/workstreams/{file_id}")
        assert answer.status_code == 200, answer.text
        return answer.json()
    finally:
        routes._graph, routes._now, auth.check_org_kill = saved


def _read(case_id: str) -> dict[str, Any]:
    """Replay one case, read every file's timeline and numbers, the waves, the waits, the health
    check and the route's answer for each file — then remove its tenant."""
    import importlib
    from datetime import timedelta

    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.context.correlation_conversation import find_waves
    from genios_engine.context.workstream_numbers import as_dict as numbers_as_dict
    from genios_engine.context.workstream_numbers import numbers_for
    from genios_engine.context.workstream_timeline import timeline_for
    from genios_engine.context.workstreams import files_for
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM
    from tests.replays.marking import judge

    case = CASES[case_id]
    now = case.sweeps[-1]
    llm = RecordedLLM(cassettes.load(case))
    run = run_case(case, llm, keep=True)
    engine, org = routes._graph.engine, run.org_id
    try:
        files: dict[str, dict[str, Any]] = {}
        with engine.connect() as c:
            for f in files_for(c, org, now=now).files:
                timeline = timeline_for(c, org, f.file_id, now=now)
                files[f.counterparty_key] = {
                    "file": f, "timeline": timeline,
                    "numbers": numbers_for(c, org, f, timeline, now=now)}
            waves = find_waves(c, org, since=now - timedelta(days=180), now=now)
            health = importlib.import_module(
                "scripts.pipeline_health").check_every_normal_says_its_n(c, org)
            waiting = {(r.canonical_key, r.field) for r in c.execute(text(
                "select n.canonical_key, f.field from graph_facts f join graph_nodes n "
                "  on n.org_id = f.org_id and n.node_id = f.subject_node_id and n.valid_to is null "
                " where f.org_id = :o and f.valid_to is null and f.field = 'thread.days_waiting'"),
                {"o": org})}
            normals = {(r.canonical_key, r.field): r.value for r in c.execute(text(
                "select n.canonical_key, f.field, f.value #>> '{}' as value from graph_facts f "
                "  join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
                "       and n.valid_to is null "
                " where f.org_id = :o and f.valid_to is null and f.status = 'active' "
                "   and f.field in ('party.our_reply_days', 'party.our_reply_n', "
                "                   'derived.our_reply_days', 'derived.our_reply_n')"),
                {"o": org})}
        served = {key: _route(engine, org, seen["file"].file_id, now)
                  for key, seen in files.items()}
        expected = {key: numbers_as_dict(seen["numbers"]) for key, seen in files.items()}
        return {"files": files, "waves": waves, "health": health, "waiting": waiting,
                "normals": normals, "served": served, "expected": expected,
                "landed": run.landed, "mark": judge(case, run), "misses": llm.misses}
    finally:
        remove_tenant(engine, org)


@pytest.fixture(scope="module")
def read():
    _scratch_db()
    return {case_id: _read(case_id) for case_id in REPLAYED}


def _person(seen: dict, file_key: str, person: str):
    [p] = [p for p in seen["files"][file_key]["numbers"].people if p.key == person]
    return p


@pytest.mark.pg
@pytest.mark.golden
def test_every_case_replays_exactly(read):
    for case_id, seen in read.items():
        assert not seen["misses"], f"{case_id}: the chain asked something its cassette does not hold"


@pytest.mark.pg
@pytest.mark.golden
def test_your_reply_time_is_exact_on_the_new_case(read):
    from genios_engine.contracts.measured import Measured
    meera = _person(read["F45"], "bluepeak.test", "meera@bluepeak.test")
    assert meera.your_reply_time == Measured(value=1.5, n=6, basis="person", unit="days")
    assert meera.your_reply_time.says() == "usually 1.5 days (n=6, person)"
    assert meera.your_normal == Measured(value=1.5, n=6, basis="person", unit="days")
    assert meera.their_reply_time.says() == "not measured", "she wrote first every time"
    normals = read["F45"]["normals"]
    assert (normals[("meera@bluepeak.test", "party.our_reply_days")],
            normals[("meera@bluepeak.test", "party.our_reply_n")]) == ("1.5", "6")
    overall = {k[1]: v for k, v in normals.items() if k[1].startswith("derived.")}
    assert overall == {"derived.our_reply_days": "1.5", "derived.our_reply_n": "6"}


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id, file_key, person, words", [
    ("F17", "gulflaunchpad.test", "amira@gulflaunchpad.test", "once: 35.98 days"),
    ("F25", "inboxmail.test", "kavitha.nair@inboxmail.test", "once: 1.92 days"),
])
def test_one_reply_reads_once_never_a_normal(read, case_id, file_key, person, words):
    """F17 and F25 read a 'tenant normal' built from one reply counted twice (`STEP-10` §8.1)."""
    p = _person(read[case_id], file_key, person)
    assert (p.their_reply_time.n, p.their_reply_time.sparse) == (1, True)
    assert p.their_reply_time.says() == words
    assert p.their_normal is None, f"{case_id}: one reply became a normal"


@pytest.mark.pg
@pytest.mark.golden
def test_the_outreach_to_five_funds_is_one_wave(read):
    [wave] = read["F15"]["waves"]
    assert len(wave.recipients) == 5 and wave.sent.says() == "5"
    assert [m.says() for m in (wave.reply_rate, wave.bounce_rate, wave.follow_up_rate)] == [
        "0 of 5", "0 of 5", "0 of 5"]
    assert round(wave.days_since_last_send, 1) == 56.3


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id, file_key, fund", [
    ("F16", "lattice-capital.test", "partners@lattice-capital.test"),
    ("F47", "ardentridge.test", "partners@ardentridge.test"),
])
def test_a_bounce_is_on_the_funds_file_and_ends_its_wait(read, case_id, file_key, fund):
    seen = read[case_id]
    report = CASES[case_id].objects[1]
    assert _person(seen, file_key, fund).bounced_at == report.occurred_at
    assert (fund, "thread.days_waiting") not in seen["waiting"], (
        f"{case_id}: still waiting on a reply to a mail that never arrived")


@pytest.mark.pg
@pytest.mark.golden
def test_the_reports_attached_original_is_never_a_document(read):
    landed = [l for l in read["F47"]["landed"] if l.object_id == "bounce"]
    assert [l.outcome for l in landed] == ["emitted"], landed
    assert not [l for l in landed if "::" in l.source_object_id], "an attached part landed"


@pytest.mark.pg
@pytest.mark.golden
def test_every_file_names_the_mailbox_it_was_read_from_and_its_window(read):
    for case_id, seen in read.items():
        for key, f in seen["files"].items():
            if not any(t.kind == "mail" for t in f["timeline"].touches):
                continue
            mailboxes = f["numbers"].mailboxes
            assert mailboxes, f"{case_id}/{key}: a file that says nothing about what was read"
            assert all(m.window_days == 60 and m.window_start is not None for m in mailboxes), (
                case_id, key, mailboxes)


@pytest.mark.pg
@pytest.mark.golden
def test_an_answer_in_the_other_mailbox_is_in_the_file(read):
    seedfund = read["F46"]["files"]["seedfund.test"]
    assert sorted(m.connection_id for m in seedfund["numbers"].mailboxes) == [
        "conn_golden_gmail", "conn_golden_gmail_personal"]
    assert [(t.direction, t.mailbox) for t in seedfund["timeline"].touches] == [
        ("out", "conn_golden_gmail_personal"), ("in", "conn_golden_gmail")]
    assert seedfund["file"].whose_move == "ours"


@pytest.mark.pg
@pytest.mark.golden
def test_the_route_and_the_health_check_read_the_same_numbers(read):
    for case_id, seen in read.items():
        assert seen["health"].ok, (case_id, seen["health"].detail)
        for key, body in seen["served"].items():
            assert body["numbers"] == seen["expected"][key], f"{case_id}/{key}"
            assert body["file"]["file_id"] == seen["files"][key]["file"].file_id
