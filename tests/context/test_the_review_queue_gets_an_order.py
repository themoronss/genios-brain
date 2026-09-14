"""The first declared angle, end to end — and the four ways it is forbidden to matter.

`condition_now_true` asks about the one queue the deterministic layer built BY REFUSING:
`parse_condition` returns None for anything it cannot match to a date, a count or a named event,
and files the sentence under `derived.timeline.condition_review` rather than guessing. That queue
arrived flat — twenty-four conditions on the pilot, in no order, with no way to tell which
mattered — and this angle orders it.

Ordering it is ALL it may do, and that is what most of this file tests. A card is built to the
last byte before a verdict is looked at; a refusal never reaches one; a tenant with no angle layer
at all gets exactly today's queue. The rule those three share is this branch's standing law — no
gate may refuse on absence, only on positive contrary evidence — and the place it is easiest to
break is a reader that has learned to expect a model.

The first test is the one that would have caught a real mistake. `sees` names five `graph_facts`
fields and `store._seen` fetches them with `subject_node_id = :s`: if any lived on a THREAD node
rather than the counterparty, the angle would not error — it would ask a model about blanks, every
sweep, and bill for it.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.angles.contract import fan_node_ref, fan_subject_ref
from genios_engine.context.angles.library import CONDITION_NOW_TRUE
from genios_engine.context.angles.store import evaluate_angle
from genios_engine.context.condition_situations import (MODEL_CONFIDENCE_FIELD,
                                                        MODEL_READING_FIELD, TRIAGE_ANGLE_ID,
                                                        gather_condition_queue_verdicts,
                                                        gather_conditions_in_review,
                                                        read_conditions_in_review)
from genios_engine.context.graph_store import GraphStore

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"
PERSON = "n_ankit"
OWNER = "mrrohitswerashi@gmail.com"

_SCHEMA = (
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table context_angle_verdicts (org_id text, angle_id text, angle_version text, "
    "subject_ref text, verdict text, confidence_bp integer, refused boolean, saw_hash text, "
    "model_run_id text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, angle_id, subject_ref))",
    "create table l2_model_runs (run_id text primary key, org_id text, site text, "
    "subject_ref text, prompt_version text, prompt_hash text, model_snapshot text, "
    "max_tokens integer, input_tokens integer, output_tokens integer, success boolean, "
    "error text, parsed_output text, raw_output text, response_hash text, latency_ms integer, "
    "called_at timestamp)",
    "create table llm_costs (org_id text, model text, purpose text, input_tokens integer, "
    "output_tokens integer, success boolean, error text, subject_ref text, created_at timestamp)",
)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for stmt in _SCHEMA:
            c.execute(text(stmt))
    s = object.__new__(GraphStore)
    s._engine = engine
    return s


def _condition(condition_id="cond_1", actor="Ankit", action="send the deck",
               quote="happy to send it once we have spoken again") -> dict:
    return {"actor": actor, "action": action, "predicate": None,
            "condition_text": "once we have spoken again", "condition_id": condition_id,
            "stated_at": (NOW - timedelta(days=40)).isoformat(),
            "statement": [{"quote": quote, "start_offset": 0, "end_offset": len(quote),
                           "verified": False, "source_ref": "prepared_content:pc_x"}]}


def _fact(store, field, value, node=PERSON):
    with store._engine.begin() as c:
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active',null)"),
                  {"o": ORG, "n": node, "f": field, "v": value})


def _queued(store, *conditions, node=PERSON):
    import json
    _fact(store, "derived.timeline.condition_review",
          json.dumps({"review": list(conditions or (_condition(),))}), node=node)


def _relationship(store, node=PERSON):
    """The four fields `sees` names beyond the gate — on the COUNTERPARTY node, which is where
    `derived.py` writes them and where `DormantCondition.subject_node_id` points."""
    _fact(store, "thread.last_inbound", "2026-08-01T00:00:00+00:00", node=node)
    _fact(store, "thread.last_outbound", "2026-07-02T00:00:00+00:00", node=node)
    _fact(store, "party.role", "founder", node=node)
    _fact(store, "relationship.nature", "investor", node=node)


def _asker(word="met", confidence=6_000, seen=None, by_id=None):
    def ask(angle, subject_ref, slice_):
        if seen is not None:
            seen.append((subject_ref, dict(slice_)))
        if by_id is not None:
            return (by_id[slice_["derived.timeline.condition_review"]["condition_id"]], confidence)
        return (word, confidence)
    return ask


def _cards(store, verdicts=None):
    with store._engine.begin() as c:
        queue = gather_conditions_in_review(c, ORG)
    return read_conditions_in_review(queue, NOW, OWNER, verdicts)


def _facts_of(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# ── the reachability property, which is the expensive one to get wrong ───────────────────────

def test_every_field_the_angle_declares_reaches_the_model(store) -> None:
    """THE MISTAKE THIS FORBIDS IS SILENT AND BILLABLE. `store._seen` fetches `sees` with
    `subject_node_id = :s`, so a field living on a different node comes back absent — no error,
    no warning, just a model reasoning about a counterparty from blanks on every sweep.

    `thread.last_inbound` looks like a THREAD fact and is not: `derived.py` writes it onto person
    nodes (`if row.subject_node_id in people`), and the condition's subject is "the resolved
    counterparty, never a raw name". The two meet, and this is what says so.
    """
    _queued(store)
    _relationship(store)
    seen: list = []
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW, asker=_asker(seen=seen))

    [(subject, slice_)] = seen
    # A FANNED REF, and the node half is what `_seen` must select on. `n_ankit#5cf2…` is not a
    # `subject_node_id`; selecting on it returns nothing, with no error — the four relationship
    # fields below would simply be blank on every sweep, and billed for.
    assert subject == fan_subject_ref(PERSON, "cond_1")
    assert fan_node_ref(subject) == PERSON
    assert set(slice_) == set(CONDITION_NOW_TRUE.sees)
    assert all(slice_[name] for name in CONDITION_NOW_TRUE.sees), slice_


def test_the_gate_value_is_reused_rather_than_read_twice(store) -> None:
    """`derived.timeline.condition_review` is in both `gate` and `sees`. The slice carries the
    sentences without a second read, which is why the queue's own text costs nothing to show."""
    _queued(store)
    _relationship(store)
    seen: list = []
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW, asker=_asker(seen=seen))
    item = seen[0][1]["derived.timeline.condition_review"]
    # ONE condition after the fan-out, not the list it came from.
    assert isinstance(item, dict) and "review" not in item
    assert "once we have spoken again" in str(item)


