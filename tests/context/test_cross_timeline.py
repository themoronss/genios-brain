"""L2.3.4 · BLG-06 — the cross-timeline (dormant condition) suite.

Doc 03's acceptance, in one sentence: *a conditional commitment from four months ago, whose
predicate the current graph now satisfies, emits `condition_satisfied` carrying BOTH evidence
spans; an unparseable condition never auto-fires.* Both halves are asserted here, and most of the
rest of the file is the second half — the refusals, because this is the surface where a wrong
answer costs the most. A rhetorical aside ("let's revisit once things settle down") turned into a
firing predicate is a nudge about a throwaway line, and doc 03 names it as the first failure mode.

`eval_time` is the frozen instant from `tests/context/conftest.py`. Nothing in this file reads a
clock, because nothing in the module does.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, DecisionState, EntityMention
from genios_engine.context.correlation_timeline import (FIELD_DORMANT, FIELD_REVIEW,
                                                        FIELD_SATISFIED, FULL_STRENGTH_DAYS,
                                                        HALF_LIFE_DAYS, STALE_STRENGTH_BP,
                                                        VERSION_PREFIX, ClaimRecord,
                                                        ConditionWorld, PredicateKind,
                                                        SatisfiedCondition, Verdict, WorldFact,
                                                        build_world, conditions_from,
                                                        correlate_timeline,
                                                        default_condition_vocabulary, evaluate,
                                                        parse_condition, satisfy,
                                                        store_condition, strength_bp)

_STATEMENT = "Happy to revisit once you have two enterprise references."
_FACT = "Signed Northwind today — that's our second enterprise reference."


def span(text: str, ref: str) -> EvidenceSpan:
    return EvidenceSpan(source_ref=ref, quote=text, start_offset=0, end_offset=len(text),
                        verified=True)


def commitment(*, condition: str | None, actor: str = "Priya", action: str = "revisit the deal",
               beneficiary: str | None = "rohit@antler.co",
               quote: str = _STATEMENT) -> Commitment:
    """A promise L1 could really have published — built through the contract, so a commitment
    this suite asserts on is one L1's publishing seam would have accepted."""
    return Commitment(actor=actor, action=action, beneficiary=beneficiary,
                      is_conditional=condition is not None, condition_text=condition,
                      evidence=[span(quote, "prepared_content:evt_may")], confidence_bp=7000)


def world(*facts: WorldFact) -> ConditionWorld:
    return ConditionWorld(facts={fact.key: fact for fact in facts})


def enterprise_reference_count(*, value: int, observed_at: datetime,
                               evidence: bool = True) -> WorldFact:
    return WorldFact(key="count:organization:account.segment=enterprise", value=value,
                     evidence=(span(_FACT, "prepared_content:evt_august"),) if evidence else (),
                     observed_at=observed_at)


# =================================================================================================
# STEP 2 — WHAT PARSES, AND WHAT DELIBERATELY DOES NOT
# =================================================================================================

@pytest.mark.parametrize("text,kind,key,threshold", [
    ("once you have two enterprise references", PredicateKind.COUNT,
     "count:organization:account.segment=enterprise", 2),
    ("when we have 3 customers", PredicateKind.COUNT, "count:organization", 3),
    ("at least two paying customers", PredicateKind.COUNT,
     "count:organization:account.status=paying", 2),
    ("after we have 4 case studies", PredicateKind.COUNT, "count:document", 4),
    ("after funding closes", PredicateKind.EVENT, "event:funding_closed", 1),
    ("once legal confirms", PredicateKind.EVENT, "event:legal_confirmed", 1),
])
def test_the_conditions_a_rule_can_settle_are_settled_by_rule(text, kind, key, threshold) -> None:
    """Doc 03: deterministic patterns cover dates and simple counts. These are the ones a rule
    can settle, so no model is consulted about any of them."""
    predicate = parse_condition(text)
    assert predicate is not None, text
    assert predicate.kind is kind
    assert predicate.world_key == key
    assert predicate.threshold == threshold
    assert predicate.source_phrase == text


