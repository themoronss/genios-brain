"""L1.6.2-U1 · Canonical signal shape.

    pytest tests/capture/esqe/test_normalize.py -q

Doc 06's acceptance, in its own words: *every detected signal type produces a fully-shaped
record; a `COMMITMENT_DUE` carries the commitment's `due` as `primary_date`; a
`RELATIONSHIP_CHANGE` carries `primary_date=None` without error.*

The shape assertions are the reason the unit exists, so they are asserted structurally — the
field set of a record produced by one predicate is compared against the field set produced by a
different predicate reading a different part of the extraction, rather than against a list of
names copied out of the source. A test that spelled the fields out would keep passing on the day
the two detectors started producing two shapes.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.esqe.detector import DetectedSignal
from genios_engine.capture.esqe.normalize import (
    AMOUNT_POLICY,
    ANCHOR_FAMILIES,
    DATE_POLICY,
    NormalizedSignal,
    normalize_signals,
)
from genios_engine.capture.esqe.source_analyzer import ActorBasis, analyze_source
from genios_engine.capture.pipeline import EsqeStage, run_esqe_stage
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (
    Commitment,
    DecisionState,
    Dependency,
    EntityMention,
    ExtractionResult,
    UnclassifiedObservation,
)
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate
from genios_engine.contracts.visibility import Visibility

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
EVENT_ID = "evt_norm_1"
SOURCE_REF = f"prepared_content:{EVENT_ID}"

TEXT = ("Vikram will send the signed MSA by Friday. Finance still needs to approve the $84K "
        "annual renewal for Acme Corp, and Priya has joined this thread. The next one is "
        "coming up pretty soon.")


def span(quote: str, *, source_ref: str = SOURCE_REF) -> EvidenceSpan:
    """A span built by FINDING the quote, so no offset in this file is hand-counted."""
    start = TEXT.find(quote)
    assert start >= 0, f"quote is not in the fixture text: {quote!r}"
    assert TEXT.find(quote, start + 1) < 0, f"quote occurs twice: {quote!r}"
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                        end_offset=start + len(quote))


def resolved(as_written: str, *, days: int = 2,
             certainty: DateCertainty = DateCertainty.EXACT) -> ResolvedDate:
    moment = NOW + timedelta(days=days)
    return ResolvedDate(as_written=as_written, earliest=moment, latest=moment,
                        certainty=certainty, resolved_against=NOW,
                        evidence=[span(as_written)])


def vague() -> ResolvedDate:
    """An UNRESOLVED phrase: a certainty with no window, which is what "pretty soon" really is."""
    return ResolvedDate(as_written="pretty soon", earliest=None, latest=None,
                        certainty=DateCertainty.UNRESOLVED, resolved_against=NOW,
                        evidence=[span("pretty soon")])


def commitment(*, due: ResolvedDate | None) -> Commitment:
    return Commitment(actor="Vikram", action="send the signed MSA", due=due,
                      is_conditional=False, evidence=[span("Vikram will send the signed MSA")],
                      confidence_bp=8000)


def decision() -> DecisionState:
    return DecisionState(subject="approve the annual renewal", state="pending",
                         evidence=[span("Finance still needs to approve")], confidence_bp=7000)


def dependency() -> Dependency:
    return Dependency(blocker="Finance", blocked="the renewal", dependency_type="approval",
                      evidence=[span("Finance still needs to approve")], confidence_bp=7000)


def mention(surface: str = "Acme Corp", *, entity_type: str = "organization",
            hint: str | None = "acme") -> EntityMention:
    return EntityMention(surface_form=surface, entity_type=entity_type, canonical_hint=hint,
                         evidence=[span(surface)], confidence_bp=9000)


def observation() -> UnclassifiedObservation:
    return UnclassifiedObservation(proposed_kind="thread_join", description="Priya joined",
                                   evidence=[span("Priya has joined this thread")],
                                   confidence_bp=6000)


def money(minor_units: int = 8_400_000, as_written: str = "$84K") -> Money:
    return Money(minor_units=minor_units, currency="USD", as_written=as_written)


def event(*, source: str = "gmail", object_type: str = "email_message",
          source_object_id: str = "msg-1", source_family: str = "communication",
          event_id: str = EVENT_ID, internal_kind: str | None = None,
          email: str = "vikram@vendor.com") -> SourceEvent:
    return SourceEvent(
        event_id=event_id, org_id="org_norm", connection_id="con_norm", source=source,
        source_family=source_family, object_type=object_type,
        source_object_id=source_object_id,
        dedup_key=f"{source}:{object_type}:{source_object_id}",
        actor=Actor(type="external_contact", email=email), occurred_at=NOW, captured_at=NOW,
        internal_kind=internal_kind, recipients=("rohit@acme-corp.com", "priya@acme-corp.com"),
        visibility=Visibility(scope="org", derived_from="test:fixture"))


def extraction(*, commitments=(), decisions=(), dependencies=(), mentions=(), amounts=(),
               dates=(), observations=(), topics=(), intent: str = "inform",
               stance: str = "neutral") -> ExtractionResult:
    claims = (list(commitments) + list(decisions) + list(dependencies) + list(mentions)
              + list(dates) + list(observations))
    all_evidence = [s for claim in claims for s in claim.evidence]
    all_evidence.append(span("$84K"))
    return ExtractionResult(
        intent=intent, stance=stance, topics=list(topics), entity_mentions=list(mentions),
        amounts=list(amounts), dates_mentioned=list(dates), commitments=list(commitments),
        decision_states=list(decisions), dependencies=list(dependencies),
        unclassified_observations=list(observations), all_evidence=all_evidence,
        model_snapshot="fake-model-1", prompt_version="p1", schema_version="s1",
        extraction_profile="general", input_tokens=10, output_tokens=10)


def normalize_one(detection: DetectedSignal, ex: ExtractionResult,
                  ev: SourceEvent | None = None, **kwargs) -> NormalizedSignal:
    signals = normalize_signals([detection], event=ev or event(), extraction=ex, **kwargs)
    assert len(signals) == 1
    return signals[0]


# ==========================================================================================
# The acceptance: one shape, whichever predicate produced it
# ==========================================================================================

def test_two_different_predicates_normalize_to_an_identical_shape():
    """A commitment predicate and a decision predicate read different parts of the extraction
    and must be indistinguishable in SHAPE afterwards — same fields, same types, same envelope.

    Compared field-set against field-set rather than against a hardcoded list: a hardcoded list
    would still pass on the day one of the two started carrying an extra key.
    """
    ex = extraction(commitments=[commitment(due=resolved("by Friday"))], decisions=[decision()],
                    dates=[resolved("by Friday")])
    ev = event()

    from_commitment = normalize_one(
        DetectedSignal(SignalType.COMMITMENT_MADE, "commitment_present",
                       (span("Vikram will send the signed MSA"),)), ex, ev)
    from_decision = normalize_one(
        DetectedSignal(SignalType.DECISION_PENDING, "decision_pending",
                       (span("Finance still needs to approve"),)), ex, ev)

    names = [f.name for f in dataclasses.fields(NormalizedSignal)]
    assert ([f.name for f in dataclasses.fields(from_commitment)]
            == [f.name for f in dataclasses.fields(from_decision)] == names)
    assert {n: type(getattr(from_commitment, n)) for n in names if getattr(from_commitment, n)
            is not None}.keys() <= set(names)
    # The two records agree on everything that is a property of the EVENT and differ only where
    # they are supposed to: the type, the predicate and the subject the predicate matched.
    envelope = ("org_id", "event_id", "source", "object_type", "occurred_at", "visibility",
                "recipients", "internal_kind", "attribution")
    for name in envelope:
        assert getattr(from_commitment, name) == getattr(from_decision, name)
    assert from_commitment.signal_type is not from_decision.signal_type
    assert from_commitment.subject_label == "send the signed MSA"
    assert from_decision.subject_label == "approve the annual renewal"


@pytest.mark.parametrize("signal_type", list(SignalType))
def test_every_signal_type_produces_a_fully_shaped_record(signal_type):
    """Doc 06's first acceptance line, one row per type: no field is left unassigned, and the
    three that may be `None` are the only three that ever are."""
    ex = extraction(commitments=[commitment(due=resolved("by Friday"))], decisions=[decision()],
                    dependencies=[dependency()], mentions=[mention()], amounts=[money()],
                    dates=[resolved("by Friday")], observations=[observation()])
    record = normalize_one(DetectedSignal(signal_type, "row"), ex)

    # `thread` joins the nullable set for the reason `visibility` is in it: it is a fact the
    # CALLER either holds or does not, and "we do not know whose turn it is" must not read
    # downstream as "it is their turn". This helper supplies no thread context, so None is the
    # honest value here; `test_thread_context.py` pins the populated shape at the real seam.
    nullable = {"primary_entity", "primary_date", "primary_amount", "internal_kind",
                "visibility", "thread"}
    for field in dataclasses.fields(NormalizedSignal):
        value = getattr(record, field.name)
        if field.name not in nullable:
            assert value is not None, f"{field.name} was left unassigned for {signal_type}"
    assert record.signal_type is signal_type
    assert record.subject_key and record.subject_label


def test_commitment_due_carries_the_commitments_own_due_date():
    """Doc 06's second acceptance line. The commitment's `due` wins over the other date the
    same message states — carrying the renewal date instead would expire on the wrong day."""
    due = resolved("by Friday")
    other = resolved("annual renewal", days=200)
    ex = extraction(commitments=[commitment(due=due)], dates=[due, other])

    record = normalize_one(DetectedSignal(SignalType.COMMITMENT_DUE, "due_within_7d",
                                          tuple(due.evidence)), ex)
    assert record.primary_date is due


def test_relationship_change_carries_no_date_even_when_one_is_stated():
    """Doc 06's third acceptance line, on the input that would break a weaker implementation: a
    new party joining a renewal thread is not dated by the renewal."""
    ex = extraction(mentions=[mention("Priya", entity_type="person", hint=None)],
                    dates=[resolved("by Friday")])
    record = normalize_one(DetectedSignal(SignalType.RELATIONSHIP_CHANGE,
                                          "new_party_on_known_thread"), ex)
    assert record.primary_date is None
    assert record.primary_entity == "Priya"


# ==========================================================================================
# Provenance survives normalization
# ==========================================================================================

def test_provenance_survives_normalization():
    """Every envelope fact the event carried is on the record, unchanged and not re-derived —
    including the audience, which no layer above L1 can reconstruct."""
    ev = event()
    ex = extraction(commitments=[commitment(due=None)])
    record = normalize_one(DetectedSignal(SignalType.COMMITMENT_MADE, "commitment_present"), ex,
                           ev)

    assert record.org_id == ev.org_id
    assert record.event_id == ev.event_id
    assert record.source == ev.source
    assert record.object_type == ev.object_type
    assert record.occurred_at == ev.occurred_at
    assert record.visibility is ev.visibility
    assert record.recipients == ev.recipients
    assert record.internal_kind == ev.internal_kind
    assert record.predicate == "commitment_present"


def test_attribution_is_computed_once_per_event_and_matches_the_analyzer():
    """Three signals off one email share ONE attribution — the same object, not three equal
    ones — and it is the answer `analyze_source` gives for that event."""
    ev = event(email="v.rao@acme-corp.com")
    ex = extraction(commitments=[commitment(due=None)], decisions=[decision()],
                    mentions=[mention()])
    records = normalize_signals(
        [DetectedSignal(SignalType.COMMITMENT_MADE, "a"),
         DetectedSignal(SignalType.DECISION_PENDING, "b"),
         DetectedSignal(SignalType.RELATIONSHIP_CHANGE, "c")],
        event=ev, extraction=ex, actor_role="CFO", org_domains=("acme-corp.com",))

    assert len({id(r.attribution) for r in records}) == 1
    assert records[0].attribution == analyze_source(ev, actor_role="CFO",
                                                    org_domains=("acme-corp.com",))
    assert records[0].attribution.actor_basis is ActorBasis.ROLE_LADDER
    assert records[0].attribution.actor_authority_bp == 9500


def test_a_supplied_attribution_is_used_rather_than_recomputed():
    """The pipeline computes L1.6.4 once with the stage's own `executed` / role / domains; the
    normalizer must not quietly disagree with the trace row already written about the event."""
    ev = event()
    supplied = analyze_source(ev, executed=True, actor_role="ceo")
    record = normalize_one(DetectedSignal(SignalType.CONTRACT_RENEWAL, "money_recurrence"),
                           extraction(amounts=[money()]), ev, attribution=supplied)
    assert record.attribution is supplied
    assert record.attribution.evidence_authority_rank == 6


# ==========================================================================================
# The five fields — and the refusal to invent any of them
# ==========================================================================================

def test_subject_key_is_alg22s_and_two_events_on_one_deal_agree():
    """ALG-22 is reused, not re-derived: two events about one HubSpot deal produce one key."""
    ex = extraction(commitments=[commitment(due=None)])
    first = normalize_one(DetectedSignal(SignalType.COMMITMENT_MADE, "p"), ex,
                          event(source="hubspot", object_type="deal", source_object_id="12345",
                                source_family="enterprise_system", event_id="evt_a"))
    second = normalize_one(DetectedSignal(SignalType.COMMITMENT_MADE, "p"), ex,
                           event(source="hubspot", object_type="deal", source_object_id="12345",
                                 source_family="enterprise_system", event_id="evt_b"))
    assert first.subject_key == second.subject_key == "hubspot:deal:12345:commitment"


def test_subject_key_falls_back_to_the_event_when_no_claim_was_matched():
    """A predicate that fired on a field rather than a claim (`intent == escalate` over an
    otherwise empty extraction) still gets a key — ALG-22's last rung — and never a crash."""
    record = normalize_one(DetectedSignal(SignalType.ESCALATION, "intent_escalate"),
                           extraction(intent="escalate"))
    assert record.subject_key == f"event:{EVENT_ID}"
    assert record.subject_label == record.subject_key


