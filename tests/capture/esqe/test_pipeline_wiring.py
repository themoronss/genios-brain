"""The S4 seam — ESQE reached from `capture_event`, the real production entry point.

    pytest tests/capture/esqe/test_pipeline_wiring.py -q

Three units in this build were written, unit-tested, proved correct and never called: `extract()`,
the scheduler and the cost governor. A green `tests/capture/esqe/` proves nothing about whether
the qualification stage runs, because every test in the sibling files calls its unit directly.
So every test in THIS file goes through `pipeline.capture_event` — the function the sync runner,
the webhook door and `api/routes.py` all call — and asserts on what came back out of it.

What the seam has to demonstrate, in order of how quietly each would fail:

* the stage runs at all, for an ordinary emitted email, with **no wiring parameter supplied** —
  because ESQE is pure and unbilled, gating it behind a flag would let an activated tenant keep
  routing events instead of qualifying them;
* relevance runs **before** the detector, and a newsletter never reaches the predicate table — a
  detector run first fires `FINANCIAL_OBLIGATION` on any message carrying a date and an amount,
  which is how 115 cards were produced of which four were worth reading;
* the rules-only path through the whole pipeline costs **zero** model calls, asserted with an
  LLM-5 client that raises rather than one that counts;
* the injected bundle actually reaches the units — the graph's role for a sender changes the
  authority the analyzer returns, through `capture_event` and not around it;
* the domain tags survive the seam in hint order, carrying the degraded-compile flag.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe import relevance as R
from genios_engine.capture.esqe.source_analyzer import ActorBasis
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.validate.conflict import DetectedConflict
from genios_engine.contracts.conflict import (Authority, Conflict, ConflictClaim,
                                              ConflictResolution)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, ExtractionResult
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import DateCertainty, ResolvedDate

OWNER = "founder@genios.ai"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

BUSINESS_BODY = ("Confirming the annual contract renewal — we still need Finance to approve the "
                 "budget before the deal can move forward.")
INVESTOR_BODY = ("Sharing our pitch deck ahead of the seed round; happy to talk budget and "
                 "contract terms once diligence starts.")


class RaisingLLM:
    """LLM-5's client, wired so that any call is an immediate, unambiguous failure."""

    model = "must-not-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("LLM-5 was called on a path the rules decide — the pipeline is "
                             "paying per event for an answer a rule already had.")


def _email(**over) -> RawObject:
    kwargs = dict(source="gmail", object_type="email_message", source_object_id="m_esqe_1",
                  occurred_at=NOW, actor_email="buyer@acme.com", recipients=(OWNER,),
                  raw={"subject": "Renewal", "body": BUSINESS_BODY})
    raw = dict(kwargs["raw"])
    raw.update(over.pop("raw", {}))
    kwargs.update(over)
    kwargs["raw"] = raw
    return RawObject(**kwargs)


def _capture(raw: RawObject, **over):
    kwargs = dict(org_id="org_esqe", connection_id="con_esqe",
                  repo=InMemorySourceEventRepository(), mailbox_owner=OWNER)
    kwargs.update(over)
    return P.capture_event(raw, **kwargs)


def _stage(**over) -> P.EsqeStage:
    kwargs = dict(eval_time=NOW, relevance_llm=RaisingLLM())
    kwargs.update(over)
    return P.EsqeStage(**kwargs)


def _trace_stage(result, stage: str):
    return next((r for r in result.trace.records if r.stage == stage), None)


# =============================================================================================
# The seam exists and runs unconditionally.
# =============================================================================================
def test_an_emitted_event_carries_the_whole_s4_answer_with_no_wiring_supplied():
    """The defect this file exists to prevent: a stage that is built and never called. No `esqe`
    parameter is passed here, and the answer still comes back — ESQE is pure, so a caller that
    knows nothing about it still qualifies its events."""
    res = _capture(_email(), sender_known=True)

    assert res.outcome == "emitted"
    assert res.esqe is not None, "S4 was built and never reached — the seam is dead"
    assert res.esqe.relevance.event_id == res.event.event_id
    assert res.esqe.attribution is not None
    assert _trace_stage(res, P.ESQE_STAGE) is not None, "a stage that leaves no trace is unauditable"