@pytest.mark.parametrize("text", [
    "once things settle down",
    "when the time is right",
    "after we've had a chance to think about it",
    "if it makes sense for both sides",
    "once you have two flurbles",              # a noun the vocabulary does not declare
    "once you have two strategic references",  # a qualifier the vocabulary does not declare
    "",
])
def test_an_unparseable_condition_is_refused_rather_than_approximated(text: str) -> None:
    """The review queue, not a guess. A parser that reached for the nearest plausible reading
    would eventually fire on every rhetorical aside in a founder's inbox, and the second false
    nudge is the last one anybody reads."""
    assert parse_condition(text) is None


def test_a_date_is_read_as_a_date_and_not_as_a_count_of_months() -> None:
    """"after March 1" contains a number and a noun. Tried as a date first, or it parses as a
    count of one march — which would then be satisfied by nothing, for ever, silently."""
    stated = datetime(2025, 12, 1, tzinfo=timezone.utc)
    predicate = parse_condition("after March 1", stated_at=stated)
    assert predicate is not None and predicate.kind is PredicateKind.INSTANT
    assert predicate.instant == datetime(2026, 3, 1, tzinfo=timezone.utc)


def test_a_bare_date_resolves_against_the_statement_not_against_a_running_clock() -> None:
    """The same sentence must parse to the same instant on every replay. Resolving "March 1"
    against `now()` gives a sweep replayed next year a different predicate for one sentence."""
    early = parse_condition("revisit after March 1", stated_at=datetime(2026, 1, 5,
                                                                       tzinfo=timezone.utc))
    late = parse_condition("revisit after March 1", stated_at=datetime(2026, 6, 5,
                                                                       tzinfo=timezone.utc))
    assert early.instant == datetime(2026, 3, 1, tzinfo=timezone.utc)
    assert late.instant == datetime(2027, 3, 1, tzinfo=timezone.utc)


def test_the_vocabulary_can_be_extended_without_touching_the_parser() -> None:
    """A tenant whose pack knows what a "reference" is says so in a value, not in a code change.
    Everything outside the declaration stays unparseable, which is what keeps the guess out."""
    vocab = default_condition_vocabulary().with_terms(
        qualifiers={"strategic": ("account.tier", "strategic")})
    assert parse_condition("once you have two strategic references") is None
    widened = parse_condition("once you have two strategic references", vocabulary=vocab)
    assert widened.world_key == "count:organization:account.tier=strategic"


# =================================================================================================
# STEP 1 — WHAT BECOMES A DORMANT CONDITION
# =================================================================================================

def test_an_unconditional_promise_is_not_a_dormant_condition() -> None:
    """It is a deadline, and it belongs to the commitment tracker. Parking it here would take a
    real due date out of the surface that chases it."""
    assert store_condition(commitment(condition=None), subject_node_id="node_p",
                           stated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)) is None


def test_a_promise_with_no_resolved_subject_is_not_stored() -> None:
    """A finding with nobody to show it to. The alternative — inventing a subject — is the same
    false-identity failure the dependency traversal refuses."""
    assert store_condition(commitment(condition="once funding closes"), subject_node_id="  ",
                           stated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)) is None


def test_the_same_promise_restated_is_one_dormant_condition(eval_time) -> None:
    """Content-addressed, not event-keyed: three emails repeating one promise would otherwise park
    three copies and satisfy all three, four months later, indistinguishably."""
    records = [
        ClaimRecord(event_id="evt_1", occurred_at=eval_time - timedelta(days=120),
                    commitments=(commitment(
                        condition="once you have two enterprise references"),)),
        ClaimRecord(event_id="evt_2", occurred_at=eval_time - timedelta(days=90),
                    commitments=(commitment(
                        condition="once you have two enterprise references"),)),
    ]
    conditions = conditions_from(records, lambda name: "node_partner")
    assert len(conditions) == 1
    assert conditions[0].stated_at == eval_time - timedelta(days=120), "the May sentence is kept"


