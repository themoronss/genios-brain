"""A covered file's review becomes ONE audited Layer 4 decision (STEP-12 M33, `06` D1).

Tree `yc2_w27_s12` M33.C1.L-logic.V0.U01. Until here the expert's review was advice: stored, read back,
shown on the file, and read by nothing that decides (M32, shadow). `06` D1 (answered 10 Oct): the
expert's judgment decides what matters — numbers, permissions and recipients never come from the model.
So a file whose review stands is decided ONCE, from that review, as an ordinary Layer 4 run: the same
contract, the same audit bundle (`reason/audit.persist_execution`), the same delivery authority
(`reason/authority.py`) — and no model asked, because the model already spoke.

THE REQUEST (`request_for`). One `ReasoningRequest` per file per review:

  * its CAPABILITY is the expert's own, `expert.file_review` — two units: `expert.review`, the
    `ReviewReader` below, and `core.constraint`, the gate every delivered decision carries (the
    authority predicate joins its completed result, and the `read_only` policy it proves); one play:
    the NEXT MOVE the review names (`expert.next_move` — its label the move, its window the review's
    date), or, when the review names none, the WATCH it keeps (`expert.watch`). Its domain is the
    tenant pack the decision binds to; its ranking the six-weight model, because under D1 importance
    is the appraisal's to set; its do-nothing sentence the review's own do-nothing scenario;
  * its CONTEXT is the file — the anchor as the root — holding what decides as `expert.*` facts: the
    mode, the appraisal's three levels, the next move, WHICH review it is (file, fingerprint, model,
    prompt version, dossier digest) and every id the review's facts cite (`expert.cited`), each with
    its own evidence ref. The review's prose stays in `expert_reviews`, keyed by the fingerprint the
    snapshot names — a replay reads it back from there, never from a model.

THE DECISION (`ExpertDecisionMaker`) — the mode is the outcome, one table (`OUTCOME_OF`), and
`reason/output_lane.route` the lane (`STEP-13` §3.5):

  act       DECISION — there is a move to make now: the next move is the play, ranked by the formula
            over the appraisal's numbers; under the confidence floor it is HELD (DEFER), as any
            decision is (`decision_maker.resolve_confidence_floor`, Law 03);
  find_out  INSUFFICIENT_CONTEXT — a question must be answered before anyone moves; naming the gap is
            the output (`OutputLane.INVESTIGATION`, `05` §6: "Investigation until the unknown is
            answered");
  wait      DEFER — nothing until a date or a signal (MONITOR);
  blocked   DEFER — someone else must move first (MONITOR). Not `BLOCKED`: Layer 4's blocked is a
            permission that eliminated every play — ours, never the reader's — and routes to SUPPRESS,
            which would go quiet on a file that is still live. The mode travels beside the outcome
            (`expert_mode:<mode>` on every decision), so the two waits stay told apart;
  nothing   NO_ACTION — the file needs nothing from the founder (SUPPRESS: declared silence).

CONFIDENCE IS CODE'S (`ReviewReader._confidence`). Never the model's number — the review carries none.
A judgment is as strong as the record its FACTS stand on: every id a fact cites was shown in the dossier
(`contracts/expert_review.validate` refused the review otherwise), and code counts the distinct SOURCE
EVENTS among them — the mails and meetings themselves, not code's own readings of them (numbers, the
playbook, asks, promises, situations, history). One event is the base, `ONE_EVENT_BP` = 6,000 — the
file's own record, enough to assert a move (`output_lane.DEFAULT_DECISION_FLOOR_BP`); each further event
raises it by Rule 11's own arithmetic (`decision_maker.bounded_raise`, a full witness: half the
headroom), so no number of mails reaches certainty. A review whose facts cite no event stands on
readings alone — `NO_EVENT_BP` = 4,000, under the confidence floor: its move is held, not asserted.

D1 — THE APPRAISAL SETS IMPORTANCE AND URGENCY, as numbers code owns (`LEVEL_BP`): urgency → the
candidates' `urgency_bp`, stakes → the file's importance, carried as the decision maker reads it
(`SITUATION_IMPORTANCE_KEY`, measured: `fallback` False). Reversibility is kept as a fact, for the card.

⛔ NO MODEL, BY CONSTRUCTION. `ExpertDecisionMaker` never reaches `llm_decision_maker` (the test-mode
decider sits at the top of `DecisionMaker.decide`, which this class replaces), and it says so
(`asks_no_model`) so the orchestrator skips the test-mode R-1 for it (M33.C1.L-logic.V0.U05). Pure: no
I/O, no clock, no model — a replay of the stored request recomputes the decision byte for byte.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from genios_engine.contracts.expert_review import MODES, ExpertReview
from genios_engine.contracts.reasoning import (
    RANKING_WEIGHTS_V2,
    RANKING_WEIGHTS_V2_VERSION,
    CandidateDisposition,
    CapabilityManifest,
    ContextSnapshot,
    DecisionOutcome,
    ExecutionMode,
    FailurePolicy,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningDecision,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.decision_maker import (
    BELOW_FLOOR_REASON,
    CONFIDENCE_AUTHORITY_KEY,
    LANE_KEY,
    SITUATION_IMPORTANCE_KEY,
    DecisionMaker,
    DecisionSynthesis,
    RaiseClaim,
    bounded_raise,
    build_candidates,
    compose_confidence,
    do_nothing_record,
    resolve_confidence_floor,
)
from genios_engine.reason.evidence import build_evidence_ref
from genios_engine.reason.orchestrator import ReasoningExecution, ReasoningOrchestrator
from genios_engine.reason.output_lane import DEFAULT_DECISION_FLOOR_BP, route
from genios_engine.reason.reasoners import ConstraintReasoner
from genios_engine.reason.registry import ReasonerRegistry

from . import store

#: The expert's capability — its last segment is the signal's rule (`domain_shadow`), so no pack rule
#: may be named `file_review`.
CAPABILITY_ID = "expert.file_review"
READER_ID = "expert.review"
DECIDE_VERSION = "1.0.0"
TRIGGER_KIND = "expert.review"
SELECTOR_VERSION = "expert.decide@1"
#: The lane name the confidence floor is resolved for (`decision_maker.LANE_KEY`) — undeclared in
#: `CONFIDENCE_FLOOR_BY_LANE`, so it takes the seed floor, as an unnamed lane must.
ADAPTER = "expert_review"

MOVE_PLAY = "expert.next_move"
WATCH_PLAY = "expert.watch"
#: How long a move with no date of its own stays open — a week, as an authored play's default.
DEFAULT_WINDOW_DAYS = 7
#: How long the decision stands before it is renewed — a week, the capability default, unless the
#: file moves first (a new review is a new request).
EXPIRY_HOURS = 168

#: The mode is the outcome — STEP-12 §8.4 item 2, `STEP-13` §3.5. See the module docstring.
OUTCOME_OF: Mapping[str, DecisionOutcome] = {
    "act": DecisionOutcome.DECISION,
    "find_out": DecisionOutcome.INSUFFICIENT_CONTEXT,
    "wait": DecisionOutcome.DEFER,
    "blocked": DecisionOutcome.DEFER,
    "nothing": DecisionOutcome.NO_ACTION,
}
assert set(OUTCOME_OF) == set(MODES), "every mode of the review contract has its outcome"

#: D1 — the appraisal's levels as basis points. Medium is the formula's own neutral urgency (5,000).
LEVEL_BP: Mapping[str, int] = {"low": 2_500, "medium": 5_000, "high": 8_000}

#: A move resting on one source event — the file's own record — may be asserted: the DECISION lane's floor.
ONE_EVENT_BP = DEFAULT_DECISION_FLOOR_BP
#: A judgment whose facts cite no event at all — under `DEFAULT_CONFIDENCE_FLOOR_BP` (4,500).
NO_EVENT_BP = 4_000
#: What a source event's id looks like in the dossier (`[evt_…]`); every other id is code's reading.
EVENT_PREFIX = "evt_"

#: The decision's record of the mode, on every outcome.
MODE_MARKER = "expert_mode"

F_MODE, F_STAKES, F_URGENCY, F_REVERSIBILITY = ("expert.mode", "expert.stakes", "expert.urgency",
                                                "expert.reversibility")
F_REVIEW, F_CITED, F_NEXT_MOVE = "expert.review", "expert.cited", "expert.next_move"


def is_expert(capability_id: Any) -> bool:
    """Was this decision the expert's — a covered file's, decided from its review?"""
    return str(capability_id or "") == CAPABILITY_ID


def cited_ids(review: ExpertReview) -> tuple[str, ...]:
    """Every id the review's FACTS cite — what is true, and what it rests on. Sorted, once each."""
    return tuple(sorted({e for f in review.facts for e in f.evidence}))