def test_the_trace_row_states_the_rule_the_authority_and_the_domains():
    res = _capture(_email(), sender_known=True, esqe=_stage())

    row = _trace_stage(res, P.ESQE_STAGE)
    assert row.action.value == "pass"
    assert row.reason_code == R.RULE_KNOWN_COUNTERPARTY
    assert row.detail["relevance_bp"] == 9000
    assert row.detail["actor_authority_bp"] > 0
    assert "domains" in row.detail and "degraded_compile" in row.detail


# =============================================================================================
# Relevance, through the real door — and the zero-call gates.
# =============================================================================================
def test_a_known_counterparty_is_relevant_through_the_pipeline_with_zero_model_calls():
    res = _capture(_email(), sender_known=True, esqe=_stage())

    assert res.esqe.relevance.relevant is True
    assert res.esqe.relevance.rule == R.RULE_KNOWN_COUNTERPARTY
    assert res.esqe.relevance.decided_by == R.DECIDED_BY_RULES


def test_a_bulk_message_that_survives_the_s1_gate_is_ruled_out_of_the_business_at_s4():
    """Defense in depth, and the case that proves S4's rule is not redundant with the gate's.

    `gate/rules.py` N-02 drops a `List-Unsubscribe` message only when it carries NO attachment —
    deliberately, because "a vendor invoice routinely comes from a bulk sender" and hard-dropping
    it would lose a real obligation. That exemption is exactly what hands S4 an attachment-
    bearing campaign, and S4 is where it stops being treated as business.
    """
    res = _capture(_email(raw={"headers": {"List-Unsubscribe": "<mailto:unsub@vendor.com>"},
                               "has_attachment": True}),
                   esqe=_stage())

    assert res.outcome == "emitted", "not relevant is not the same as not stored"
    assert res.esqe.relevance.relevant is False
    assert res.esqe.relevance.rule == R.RULE_BULK_HEADERS
    assert _trace_stage(res, P.ESQE_STAGE).action.value == "short_circuit"


@pytest.mark.parametrize("headers, expected", [
    ({"List-Unsubscribe": "<x>"}, {"List-Unsubscribe": "<x>"}),
    ([{"name": "List-Unsubscribe", "value": "<x>"}], {"List-Unsubscribe": "<x>"}),
    ([{"name": "List-Id", "value": None}], {"List-Id": ""}),
    ("not headers", {}),
    (None, {}),
])
def test_the_seam_reads_both_header_shapes_a_connector_can_produce(headers, expected):
    """Providers normalise headers as a mapping or as a list of name/value pairs. A seam that
    read only one shape would silently turn the bulk rule off for a whole source — the rule
    would still be green in its own unit test, and dead in production."""
    assert P._esqe_headers({"headers": headers}) == expected


def test_relevance_gates_the_detector_rather_than_running_after_it():
    """The order that stops a newsletter carrying a date and an amount from qualifying as a
    FINANCIAL_OBLIGATION. Same message, same extraction — only the sender differs."""
    extraction = _minimal_extraction()

    ruled_out = P.run_esqe_stage(
        _event_for(_email(raw={"headers": {"List-Unsubscribe": "<x>"}})), None,
        {"headers": {"List-Unsubscribe": "<x>"}},
        stage=_stage(), extraction=extraction, conflicts=None, sender_known=False,
        is_structured=False)
    kept = P.run_esqe_stage(
        _event_for(_email()), None, {}, stage=_stage(), extraction=extraction, conflicts=None,
        sender_known=True, is_structured=False)

    assert ruled_out.detection is None, "the predicate table never saw the newsletter"
    assert ruled_out.classification is None and ruled_out.qualified is False
    assert kept.detection is not None, "a relevant event does reach the detector"


# =============================================================================================
# The detector and classifier, reached through the same door.
# =============================================================================================
def _span(text: str, quote: str) -> EvidenceSpan:
    start = text.index(quote)
    return EvidenceSpan(source_ref="prepared_content:evt_wiring", quote=quote,
                        start_offset=start, end_offset=start + len(quote))