def test_the_condition_is_filed_against_who_the_promise_is_owed_to(eval_time) -> None:
    """Beneficiary first: a promise is about the party waiting for it. Filing it under the actor
    would put the partner's card on our own person."""
    records = [ClaimRecord(event_id="evt_1", occurred_at=eval_time - timedelta(days=100),
                           commitments=(commitment(condition="after funding closes",
                                                   beneficiary="partner@fund.com"),))]
    conditions = conditions_from(
        records, lambda name: {"partner@fund.com": "node_partner"}.get(name))
    assert [c.subject_node_id for c in conditions] == ["node_partner"]


# =================================================================================================
# STEP 3 — THE FOUR ANSWERS, AND THE ONE THAT IS USUALLY GOT WRONG
# =================================================================================================

def _condition(text: str, *, eval_time, days_ago: int = 120):
    return store_condition(commitment(condition=text), subject_node_id="node_partner",
                           stated_at=eval_time - timedelta(days=days_ago))


def test_a_condition_the_world_now_meets_is_satisfied(eval_time) -> None:
    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    verdict = evaluate(condition, world(enterprise_reference_count(
        value=2, observed_at=eval_time - timedelta(days=11))), eval_time=eval_time)
    assert verdict.verdict is Verdict.SATISFIED
    assert verdict.satisfying.value == 2


def test_a_world_that_counted_and_came_up_short_answers_not_yet(eval_time) -> None:
    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    verdict = evaluate(condition, world(enterprise_reference_count(
        value=1, observed_at=eval_time - timedelta(days=11))), eval_time=eval_time)
    assert verdict.verdict is Verdict.NOT_YET


def test_a_world_that_cannot_see_the_subject_answers_unknown_not_not_yet(eval_time) -> None:
    """THE DISTINCTION THIS COMPONENT TURNS ON. "We counted and there is one" and "we cannot count
    this at all" both read as "not satisfied" and license completely different things — the second
    one is a statement about our plumbing wearing the typography of a statement about the
    customer, which is the false negative inference `contracts/quality` exists to prevent."""
    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    assert evaluate(condition, ConditionWorld(), eval_time=eval_time).verdict is Verdict.UNKNOWN


def test_an_unparseable_condition_never_auto_fires_whatever_the_world_says(eval_time) -> None:
    """Doc 03's acceptance row, and the mitigation for a rhetorical condition being matched."""
    condition = _condition("once things settle down", eval_time=eval_time)
    assert condition.review_required is True
    verdict = evaluate(condition, world(enterprise_reference_count(
        value=9, observed_at=eval_time)), eval_time=eval_time)
    assert verdict.verdict is Verdict.REVIEW_ONLY
    assert satisfy(condition, world(enterprise_reference_count(value=9, observed_at=eval_time)),
                   eval_time=eval_time) is None


def test_a_world_fact_with_no_receipt_cannot_satisfy_anything(eval_time) -> None:
    """The world says so and cannot show why. One span is the unconvincing half of the card, and a
    card nobody believes spends the trust the next one needs."""
    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    verdict = evaluate(condition, world(enterprise_reference_count(
        value=5, observed_at=eval_time, evidence=False)), eval_time=eval_time)
    assert verdict.verdict is Verdict.UNKNOWN


def test_an_instant_condition_is_satisfied_by_the_calendar(eval_time) -> None:
    condition = _condition("after 2026-01-15", eval_time=eval_time)
    assert evaluate(condition, ConditionWorld(), eval_time=eval_time).verdict is Verdict.SATISFIED
    earlier = eval_time - timedelta(days=60)
    assert evaluate(condition, ConditionWorld(), eval_time=earlier).verdict is Verdict.NOT_YET