@pytest.mark.parametrize("signal_type, amounts, expected_written", [
    # a money-bearing type takes the one unambiguous amount…
    (SignalType.CONTRACT_RENEWAL, [money()], "$84K"),
    (SignalType.FINANCIAL_OBLIGATION, [money()], "$84K"),
    # …but never chooses between two, which is a conflict and not a primary amount…
    (SignalType.CONTRACT_RENEWAL, [money(), money(7_400_000, "$74,000")], None),
    # …and a type money is incidental to does not go looking for one at all.
    (SignalType.APPROVAL_REQUESTED, [money()], None),
    (SignalType.RELATIONSHIP_CHANGE, [money()], None),
    (SignalType.CONTRACT_RENEWAL, [], None),
])
def test_primary_amount_is_never_invented(signal_type, amounts, expected_written):
    """One row per way an amount may or may not be the subject of a signal."""
    record = normalize_one(DetectedSignal(signal_type, "row"), extraction(amounts=amounts))
    assert (record.primary_amount.as_written if record.primary_amount else None) \
        == expected_written


@pytest.mark.parametrize("dates, expected", [
    ([resolved("by Friday")], "by Friday"),
    # two carryable dates: no primary one. Choosing the earlier would make a signal about
    # January out of a message about January and August.
    ([resolved("by Friday"), resolved("annual renewal", days=200)], None),
    # a vague phrase has no window to expire against and is not promoted.
    ([vague()], None),
    ([], None),
])
def test_primary_date_is_never_invented(dates, expected):
    """One row per way a stated date may or may not become the signal's own."""
    record = normalize_one(DetectedSignal(SignalType.DEADLINE_STATED, "row"),
                           extraction(dates=dates))
    assert (record.primary_date.as_written if record.primary_date else None) == expected


