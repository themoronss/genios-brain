"""The end of the chain the angle layer was built for.

`residue.py` measures what Layer 2 could not explain. `reply_owed_triage` asks a model which of
those matter. Both stopped there: the measurement had no reader and the verdict had no
destination, so the one shape the whole thing was built to surface — "they replied, we went quiet,
and nothing said so" — was recorded, judged, and shown to nobody.

TWO TESTS CARRY THIS FILE.

`test_the_card_does_not_cover_its_own_subject` is the one that would have shipped a bug. This card
links its counterparty with the same `concerns` hop every reading uses, and residue calls a
subject covered when a live situation concerns it. So without an exclusion: sweep one records the
residue and the card appears; sweep two sees the card, calls the subject explained, DELETES the
residue row; the verdict retires, the reading produces nothing, the card goes; sweep three finds
the subject unexplained again. A card appearing and vanishing on alternate sweeps for ever. The
fix is semantic — a card reporting that nothing explains a subject does not itself explain it.

`test_no_verdict_no_card` is the standing rule at the only place in this layer where a card's
EXISTENCE depends on a model. That is allowed — "a model may propose a situation" — precisely
because its absence removes nothing: the tenant returns to the cards they have today.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.attention_situations import (ACTIONABLE, ANCHOR_UNREPORTED,
                                                        MAX_PER_SWEEP, SITUATION_TYPE,
                                                        gather_unreported_attention,
                                                        read_unreported_attention)
from genios_engine.context.graph_store import GraphStore
from genios_engine.context.residue import RESIDUE_BALL_IN_COURT, detect_residue, read_residue

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"
PERSON = "n_theresa"

_SCHEMA = (
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table graph_observations (org_id text, observation_id text, subject_node_id text, "
    "status text, kind text)",
    "create table graph_nodes (org_id text, node_id text, canonical_key text, node_type text, "
    "display_name text, valid_to text)",
    "create table graph_edges (org_id text, edge_type text, from_node_id text, to_node_id text, "
    "valid_to text)",
    "create table context_situations (org_id text, situation_id text, correlation_id text, "
    "anchor_node_id text, status text, situation_type text)",
    "create table context_correlation_members (org_id text, correlation_id text, event_id text)",
    "create table graph_source_refs (org_id text, event_id text, fact_version_id text, "
    "observation_id text)",
    "create table qualified_signals (org_id text, event_id text, signal_type text)",
    "create table open_loops (org_id text, loop_id text, subject_node_id text, kind text, "
    "status text)",
    "create table context_residue (org_id text, residue_kind text, subject_ref text, "
    "detail text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, residue_kind, subject_ref))",
    "create table context_angle_verdicts (org_id text, angle_id text, angle_version text, "
    "subject_ref text, verdict text, confidence_bp integer, refused boolean, saw_hash text, "
    "model_run_id text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, angle_id, subject_ref))",
)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for stmt in _SCHEMA:
            c.execute(text(stmt))
        c.execute(text("insert into graph_nodes values (:o,:n,'p:theresa','person','Theresa',null)"),
                  {"o": ORG, "n": PERSON})
        c.execute(text("insert into graph_facts values (:o,:n,'thread.ball_in_court','us',"
                       "'active',null)"), {"o": ORG, "n": PERSON})
    s = object.__new__(GraphStore)
    s._engine = engine
    return s


def _verdict(store, word=ACTIONABLE, node=PERSON):
    with store._engine.begin() as c:
        c.execute(text("insert into context_angle_verdicts values "
                       "(:o,'reply_owed_triage','1.0.0',:s,:v,6000,0,'h',null,:t,:t)"),
                  {"o": ORG, "s": node, "v": word, "t": NOW})


def _cover(store, node=PERSON, situation_type="admin_contact", anchor="n_anchor"):
    """A real reading covering the subject — an anchor node plus the `concerns` hop."""
    with store._engine.begin() as c:
        c.execute(text("insert into context_situations values "
                       "(:o,'sit1','c1',:a,'active',:st)"),
                  {"o": ORG, "a": anchor, "st": situation_type})
        c.execute(text("insert into graph_edges values (:o,'concerns',:a,:n,null)"),
                  {"o": ORG, "a": anchor, "n": node})


def _cards(store, now=NOW):
    with store._engine.begin() as c:
        rows = gather_unreported_attention(c, ORG)
        names = {PERSON: "Theresa"}
        facts = {PERSON: {"thread.ball_in_court": "us"}}
    return read_unreported_attention(rows, now, names, facts)


def _facts_of(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# ── the chain, end to end ────────────────────────────────────────────────────────────────────

def test_the_coverage_miss_becomes_a_card(store) -> None:
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=11))
    _verdict(store)
    [card] = _cards(store)

    facts = _facts_of(card)
    assert card.anchor == ANCHOR_UNREPORTED
    assert card.concerns_node == PERSON
    assert facts["attention.counterparty"] == "Theresa"
    assert facts["attention.days_unexplained"] == 11
    assert facts["attention.reading"] == ACTIONABLE
    assert "11d" in card.display_name


def test_the_card_does_not_cover_its_own_subject(store) -> None:
    """THE BUG THIS WOULD OTHERWISE HAVE SHIPPED. The card links its counterparty with the same
    `concerns` hop every reading uses, and residue counts that as coverage. Left alone, the card
    explains its own subject, deletes the residue row it came from, and vanishes — then returns on
    the sweep after. `residue.SELF_REPORTED_TYPE` is excluded from the predicate because a card
    reporting that nothing explains a subject does not itself explain it.
    """
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=3))
    _verdict(store)
    assert len(_cards(store)) == 1

    # The card, persisted exactly as the dispatch would persist it.
    _cover(store, situation_type=SITUATION_TYPE, anchor="n_unreported_anchor")

    detect_residue(store, ORG, eval_time=NOW)
    with store._engine.begin() as c:
        still = read_residue(c, ORG, kind=RESIDUE_BALL_IN_COURT)
    assert len(still) == 1, "the card explained its own subject and deleted the residue row"
    assert len(_cards(store)) == 1, "the card would have vanished on the next sweep"


def test_a_real_reading_does_close_it(store) -> None:
    """THE OTHER HALF, and what keeps the exclusion from being a suppression. Any situation type
    but this one is coverage: when a deterministic reading finally speaks about the subject, the
    residue goes and the last-resort card goes with it."""
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=3))
    _verdict(store)
    assert len(_cards(store)) == 1

    _cover(store, situation_type="reply_owed", anchor="n_real_anchor")
    detect_residue(store, ORG, eval_time=NOW)
    with store._engine.begin() as c:
        assert read_residue(c, ORG, kind=RESIDUE_BALL_IN_COURT) == []
    assert _cards(store) == []


# ── the standing rule, at the one place a card depends on a model ────────────────────────────

def test_no_verdict_no_card(store) -> None:
    """A build with no angle layer, no budget, or a refusal produces exactly today's cards. The
    card is an addition; its absence removes nothing."""
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=5))
    assert _cards(store) == []


@pytest.mark.parametrize("word", ["developing", "ambient", "noise", "unknowable"])
def test_only_important_becomes_an_interruption(store, word: str) -> None:
    """The enum already separates "act" from "aware". Surfacing the rest would refill the queue
    this exists to shrink."""
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=5))
    _verdict(store, word=word)
    assert _cards(store) == []


def test_a_refused_verdict_never_reaches_the_reading(store) -> None:
    """`triaged_residue` filters refusals in SQL, so `unknowable` never crosses the seam at all."""
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=5))
    with store._engine.begin() as c:
        c.execute(text("insert into context_angle_verdicts values "
                       "(:o,'reply_owed_triage','1.0.0',:s,'important',6000,1,'h',null,:t,:t)"),
                  {"o": ORG, "s": PERSON, "t": NOW})
    assert _cards(store) == []


# ── what the card refuses to claim ───────────────────────────────────────────────────────────

def test_it_never_states_how_long_a_reply_has_been_owed(store) -> None:
    """That number belongs to `reply_owed`, which compares two recorded instants — and the facts
    that produce it are the ones whose absence put this subject here. Declared, not guessed."""
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=9))
    _verdict(store)
    [card] = _cards(store)

    assert card.missing == ["outreach.days_owed", "attention.reason_uncovered"]
    assert not any(name.startswith("outreach.") for name, _v, _k in card.facts)
    assert "owed" not in card.display_name


def test_the_elapsed_time_is_measured_and_not_the_models(store) -> None:
    """Every number here was measured before the model was asked. `first_seen_at` is never
    rewritten by the detector, which is what makes it a duration rather than an estimate."""
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=4))
    _verdict(store)
    # A later sweep must not restart the clock.
    detect_residue(store, ORG, eval_time=NOW - timedelta(days=1))
    assert _facts_of(_cards(store)[0])["attention.days_unexplained"] == 4


def test_one_sweep_cannot_turn_a_recovery_path_into_a_feed(store) -> None:
    rows = tuple({"subject_ref": f"n_{i}", "residue_kind": RESIDUE_BALL_IN_COURT,
                  "triage": ACTIONABLE, "first_seen_at": NOW - timedelta(days=5)}
                 for i in range(MAX_PER_SWEEP + 10))
    assert len(read_unreported_attention(rows, NOW)) == MAX_PER_SWEEP


# ── it is routable ───────────────────────────────────────────────────────────────────────────

def test_the_anchor_routes_and_is_dispatched() -> None:
    """A reading whose anchor no domain declares is silently skipped — and one no `READINGS` entry
    dispatches never runs at all."""
    from genios_engine.context.domain_spec import domains_declaring, spec_for
    from genios_engine.context.outreach_situations import READINGS

    assert domains_declaring(ANCHOR_UNREPORTED) == ("admin",)
    assert spec_for("admin").type_for(ANCHOR_UNREPORTED) == SITUATION_TYPE
    assert ANCHOR_UNREPORTED in {anchor for anchor, _ in READINGS}