# =================================================================================================
# STEP 4 — BOTH SPANS, OR NOTHING
# =================================================================================================

def test_a_satisfaction_carries_the_sentence_from_may_and_the_fact_from_august(eval_time) -> None:
    """Doc 03's headline acceptance. The card must show both; either alone is unconvincing."""
    condition = _condition("once you have two enterprise references", eval_time=eval_time,
                           days_ago=120)
    found = satisfy(condition, world(enterprise_reference_count(
        value=2, observed_at=eval_time - timedelta(days=11))), eval_time=eval_time)
    assert found is not None
    assert found.condition.statement_evidence[0].quote == _STATEMENT
    assert found.satisfying.evidence[0].quote == _FACT
    assert (found.condition.statement_evidence[0].source_ref
            != found.satisfying.evidence[0].source_ref)


def test_a_satisfaction_missing_the_satisfying_span_cannot_be_constructed(eval_time) -> None:
    """Enforced in the constructor, not in a renderer: a satisfaction carrying one span would be
    rendered by every consumer as though it carried both."""
    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    with pytest.raises(ValueError, match="SATISFYING"):
        SatisfiedCondition(condition=condition,
                           satisfying=enterprise_reference_count(value=2, observed_at=eval_time,
                                                                 evidence=False),
                           satisfied_at=eval_time, strength_bp=10_000)


def test_a_satisfaction_missing_the_original_statement_cannot_be_constructed(eval_time) -> None:
    from dataclasses import replace

    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    naked = replace(condition, statement_evidence=())
    with pytest.raises(ValueError, match="ORIGINAL"):
        SatisfiedCondition(condition=naked,
                           satisfying=enterprise_reference_count(value=2, observed_at=eval_time),
                           satisfied_at=eval_time, strength_bp=10_000)


# =================================================================================================
# STEP 5 — THE HALF-LIFE
# =================================================================================================

@pytest.mark.parametrize("days,expected", [
    (0, 10_000),
    (FULL_STRENGTH_DAYS, 10_000),
    (FULL_STRENGTH_DAYS + HALF_LIFE_DAYS, 5_000),
    (FULL_STRENGTH_DAYS + 2 * HALF_LIFE_DAYS, 2_500),
    (FULL_STRENGTH_DAYS + 3 * HALF_LIFE_DAYS, 1_250),
])
def test_a_satisfaction_decays_on_the_stated_schedule(days, expected, eval_time) -> None:
    """Full strength for thirty days, then a halving every thirty. Integer basis points, so two
    replays of one sweep cannot disagree in the last digit and sort differently."""
    assert strength_bp(satisfied_at=eval_time - timedelta(days=days),
                       eval_time=eval_time) == expected


def test_the_decay_moves_every_day_rather_than_falling_off_a_monthly_cliff(eval_time) -> None:
    """A step function would rank two conditions satisfied a day apart a factor of two apart,
    which is an artefact of the arithmetic and not of the world."""
    a_day_in = strength_bp(satisfied_at=eval_time - timedelta(days=FULL_STRENGTH_DAYS + 1),
                           eval_time=eval_time)
    assert 5_000 < a_day_in < 10_000


def test_an_old_satisfaction_goes_stale_rather_than_lingering_at_a_small_number(eval_time) -> None:
    """Globe: act while the evidence is fresh. Below the floor it is zero, so nothing downstream
    has to invent its own idea of "too old"."""
    old = strength_bp(satisfied_at=eval_time - timedelta(days=400), eval_time=eval_time)
    assert old == 0
    condition = _condition("once you have two enterprise references", eval_time=eval_time,
                           days_ago=400)
    found = satisfy(condition, world(enterprise_reference_count(
        value=2, observed_at=eval_time - timedelta(days=400))), eval_time=eval_time)
    assert found.stale is True
    assert found.strength_bp < STALE_STRENGTH_BP


