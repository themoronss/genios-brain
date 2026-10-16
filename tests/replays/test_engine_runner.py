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
                     "useful move."}},
        # STEP-05: with every kept event in memory, the account's own situation now reaches the
        # decider — answered as every case answers it.
        {"when": ["account admin", "lotusvc.test"], "answer": {
            "outcome": "decision", "confidence_bp": 5000,
            "move": {"triage_to_five_outcomes": 6200},
            "rationale": "Someone at this company asked us something and the ball is in our "
                         "court."}}],
              # Written from the narrator's prompt alone: it knows the attendee and nothing open.
              "narrator": [{"when": ["admin_contact", "kavya@lotusvc.test"], "answer": {
                  "headline": "Meeting with kavya@lotusvc.test is clear",
                  "situation": "Nothing open is on record with kavya@lotusvc.test before the "
                               "meeting.",
                  "artifact": "Nothing is missing on record; confirm the agenda before the "
                              "meeting."}},
                  # STEP-05: the account's own card, written from its prompt alone — Kavya's
                  # question is the one quote it shows, with no date on it.
                  {"when": ["account_admin", "lotusvc.test"], "answer": {
                      "headline": "Send Kavya at lotusvc.test your latest deck",
                      "situation": "Kavya at lotusvc.test asked for your latest deck. The next "
                                   "move is ours; no date is on the request.",
                      "artifact": "Hi Kavya, sharing our latest deck as you asked."}}]},
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


def test_the_expert_is_switched_on_for_a_case_that_authors_its_answers():
    """STEP-12 (M32.C5.L-integration.V2.U04): every golden case whose sweeps review a file authors the
    expert's answers (`test_every_changed_file_has_an_expert_answer`) and runs with the expert on; a
    case built here to exercise the harness authors none and runs as before — or as the caller says."""
    import ast
    import inspect
    plain = _parse(CASE)
    authored = _parse(dict(CASE, model={"expert": [{"when": ["<f97.test>"], "by": "claude",
                                                    "answer": {}}]}))
    assert (er.expert_on(plain), er.expert_on(authored)) == (False, True)
    assert (er.expert_on(plain, True), er.expert_on(authored, False)) == (True, False)
    body = ast.parse(inspect.getsource(er.run_case))
    guarded = [n for n in ast.walk(body) if isinstance(n, ast.If)
               and "expert_on" in ast.unparse(n.test)
               and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "switch_on_the_expert"
                       for b in n.body for c in ast.walk(b))]
    assert len(guarded) == 1, "run_case switches the expert on under expert_on, once"


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
            {"o": org, "why": '["partners meet Monday", {"sentence": "headline", "source": "expert_check", '
                              '"evidence": ["evt_k"], "quotes": ["Introly connected us. Can you send the deck?"]}]',
             "act": '[{"label": "Send the deck"}]',
             "art": '{"kind": "draft_reply", "body": "Hi Kavya, the deck is attached."}',
             "exp": at + timedelta(days=3)})
    try:
        (card,) = er._cards(pg_store.engine, org, [{"card_id_absent"}, {"card_r1"}])
        assert card.card_id == "card_r1" and card.sweeps == (1,)
        for said in ("Reply to Kavya", "asked for the deck", "partners meet Monday",
                     "Send the deck", "the deck is attached", "Lotus Ventures"):
            assert said in card.text, said
        # STEP-04: who the card is about, apart from what it says — the marking judges it.
        assert card.subject == "Lotus Ventures"
        # STEP-13: an expert card's sentence sources are its evidence, read apart — a quote naming the
        # connector does not make the card about the connector (F37).
        assert "Introly" not in card.text
        assert [s["sentence"] for s in card.sources] == ["headline"]
        assert card.sources[0]["quotes"] == ["Introly connected us. Can you send the deck?"]
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from cards where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.mark.pg
@needs_db
def test_a_tenant_is_created_as_signup_creates_it_with_its_owner_seat_and_declarations(pg_store):
    """STEP-04 (`yc2_w27_s04/M22.C5.L-logic.V2.U02`, F54). Signup gives a tenant its owner seat
    (`platform/seats.ensure_owner_seat`) and the golden runner did not — so the sent-folder half of
    the W-01 whitelist never fired on the golden set while it does in production. And a case shaped
    like production declares the founder's other addresses and the company's domains, the way
    `scripts/declare_self_identity.py` does for the design partner."""
    from sqlalchemy import text

    from genios_engine.platform.self_identity import identity_for
    raw = copy.deepcopy(CASE)
    raw["founder"] = {**FOUNDER, "also": ["ceo@nimbuslabs.test"], "domains": ["nimbuslabs.test"]}
    case = _parse(raw)
    org = "org_golden_seat_probe"
    try:
        er._fresh_tenant(pg_store.engine, org, case)
        er._fresh_tenant(pg_store.engine, org, case)          # a re-run is a fresh tenant again
        with pg_store.engine.connect() as c:
            seats = c.execute(text("select seat_id, email, active from org_seats where org_id = :o"),
                              {"o": org}).fetchall()
            us = identity_for(c, org)
        assert [(r.seat_id, r.email, r.active) for r in seats] == [
            ("seat_owner", "arjun@nimbuslabs.test", True)]
        assert us.is_us("ceo@nimbuslabs.test") and us.is_us("anyone@nimbuslabs.test")
    finally:
        er.remove_tenant(pg_store.engine, org)
    with pg_store.engine.connect() as c:
        assert c.execute(text("select count(*) from org_self_identities where org_id = :o"),
                         {"o": org}).scalar() == 0


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