def _braces(value: str) -> str:
    """The review's words inside a render template, read literally (`deliver/render._interpolate`)."""
    return str(value).replace("{", "{{").replace("}", "}}")


def _window_days(by_when: date | None, eval_time: datetime) -> int:
    if by_when is None:
        return DEFAULT_WINDOW_DAYS
    return max(1, min(365, (by_when - eval_time.date()).days))


def _play(review: ExpertReview, eval_time: datetime) -> PlayDefinition:
    """The next move the review names — or, when it names none, the watch it keeps."""
    move = review.next_move
    if move is None:
        return PlayDefinition(
            WATCH_PLAY, DECIDE_VERSION, "Watch the file", (review.wait_or_stop,), read_only=True,
            window_days=DEFAULT_WINDOW_DAYS,
            metadata={"wait_or_stop": review.wait_or_stop, "done_when": review.done_when,
                      "external_recipient_required": False})
    return PlayDefinition(
        MOVE_PLAY, DECIDE_VERSION, move.what, (move.what,), read_only=True,
        window_days=_window_days(move.by_when, eval_time),
        metadata={"who": move.who, "what": move.what, "for_whom": move.for_whom,
                  "by_when": move.by_when.isoformat() if move.by_when else None,
                  "alternative": review.alternative, "wait_or_stop": review.wait_or_stop,
                  "done_when": review.done_when,
                  # ⛔ READ-ONLY, AND NO RECIPIENT IS REACHED: the move is the founder's to make.
                  # Nothing in this play sends anything — permissions are never the model's (D1).
                  "external_recipient_required": False})