def test_a_satisfaction_dated_in_the_future_is_full_strength_not_negative(eval_time) -> None:
    """Clock skew between a source and a sweep is not a reason to discard a real fact."""
    assert strength_bp(satisfied_at=eval_time + timedelta(days=3), eval_time=eval_time) == 10_000


# =================================================================================================
# THE WORLD BUILDER — counted populations, dated and evidenced
# =================================================================================================

def _entity(surface: str, ref: str, entity_type: str = "organization") -> EntityMention:
    quote = f"{surface} signed today."
    return EntityMention(surface_form=surface, entity_type=entity_type,
                         evidence=[span(quote, ref)], confidence_bp=8000)


def test_a_count_is_of_distinct_parties_not_of_mentions(eval_time) -> None:
    """Ten emails naming one customer are one customer. Counting mentions would satisfy "two
    enterprise customers" out of a single thread."""
    records = [ClaimRecord(event_id=f"evt_{i}", occurred_at=eval_time - timedelta(days=30 - i),
                           entities=(_entity("Northwind", f"prepared_content:evt_{i}"),))
               for i in range(5)]
    built = build_world(records)
    assert built.get("count:organization").value == 1


def test_a_narrowed_count_is_published_only_where_the_caller_declared_the_narrowing(
        eval_time) -> None:
    """A qualifier nobody can answer for is not published at all, so the predicate answers
    UNKNOWN — never NOT_YET, because nobody counted."""
    records = [ClaimRecord(event_id="evt_1", occurred_at=eval_time - timedelta(days=20),
                           entities=(_entity("Northwind", "prepared_content:evt_1"),
                                     _entity("Summit Labs", "prepared_content:evt_1")))]
    bare = build_world(records)
    assert bare.get("count:organization:account.segment=enterprise") is None
    narrowed = build_world(records, qualifier_facts={
        "northwind": {"account.segment": "enterprise"},
        "summit labs": {"account.segment": "enterprise"}})
    assert narrowed.get("count:organization:account.segment=enterprise").value == 2


def test_a_count_is_dated_and_evidenced_by_the_member_that_completed_it(eval_time) -> None:
    """The newest member pushed the count over the line, so it is both the right receipt and the
    right origin for the half-life."""
    records = [
        ClaimRecord(event_id="evt_old", occurred_at=eval_time - timedelta(days=200),
                    entities=(_entity("Northwind", "prepared_content:evt_old"),)),
        ClaimRecord(event_id="evt_new", occurred_at=eval_time - timedelta(days=11),
                    entities=(_entity("Summit Labs", "prepared_content:evt_new"),)),
    ]
    counted = build_world(records).get("count:organization")
    assert counted.value == 2
    assert counted.observed_at == eval_time - timedelta(days=11)
    assert counted.evidence[0].source_ref == "prepared_content:evt_new"


def test_only_a_decision_that_was_actually_made_publishes_its_event(eval_time) -> None:
    """A pending decision is not an event that happened, and firing a condition on one would tell
    a partner the round closed while it is still open."""
    pending = DecisionState(subject="funding closes", state="pending",
                            evidence=[span("Still working on the round.",
                                           "prepared_content:evt_p")], confidence_bp=7000)
    made = DecisionState(subject="funding closes", state="made",
                         evidence=[span("The round closed this morning.",
                                        "prepared_content:evt_m")], confidence_bp=8000)
    assert build_world([ClaimRecord("evt_p", eval_time, decisions=(pending,))]).facts == {}
    built = build_world([ClaimRecord("evt_m", eval_time, decisions=(made,))])
    assert built.get("event:funding_closed").evidence[0].quote.startswith("The round closed")