# =================================================================================================
# STEP-14 · the runner records what the APP showed, and every version's words (`yc2_w27_s14` M42.C4.L-integration.V1.U02)
# =================================================================================================
@pytest.mark.pg
def test_the_card_reader_says_when_the_app_showed_it_and_every_versions_words(pg_store):
    """s14-D4, s14-F2, s14-F14: a card counts once the APP showed it — the sweeps it was in the queue at the sweep's
    instant (`app_sweeps`), apart from the sweeps it merely existed (`sweeps`) — and a card rewritten in place is
    judged on every version's words, not its last (`versions`, from its `card.created` / `card.rebuilt` /
    `card.versioned` events)."""
    import json
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text
    org = "org_golden_versions"
    at = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    v1 = {"headline": "Reply to Kavya", "situation": "Kavya asked for the deck", "move": None, "draft": None,
          "lane": "decision", "mode": "act", "ask": None, "recipient": None, "by_when": None}
    v2 = {**v1, "headline": "Send Kavya the deck by Friday", "by_when": "2026-09-19",
          "move": "Send Kavya the deck by Friday and tell Ritika"}       # no card shows the move whole yet
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'versions') on conflict do nothing"), {"o": org})
        c.execute(text("delete from card_events where org_id = :o"), {"o": org})
        c.execute(text("delete from cards where org_id = :o"), {"o": org})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, why, "
            " actions, artifact, state, expires_at, version) values ('card_v', 'sig_v', :o, 'prescriptive', 'high', "
            " :h, :s, 80, '[]', '[]', '{}', 'queued', :exp, 2)"),
            {"o": org, "h": v2["headline"], "s": v2["situation"], "exp": at + timedelta(days=3)})
        for n, (kind, words) in enumerate((("card.created", v1), ("card.versioned", v2))):
            detail = {"version": n + 1, "words": words} if kind == "card.created" else {
                "version": 2, "words": words, "before": v1}
            c.execute(text("insert into card_events (id, card_id, org_id, kind, detail, occurred_at) values "
                           "(:i, 'card_v', :o, :k, cast(:d as jsonb), :at)"),
                      {"i": f"cev_v{n}", "o": org, "k": kind, "d": json.dumps(detail), "at": at + timedelta(hours=n)})
    try:
        (card,) = er._cards(pg_store.engine, org, [{"card_v"}, {"card_v"}], [set(), {"card_v"}])
        assert (card.sweeps, card.app_sweeps) == ((0, 1), (1,))
        assert card.versions == ("Reply to Kavya\nKavya asked for the deck",
                                 "Send Kavya the deck by Friday\nKavya asked for the deck")
        (unshown,) = er._cards(pg_store.engine, org, [{"card_v"}])
        assert unshown.app_sweeps == (), "nobody asked the app: nothing was shown"
        with pg_store.engine.begin() as c:     # a card created before its first words were kept…
            c.execute(text("update card_events set detail = '{}' where id = 'cev_v0'"))
        assert er._cards(pg_store.engine, org, [{"card_v"}])[0].versions == card.versions, \
            "…its first words are the ones its first version kept as before"
        with pg_store.engine.begin() as c:     # a card never versioned, refreshed in place once
            c.execute(text("delete from card_events where id = 'cev_v1'"))
            c.execute(text("update card_events set detail = cast(:d as jsonb) where id = 'cev_v0'"),
                      {"d": json.dumps({"version": 1, "words": v1})})
            c.execute(text("insert into card_events (id, card_id, org_id, kind, detail, occurred_at) values "
                           "('cev_r', 'card_v', :o, 'card.rebuilt', cast(:d as jsonb), :at)"),
                      {"o": org, "d": json.dumps({"words": {**v1, "headline": "Reply to Kavya today"}}),
                       "at": at + timedelta(hours=3)})
        assert er._cards(pg_store.engine, org, [{"card_v"}])[0].versions == (
            "Reply to Kavya\nKavya asked for the deck", "Reply to Kavya today\nKavya asked for the deck")
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from card_events where org_id = :o"), {"o": org})
            c.execute(text("delete from cards where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@needs_db
def test_a_run_asks_the_app_queue_at_each_sweeps_instant_and_leaves_no_impression(monkeypatch):
    from genios_engine.api import routes
    from genios_engine.deliver.store import CardStore
    asked: list = []
    original = CardStore.queue

    def _spy(self, org_id, **kw):
        asked.append((org_id, kw.get("admin"), kw.get("record_impressions"), kw.get("eval_time")))
        return original(self, org_id, **kw)
    monkeypatch.setattr(CardStore, "queue", _spy)
    case = _parse(CASE)
    _recorder, run = _record(case)
    assert [(a[1], a[2], a[3]) for a in asked if a[0] == run.org_id] == [
        (True, False, at) for at in case.sweeps], "once per sweep, the admin's whole queue, at its instant"
    assert all(set(c.app_sweeps) <= set(c.sweeps) for c in run.cards)
    assert routes._card_store is not None


# ── STEP-16 (`yc2_w27_s16` M47.C4.L-integration.V4.U02): your acts, through the real doors; how each card ended ────
def _acting_case(*acts) -> fc.FounderCase:
    raw = {"case_id": "F92", "title": "You call a card wrong between two sweeps", "kind": "must_detect",
           "label_row": 10, "labelled_by": "claude", "replays": [], "founder": FOUNDER,
           "sweeps": ["2026-09-18T12:00:00Z", "2026-09-19T12:00:00Z"],
           "objects": [{"id": "ask", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-18T09:30:00Z",
                        "from": "Kavya Menon <kavya@lotusvc.test>", "to": ["arjun@nimbuslabs.test"],
                        "thread": "t-lotus", "subject": "Deck?", "body": ASK, "labels": ["INBOX"]}],
           "expected": {"cards": [{"about": ["Kavya"], "min": 1, "max": 1}, {"about": ["metrics"], "min": 1, "max": 1}]},
           "forbidden": {}, "witness": None,
           "not_expressible": {}, "acts": list(acts)}
    return fc.parse_case(raw, source="test.json")


def _a_card(engine, org, *, card_id="card_k", state="queued", file_id="node_kavya"):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text
    at = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'acts') on conflict do nothing"), {"o": org})
        c.execute(text("insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, subject_node_id, "
                       "score, reason_code, eval_time, status) values (:s, :o, 'founder_office', '0.1.0', "
                       "'file_review', :f, 50, 'file_review', :at, 'open')"),
                  {"s": f"sig_{card_id}", "o": org, "f": file_id, "at": at})
        c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                       "score, expires_at, state, file_id) values (:c, :s, :o, 'prescriptive', 'high', "
                       "'Send Kavya the deck', 'Kavya asked for the deck', 80, :exp, :st, :f)"),
                  {"c": card_id, "s": f"sig_{card_id}", "o": org, "exp": at + timedelta(days=3), "st": state,
                   "f": file_id})
    return at