def _render(review: ExpertReview) -> dict[str, Any]:
    """The card's words, the review's own (`deliver/pipeline` renders an expert decision from these
    without a narrator call — M33.C1.L-interface.V1.U08): the move as the headline, the expert's
    reading of the file as the situation, the draft as the artifact."""
    move = review.next_move
    return {"artifact_kind": "draft_message" if review.draft else "none",
            "fallback": {"headline": _braces(move.what if move is not None else review.frames.primary),
                         "situation": _braces(review.frames.primary)},
            "draft": review.draft}


def capability_for(review: ExpertReview, *, root_entity_type: str, domain: str, eval_time: datetime,
                   live_delivery_enabled: bool = False) -> CapabilityManifest:
    """The expert's capability for one review — one reader, the constraint gate, one play."""
    reader = ReasonerSpec(READER_ID, DECIDE_VERSION, required_fields=(F_MODE,),
                          failure_policy=FailurePolicy.REQUIRED)
    constraint = ReasonerSpec("core.constraint", "1.0.0", dependencies=(READER_ID,),
                              input_kind="candidate_plays", output_kind="candidate_checks",
                              failure_policy=FailurePolicy.REQUIRED)
    return CapabilityManifest(
        capability_id=CAPABILITY_ID, version=DECIDE_VERSION, domain=domain,
        root_entity_type=root_entity_type,
        goal=Goal(CAPABILITY_ID, "What this file needs next, as its review judged it",
                  success_criteria=(review.done_when,)),
        reasoners=(reader, constraint),
        plays=(_play(review, eval_time),),
        ranking_weights=RANKING_WEIGHTS_V2,
        policies=("read_only",),
        live_delivery_enabled=live_delivery_enabled,
        do_nothing_consequence=review.scenarios.do_nothing,
        expiry_hours=EXPIRY_HOURS,
        metadata={
            CONFIDENCE_AUTHORITY_KEY: READER_ID,
            LANE_KEY: ADAPTER,
            # D1: the appraisal's stakes, measured — never the formula's neutral fallback.
            SITUATION_IMPORTANCE_KEY: {"importance_bp": LEVEL_BP[review.appraisal.stakes],
                                       "fallback": False, "source": "expert_appraisal"},
            "situation_type": "file_review",
            "render": _render(review),
        })