def test_a_claim_with_no_receipt_never_reaches_the_world(eval_time) -> None:
    """It could not be shown on a card, so counting it would build a satisfaction that cites
    nothing."""
    record = ClaimRecord(event_id="evt_1", occurred_at=eval_time,
                         entities=(_entity("Northwind", "prepared_content:evt_1"),))
    stripped = ClaimRecord(event_id="evt_1", occurred_at=eval_time,
                           entities=tuple(e.model_copy(update={"evidence": []})
                                          for e in record.entities))
    assert build_world([stripped]).facts == {}


# =================================================================================================
# THE FOUR-MONTH CASE, END TO END — doc 03's acceptance in one test
# =================================================================================================

def test_a_condition_set_four_months_ago_fires_when_the_world_catches_up(eval_time) -> None:
    """The whole surface, in one pass: a partner's conditional promise in May, two enterprise
    references by August, one `condition_satisfied` carrying both spans and a fresh strength."""
    vocab = default_condition_vocabulary()
    records = [
        ClaimRecord(event_id="evt_may", occurred_at=eval_time - timedelta(days=120),
                    commitments=(commitment(condition="once you have two enterprise references",
                                            beneficiary="partner@fund.com"),)),
        ClaimRecord(event_id="evt_june", occurred_at=eval_time - timedelta(days=90),
                    entities=(_entity("Northwind", "prepared_content:evt_june"),)),
        ClaimRecord(event_id="evt_august", occurred_at=eval_time - timedelta(days=11),
                    entities=(_entity("Summit Labs", "prepared_content:evt_august"),)),
    ]
    conditions = conditions_from(records, lambda name: "node_partner", vocabulary=vocab)
    built = build_world(records, vocabulary=vocab, qualifier_facts={
        "northwind": {"account.segment": "enterprise"},
        "summit labs": {"account.segment": "enterprise"}})
    result = correlate_timeline(conditions, built, eval_time=eval_time)

    assert len(result.satisfied) == 1
    found = result.satisfied[0]
    assert found.condition.statement_evidence[0].source_ref == "prepared_content:evt_may"
    assert found.satisfying.evidence[0].source_ref == "prepared_content:evt_august"
    assert found.satisfied_at == eval_time - timedelta(days=11)
    assert found.strength_bp == 10_000 and found.stale is False
    assert result.fresh == result.satisfied


def test_the_same_pass_sorts_the_rest_into_waiting_unknown_and_review(eval_time) -> None:
    """Four answers, four buckets. The review bucket is a SURFACE — doc 03's third failure mode is
    unparseable conditions accumulating silently, and a queue nobody can see is that silence."""
    vocab = default_condition_vocabulary()
    records = [ClaimRecord(event_id="evt_1", occurred_at=eval_time - timedelta(days=100),
                           commitments=(
                               commitment(condition="once you have two enterprise references",
                                          action="revisit"),
                               commitment(condition="when we have 3 customers", action="expand"),
                               commitment(condition="once things settle down", action="chat")))]
    conditions = conditions_from(records, lambda name: "node_partner", vocabulary=vocab)
    built = world(WorldFact(key="count:organization", value=1,
                            evidence=(span(_FACT, "prepared_content:evt_x"),),
                            observed_at=eval_time - timedelta(days=5)))
    result = correlate_timeline(conditions, built, eval_time=eval_time)
    assert len(conditions) == 3
    assert [c.condition_text for c in result.waiting] == ["when we have 3 customers"]
    assert [c.condition_text for c in result.unknown] == [
        "once you have two enterprise references"]
    assert [c.condition_text for c in result.review] == ["once things settle down"]


def test_the_pass_is_replayable_at_one_instant(eval_time) -> None:
    """Same conditions, same world, same instant — byte-identical answers, which is what makes a
    re-run an overwrite rather than a second, disagreeing finding."""
    condition = _condition("once you have two enterprise references", eval_time=eval_time)
    built = world(enterprise_reference_count(value=2, observed_at=eval_time - timedelta(days=11)))
    first = correlate_timeline([condition], built, eval_time=eval_time)
    second = correlate_timeline([condition], built, eval_time=eval_time)
    assert first == second


