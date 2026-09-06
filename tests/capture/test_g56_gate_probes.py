"""G5 and G6, probed independently of the tests the building waves wrote.

    pytest tests/capture/test_g56_gate_probes.py -q

The sibling suites under `tests/capture/validate` and `tests/capture/esqe` were written by the
waves that built those units, and every one of them is green. That is exactly the state in which
this build has three times shipped a unit nothing called — `extract()`, the scheduler, the cost
governor — so these probes are deliberately NOT a second opinion about the units. They drive
`run_sync` and `capture_event`, the two functions the product actually enters L1 through, and
assert on what falls out of them.

What each section pins:

* **G5** — the \\$74K-signed vs \\$84K-email fixture, as the two SEPARATE events the Gmail
  connector emits (`email_message` + `email_attachment` linked by `parent_object_id`), reaching
  ALG-12 through a real sweep. Both claims retained, the resolution recorded and explained, and
  the two claims traced to two different events. Plus the negative that keeps the card
  trustworthy: a date RANGE containing a point is agreement, not a conflict.
* **G5 determinism** — subject keys, which are ALG-12's grouping half, are identical in a
  subprocess started under a different `PYTHONHASHSEED`.
* **G6** — doc 04's worked example, through `capture_event`, produces EXACTLY the three signal
  types doc 09 names, and every type it can ever emit is a member of the closed 14.
* **Zero-LLM** — the rules-only relevance path is proved with a client that RAISES, not one that
  counts, so a single call is a failure with a stack trace rather than an assertion at the end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.validate.conflict import (ConflictLane, ExtractionClaimGrouper,
                                                     render_conflict_card)
from genios_engine.contracts.conflict import ConflictResolution
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult)
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

OWNER = "founder@genios.ai"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

THREAD = "thread_9fa1"
MESSAGE = "msg_9fa1c2"
ATTACHMENT = "msg_9fa1c2::aws_agreement_signed.pdf"

MAIL_BODY = ("Following up on the AWS Enterprise Agreement with Northwind Ltd — the $84K "
             "annual contract is what we budgeted for.")
PDF_BODY = ("AWS ENTERPRISE AGREEMENT between Northwind Ltd and GeniOS. Total annual "
            "commitment of $74,000, payable on signature.")


# =============================================================================================
# harness — a mailbox that emits a message and its attachment as two events
# =============================================================================================
def _cite(text: str, quote: str) -> list[dict]:
    start = text.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


@dataclass
class _Result:
    parsed: dict
    raw: str
    input_tokens: int = 100
    output_tokens: int = 50
    model: str = "fake-model-1"
    cached: bool = False
    ok: bool = True
    error: str | None = None


class _AmountLLM:
    """Answers from the CONTENT it is shown. `run_sync` captures a page through a thread pool,
    so the mail and the PDF race and an order-keyed fixture would be flaky by construction."""

    model = "fake-model-1"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls.append(prompt)
        if "74,000" in prompt:
            text, minor, written = PDF_BODY, 7_400_000, "$74,000"
        else:
            text, minor, written = MAIL_BODY, 8_400_000, "$84K"
        payload = {
            "intent": "inform", "stance": "neutral",
            "entity_mentions": [{"surface_form": "Northwind Ltd",
                                 "entity_type": "organization",
                                 "evidence": _cite(text, "Northwind Ltd"),
                                 "confidence_bp": 9000}],
            "amounts": [{"minor_units": minor, "currency": "USD", "as_written": written}],
            "all_evidence": _cite(text, written),
        }
        return _Result(parsed=payload, raw=json.dumps(payload, sort_keys=True))


class _Mailbox:
    """One Gmail message → two RawObjects, exactly as `connectors/composio.py` emits them."""

    source = "gmail"

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        return [
            RawObject(source="gmail", object_type="email_message", source_object_id=MESSAGE,
                      parent_object_id=THREAD, occurred_at=NOW,
                      actor_email="buyer@northwind.com", recipients=(OWNER,),
                      raw={"subject": "AWS Enterprise Agreement", "body": MAIL_BODY}),
            RawObject(source="gmail", object_type="email_attachment",
                      source_object_id=ATTACHMENT, parent_object_id=MESSAGE,
                      occurred_at=NOW - timedelta(days=1),
                      actor_email="buyer@northwind.com", recipients=(OWNER,),
                      raw={"subject": "aws_agreement_signed.pdf", "body": PDF_BODY,
                           "has_attachment": True}),
        ]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def _sweep(llm=None):
    llm = llm or _AmountLLM()
    return run_sync(_Mailbox(), org_id="org_g56", connection_id="con_g56",
                    repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
                    semantic=P.SemanticLane(llm=llm, eval_time=NOW)), llm


# =============================================================================================
# G5 — the headline fixture, through the real sweep
# =============================================================================================
@pytest.mark.gate
def test_g5_the_two_amounts_meet_and_conflict_across_two_separate_events():
    """The gate fixture, and the WIRING claim underneath it: nothing in this test constructs a
    lane, a grouper or a detector. It runs a sync and reads the summary."""
    summary, _ = _sweep()

    assert summary.emitted == 2, "both the mail and its attachment must land as events"
    assert summary.conflicts is not None, (
        "ALG-12 never ran on the sweep — the conflict lane has no production caller")

    detected, = summary.conflicts.conflicts
    conflict = detected.conflict

    values = sorted(claim.value.minor_units for claim in conflict.claims)
    assert values == [7_400_000, 8_400_000], "BOTH competing claims must be retained"
    assert len({claim.evidence[0].quote for claim in conflict.claims}) == 2, (
        "each side keeps its own receipt, or the card cannot explain itself")
    assert len(detected.event_ids) == 2, (
        "one event contradicting itself is not the fixture — the claims must span two events")
    assert conflict.detected_at == NOW, "detected_at is the run's frozen instant, never a clock"


@pytest.mark.gate
def test_g5_the_resolution_is_recorded_and_the_reason_is_stated():
    """A resolution is a recommendation with its reasoning attached. Whatever ALG-12 decides,
    the card must render both sides and say why — or say that it will not say why."""
    summary, _ = _sweep()
    conflict = summary.conflicts.conflicts[0].conflict

    assert isinstance(conflict.resolution, ConflictResolution)
    card = render_conflict_card(conflict)
    assert len(card.lines) == 2, "a card showing one side cannot explain a disagreement"
    rendered = card.render()
    assert "$74,000" in rendered and "$84K" in rendered, (
        "both values must appear in the source's own words")
    if conflict.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY:
        assert card.verdict is not None, "an authority resolution must state whose authority"
    else:
        assert card.verdict is None, (
            "only authority settles a conflict; anything else must not print a verdict")


@pytest.mark.gate
def test_g5_an_executed_agreement_resolves_by_authority_to_74k():
    """The gate's stated outcome, with the one input production cannot yet supply.

    `Authority.SIGNED_DOCUMENT` is reached only through `Provenance.executed`, and no unit in L1
    determines whether a PDF is signed — so on live mail the pair weighs ATTACHMENT (3) against
    EMAIL_PROSE (2), a gap of one, which doc 05 resolves `unresolved_surface_both`. This drives
    the SAME production grouper and lane with `executed` supplied, so the resolution half of the
    gate is proved on the real units rather than on a fixture that hand-builds claims.
    """
    summary, _ = _sweep()
    events = {r.event.source_object_id: r for r in summary.results}
    lookup = {r.event.source_object_id: r.event for r in summary.results}.get
    prepared = {r.event.event_id: r.prepared for r in summary.results}
    group_key = {(c.event_id, c.ordinal): g.group_key
                 for g in summary.claim_groups for c in g.claims}

    lane = ConflictLane(
        grouper=ExtractionClaimGrouper(event_lookup=lookup,
                                       executed=frozenset({ATTACHMENT}),
                                       prepared_for=lambda e: prepared.get(e.event_id),
                                       group_key_for=group_key.get),
        detected_at=NOW)
    outcome = None
    for key in (MESSAGE, ATTACHMENT):
        outcome = lane.observe(events[key].event, events[key].extraction)

    detected, = outcome.conflicts
    assert detected.conflict.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY
    assert detected.conflict.resolved_value.minor_units == 7_400_000, "the signed PDF wins"
    assert len(detected.conflict.claims) == 2, "the loser is still on the record"
    assert render_conflict_card(detected.conflict).verdict is not None


@pytest.mark.gate
def test_g5_a_redelivered_sweep_does_not_make_a_message_contradict_itself():
    """Two sweeps of the same mailbox. Landing dedups within a sweep; this is the case it
    cannot catch, and a claim_id keyed on `event_id` would fabricate a conflict here."""
    llm = _AmountLLM()
    repo = InMemorySourceEventRepository()
    for _ in range(2):
        summary = run_sync(_Mailbox(), org_id="org_g56", connection_id="con_g56", repo=repo,
                           mailbox_owner=OWNER,
                           semantic=P.SemanticLane(llm=llm, eval_time=NOW))
    assert summary.duplicate == 2, "the second sweep re-landed the same two objects"
    assert summary.conflicts is None or summary.conflicts.conflicts == (), (
        "a re-delivered message is one source, not two sources disagreeing")


@pytest.mark.gate
@pytest.mark.parametrize("point, window_days, conflict_expected", [
    pytest.param(datetime(2026, 3, 12, tzinfo=timezone.utc), (10, 17), False,
                 id="point_inside_range_is_one_claim_written_twice"),
    pytest.param(datetime(2026, 3, 21, tzinfo=timezone.utc), (10, 17), True,
                 id="point_outside_range_is_a_real_disagreement"),
])
def test_g5_a_range_containing_a_point_is_not_a_conflict(point, window_days, conflict_expected):
    """Overlap, not equality. "Oct 10-17" and "Oct 15" are one deadline written two ways, and a
    detector that demanded equality would file a conflict card on every approximated date."""
    from genios_engine.capture.validate.conflict import NormalizedClaim, detect_conflicts
    from genios_engine.contracts.conflict import Authority

    # `verified=True` because this probe is about DATE OVERLAP, and a conflict is only asked
    # about claims whose receipts ALG-08 located (D3, `NormalizedClaim.is_admissible`). Left at
    # the constructor default — correct for an extractor's raw output — both claims would be
    # inadmissible and the probe would report "no conflict" for a reason it never tests.
    span = EvidenceSpan(source_ref="prepared_content:e1", quote="by the 15th",
                        start_offset=0, end_offset=11, verified=True)
    lo, hi = window_days
    ranged = ResolvedDate(as_written=f"March {lo}-{hi}", certainty=DateCertainty.RANGE,
                          earliest=datetime(2026, 3, lo, tzinfo=timezone.utc),
                          latest=datetime(2026, 3, hi, tzinfo=timezone.utc),
                          resolved_against=NOW, evidence=[span])
    exact = ResolvedDate(as_written="March 15", certainty=DateCertainty.EXACT,
                         earliest=point, latest=point,
                         resolved_against=NOW, evidence=[span])

    claims = [NormalizedClaim(claim_id="a", subject_key="contract:x", field="date.value",
                              value=ranged, authority=Authority.EMAIL_PROSE, evidence=(span,),
                              asserted_at=NOW, event_id="e1"),
              NormalizedClaim(claim_id="b", subject_key="contract:x", field="date.value",
                              value=exact, authority=Authority.EMAIL_PROSE, evidence=(span,),
                              asserted_at=NOW, event_id="e2")]

    found = detect_conflicts(claims, detected_at=NOW).conflicts
    assert bool(found) is conflict_expected


# =============================================================================================
# G5 determinism — the grouping key cannot move with the hash seed
# =============================================================================================
_SUBJECT_KEY_PROBE = """
import json
from datetime import datetime, timezone
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture import pipeline as P
import tests.capture.test_g56_gate_probes as probe