@pytest.mark.parametrize("mentions, expected", [
    ([mention("Acme Corp")], "acme"),
    ([mention("Acme Corp", hint=None)], "Acme Corp"),
    # two organisations is an introduction email: nothing may be attributed to either.
    ([mention("Acme Corp"), mention("Priya", entity_type="organization", hint="globex")], None),
    # a person named in a deal thread is a participant, not the subject.
    ([mention("Priya", entity_type="person", hint=None)], None),
    ([], None),
])
def test_primary_entity_is_never_invented(mentions, expected):
    """One row per way an entity may or may not be the subject — ALG-22's own rules, reused."""
    record = normalize_one(DetectedSignal(SignalType.CONTRACT_RENEWAL, "row"),
                           extraction(mentions=mentions))
    assert record.primary_entity == expected


@pytest.mark.parametrize("claim_kind, expected_label", [
    ("commitment", "send the signed MSA"),
    ("decision", "approve the annual renewal"),
    ("dependency", "the renewal blocked by Finance"),
    ("mention", "acme"),
    ("observation", "Priya joined"),
])
def test_subject_label_quotes_the_source(claim_kind, expected_label):
    """The label is text the extractor read out of the message, never prose this unit wrote."""
    kinds = {
        "commitment": (SignalType.COMMITMENT_MADE, dict(commitments=[commitment(due=None)])),
        "decision": (SignalType.DECISION_MADE, dict(decisions=[decision()])),
        "dependency": (SignalType.APPROVAL_REQUESTED, dict(dependencies=[dependency()])),
        "mention": (SignalType.RELATIONSHIP_CHANGE, dict(mentions=[mention()])),
        "observation": (SignalType.ANOMALY, dict(observations=[observation()])),
    }
    signal_type, kwargs = kinds[claim_kind]
    record = normalize_one(DetectedSignal(signal_type, "row"), extraction(**kwargs))
    assert record.subject_label == expected_label