# ── the verdict reaches the card, and says what it actually knows ────────────────────────────

def test_a_verdict_orders_the_queue(store) -> None:
    _queued(store)
    _relationship(store)
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW,
                   asker=_asker("met", 6_000))
    with store._engine.begin() as c:
        verdicts = gather_condition_queue_verdicts(c, ORG)
    assert verdicts == {fan_subject_ref(PERSON, "cond_1"): ("met", 6_000)}

    [card] = _cards(store, verdicts)
    facts = _facts_of(card)
    assert facts[MODEL_READING_FIELD] == "met"
    assert facts[MODEL_CONFIDENCE_FIELD] == 6_000


def test_each_condition_gets_its_own_verdict(store) -> None:
    """THE CORRECTION THIS ANGLE SHIPPED WITHOUT. `correlation_timeline._fact_rows` writes ONE
    fact per node whose value is a LIST, so before `Angle.fan_out` existed the gate admitted one
    subject per counterparty and a four-way enum could not say WHICH of two sentences was met.
    The first cut answered for the whole queue under fields named `queue`, and a reader still had
    to open every card on the node to learn what the verdict meant.

    Now each condition is its own subject, and two sentences from one counterparty may disagree.
    """
    _queued(store, _condition("c1"), _condition("c2", action="introduce us"))
    _relationship(store)
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW,
                   asker=_asker(by_id={"c1": "met", "c2": "not_a_condition"}))
    with store._engine.begin() as c:
        verdicts = gather_condition_queue_verdicts(c, ORG)

    cards = _cards(store, verdicts)
    assert len(cards) == 2
    by_key = {card.canonical_key: _facts_of(card)[MODEL_READING_FIELD] for card in cards}
    assert by_key == {"condition:c1": "met", "condition:c2": "not_a_condition"}


def test_a_verdict_never_leaks_onto_a_sibling_condition(store) -> None:
    """The failure the fan-out removes: one counterparty, two sentences, and an opinion about the
    first quietly stamped on the second. A refusal on `c2` must leave `c2` unmarked rather than
    inheriting `c1`'s answer."""
    _queued(store, _condition("c1"), _condition("c2", action="introduce us"))
    _relationship(store)
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW,
                   asker=_asker(by_id={"c1": "met", "c2": "unknowable"}))
    with store._engine.begin() as c:
        verdicts = gather_condition_queue_verdicts(c, ORG)

    by_key = {card.canonical_key: _facts_of(card) for card in _cards(store, verdicts)}
    assert by_key["condition:c1"][MODEL_READING_FIELD] == "met"
    assert MODEL_READING_FIELD not in by_key["condition:c2"]


