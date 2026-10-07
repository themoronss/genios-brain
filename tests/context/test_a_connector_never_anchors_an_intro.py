"""STEP-09 · a connector the company brief names is an introducer — an introduction is filed under the
person it introduces, never under the connector.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_connector_never_anchors_an_intro.py -q

`context/pipeline.process_event` (tree `yc2_w27_s09 · M27.C1.L-logic.V0.U01`). The extraction's role
`connector` is free text the graph never read (`03` F80), so `correlation.choose_anchors`' rule "a
connector never anchors" could not fire: on the golden set every Introly introduction was filed under
Introly, and in production 254 Boardy threads sit under one `boardy.ai` correlation. Now an address the
founder's brief names as a connector is typed `introducer` wherever it appears — on the brief's word,
recorded as a `party.role` fact — so an introduction anchors on the person introduced. Alone in a
message, as when the connector asks the founder something of its own (golden F09, replay 02 m04), it
still anchors: that ask is the connector's own file. A tenant with no brief is unchanged.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, anchors, brief, facts, later,
                               mention, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_connector_anchor"
CONTACT = "rahul@kestrelcap.test"
RUNNER = Path(__file__).resolve().parents[2] / "genios_engine" / "context" / "runner.py"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _intro(store, event_id, **kw):
    return process(store, ORG, event_id=event_id, sender=CONNECTOR, sender_name="Introly",
                   recipients=(FOUNDER, CONTACT), thread=f"t_{event_id}", headers=UNSUBSCRIBE,
                   **kw)


def test_an_introduction_is_filed_under_the_person_introduced(store):
    _intro(store, "evt_intro", company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_intro") == {"kestrelcap.test"}


def test_the_connector_is_an_introducer_on_the_briefs_word(store):
    _intro(store, "evt_intro", company_brief=brief(ORG))
    [(role, evidence)] = facts(store, ORG, CONNECTOR, "party.role")
    assert role == "introducer" and evidence.get("standing") == "company_brief"


def test_the_connectors_own_ask_is_its_own_file(store):
    """Golden F09: "which stage are you raising at?" — to the founder alone, about no one else."""
    process(store, ORG, event_id="evt_ask", sender=CONNECTOR, sender_name="Introly",
            thread="t_ask", headers=UNSUBSCRIBE, company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_ask") == {"introly.test"}


def test_mail_to_the_connector_is_part_of_its_own_file(store):
    process(store, ORG, event_id="evt_mine", sender=FOUNDER, recipients=(CONNECTOR,),
            thread="t_mine", company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_mine") == {"introly.test"}
    assert [r for r, _ in facts(store, ORG, CONNECTOR, "party.role")] == ["introducer"]


def test_the_connector_named_in_anothers_mail_is_still_infrastructure(store):
    """Rahul thanks Introly in a thread of his own. The connector's address is not on that mail, but
    its company is named in it — and an intro network is infrastructure wherever it appears, so the
    mail is filed under Rahul alone, not under Introly as well."""
    _intro(store, "evt_intro", company_brief=brief(ORG))
    process(store, ORG, event_id="evt_thanks", sender=CONTACT, sender_name="Rahul Menon",
            thread="t_thanks", mentions=(mention("Introly", "organization"),),
            company_brief=brief(ORG), at=later(1))
    assert anchors(store, ORG, "evt_thanks") == {"kestrelcap.test"}


def test_a_connectors_auto_reply_is_no_file_and_owed_nothing(store):
    """"We got your message" from the network's responder is not its ask, and not an introduction."""
    process(store, ORG, event_id="evt_auto", sender=CONNECTOR, sender_name="Introly",
            thread="t_auto", headers={**UNSUBSCRIBE, "Auto-Submitted": "auto-replied"},
            company_brief=brief(ORG))
    assert anchors(store, ORG, "evt_auto") == set()
    assert facts(store, ORG, CONNECTOR, "thread.ball_in_court") == []


def test_a_tenant_with_no_brief_is_unchanged(store):
    """No brief: the unsubscribe header keeps the recipients out, and the intro anchors where it
    always did — the byte-for-byte promise every STEP-07 site keeps for a tenant with no brief."""
    _intro(store, "evt_intro", company_brief=None)
    assert anchors(store, ORG, "evt_intro") == {"introly.test"}
    assert facts(store, ORG, CONNECTOR, "party.role") == []


def test_a_sender_the_brief_does_not_name_a_connector_is_not_one(store):
    process(store, ORG, event_id="evt_other", sender="team@matchmaker.test",
            recipients=(FOUNDER, CONTACT), thread="t_other", company_brief=brief(ORG))
    assert facts(store, ORG, "team@matchmaker.test", "party.role") == []
    assert "matchmaker.test" in anchors(store, ORG, "evt_other")


def _calls(fn: ast.FunctionDef, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", getattr(n.func, "id", None)) == name]


def test_the_drain_reads_the_brief_once_per_pass_and_hands_it_down():
    """By the AST: `process_pending` reads the brief beside who is us and hands it to every event,
    down every road into memory to `process_event`; the rebuild script does the same."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    pending = fns["process_pending"]
    [reader] = [a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                and n.module == "genios_engine.platform.company_brief"
                for a in n.names if a.name == "current"]
    assert _calls(pending, reader), "the drain does not read the company brief"
    for caller, callee in (("process_pending", "_safe_process_one"),
                           ("_safe_process_one", "_process_one"),
                           ("_process_one", "_commit_metadata"),
                           ("_process_one", "process_event"),
                           ("_commit_metadata", "process_event")):
        [call] = _calls(fns[caller], callee)
        assert "company_brief" in {k.arg for k in call.keywords}, f"{caller} → {callee}"
    rebuild = ast.parse((RUNNER.parents[2] / "scripts" / "rebuild_graph.py").read_text())
    [replay] = [n for n in ast.walk(rebuild) if isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == "_safe_process_one"]
    assert "company_brief" in {k.arg for k in replay.keywords}