def test_no_clock_and_no_model_are_reachable_from_this_module() -> None:
    """Doc 03's group gate greps `context/correlation*.py` for a model client — M-5 is specified
    for this component and is deliberately not built here, because the same doc forbids the import
    in this package. The clock check is the same rule stated for time."""
    from pathlib import Path

    from genios_engine.context import correlation_timeline

    source = Path(correlation_timeline.__file__).read_text()
    for forbidden in ("LLMClient", "anthropic", "datetime.now(", "utcnow("):
        assert forbidden not in source, forbidden
    assert "float(" not in source


# =================================================================================================
# THE WIRING
# =================================================================================================

def test_the_drain_calls_the_timeline_pass() -> None:
    import inspect

    from genios_engine.context.runner import process_pending

    source = inspect.getsource(process_pending)
    assert "refresh_dormant_conditions(" in source


@pytest.mark.pg
def test_the_drain_writes_a_satisfied_condition_for_a_real_orgs_claims(pg_store, org_id,
                                                                      eval_time):
    """THE WIRING TEST. Seed what L1 really files — the May promise and the August fact, four
    months apart, in `source_events` + `l1_extraction_results` — then run the REAL drain and read
    the graph back. Nothing here constructs the correlator.

    The narrowed "enterprise" count is deliberately NOT reachable from the drain's default
    caller (no source declares the segment), so the condition seeded here is the one the shipped
    vocabulary CAN answer — a bare customer count. The narrowed path is proven in the unit tests
    above, and asserting it here would be asserting a qualifier nothing in this build publishes.
    """
    from sqlalchemy import text

    from genios_engine.context.identity import register_node_identity
    from genios_engine.context.runner import process_pending

    node_id, email = "node_tl_partner", "partner@fund.example"
    with pg_store.engine.begin() as conn:
        _reset(conn, org_id, node_id)
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name, "
            "valid_from) values (:n, :o, 'person', :k, 'partner', now())"),
            {"n": node_id, "o": org_id, "k": email})
        register_node_identity(conn, org_id=org_id, node_id=node_id, node_type="person",
                               canonical_key=email, display_name="partner")
        _seed(conn, org_id, event="evt_tl_may", occurred_at=eval_time - timedelta(days=120),
              output={"commitments": [{
                  "actor": "Priya", "action": "revisit the round", "beneficiary": email,
                  "is_conditional": True, "condition_text": "once you have 2 customers",
                  "confidence_bp": 7000,
                  "evidence": [_span_json(_STATEMENT, "prepared_content:evt_tl_may")]}]})
        for n, name in enumerate(("Northwind", "Summit Labs")):
            _seed(conn, org_id, event=f"evt_tl_ref_{n}",
                  occurred_at=eval_time - timedelta(days=11 - n),
                  output={"entity_mentions": [{
                      "surface_form": name, "entity_type": "organization", "confidence_bp": 8000,
                      "evidence": [_span_json(f"{name} signed today.",
                                              f"prepared_content:evt_tl_ref_{n}")]}]})

    result = process_pending(org_id=org_id, store=pg_store, llm=None, crypto_key="k" * 32,
                             eval_time=eval_time)
    assert result["timeline_facts"] >= 1

    with pg_store.engine.connect() as conn:
        rows = dict(conn.execute(text(
            "select field, value from graph_facts where org_id = :o "
            "and left(fact_version_id, :n) = :p and valid_to is null"),
            {"o": org_id, "n": len(VERSION_PREFIX) + 1, "p": f"{VERSION_PREFIX}:"}).all())

    assert FIELD_SATISFIED in rows, rows.keys()
    satisfied = rows[FIELD_SATISFIED]["satisfied"][0]
    assert satisfied["condition_text"] == "once you have 2 customers"
    assert satisfied["statement"][0]["source_ref"] == "prepared_content:evt_tl_may"
    assert satisfied["satisfied_by"][0]["source_ref"] == "prepared_content:evt_tl_ref_1"
    assert satisfied["strength_bp"] == 10_000
    assert FIELD_DORMANT not in rows and FIELD_REVIEW not in rows