def _gone(engine, org):
    from sqlalchemy import text
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})


from tests.deliver.test_a_card_verdict_reaches_every_reader import decided  # noqa: E402,F401 — fixture
from tests.reason.expert.test_a_covered_file_decides_once import world  # noqa: E402,F401 — fixture
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: E402,F401 — fixture


@pytest.mark.pg
@needs_db
def test_an_act_is_played_through_the_dashboards_door_at_the_sweeps_instant(decided):
    """A decided file's card (the decision's own door built it), called wrong with your words by the runner: the
    verdict and the correction are the real door's, at the sweep's instant."""
    from tests.deliver.test_a_card_verdict_reaches_every_reader import AT
    from sqlalchemy import text
    store, org, anchor, card = decided
    case = _acting_case({"after_sweep": 0, "on": ["metrics"], "wrong": "not_relevant",
                         "words": "Arjun gets the numbers only after the partner meeting is booked.", "scope": "file"},
                        {"after_sweep": 1, "on": ["metrics"], "wrong": "bad_timing"})
    [played] = er.play_acts(store.engine, store, case, org, 0, AT)
    assert (played.index, played.card_id, played.ok) == (0, card.card_id, True), played
    with store.engine.connect() as c:
        kept = c.execute(text("select file_id, scope, corrected_at from founder_corrections where org_id = :o"),
                         {"o": org}).one()
        verdict = c.execute(text("select cause, reason, occurred_at from card_feedback_verdicts where org_id = :o"),
                            {"o": org}).one()
    assert (kept.file_id, kept.scope, kept.corrected_at) == (anchor, "file", AT)
    assert tuple(verdict) == ("wrong", "not_relevant", AT)
    again = er.play_acts(store.engine, store, case, org, 0, AT)[0]
    assert again.ok is False and again.said.startswith("no open card"), \
        "a card already acted on is no open card to play on: said, never silently skipped"