def test_the_reader_and_the_evaluator_name_a_condition_the_same_way(store) -> None:
    """Rebuilding the fanned ref by hand in the reader is the two-spellings failure this module
    records against its own field name: the join matches nothing, silently, and every card simply
    lacks a reading."""
    _queued(store, _condition("c1"))
    _relationship(store)
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        [ref] = list(gather_condition_queue_verdicts(c, ORG))
    assert ref == fan_subject_ref(PERSON, "c1")


# ── the three ways it is forbidden to matter ─────────────────────────────────────────────────

def test_a_card_is_byte_identical_without_the_angle(store) -> None:
    """THE STANDING LAW, AT THE PLACE IT IS EASIEST TO BREAK. A build with no angle layer, a sweep
    that made no calls, and a tenant nobody has budget for must all produce the queue that exists
    today — flat, which is worse than ordered and is still a queue somebody can work."""
    _queued(store)
    _relationship(store)
    before = [_facts_of(card) for card in _cards(store, None)]

    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        verdicts = gather_condition_queue_verdicts(c, ORG)
    after = [_facts_of(card) for card in _cards(store, verdicts)]

    assert len(before) == len(after) == 1
    assert all(before[0][k] == after[0][k] for k in before[0])
    assert set(after[0]) - set(before[0]) == {MODEL_READING_FIELD, MODEL_CONFIDENCE_FIELD}


def test_a_refusal_never_reaches_a_card(store) -> None:
    """`unknowable` is a fact about the ANGLE — it could not tell from a relationship slice — not
    about this counterparty. `AngleRun.refused` counts it, and that counter is where an angle
    whose refusals dominate becomes visible. A card would carry it to no purpose and order
    nothing."""
    _queued(store)
    _relationship(store)
    run = evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW,
                         asker=_asker("unknowable", 3_000))
    assert run.refused == 1

    with store._engine.begin() as c:
        assert gather_condition_queue_verdicts(c, ORG) == {}
    assert MODEL_READING_FIELD not in _facts_of(_cards(store, {})[0])


def test_the_predicate_stays_missing(store) -> None:
    """THE ANGLE MUST NOT DO WHAT THE PARSER REFUSED TO DO. `condition.predicate` is what would
    let a condition be EVALUATED rather than reported, and its absence is why every row is in this
    queue at all. A verdict is not a predicate — it carries no world key and cannot be re-checked
    next sweep — so the coverage score must keep saying "not evaluable" with a verdict present."""
    _queued(store)
    _relationship(store)
    evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW, asker=_asker())
    with store._engine.begin() as c:
        verdicts = gather_condition_queue_verdicts(c, ORG)

    [card] = _cards(store, verdicts)
    assert card.missing == ["condition.predicate"]
    assert "condition.predicate" not in _facts_of(card)


def test_a_database_without_the_verdict_table_leaves_the_queue_flat(store) -> None:
    """Migration 0165 is recent and a fixture builds only the tables its subject needs. A gather
    that can take a sweep down is the "may only ever ADD" rule broken where nobody looks."""
    _queued(store)
    with store._engine.begin() as c:
        c.execute(text("drop table context_angle_verdicts"))
        assert gather_condition_queue_verdicts(c, ORG) == {}


# ── the one-hop law, which this angle is the first thing able to violate ─────────────────────

def test_the_angle_cannot_read_its_own_verdict(store) -> None:
    """A MODEL RE-JUDGING A SUBJECT ON EVIDENCE IT PRODUCED is how one wrong reading stops being
    an opinion and becomes a trend. Enforced by construction rather than by a filter: the verdict
    lands in `context_angle_verdicts`, the slice is built from `graph_facts`, and the two never
    meet. The second sweep asks NOTHING — not because the answer was filtered out, but because
    the slice never moved."""
    _queued(store)
    _relationship(store)
    first = evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW, asker=_asker())
    assert first.asked == 1

    seen: list = []
    second = evaluate_angle(store, ORG, CONDITION_NOW_TRUE, eval_time=NOW,
                            asker=_asker(seen=seen))
    assert (second.asked, second.unchanged) == (0, 1)
    assert seen == []


def test_the_queue_reading_is_not_a_field_any_gate_or_slice_names(store) -> None:
    """The structural half of the law above, stated where a future edit would break it: neither
    field this unit introduced may ever appear in an angle's `gate` or `sees`. The day one does,
    a model is reading its own output out of `graph_facts` and no runtime test would notice."""
    from genios_engine.context.angles.contract import registered

    for angle in registered():
        assert MODEL_READING_FIELD not in angle.gate + angle.sees
        assert MODEL_CONFIDENCE_FIELD not in angle.gate + angle.sees