@pytest.mark.pg
def test_an_unparseable_condition_reaches_the_review_queue_and_not_a_card(pg_store, org_id,
                                                                         eval_time):
    """The other half of doc 03's acceptance, through the real drain: stored, visible to a human,
    and never rendered as a satisfaction."""
    from sqlalchemy import text

    from genios_engine.context.identity import register_node_identity
    from genios_engine.context.runner import process_pending

    node_id, email = "node_tl_review", "review@fund.example"
    with pg_store.engine.begin() as conn:
        _reset(conn, org_id, node_id)
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name, "
            "valid_from) values (:n, :o, 'person', :k, 'reviewer', now())"),
            {"n": node_id, "o": org_id, "k": email})
        register_node_identity(conn, org_id=org_id, node_id=node_id, node_type="person",
                               canonical_key=email, display_name="reviewer")
        _seed(conn, org_id, event="evt_tl_vague", occurred_at=eval_time - timedelta(days=60),
              output={"commitments": [{
                  "actor": "Priya", "action": "circle back", "beneficiary": email,
                  "is_conditional": True, "condition_text": "once things settle down",
                  "confidence_bp": 7000,
                  "evidence": [_span_json("Let's circle back once things settle down.",
                                          "prepared_content:evt_tl_vague")]}]})

    process_pending(org_id=org_id, store=pg_store, llm=None, crypto_key="k" * 32,
                    eval_time=eval_time)

    with pg_store.engine.connect() as conn:
        rows = dict(conn.execute(text(
            "select field, value from graph_facts where org_id = :o "
            "and left(fact_version_id, :n) = :p and valid_to is null and subject_node_id = :s"),
            {"o": org_id, "n": len(VERSION_PREFIX) + 1, "p": f"{VERSION_PREFIX}:", "s": node_id}
        ).all())
    assert FIELD_REVIEW in rows
    assert rows[FIELD_REVIEW]["review"][0]["predicate"] is None
    assert FIELD_SATISFIED not in rows


def _span_json(quote: str, ref: str) -> dict:
    return {"source_ref": ref, "quote": quote, "start_offset": 0, "end_offset": len(quote),
            "verified": True}


def _reset(conn, org_id: str, node_id: str) -> None:
    from sqlalchemy import text

    conn.execute(text("delete from l1_extraction_results where org_id=:o and event_id like "
                      "'evt_tl_%'"), {"o": org_id})
    conn.execute(text("delete from source_events where org_id=:o and event_id like 'evt_tl_%'"),
                 {"o": org_id})
    conn.execute(text("delete from graph_facts where org_id=:o and left(fact_version_id, :n)=:p"),
                 {"o": org_id, "n": len(VERSION_PREFIX) + 1, "p": f"{VERSION_PREFIX}:"})
    conn.execute(text("delete from graph_aliases where org_id=:o and node_id=:n"),
                 {"o": org_id, "n": node_id})
    conn.execute(text("delete from graph_nodes where org_id=:o and node_id=:n"),
                 {"o": org_id, "n": node_id})


def _seed(conn, org_id: str, *, event: str, occurred_at, output: dict) -> None:
    import json

    from sqlalchemy import text

    conn.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at) values "
        "(:e, :o, 'conn_tl', 'gmail', 'email_message', :e, :e, '{}'::jsonb, :at)"),
        {"e": event, "o": org_id, "at": occurred_at})
    conn.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output) "
        "values (:k, :o, :e, cast(:out as jsonb))"),
        {"k": f"pk_{event}", "o": org_id, "e": event, "out": json.dumps(output)})