summary = run_sync(probe._Mailbox(), org_id="org_g56", connection_id="con_g56",
                   repo=InMemorySourceEventRepository(), mailbox_owner=probe.OWNER,
                   semantic=P.SemanticLane(llm=probe._AmountLLM(), eval_time=probe.NOW))
print(json.dumps(sorted(d.subject_key for d in summary.conflicts.conflicts)))
"""


@pytest.mark.gate
@pytest.mark.parametrize("seed", ["0", "1", "98765"])
def test_g5_subject_keys_are_stable_under_a_different_hash_seed(seed):
    """ALG-12 groups by `(subject_key, field)`. A key derived from set or dict iteration order
    would drift only here, and only on some runs — so the seed is set for a whole interpreter,
    which is the only way to change it at all."""
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(root)}
    out = subprocess.run([sys.executable, "-c", _SUBJECT_KEY_PROBE], capture_output=True,
                         text=True, env=env, cwd=str(root), timeout=180)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["entity:northwind:amount"]


# =============================================================================================
# G6 — doc 04's worked example, through capture_event
# =============================================================================================
WORKED = ("Hey Rohit, we can probably move forward with the $84K annual contract, but I still "
          "need Finance to confirm whether we can absorb the increase. Also, our renewal is "
          "coming up pretty soon.")


def _span(quote: str) -> EvidenceSpan:
    start = WORKED.index(quote)
    return EvidenceSpan(source_ref="prepared_content:evt_worked", quote=quote,
                        start_offset=start, end_offset=start + len(quote))


def _worked_extraction() -> ExtractionResult:
    """Doc 04 L1.4.3-U2's required `ExtractionResult`, transcribed from the spec table rather
    than imported from the wave's own fixture — a gate that reuses the fixture under test proves
    only that the fixture is self-consistent."""
    amount = Money(minor_units=8_400_000, currency="USD", as_written="$84K")
    soon = ResolvedDate(as_written="pretty soon", certainty=DateCertainty.RELATIVE,
                        earliest=NOW, latest=NOW + timedelta(days=30),
                        resolved_against=NOW, evidence=[_span("pretty soon")])
    return ExtractionResult(
        intent="commit", stance="cautious",
        topics=["contract_renewal", "budget"],
        entity_mentions=[
            EntityMention(surface_form="Finance", entity_type="organization",
                          evidence=[_span("Finance")], confidence_bp=9000),
            EntityMention(surface_form="Rohit", entity_type="person",
                          evidence=[_span("Rohit")], confidence_bp=9000)],
        amounts=[amount],
        dates_mentioned=[soon],
        commitments=[Commitment(actor="Finance", action="confirm absorption of increase",
                                is_conditional=True,
                                condition_text="whether we can absorb the increase",
                                evidence=[_span("need Finance to confirm")],
                                confidence_bp=9000)],
        decision_states=[DecisionState(subject="annual contract", state="pending",
                                       blocked_on="Finance confirmation",
                                       evidence=[_span("annual contract")],
                                       confidence_bp=9000)],
        dependencies=[Dependency(blocker="Finance", blocked="Rohit",
                                 dependency_type="approval",
                                 evidence=[_span("need Finance to confirm")],
                                 confidence_bp=9000)],
        implied_actions=["Finance needs to confirm"],
        all_evidence=[_span("$84K"), _span("pretty soon"), _span("Finance"), _span("Rohit"),
                      _span("need Finance to confirm"), _span("annual contract")],
        model_snapshot="m", prompt_version="p", schema_version="s",
        extraction_profile="general", input_tokens=1, output_tokens=1)


EXPECTED_G6 = {SignalType.CONTRACT_RENEWAL, SignalType.DECISION_PENDING,
               SignalType.APPROVAL_REQUESTED}


class _RaisingLLM:
    """LLM-5's client, wired so that ANY call is an immediate failure with a stack trace.
    A counting fake would let the call happen and report it later, by which time the assertion
    no longer says which of eleven predicates paid for a model."""

    model = "must-not-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("LLM-5 was called on a path the rules already decide")


def _worked_event() -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id="m_worked",
                     occurred_at=NOW, actor_email="rohit@northwind.com", recipients=(OWNER,),
                     raw={"subject": "Annual contract", "body": WORKED})


def _run_worked(**over):
    kwargs = dict(org_id="org_g6", connection_id="con_g6",
                  repo=InMemorySourceEventRepository(), mailbox_owner=OWNER, sender_known=True,
                  esqe=P.EsqeStage(eval_time=NOW, relevance_llm=_RaisingLLM()))
    kwargs.update(over)
    return P.capture_event(_worked_event(), **kwargs)


@pytest.mark.gate
def test_g6_the_worked_example_produces_exactly_the_three_stated_types():
    """`==`, never `>=`. A detector that also fired FINANCIAL_OBLIGATION on the $84K would still
    pass a subset assertion, and the gate exists because over-firing is the failure that
    produced 115 cards of which four were worth reading."""
    outcome = P.run_esqe_stage(
        _run_worked().event, None, {}, stage=P.EsqeStage(eval_time=NOW,
                                                         relevance_llm=_RaisingLLM()),
        extraction=_worked_extraction(), conflicts=None, sender_known=True, is_structured=False)

    assert outcome.detection is not None, "the worked example never reached the predicate table"
    assert set(outcome.detection.types) == EXPECTED_G6, (
        f"expected exactly {sorted(t.value for t in EXPECTED_G6)}, "
        f"got {sorted(t.value for t in outcome.detection.types)}")


@pytest.mark.gate
def test_g6_the_primary_type_and_the_secondaries_partition_the_same_three():
    """The classifier must not invent or lose a type while ordering them."""
    outcome = P.run_esqe_stage(
        _run_worked().event, None, {}, stage=P.EsqeStage(eval_time=NOW,
                                                         relevance_llm=_RaisingLLM()),
        extraction=_worked_extraction(), conflicts=None, sender_known=True, is_structured=False)

    classification = outcome.classification
    assert classification is not None
    assert {classification.primary, *classification.secondary_types} == EXPECTED_G6
    assert classification.primary not in classification.secondary_types


@pytest.mark.gate
def test_g6_every_type_the_detector_can_emit_is_a_member_of_the_closed_fourteen():
    """Driven over every predicate the table has, not only the worked example's three: a
    detector that returned a bare string would still satisfy a `set(...) ==` check written
    against types it happened to produce."""
    assert len(SignalType) == 14, "the taxonomy is closed at fourteen; doc 08 owns it"
    emitted: set = set()
    for conflicts in ((), ):
        for extraction in (_worked_extraction(), _minimal_for_anomaly()):
            outcome = detect_signals(DetectionInput(extraction=extraction, eval_time=NOW,
                                                    conflicts=conflicts))
            emitted |= set(outcome.types)
            for signal in outcome.signals:
                assert isinstance(signal.signal_type, SignalType), (
                    f"{signal.signal_type!r} is not a SignalType member")
    assert emitted, "the probe proved nothing — no predicate fired at all"
    assert emitted <= set(SignalType)


def _minimal_for_anomaly() -> ExtractionResult:
    """An extraction with structure and no predicate — the ANOMALY catch-all's own case."""
    return ExtractionResult(
        intent="inform", stance="neutral",
        questions=["can you confirm the seat count?"],
        model_snapshot="m", prompt_version="p", schema_version="s",
        extraction_profile="general", input_tokens=1, output_tokens=1)


@pytest.mark.gate
def test_g6_the_rules_only_path_costs_zero_model_calls_through_the_real_door():
    """The client raises. If the rules-only relevance path ever reaches LLM-5, this test does
    not report a count — it fails inside the call, naming the caller."""
    result = _run_worked()

    assert result.outcome == "emitted"
    assert result.esqe is not None, "S4 did not run on the production entry point"
    assert result.esqe.relevance.relevant is True
    assert result.esqe.relevance.decided_by == "rules", (
        "a rules-decidable event was routed to the model")


@pytest.mark.gate
def test_g6_a_whole_sweep_qualifies_its_events_with_no_relevance_client_at_all():
    """The unconditional half of the seam: ESQE is pure and unbilled, so a caller that passes no
    `esqe` bundle still gets every event qualified rather than merely routed."""
    summary, _ = _sweep()

    assert summary.results, "the sweep captured nothing"
    for result in summary.results:
        assert result.esqe is not None, (
            f"{result.event.object_type} left S4 unrun — the stage is gated behind a flag")
        assert result.esqe.attribution is not None
        row = next(r for r in result.trace.records if r.stage == P.ESQE_STAGE)
        assert row.detail["relevance_bp"] >= 0