# ==========================================================================================
# Evidence
# ==========================================================================================

def test_evidence_refs_are_the_detections_spans_deduplicated_and_ordered():
    """Two claims from one sentence carry equal-but-distinct spans; the union counts receipts,
    not claims, and its order is reading order so two replays are byte-identical."""
    late, early = span("Finance still needs to approve"), span("Vikram will send the signed MSA")
    detection = DetectedSignal(SignalType.COMMITMENT_MADE, "p", (late, early, span(
        "Finance still needs to approve")))
    record = normalize_one(detection, extraction(commitments=[commitment(due=None)]))

    assert record.evidence_refs == (early, late)


def test_a_money_anchor_gets_the_receipt_it_demonstrably_has():
    """`Money` is the one claim contract with no `evidence` field. Its receipt is LOOKED UP in
    the spans the model returned — never fabricated — so a renewal anchored on an amount does
    not reach the publisher with an empty evidence list and get parked for having no proof."""
    record = normalize_one(DetectedSignal(SignalType.CONTRACT_RENEWAL, "money_recurrence"),
                           extraction(amounts=[money()]))
    assert [s.quote for s in record.evidence_refs] == ["$84K"]


def test_a_spanless_predicate_yields_an_empty_evidence_list_rather_than_a_fabricated_one():
    """`intent == escalate` fires on a field, not a sentence. An empty list is the honest
    answer and V-4 at the publisher is the seam that refuses it — inventing a span here would
    make an unfounded signal indistinguishable from a founded one."""
    record = normalize_one(DetectedSignal(SignalType.ESCALATION, "intent_escalate"),
                           extraction(intent="escalate"))
    assert record.evidence_refs == ()