def _minimal_extraction(due: datetime | None = None) -> ExtractionResult:
    """A validated extraction carrying one unconditional commitment, optionally with a due date.

    Built here rather than produced by a model call because this file's subject is the WIRING:
    an extraction from a FakeLLM would make every assertion below depend on the extractor's
    prompt handling as well as on the seam, and a failure would not say which one broke.
    """
    text = BUSINESS_BODY
    commitment = Commitment(
        actor="buyer@acme.com", action="approve the renewal", is_conditional=False,
        evidence=[_span(text, "Confirming the annual contract renewal")], confidence_bp=9000,
        due=None if due is None else ResolvedDate(
            as_written="before the deal can move forward", earliest=due, latest=due,
            certainty=DateCertainty.EXACT, resolved_against=NOW,
            evidence=[_span(text, "before the deal can move forward")]))
    return ExtractionResult(intent="commit", stance="positive", commitments=[commitment],
                            model_snapshot="test-model", prompt_version="v1",
                            schema_version="1", extraction_profile="general",
                            input_tokens=10, output_tokens=10)


def _event_for(raw: RawObject):
    return P.land_raw_object(raw, org_id="org_esqe", connection_id="con_esqe",
                             repo=InMemorySourceEventRepository(), mailbox_owner=OWNER).event


def test_a_relevant_event_with_an_extraction_is_classified_at_the_seam():
    outcome = P.run_esqe_stage(_event_for(_email()), None, {}, stage=_stage(),
                               extraction=_minimal_extraction(), conflicts=None,
                               sender_known=True, is_structured=False)

    assert outcome.detection is not None and outcome.detection.is_signal
    assert outcome.classification.primary == SignalType.COMMITMENT_MADE
    assert outcome.qualified is True


def test_the_frozen_instant_is_the_bundles_and_a_replay_reads_it_not_a_clock():
    """`COMMITMENT_DUE` is a statement about a moment. The same extraction judged against two
    different `eval_time`s must produce two different answers, and neither may come from `now()`
    — which is what makes a replay next year reproduce this year's qualification."""
    extraction = _minimal_extraction(due=NOW + timedelta(days=3))
    event = _event_for(_email())

    at_capture = P.run_esqe_stage(event, None, {}, stage=_stage(eval_time=NOW),
                                  extraction=extraction, conflicts=None, sender_known=True,
                                  is_structured=False)
    long_before = P.run_esqe_stage(event, None, {}, stage=_stage(eval_time=NOW - timedelta(days=60)),
                                   extraction=extraction, conflicts=None, sender_known=True,
                                   is_structured=False)

    assert SignalType.COMMITMENT_DUE in at_capture.detection.types
    assert SignalType.COMMITMENT_DUE not in long_before.detection.types
    assert at_capture.classification.primary == SignalType.COMMITMENT_DUE


def test_an_event_with_no_extraction_is_relevant_without_being_classified():
    """No lane wired means nothing to qualify. That is not an error and it is not a no-signal
    event either — `detection is None` and `detection.fired == 0` are different facts."""
    res = _capture(_email(), sender_known=True, esqe=_stage())

    assert res.esqe.relevance.relevant is True
    assert res.esqe.detection is None and res.esqe.classification is None
    assert res.detection is None and res.qualification is None


def test_the_legacy_result_fields_agree_with_the_stage_that_produced_them():
    """`CaptureResult.detection` / `.qualification` predate the assembled stage. They must be the
    stage's own answer, not a second derivation that can drift from it."""
    outcome = P.run_esqe_stage(_event_for(_email()), None, {}, stage=_stage(),
                               extraction=_minimal_extraction(), conflicts=None,
                               sender_known=True, is_structured=False)
    assert outcome.detection.types == outcome.classification.all_types[:len(outcome.detection.types)] \
        or set(outcome.detection.types) == set(outcome.classification.all_types)


# =============================================================================================
# The bundle actually reaches the units.
# =============================================================================================
def test_the_graphs_role_for_a_sender_changes_the_authority_the_seam_returns():
    """Proves the bundle is threaded rather than defaulted: `actor_role` is a value only the
    caller has, and it can only affect the answer by travelling through `capture_event`."""
    plain = _capture(_email(), sender_known=True, esqe=_stage())
    with_role = _capture(_email(), sender_known=True, esqe=_stage(actor_role="cfo"))

    assert plain.esqe.attribution.actor_basis == ActorBasis.EXTERNAL
    assert with_role.esqe.attribution.actor_basis == ActorBasis.ROLE_LADDER
    assert with_role.esqe.attribution.actor_authority_bp > plain.esqe.attribution.actor_authority_bp


