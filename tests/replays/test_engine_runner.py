"""STEP-01 · the runner drives the real chain, replays it exactly, and cannot be pointed elsewhere.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/replays/test_engine_runner.py -q

These test the INSTRUMENT, not the engine's answers — the founder cases are the exam. What the
instrument must do:

  * refuse to start without a scratch database, or against a production host;
  * hand every model door the recorded model, and refuse the real transport while a case runs;
  * drive the production door: the connectors' own mappings, `run_sync`, `finalize_l1` (through
    `routes._run_ledger`), and `_run_l2_chain` at the case's instant, per sweep;
  * replay a recorded case EXACTLY — the recording run and the replay report the same thing;
  * fail loudly on a cassette miss.

And the negative control the plan names (STEP-01 §3.4): the mail `tests/test_e2e_all_layers.py`
proves "all layers" with, run at the PRODUCTION floor, yields no card — that test is green only
because it sets the floor to 1 and asserts a dict.
"""
from __future__ import annotations

import copy
import os

import pytest

from tests.replays import engine_runner as er
from tests.replays import founder_case as fc
from tests.replays.harness import CassetteMiss, CassetteRecorder, RecordedLLM
from tests.replays.ideal_reader import IdealReader

needs_db = pytest.mark.skipif(not os.environ.get(er.SCRATCH_ENV),
                              reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")

FOUNDER = {"name": "Arjun Rao", "email": "arjun@nimbuslabs.test", "company": "Nimbus Labs",
           "timezone": "Asia/Kolkata"}
ASK = ("Hi Arjun,\n\nThanks for the call last week. Could you send us your latest deck and the "
       "July revenue before our partners meet on Monday?\n\nBest,\nKavya Menon\nPrincipal, Lotus "
       "Ventures")
NUDGE = ("Hi Arjun, a gentle nudge on the deck — our partner meeting is tomorrow and I would "
         "love to include Nimbus Labs.\n\nKavya")
DIGEST = "Your weekly digest: twelve rounds closed this week. Read more on our site."


def _extraction(*, question: str) -> dict:
    return {"intent": "request", "stance": "positive", "topics": ["seed round"],
            "entity_mentions": [{"surface_form": "Kavya", "entity_type": "person",
                                 "quote": "Kavya"}],
            "questions": [{"text": "Send the latest deck", "asked_by": "Kavya Menon",
                           "asked_of": "Arjun Rao", "quote": question}],
            "exchange_intent": {"category": "working", "tone": "warm",
                                "formality": "professional", "addressed_personally": True,
                                "human_authored": True, "asks_for_reply": True},
            "implied_actions": ["send the latest deck"]}


CASE = {
    "case_id": "F97", "title": "The runner's own case", "kind": "must_detect",
    "label_row": 10, "labelled_by": "claude", "replays": [], "founder": FOUNDER,
    "sweeps": ["2026-09-18T12:00:00Z", "2026-09-20T12:00:00Z"],
    "objects": [
        {"id": "ask", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-18T09:30:00Z",
         "from": "Kavya Menon <kavya@lotusvc.test>", "to": ["arjun@nimbuslabs.test"],
         "thread": "t-lotus", "subject": "Deck before Monday?", "body": ASK,
         "labels": ["INBOX", "IMPORTANT"],
         "attachments": [{"filename": "partner-memo.pdf", "mime": "application/pdf",
                          "fetch": "refused"}],
         "read": {"gate": "keep", "relevance": "business",
                  "extraction": _extraction(question="Could you send us your latest deck")}},
        {"id": "digest", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-18T07:00:00Z",
         "from": "Round Up <digest@roundup.test>", "to": ["arjun@nimbuslabs.test"],
         "subject": "Twelve rounds this week", "body": DIGEST,
         "labels": ["INBOX", "CATEGORY_PROMOTIONS"],
         "headers": {"List-Unsubscribe": "<mailto:leave@roundup.test>", "Precedence": "bulk"},
         "read": {"gate": "drop", "relevance": "not_business"}},
        {"id": "call", "source": "gcal", "sweep": 0, "occurred_at": "2026-09-18T10:00:00Z",
         "summary": "Nimbus Labs x Lotus Ventures", "start": "2026-09-22T05:30:00Z",
         "end": "2026-09-22T06:00:00Z", "organizer": "kavya@lotusvc.test",
         "attendees": ["kavya@lotusvc.test", "arjun@nimbuslabs.test"]},
        {"id": "nudge", "source": "gmail", "sweep": 1, "occurred_at": "2026-09-20T08:00:00Z",
         "from": "Kavya Menon <kavya@lotusvc.test>", "to": ["arjun@nimbuslabs.test"],
         "thread": "t-lotus", "subject": "Re: Deck before Monday?", "body": NUDGE,
         "labels": ["INBOX"],
         "read": {"gate": "keep", "relevance": "business",
                  "extraction": _extraction(question="a gentle nudge on the deck")}},
    ],
    "expected": {"cards": [{"about": ["Kavya"], "min": 1, "max": 1}]},
    "forbidden": {"names": [], "phrases": []}, "witness": None, "not_expressible": {},
    "model": {"decider": [{"when": ["admin contact", "kavya@lotusvc.test"], "answer": {
        "outcome": "decision", "confidence_bp": 5500,
        "move": {"one_page_brief_before_every_external_meeting": 6200},
        "rationale": "A confirmed external meeting on 22 Sep: a one-page brief before it is the "
                     "useful move."}}],
              # Written from the narrator's prompt alone: it knows the attendee and nothing open.
              "narrator": [{"when": ["admin_contact", "kavya@lotusvc.test"], "answer": {
                  "headline": "Meeting with kavya@lotusvc.test is clear",
                  "situation": "Nothing open is on record with kavya@lotusvc.test before the "
                               "meeting.",
                  "artifact": "Nothing is missing on record; confirm the agenda before the "
                              "meeting."}}]},
}

#: The mail of `tests/test_e2e_all_layers.py`, and the extraction it hands Layer 1 — as quotes.
E2E_BODY = ("Priya from Acme said the proposal looks good. Budget is approved. "
            "Can you send the revised contract by Friday?")
E2E = {
    "case_id": "F98", "title": "The e2e mail, at the production floor", "kind": "must_detect",
    "label_row": 10, "labelled_by": "claude", "replays": [], "founder": FOUNDER,
    "sweeps": ["2026-08-08T12:00:00Z"],
    "objects": [{
        "id": "e2e", "source": "gmail", "sweep": 0, "occurred_at": "2026-08-08T12:00:00Z",
        "from": "Priya <priya@acme.io>", "to": ["arjun@nimbuslabs.test"], "thread": "thread_e2e",
        "subject": "Revised contract", "body": E2E_BODY, "labels": ["INBOX"],
        "read": {"gate": "keep", "relevance": "business", "extraction": {
            "intent": "commit", "stance": "positive",
            "entity_mentions": [{"surface_form": "Acme", "entity_type": "organization",
                                 "quote": "Acme", "confidence_bp": 8800}],
            "decision_states": [{"subject": "revised contract", "state": "pending",
                                 "blocked_on": "our side",
                                 "quote": "send the revised contract by Friday",
                                 "confidence_bp": 8000}],
            "dependencies": [{"blocker": "us", "blocked": "Acme", "dependency_type": "approval",
                              "quote": "Budget is approved", "confidence_bp": 7900}]}}}],
    "expected": {"cards": [{"about": ["Acme", "Priya"], "min": 1, "max": 1}]},
    "forbidden": {"names": [], "phrases": []}, "witness": None, "not_expressible": {},
}


def _parse(raw: dict) -> fc.FounderCase:
    return fc.parse_case(copy.deepcopy(raw), source="test.json")


def _record(case: fc.FounderCase):
    recorder = CassetteRecorder(IdealReader(case))
    return recorder, er.run_case(case, recorder)


def _comparable(run: fc.CaseRun):
    """A report with the ids a landing mints at random taken out — what two runs must share.

    A card is compared line by line, unordered: two identical runs give the same card with its WHY
    lines in a different order (the evidence the reasoning binds is not ordered by content —
    03-FINDINGS F38). What it says is the same; the order it says it in is the engine's to fix."""
    return (
        tuple((x.object_id, x.source_object_id, x.outcome, x.reason, x.sweep) for x in run.landed),
        dict(run.memory),
        tuple(sorted((s.situation_type, s.domain, s.status, s.anchor) for s in run.situations)),
        tuple(sorted((c.state, c.level, tuple(sorted(c.text.splitlines())), c.sweeps)
                     for c in run.cards)),
        run.funnel, run.chain_ok, tuple(sorted(run.model_calls)))


# =================================================================================================
# 1 · the runner refuses to be pointed anywhere but a scratch database
# =================================================================================================
def test_it_refuses_without_a_scratch_database(monkeypatch):
    monkeypatch.delenv(er.SCRATCH_ENV, raising=False)
    with pytest.raises(er.RunnerRefused, match=er.SCRATCH_ENV):
        er.pin_scratch_database()


def test_it_refuses_a_production_host(monkeypatch):
    monkeypatch.setenv(er.SCRATCH_ENV, "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres")
    with pytest.raises(er.RunnerRefused, match="production"):
        er.pin_scratch_database()


# =================================================================================================
# 2 · every door gets the recorded model, and the real transport is refused
# =================================================================================================
def test_every_door_is_handed_the_recorded_model_and_restored():
    from genios_engine.api import routes
    from genios_engine.context.llm.client import LLMClient
    from genios_engine.platform import wiring
    from genios_engine.platform.config import get_settings
    from genios_engine.reason import llm_decision_maker, llm_sites
    from tests.replays.model_sites import DOORS

    recorded = RecordedLLM({})
    before = (routes._llm, wiring.make_llm_client, llm_decision_maker.client,
              get_settings().anthropic_api_key)
    with er.production_switches(recorded):
        opened = {
            "routes._llm": routes._llm,
            "wiring.make_llm_client": wiring.make_llm_client(),
            "wiring.make_relevance_classifier": wiring.make_relevance_classifier("org")._llm,
            "llm_decision_maker.client": llm_decision_maker.client(),
            "llm_sites.make_site_client": llm_sites.make_site_client("haiku"),
        }
        assert set(opened) == set(DOORS), "a door in model_sites.DOORS the runner does not open"
        assert all(v is recorded for v in opened.values()), opened
        assert routes.make_relevance_classifier("org")._llm is recorded
        assert llm_decision_maker.enabled_for("any-org"), "production runs the LLM decider"
        with pytest.raises(er.UnrecordedModelCall, match="relevance"):
            LLMClient(api_key="k", model="m").call(
                "You are classifying messages for a company's business-intelligence system.")
        import anthropic
        with pytest.raises(er.UnrecordedModelCall):
            anthropic.Anthropic(api_key="k")
    after = (routes._llm, wiring.make_llm_client, llm_decision_maker.client,
             get_settings().anthropic_api_key)
    assert after == before, "a door was left open after the run"


def test_a_run_starts_with_every_model_cache_cold():
    """A second run of one case in one process must not be served the first run's answers."""
    import ast
    import importlib
    from pathlib import Path

    reason = Path(__file__).resolve().parents[2] / "genios_engine" / "reason"
    caches = set()
    for path in reason.rglob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            targets = (node.targets if isinstance(node, ast.Assign) else
                       [node.target] if isinstance(node, ast.AnnAssign) else [])
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "_cache":
                    module = "genios_engine." + ".".join(
                        path.relative_to(reason.parent).with_suffix("").parts)
                    caches.add((module, "_cache"))
    assert caches <= set(er.COLD_CACHES), (
        f"in-process model caches the runner does not empty: {sorted(caches - set(er.COLD_CACHES))}")
    for module, attribute in er.COLD_CACHES:
        getattr(importlib.import_module(module), attribute)["sentinel"] = 1
    er.cold_start()
    for module, attribute in er.COLD_CACHES:
        assert not getattr(importlib.import_module(module), attribute), (module, attribute)


# =================================================================================================
# 3 · the real chain, recorded and replayed
# =================================================================================================
@pytest.mark.pg
@needs_db
def test_a_case_is_driven_through_the_production_door_and_replays_exactly():
    case = _parse(CASE)
    recorder, recorded_run = _record(case)
    assert recorder.cassette, "the chain asked the model nothing — the door is not the production one"
    replay = RecordedLLM(recorder.cassette)
    replayed_run = er.run_case(case, replay)
    assert replay.misses == [] and replayed_run.misses == ()
    assert _comparable(replayed_run) == _comparable(recorded_run), (
        "the replay differs from the run it replays")

    assert [x.event_id for x in replayed_run.landed] == [x.event_id for x in recorded_run.landed], (
        "the pinned world mints the same ids on every run of a case")
    run = replayed_run
    outcomes = {(x.object_id, x.source_object_id.endswith("::att1")): x for x in run.landed}
    assert outcomes[("ask", False)].outcome == "emitted"
    # STEP-03: the gate ARCHIVES the digest — kept, read by no model — where it used to drop it, and
    # still names the rule that stopped it.
    assert outcomes[("digest", False)].outcome == "archived" and outcomes[("digest", False)].reason
    stub = outcomes[("ask", True)]
    assert stub.outcome == "parked" and stub.reason == "DOC-05", (
        "a refused attachment lands as the fetch_failed stub production gets")
    assert outcomes[("nudge", False)].sweep == 1
    assert run.memory["call"] > 0, "a calendar event is memory through the structured lane"
    assert run.chain_ok == (True, True)
    assert len(run.funnel) == 2 and all("situations_formed" in f for f in run.funnel)
    assert {s.situation_type for s in run.situations}, "no situation read back"
    sites = {site for site, _key in run.model_calls}
    assert {"junk_gate_batch", "relevance", "extraction"} <= sites, sites


def test_the_world_is_pinned_for_a_run_and_released_after():
    from genios_engine.capture.acquire import sync_runner
    from genios_engine.context import runner as l2_runner
    from genios_engine.platform.ids import new_id

    before = (sync_runner._CAPTURE_WORKERS, l2_runner._MAX_WORKERS)
    with er.pinned_world("golden:F97"):
        first = [new_id("evt"), new_id("node")]
        assert (sync_runner._CAPTURE_WORKERS, l2_runner._MAX_WORKERS) == (1, 1)
    with er.pinned_world("golden:F97"):
        again = [new_id("evt"), new_id("node")]
    with er.pinned_world("golden:F98"):
        other = [new_id("evt"), new_id("node")]
    assert first == again, "one case mints one sequence of ids"
    assert set(first).isdisjoint(other), "two cases never mint the same id"
    assert all(len(i.split("_", 1)[1]) == 24 for i in first), "the id keeps new_id's shape"
    assert (sync_runner._CAPTURE_WORKERS, l2_runner._MAX_WORKERS) == before
    assert new_id("evt") not in first, "outside a run, ids are random again"


@pytest.mark.pg
@needs_db
def test_a_run_leaves_the_shared_database_as_it_found_it():
    """The scratch database is shared by the whole suite, and some tests read a table whole: a
    golden tenant left switched on after its run turned up in another test's list of activations
    (found by QA, 2026-10-06 — 42 golden tenants in `test_l1_pilot_activation`). A run removes its
    tenant; `keep=True` is for a reader who wants to look at what the run left."""
    from sqlalchemy import text

    from genios_engine.api import routes

    case = _parse(CASE)
    er.run_case(case, CassetteRecorder(IdealReader(case)))
    with routes._graph.engine.connect() as c:
        left = {table: c.execute(text(f"select count(*) from {table} where org_id = :o"),
                                 {"o": "org_golden_f97"}).scalar()
                for table in ("l1_semantic_activation", "l2_v2_activation", "l3_activation",
                              "l4_activation", "source_events", "cards")}
        org = c.execute(text("select count(*) from orgs where id = 'org_golden_f97'")).scalar()
    assert org == 0 and not any(left.values()), (org, left)
    assert "org_golden_f97" not in routes._LIVE_ORGS


@pytest.mark.pg
@needs_db
def test_a_cassette_miss_fails_the_case_loudly():
    from sqlalchemy import text

    from genios_engine.api import routes
    with pytest.raises(CassetteMiss):
        er.run_case(_parse(CASE), RecordedLLM({}))
    with routes._graph.engine.connect() as c:
        assert c.execute(text("select count(*) from orgs where id = 'org_golden_f97'")).scalar() == 0, (
            "a run that raised left its tenant behind")


@pytest.mark.pg
@needs_db
def test_the_card_reader_reads_what_the_founder_sees(pg_store):
    """No founder case may yet produce a card, so the reader is held to a row written here."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text
    org = "org_golden_reader"
    at = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'reader') "
                       "on conflict do nothing"), {"o": org})
        c.execute(text("delete from cards where org_id = :o"), {"o": org})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, why, actions, artifact, state, expires_at, business_subject) "
            "values ('card_r1', 'sig_r1', :o, 'prescriptive', 'high', 'Reply to Kavya', "
            "'Kavya asked for the deck', 80, cast(:why as jsonb), cast(:act as jsonb), "
            "cast(:art as jsonb), 'queued', :exp, 'Lotus Ventures')"),
            {"o": org, "why": '["partners meet Monday"]', "act": '[{"label": "Send the deck"}]',
             "art": '{"kind": "draft_reply", "body": "Hi Kavya, the deck is attached."}',
             "exp": at + timedelta(days=3)})
    try:
        (card,) = er._cards(pg_store.engine, org, [{"card_id_absent"}, {"card_r1"}])
        assert card.card_id == "card_r1" and card.sweeps == (1,)
        for said in ("Reply to Kavya", "asked for the deck", "partners meet Monday",
                     "Send the deck", "the deck is attached", "Lotus Ventures"):
            assert said in card.text, said
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from cards where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


# =================================================================================================
# 4 · the negative control
# =================================================================================================
@pytest.mark.pg
@needs_db
def test_the_e2e_mail_yields_no_card_at_the_production_floor():
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.capture.esqe.qualification import DEFAULT_FLOOR_BP, PostgresFloorStore

    case = _parse(E2E)
    run = er.run_case(case, CassetteRecorder(IdealReader(case)), keep=True)
    try:
        _the_floor_was_productions(run, routes, text, DEFAULT_FLOOR_BP, PostgresFloorStore)
    finally:
        er.remove_tenant(routes._graph.engine, run.org_id)


def _the_floor_was_productions(run, routes, text, DEFAULT_FLOOR_BP, PostgresFloorStore):
    assert isinstance(routes._floor_store, PostgresFloorStore), "the runner swapped the floor"
    assert routes._floor_store.get(run.org_id) is None, (
        f"the tenant has a floor row; production's untuned tenant reads {DEFAULT_FLOOR_BP}")
    with routes._graph.engine.connect() as c:
        floors = set(c.execute(text("select floor_bp from qualification_drops where org_id = :o"),
                               {"o": run.org_id}).scalars())
    assert floors == {DEFAULT_FLOOR_BP}, (
        f"the e2e mail's signals are dropped at the production floor, so the floor is read: {floors}")
    assert run.chain_ok == (True,)
    assert run.cards == (), (
        "the e2e mail now yields a card at the production floor — the engine moved; record it "
        "on the golden board, then point this control at a mail that is junk by design")