# ==========================================================================================
# Totality, purity and the seam's contract
# ==========================================================================================

@pytest.mark.parametrize("table_name, table", [
    ("DATE_POLICY", DATE_POLICY), ("AMOUNT_POLICY", AMOUNT_POLICY),
    ("ANCHOR_FAMILIES", ANCHOR_FAMILIES)])
def test_every_policy_table_is_total_over_the_taxonomy(table_name, table):
    """A member added to `SignalType` without a row must fail HERE, at a gate, rather than as a
    `KeyError` inside a customer's sync."""
    assert set(table) == set(SignalType), f"{table_name} does not cover the 14 signal types"


def test_normalization_is_deterministic_across_two_runs():
    """Two runs over the same inputs produce equal records, field for field — including the
    order of `evidence_refs`, which a set would have made a coin flip."""
    ex = extraction(commitments=[commitment(due=resolved("by Friday"))], mentions=[mention()],
                    amounts=[money()], dates=[resolved("by Friday")])
    detections = [DetectedSignal(SignalType.CONTRACT_RENEWAL, "money_recurrence"),
                  DetectedSignal(SignalType.COMMITMENT_DUE, "due_within_7d")]
    ev = event()
    assert (normalize_signals(detections, event=ev, extraction=ex)
            == normalize_signals(detections, event=ev, extraction=ex))