def context_for(row: store.StoredReview, *, org_id: str, root_entity_type: str, eval_time: datetime,
                graph_version: int) -> ContextSnapshot:
    """The file, as what decides: the review's mode, levels and move, which review, what it cites."""
    review = row.review
    move = review.next_move
    cited = cited_ids(review)
    facts: dict[str, Any] = {
        F_MODE: {"value": review.mode},
        F_STAKES: {"value": review.appraisal.stakes},
        F_URGENCY: {"value": review.appraisal.urgency},
        F_REVERSIBILITY: {"value": review.appraisal.reversibility},
        F_REVIEW: {"value": {"file_id": row.file_id, "fingerprint": row.fingerprint, "model": row.model,
                             "prompt_version": row.prompt_version,
                             "dossier_digest": row.dossier_digest}},
        F_CITED: {"value": list(cited)},
    }
    if move is not None:
        facts[F_NEXT_MOVE] = {"value": {"who": move.who, "what": move.what, "for_whom": move.for_whom,
                                        "by_when": move.by_when.isoformat() if move.by_when else None}}
    evidence = tuple(build_evidence_ref(
        org_id=org_id, entity_ref=row.file_id, field=F_CITED, value=item, source_ref=item,
        # Each source event is its own origin; code's readings assert none, and so can never raise.
        independence_group=f"event:{item}" if item.startswith(EVENT_PREFIX) else None)
        for item in cited)
    return ContextSnapshot(
        org_id=org_id, graph_version=int(graph_version), root_entity_id=row.file_id,
        root_entity_type=root_entity_type, evaluation_time=eval_time,
        selector_version=SELECTOR_VERSION, facts=facts, evidence=evidence)


def request_for(row: store.StoredReview, *, org_id: str, root_entity_type: str, domain: str,
                eval_time: datetime, graph_version: int, mode: ExecutionMode = ExecutionMode.LIVE,
                live_delivery_enabled: bool = False,
                config_snapshot_id: str | None = None) -> ReasoningRequest:
    """One audited Layer 4 request for one file, from its VALID review. Raises ValueError for any
    other row: only a valid review may be read for a decision (`migrations/0197`)."""
    if row.status != store.VALID or row.review is None:
        raise ValueError(f"only a valid review decides — file {row.file_id} fingerprint "
                         f"{row.fingerprint} is {row.status}")
    return ReasoningRequest(
        org_id=org_id,
        capability=capability_for(row.review, root_entity_type=root_entity_type, domain=domain,
                                  eval_time=eval_time, live_delivery_enabled=live_delivery_enabled),
        context=context_for(row, org_id=org_id, root_entity_type=root_entity_type,
                            eval_time=eval_time, graph_version=graph_version),
        evaluation_time=eval_time, trigger_kind=TRIGGER_KIND, trigger_ref=row.fingerprint,
        mode=mode, config_snapshot_id=config_snapshot_id)


def _value(request: ReasoningRequest, field: str) -> Any:
    record = request.context.facts.get(field)
    return record.get("value") if isinstance(record, Mapping) else record


class ReviewReader:
    """`expert.review` — reads what the review decided out of the frozen snapshot, and nothing else.

    Publishes the decision's confidence (it is the capability's confidence authority) and the
    appraisal's urgency, and cites every evidence ref the snapshot froze. A reader, not a judge: the
    mode becomes the outcome in `ExpertDecisionMaker`, one table, one place.
    """

    _spec = ReasonerSpec(READER_ID, DECIDE_VERSION, required_fields=(F_MODE,),
                         failure_policy=FailurePolicy.REQUIRED)

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    @staticmethod
    def _confidence(request: ReasoningRequest) -> tuple[int, tuple[str, ...]]:
        """The confidence the cited source events earn, and those events' refs. See the module docstring."""
        events = tuple(sorted(ref.evidence_id for ref in request.context.evidence
                              if str(ref.value).startswith(EVENT_PREFIX)))
        if not events:
            return NO_EVENT_BP, events
        confidence = ONE_EVENT_BP
        for ref_id in events[1:]:
            confidence = bounded_raise(confidence, RaiseClaim(
                unit_id=READER_ID, claimed_bp=10_000, groups=(ref_id,), witness_bp=10_000,
                evidence_ids=(ref_id,)))
        return confidence, events

    def evaluate(self, request: ReasoningRequest,
                 prior_results: Mapping[str, ReasonerResult]) -> ReasonerResult:
        confidence, events = self._confidence(request)
        urgency = LEVEL_BP[str(_value(request, F_URGENCY))]
        cited = tuple(ref.evidence_id for ref in request.context.evidence)
        return ReasonerResult(
            reasoner_id=READER_ID, reasoner_version=DECIDE_VERSION, status=ResultStatus.COMPLETED,
            metrics={"confidence_bp": confidence, "urgency_bp": urgency,
                     "source_events": len(events)},
            findings=(Finding(f"{READER_ID}.record", "expert.record",
                              metrics={"source_events": len(events), "cited": len(cited)},
                              evidence_ids=cited),),
            evidence_ids=cited,
            reason_codes=(f"{MODE_MARKER}:{_value(request, F_MODE)}",))


