"""STEP-09 · the acceptance: every piece of work the company brief names has a file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_every_piece_of_work_has_a_file.py -q

Tree `yc2_w27_s09 · M27.C5.L-integration.V4.U02`. STEP-09 §8 as a test, on the golden cases it is
about, each replayed from its cassette through the real chain and read through the same read model
`GET /v1/workstreams` serves (`context/workstreams.files_for`) before its tenant is removed:

  * each of the 8 people the connector introduced (F03–F08, F37) has a file of their own — kind
    `intro`, introduced by the connector — that holds their introduction, and F03's two nudges about
    Rahul join his: 0 of 8 before STEP-09, by design (`STEP-09` §8.1);
  * the connector anchors no introduction and is owed no reply in any of them; its own ask (F09,
    golden replay 02 m04) is a file of its own;
  * each portal and program the brief watches that wrote (F01, F02, F23) is one file, of kind
    `watched`, holding every notice it sent — none had a file before;
  * the must-abstain cases STEP-09 touches hold: the connector is never the person to reply to
    (F37), a program's newsletter is never a file or a card (F32);
  * the health check reads the same answer: no named counterparty with mail and no file.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = {c.case_id: c for c in load_cases()}
CONNECTOR = "hello@introly.test"
FOUNDER = "arjun@nimbuslabs.test"
INTRO_CASES = ("F03", "F04", "F05", "F06", "F07", "F08", "F37")
#: The domain the brief watches, per case, and the provider objects it sent.
WATCHED = {"F01": {"startupsetu.gov.test": ("status",)},
           "F02": {"startupsetu.gov.test": ("ask", "received", "granted"),
                   "digivault.gov.test": ("locker",)},
           "F23": {"statestartup.gov.test": ("a", "b", "c", "d")}}
ABSTAIN = ("F32", "F37")
REPLAYED = (*INTRO_CASES, "F09", *WATCHED, "F32")


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _introductions(case) -> list[tuple[str, str]]:
    """(object id, person introduced) for every mail the connector sent to someone besides us."""
    return [(o.object_id, r) for o in case.objects
            if o.source == "gmail" and CONNECTOR in o.sender
            for r in o.to if r.lower() != FOUNDER]


def _read(case_id: str) -> dict[str, Any]:
    """Replay one case, read what STEP-09 promises off its rows, and remove its tenant."""
    import importlib

    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.context.workstreams import files_for
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM
    from tests.replays.marking import judge

    case = CASES[case_id]
    llm = RecordedLLM(cassettes.load(case))
    run = run_case(case, llm, keep=True)
    engine, org = routes._graph.engine, run.org_id
    try:
        with engine.connect() as c:
            ws = files_for(c, org, now=case.sweeps[-1])
            health = importlib.import_module(
                "scripts.pipeline_health").check_every_named_counterparty_has_a_file(c, org)
            owed = c.execute(text(
                "select count(*) from graph_facts f join graph_nodes n on n.org_id = f.org_id "
                "   and n.node_id = f.subject_node_id and n.valid_to is null "
                " where f.org_id = :o and n.canonical_key = :k and f.valid_to is null "
                "   and f.field = 'thread.ball_in_court'"), {"o": org, "k": CONNECTOR}).scalar()
        events: dict[str, set[str]] = {}
        for landed in run.landed:
            if landed.event_id:
                events.setdefault(landed.object_id, set()).add(landed.event_id)
        return {"files": {f.counterparty_key: f for f in ws.files}, "named": ws.named,
                "unfiled": ws.unfiled, "health": health, "connector_owed": int(owed),
                "events": events, "mark": judge(case, run), "cards": run.cards,
                "misses": llm.misses}
    finally:
        remove_tenant(engine, org)


@pytest.fixture(scope="module")
def read():
    _scratch_db()
    return {case_id: _read(case_id) for case_id in REPLAYED}


def _file_of(seen: dict, person: str):
    """The file a person's mail is in: their company's, or their own on a personal mailbox."""
    files = seen["files"]
    return files.get(person.split("@", 1)[1]) or files.get(person)


@pytest.mark.pg
@pytest.mark.golden
def test_every_person_the_connector_introduced_has_a_file_holding_the_introduction(read):
    introduced = [(case_id, oid, person) for case_id in INTRO_CASES
                  for oid, person in _introductions(CASES[case_id])]
    assert len(introduced) == 8, introduced
    for case_id, oid, person in introduced:
        seen = read[case_id]
        file = _file_of(seen, person)
        assert file is not None, f"{case_id}: {person} has no file"
        assert (file.kind, file.introduced_by) == ("intro", CONNECTOR), (case_id, person, file)
        assert seen["events"][oid] & set(file.events), f"{case_id}: {oid} is not in {person}'s file"


@pytest.mark.pg
@pytest.mark.golden
def test_the_connectors_nudges_join_the_file_of_the_person_they_name(read):
    seen = read["F03"]
    rahul = _file_of(seen, "rahul@kestrelcap.test")
    for nudge in ("nudge1", "nudge2"):
        assert seen["events"][nudge] <= set(rahul.events), nudge


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", INTRO_CASES)
def test_the_connector_anchors_no_introduction_and_is_owed_no_reply(read, case_id):
    seen = read[case_id]
    connector_file = seen["files"].get("introly.test")
    intros = {e for oid, _p in _introductions(CASES[case_id]) for e in seen["events"][oid]}
    assert connector_file is None or not intros & set(connector_file.events), connector_file
    assert seen["connector_owed"] == 0, f"{case_id}: the connector is owed a reply"
    about_it = [c for c in seen["cards"] if "introly" in (c.subject or "").lower()]
    assert not about_it, f"{case_id}: a card is about the connector: {about_it}"


@pytest.mark.pg
@pytest.mark.golden
def test_the_connectors_own_ask_is_its_own_file(read):
    seen = read["F09"]
    own = seen["files"]["introly.test"]
    assert own.kind == "connector" and seen["events"]["ask"] <= set(own.events)
    assert seen["connector_owed"] == 1, "its own ask is owed a reply, as any mail is"


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", sorted(WATCHED))
def test_each_watched_portal_or_program_that_wrote_is_one_file(read, case_id):
    seen = read[case_id]
    for domain, objects in WATCHED[case_id].items():
        file = seen["files"].get(domain)
        assert file is not None and file.kind == "watched", (case_id, domain, file)
        sent = {e for oid in objects for e in seen["events"][oid]}
        assert sent <= set(file.events), (case_id, domain, sent - set(file.events))
        assert not [k for k in seen["files"] if k != domain and k.endswith("." + domain)], (
            f"{case_id}: a subdomain of {domain} became a second file")


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", ABSTAIN)
def test_the_must_abstain_cases_it_touches_hold(read, case_id):
    mark = read[case_id]["mark"]
    assert mark.verdict == "pass", (case_id, mark.reason)


@pytest.mark.pg
@pytest.mark.golden
def test_a_programs_newsletter_is_never_a_file(read):
    assert "lakshya.test" not in read["F32"]["files"]


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", REPLAYED)
def test_the_health_check_reads_the_same_answer_and_nothing_named_is_unfiled(read, case_id):
    seen = read[case_id]
    assert seen["unfiled"] == () and seen["health"].ok, (case_id, seen["health"])
    mail = sum(n.mail for n in seen["named"])
    filed = sum(n.filed for n in seen["named"])
    if seen["named"]:
        assert f"{filed} of {mail} of their mails are filed" in seen["health"].measured
    else:
        assert seen["health"].measured.startswith("not exercised")


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", REPLAYED)
def test_no_model_call_the_cassette_does_not_hold(read, case_id):
    assert not read[case_id]["misses"], read[case_id]["misses"][:3]