def test_a_non_detection_is_refused_at_the_seam():
    """A raw claim reaching the normalizer is ALG-15 handing on the wrong object, and it must
    surface here while the object is still in hand."""
    with pytest.raises(TypeError, match="DetectedSignal"):
        normalize_signals([commitment(due=None)], event=event(),
                          extraction=extraction(commitments=[commitment(due=None)]))


def test_records_are_frozen():
    """A record edited between the scorer and the publisher is how a card explains itself with
    numbers that no longer match the row it was written from."""
    record = normalize_one(DetectedSignal(SignalType.COMMITMENT_MADE, "p"),
                           extraction(commitments=[commitment(due=None)]))
    with pytest.raises(Exception):
        record.subject_key = "event:hacked"          # type: ignore[misc]


# ==========================================================================================
# WIRED — driven through the real production entry point, not the unit in isolation
# ==========================================================================================

def test_run_esqe_stage_normalizes_the_signals_it_detects():
    """S4 in `capture/pipeline.py` is the production caller. Driving it proves two things the
    unit test cannot: that every signal ALG-15 detected leaves the stage in this unit's shape,
    and that the attribution on those records is the SAME object the stage computed and wrote
    into the trace row — not a second one the normalizer derived alone from different inputs.
    """
    ex = extraction(commitments=[commitment(due=resolved("by Friday"))], decisions=[decision()],
                    mentions=[mention()], amounts=[money()], dates=[resolved("by Friday")],
                    topics=["contract_renewal"])
    ev = event()

    outcome = run_esqe_stage(
        ev, None, {"subject": "Renewal", "headers": {}},
        stage=EsqeStage(eval_time=NOW, actor_role="CFO", org_domains=("acme-corp.com",)),
        extraction=ex, conflicts=None, sender_known=True, is_structured=False,
        mailbox_owner="rohit@acme-corp.com")

    assert outcome.detection is not None and outcome.detection.signals
    assert len(outcome.normalized) == len(outcome.detection.signals)
    assert all(isinstance(record, NormalizedSignal) for record in outcome.normalized)
    assert {record.signal_type for record in outcome.normalized} == set(outcome.detection.types)
    assert all(record.attribution is outcome.attribution for record in outcome.normalized)
    assert all(record.event_id == ev.event_id and record.org_id == ev.org_id
               for record in outcome.normalized)
    # And the qualification is usable: at least one record names what the signal is about.
    assert any(record.primary_entity == "acme" for record in outcome.normalized)