@pytest.mark.pg
@needs_db
def test_a_correction_act_is_kept_on_the_cards_file(pg_store):
    from sqlalchemy import text
    org = "org_golden_correct"
    _gone(pg_store.engine, org)
    at = _a_card(pg_store.engine, org)
    case = _acting_case({"after_sweep": 0, "on": ["Kavya"], "correct": "Kavya reads mail on Mondays only."})
    try:
        [played] = er.play_acts(pg_store.engine, pg_store, case, org, 0, at)
        assert played.ok and played.said.startswith("fc_")
        with pg_store.engine.connect() as c:
            assert c.execute(text("select file_id from founder_corrections where org_id = :o"),
                             {"o": org}).scalar() == "node_kavya"
            assert c.execute(text("select state from cards where card_id = 'card_k'")).scalar() == "queued", \
                "a correction alone leaves the card in front of you"
    finally:
        _gone(pg_store.engine, org)


@pytest.mark.pg
@needs_db
def test_the_card_reader_says_how_each_card_ended_and_by_which_object(pg_store):
    from genios_engine.platform import card_lifecycle as L
    org = "org_golden_ends"
    _gone(pg_store.engine, org)
    at = _a_card(pg_store.engine, org)
    _a_card(pg_store.engine, org, card_id="card_open", file_id="node_other")
    with pg_store.engine.begin() as c:
        L.resolve_cards(c, org_id=org, cause=L.VERIFIED, card_ids=["card_k"], at=at,
                        evidence={"event_id": "evt_signed", "loop_id": "loop_x", "basis": "answered"})
    landed = [fc.Landed(object_id="signed", source_object_id="m1", event_id="evt_signed", outcome="emitted",
                        reason=None, sweep=1)]
    try:
        cards = {c.card_id: c for c in er._cards(pg_store.engine, org, [{"card_k", "card_open"}], landed=landed)}
        assert (cards["card_k"].ended, cards["card_k"].ended_by) == ("verified", "signed")
        assert (cards["card_open"].ended, cards["card_open"].ended_by) == (None, None), "still open: no end"
    finally:
        _gone(pg_store.engine, org)