class ExpertDecisionMaker(DecisionMaker):
    """The decision a covered file's review makes — the mode is the outcome; no model is asked."""

    #: Read by `orchestrator.execute`: a run this decides asks R-1 nothing either.
    asks_no_model = True

    def decide(self, request: Any, results: Sequence[ReasonerResult], *,
               terminal: DecisionOutcome | None, uncertainty: Sequence[str],
               degraded: bool) -> DecisionSynthesis:
        uncertainty = list(uncertainty)
        mode = _value(request, F_MODE)
        uncertainty.append(f"{MODE_MARKER}:{mode}")
        composition = compose_confidence(results=results, request=request, degraded=degraded)
        confidence_bp = composition.confidence_bp
        candidates: tuple = ()
        if terminal is not None:
            # Execution ended the run — a required fact missing, a unit failed. A fact about the
            # run, recorded as it is; the review is not read past it.
            outcome = terminal
        else:
            outcome = OUTCOME_OF[str(mode)]
            if outcome in (DecisionOutcome.DECISION, DecisionOutcome.DEFER):
                # The ranked field, exactly as the formula builds it — `reason/store.py` re-derives
                # it from the stored snapshot to verify the row, and finds the same candidates.
                candidates, confidence_bp = build_candidates(request, results, degraded)
            if outcome == DecisionOutcome.DECISION:
                if not any(c.disposition == CandidateDisposition.ELIGIBLE for c in candidates):
                    outcome = DecisionOutcome.BLOCKED          # a gate removed the move: ours
                else:
                    floor_bp, _source = resolve_confidence_floor(request)
                    if confidence_bp < floor_bp:
                        outcome = DecisionOutcome.DEFER
                        uncertainty.append(f"{BELOW_FLOOR_REASON}:{confidence_bp}<{floor_bp}")
        selected = (next((c for c in candidates if c.disposition == CandidateDisposition.ELIGIBLE),
                         None) if outcome == DecisionOutcome.DECISION else None)
        lane = route(outcome=outcome, confidence_bp=confidence_bp)
        plays = {play.play_id: play for play in request.capability.plays}
        decision = ReasoningDecision(
            outcome=outcome, output_lane=lane.lane, lane_reason=lane.reason,
            capability_id=request.capability.capability_id,
            capability_version=request.capability.version,
            context_snapshot_id=request.context.context_snapshot_id,
            candidates=candidates,
            selected_candidate_id=selected.candidate_id if selected is not None else None,
            confidence_bp=confidence_bp,
            uncertainty=tuple(uncertainty),
            do_nothing_consequence=request.capability.do_nothing_consequence,
            expires_at=request.evaluation_time + timedelta(hours=request.capability.expiry_hours),
            outcome_window_days=(plays[selected.play_id].window_days
                                 if selected is not None else None),
            ranking_weights_version=RANKING_WEIGHTS_V2_VERSION,
            do_nothing=do_nothing_record(request, results))
        return DecisionSynthesis(candidates=candidates, decision=decision, confidence=composition)


#: The expert's own orchestrator: its reader, the constraint gate, and the decision maker above.
_ORCHESTRATOR = ReasoningOrchestrator(ReasonerRegistry((ReviewReader(), ConstraintReasoner())),
                                      decision_maker=ExpertDecisionMaker())


def orchestrator() -> ReasoningOrchestrator:
    """The orchestrator an expert decision runs — and replays — on."""
    return _ORCHESTRATOR


def decide(request: ReasoningRequest) -> ReasoningExecution:
    """Decide one covered file from its review: the audited run, ready for `persist_execution`."""
    if not is_expert(request.capability.capability_id):
        raise ValueError(f"not an expert decision: {request.capability.capability_id}")
    return _ORCHESTRATOR.execute(request)


__all__ = ["ADAPTER", "CAPABILITY_ID", "DECIDE_VERSION", "EVENT_PREFIX", "EXPIRY_HOURS",
           "ExpertDecisionMaker", "LEVEL_BP", "MODE_MARKER", "MOVE_PLAY", "NO_EVENT_BP",
           "ONE_EVENT_BP", "OUTCOME_OF", "READER_ID", "ReviewReader", "TRIGGER_KIND", "WATCH_PLAY",
           "capability_for", "cited_ids", "context_for", "decide", "is_expert", "orchestrator",
           "request_for"]