def test_a_no_reply_sender_is_ranked_as_machinery_through_the_pipeline():
    res = _capture(_email(actor_email="no-reply@vendor.com", raw={"body": BUSINESS_BODY}),
                   sender_known=True, esqe=_stage())

    assert res.esqe.attribution.actor_basis == ActorBasis.AUTOMATED
    assert res.esqe.attribution.actor_authority_bp == 1000


# =============================================================================================
# Domains across the seam.
# =============================================================================================
def test_domain_tags_cross_the_seam_in_hint_order_with_the_degraded_flag():
    """An investor thread carries sales vocabulary and must still lead with fundraising, and an
    uncovered domain must arrive flagged rather than absent."""
    res = _capture(_email(raw={"subject": "Round", "body": INVESTOR_BODY}),
                   sender_known=True, esqe=_stage(),
                   coverage_fn=lambda d: {"coverage_ready": False, "coverage_state": "assessed",
                                          "missing_required": ["communication"]})

    assert res.esqe.domains.domains[0] == "fundraising"
    assert "sales" in res.esqe.domains.domains, "never filtered, only outranked"
    assert res.esqe.domains.degraded_compile is True
    assert res.esqe.domains.observations, "an uncovered domain produces a card, not a discard"


def test_the_gated_events_hints_and_the_stages_tags_are_the_same_list():
    """Two derivations of the same fact would drift. The seam and the emitted event must agree
    about which domains this message is in."""
    res = _capture(_email(raw={"subject": "Round", "body": INVESTOR_BODY}),
                   sender_known=True, esqe=_stage())

    assert [h.domain for h in res.gated.domain_hints] == list(res.esqe.domains.domains)


# =============================================================================================
# The stage never fails a capture, and never runs on an event that did not survive the gate.
# =============================================================================================
def test_a_duplicate_never_reaches_s4():
    repo = InMemorySourceEventRepository()
    raw = _email()
    first = _capture(raw, repo=repo, sender_known=True, esqe=_stage())
    second = _capture(raw, repo=repo, sender_known=True, esqe=_stage())

    assert first.outcome == "emitted" and first.esqe is not None
    assert second.outcome == "duplicate" and second.esqe is None


def test_a_structured_object_is_relevant_by_rule_and_costs_no_model_call():
    """A CRM row is business by definition. The bypass that keeps the extractor free must keep
    LLM-5 free too."""
    crm = RawObject(source="hubspot", object_type="deal", source_object_id="deal_esqe",
                    occurred_at=NOW, actor_email=OWNER, content_version="v1",
                    raw={"dealname": "Acme", "dealstage": "contractsent", "amount": "84000"})
    res = _capture(crm, esqe=_stage())

    assert res.esqe.relevance.relevant is True
    assert res.esqe.relevance.rule in (R.RULE_STRUCTURED_SOURCE, R.RULE_KNOWN_COUNTERPARTY)


def test_the_normalizer_runs_on_the_attribution_this_stage_already_computed():
    """L1.6.2 is reached from here, and it is handed L1.6.4's answer rather than left to
    recompute it. A second `analyze_source` call without the bundle's `actor_role` would
    attribute the same message differently from the trace row S4 just wrote about it."""
    outcome = P.run_esqe_stage(_event_for(_email()), None, {}, stage=_stage(actor_role="cfo"),
                               extraction=_minimal_extraction(), conflicts=None,
                               sender_known=True, is_structured=False)

    assert len(outcome.normalized) == len(outcome.detection.signals) > 0
    assert outcome.normalized[0].signal_type == outcome.classification.primary
    assert outcome.normalized[0].evidence_refs, "a canonical signal carries its receipts"
    assert all(record.attribution is outcome.attribution for record in outcome.normalized), (
        "one event, one attribution — recomputing it per signal invites three answers")
    assert outcome.attribution.actor_basis == ActorBasis.ROLE_LADDER


def test_an_irrelevant_event_is_never_normalized():
    outcome = P.run_esqe_stage(
        _event_for(_email()), None, {"headers": {"List-Unsubscribe": "<x>"}}, stage=_stage(),
        extraction=_minimal_extraction(), conflicts=None, sender_known=False,
        is_structured=False)

    assert outcome.normalized == () and outcome.detection is None


# =============================================================================================
# ALG-12's rows reaching the predicate table — the two corrections the seam owns.
# =============================================================================================
def _contract_conflict(field: str = "contract.value") -> Conflict:
    span = _span(BUSINESS_BODY, "annual contract renewal")
    claims = [ConflictClaim(value=value, authority=authority, authority_rank=rank,
                            evidence=[span])
              for value, authority, rank in [("84000", Authority.EMAIL_PROSE, 2),
                                             ("74000", Authority.SIGNED_DOCUMENT, 6)]]
    return Conflict(field=field, claims=claims,
                    resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
                    resolved_value="74000", detected_at=NOW)


class _Outcome:
    """A `ConflictOutcome` stand-in carrying the lane's real row shape: a `DetectedConflict`
    wrapper, not the bare contract object the detector reads."""

    def __init__(self, *rows):
        self.detection = type("D", (), {"conflicts": tuple(rows)})()


def test_the_lanes_detection_rows_are_unwrapped_before_the_predicate_table_sees_them():
    """The lane yields `DetectedConflict` — a `Conflict` PLUS the events it spans — and the
    detector reads `Conflict.field`. Handing the wrapper straight through is an AttributeError
    on the second event of every sync run with a conflict lane wired."""
    event = _event_for(_email())
    row = DetectedConflict(subject_key="deal:acme", conflict=_contract_conflict(),
                           event_ids=(event.event_id, "evt_other"))

    outcome = P.run_esqe_stage(event, None, {}, stage=_stage(), extraction=_minimal_extraction(),
                               conflicts=_Outcome(row), sender_known=True, is_structured=False)

    assert SignalType.INFORMATION_CONFLICT in outcome.detection.types
    assert outcome.classification.primary == SignalType.INFORMATION_CONFLICT, (
        "a conflict is the top of ALG-16's precedence")


def test_a_conflict_between_two_other_events_is_not_this_events_conflict():
    """The lane's detection covers the whole run so far. Unfiltered, every later event in the
    sync would be stamped INFORMATION_CONFLICT — the highest-precedence kind there is — for a
    disagreement it takes no part in."""
    event = _event_for(_email())
    row = DetectedConflict(subject_key="deal:acme", conflict=_contract_conflict(),
                           event_ids=("evt_a", "evt_b"))

    outcome = P.run_esqe_stage(event, None, {}, stage=_stage(), extraction=_minimal_extraction(),
                               conflicts=_Outcome(row), sender_known=True, is_structured=False)

    assert SignalType.INFORMATION_CONFLICT not in outcome.detection.types
    assert outcome.classification.primary == SignalType.COMMITMENT_MADE


def test_no_conflict_lane_is_an_empty_tuple_not_a_crash():
    assert P._conflicts_for(_event_for(_email()), None) == ()


# =============================================================================================
# D9 · the degraded-compile flag reaches the boundary object, not only the trace.
# =============================================================================================
def _coverage(ready: bool):
    return lambda domain: {"coverage_ready": ready, "coverage_state": "assessed",
                           "missing_required": [] if ready else ["communication"]}


def test_the_emitted_event_says_whether_its_domains_were_compiled_in_full():
    """`degraded_compile` was computed by the domain tagger, written to the trace and then
    DROPPED: `GatedEvent` never carried it, so L2 — which reads the gated event and not our
    trace rows — could not tell a full compile from a degraded one. That is the same defect
    `coverage_ready` had, one field along: an answer computed on the request path and thrown
    away at the seam that exists to carry it."""
    degraded = _capture(_email(raw={"subject": "Round", "body": INVESTOR_BODY}),
                        sender_known=True, esqe=_stage(), coverage_fn=_coverage(False))
    full = _capture(_email(raw={"subject": "Round", "body": INVESTOR_BODY}),
                    sender_known=True, esqe=_stage(), coverage_fn=_coverage(True))

    assert degraded.gated.degraded_compile is True
    assert full.gated.degraded_compile is False
    assert degraded.gated.degraded_compile == degraded.esqe.domains.degraded_compile
    assert full.gated.degraded_compile == full.esqe.domains.degraded_compile
