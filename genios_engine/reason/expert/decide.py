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

TWO MODES END THE RUN, AS LAYER 4'S OWN TERMINALS DO. `find_out` and `nothing` decide no move, so
nothing may stand behind one: the reader (a gating unit) answers `nothing` with `matched` False and
`find_out` with the answer it lacks (INSUFFICIENT_CONTEXT, `expert.answer`), and the orchestrator ends
the run there — `core.constraint` never runs, and the audit store finds no check without a candidate
(it refuses one: a check is an index over the candidates the run kept).

ONE MANIFEST PER VERSION. The audit store keeps exactly one manifest per (capability, version), and the
expert's manifest is the review's — its move, its words, its numbers. So the version is content-
addressed: `DECIDE_VERSION` and the manifest's own hash (`capability_for`).

THROUGH ITS CHECK (STEP-13, `yc2_w27_s13` M35.C3.L-integration.V2.U02). Since STEP-13 a review is decided
through what its check let stand (`contracts/claim_check.CheckedReview`, kept on the row by 0200), never as
the model wrote it: the MODE is the check's — a move that lost its ground is held (`find_out`: the
Investigation lane, the check's one question), a move whose ask is already answered is suppressed
(`nothing`: the file's decision clears) — the play, the card's words and its success are the CHECKED words
(a number corrected, a draft withheld, a connector's move turned into the review's alternative), and the
confidence counts the source events only the STANDING facts cite. The check rides in the context snapshot
(`expert.check`), so a replay decides the same without running it again. A review with no current check
decides nothing (`request_for` refuses it); the pass checks every review before it covers.

⛔ NO MODEL, BY CONSTRUCTION. `ExpertDecisionMaker` never reaches `llm_decision_maker` (the test-mode
decider sits at the top of `DecisionMaker.decide`, which this class replaces), and it says so
(`asks_no_model`) so the orchestrator skips the test-mode R-1 for it (M33.C1.L-logic.V0.U05). Pure: no
I/O, no clock, no model — a replay of the stored request recomputes the decision byte for byte.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any

from genios_engine.contracts.claim_check import HELD, REFUSED, SHOWN, SUPPRESSED, CheckedReview
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
from genios_engine.platform.canonical import semantic_hash
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
from .card_lines import CardLines
from .card_lines import DEFAULT as WINDOW_DEFAULT
from .card_lines import MOVE_DATE as WINDOW_MOVE_DATE
from .card_lines import WINDOW_SAID

#: The expert's capability — its last segment is the signal's rule (`domain_shadow`), so no pack rule
#: may be named `file_review`.
CAPABILITY_ID = "expert.file_review"
READER_ID = "expert.review"
#: 1.1.0: decided through the review's check (STEP-13). 1.2.0: the decision carries the gold card's lines on its
#: render block and its play's window is the file's (STEP-14, `yc2_w27_s14` M43.C2.L-integration.V3.U04) — so each
#: covered file is decided once more, from its stored review, with no model.
DECIDE_VERSION = "1.2.0"
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
#: How the dossier names every kind of evidence that is code's reading, not a source event —
#: `num:`, `pb:`, `hist:`, `whatif:`, `sit:`, `loop:`, `promise:`, `wave:` …: a kind and a colon. A
#: source event is printed by its own id, which carries none (`[evt_…]` from capture's `new_id`).
KIND_SEPARATOR = ":"


def is_event(evidence_id: str) -> bool:
    """Is this cited id a source event — a mail or a meeting of the file — rather than a reading?"""
    return KIND_SEPARATOR not in str(evidence_id)

#: The decision's record of the mode, on every outcome.
MODE_MARKER = "expert_mode"
#: What a `find_out` review lacks: the answer to its question — the field the run is insufficient on.
F_ANSWER = "expert.answer"

F_MODE, F_STAKES, F_URGENCY, F_REVERSIBILITY = ("expert.mode", "expert.stakes", "expert.urgency",
                                                "expert.reversibility")
F_REVIEW, F_CITED, F_NEXT_MOVE = "expert.review", "expert.cited", "expert.next_move"
#: What the check found: the fate, why, the one question — what a replay reads instead of re-checking.
F_CHECK = "expert.check"

#: The mode the check leaves: a held move must find out first, an answered ask needs nothing.
_MODE_OF_FATE: Mapping[str, str] = {HELD: "find_out", SUPPRESSED: "nothing"}


def mode_of(review: ExpertReview, checked: CheckedReview) -> str:
    """The mode a review decides with, once checked."""
    return _MODE_OF_FATE.get(checked.fate, review.mode)

#: The reader, a GATING unit: `nothing` answers `matched` False and the run ends NO_ACTION before the
#: constraint gate runs, as a gate that does not apply ends any run (see the module docstring).
READER_SPEC = ReasonerSpec(READER_ID, DECIDE_VERSION, required_fields=(F_MODE,),
                           failure_policy=FailurePolicy.REQUIRED, gating=True)


#: THE DECISION'S KEY (STEP-13 `yc2_w27_s13` M35.C3.L-integration.V1.U06, crosscheck X12; `06` D48): the run's
#: `trigger_ref` names the review AND the check it was decided through — `<fingerprint>@<check version>` — so a
#: review checked again under a newer check is a new decision of the file (`reason/domain_shadow`'s file branch
#: replaces or clears the older check's), never "this same review" standing beside it.
DECISION_REF_SEPARATOR = "@"


def decision_ref(fingerprint: str, check_version: str) -> str:
    """The key a file's decision is made on: the review's fingerprint and the version of its check."""
    return f"{fingerprint}{DECISION_REF_SEPARATOR}{check_version}"


def fingerprint_of(ref: Any) -> str | None:
    """The review a decision's key names — a run from before the key named the fingerprint alone."""
    if not ref:
        return None
    return str(ref).split(DECISION_REF_SEPARATOR, 1)[0]


def check_version_of(ref: Any) -> str | None:
    """The check version a decision's key names — None on a run from before the key."""
    _fp, sep, version = str(ref or "").partition(DECISION_REF_SEPARATOR)
    return version if sep else None


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


def _window(review: ExpertReview, lines: CardLines | None, eval_time: datetime) -> tuple[int, str]:
    """The file's window and where it came from (`03` F179): the move's own date, from now — else the window the
    card lines measured for the file (the playbook stage's prior, the file's reply time), else a default week,
    said to be one. A review stored before 0221 has no lines: its move's date, or the default."""
    move = review.next_move
    if move is not None and move.by_when is not None:
        return _window_days(move.by_when, eval_time), WINDOW_MOVE_DATE
    if lines is not None:
        return lines.window_days, lines.window_from
    return DEFAULT_WINDOW_DAYS, WINDOW_DEFAULT


def _done(review: ExpertReview, checked: CheckedReview) -> str:
    """What done looks like, as the check let it stand — or, withheld, the move itself made."""
    words = checked.words
    if words.done_when:
        return words.done_when
    return f"{words.headline} — done" if words.headline else review.wait_or_stop


def _play(review: ExpertReview, checked: CheckedReview, eval_time: datetime,
          lines: CardLines | None = None) -> PlayDefinition:
    """The next move the check let stand — or, when there is none to show, the watch the review keeps. Its window
    is the file's (`_window`); its alternative and stop rule as the check held them (check.v3)."""
    move, words, done = review.next_move, checked.words, _done(review, checked)
    days, _source = _window(review, lines, eval_time)
    if move is None or checked.fate != SHOWN or not words.headline:
        return PlayDefinition(
            WATCH_PLAY, DECIDE_VERSION, "Watch the file", (words.wait_or_stop or "Watch the file",),
            read_only=True, window_days=days, success_events=(done,),
            metadata={"wait_or_stop": words.wait_or_stop, "done_when": done,
                      "external_recipient_required": False})
    return PlayDefinition(
        MOVE_PLAY, DECIDE_VERSION, words.headline, (words.headline,), read_only=True,
        window_days=days,
        # WHAT DONE LOOKS LIKE is the review's own `done_when` (M33.C1.L-logic.V1.U16), as checked: the
        # card's success signal (`deliver/card_builder._play_success` reads the audited play's events),
        # never NULL on a card the expert's decision raised (STEP-11's founder-card clause).
        success_events=(done,),
        metadata={"who": move.who, "what": words.headline, "for_whom": move.for_whom, "to": words.to,
                  "by_when": move.by_when.isoformat() if move.by_when else None,
                  # STEP-14 (s14-D1): the open ask the move answers — what a version of the file's card names as
                  # its ask, so another ask is told from the same ask in other words.
                  "answers": move.answers if checked.stands("answers") else None,
                  "alternative": words.alternative, "wait_or_stop": words.wait_or_stop,
                  "done_when": done,
                  # ⛔ READ-ONLY, AND NO RECIPIENT IS REACHED: the move is the founder's to make.
                  # Nothing in this play sends anything — permissions are never the model's (D1).
                  "external_recipient_required": False})


def _render(review: ExpertReview, checked: CheckedReview, *, eval_time: datetime,
            lines: CardLines | None = None) -> dict[str, Any]:
    """The card's words — the review's own as the check let them stand (`deliver/pipeline` renders an
    expert decision from these without a narrator call — M33.C1.L-interface.V1.U08): the move as the
    headline (a held file's question in its place), the expert's reading of the file as the situation,
    the draft as the artifact. A withheld line is empty, never the unchecked words.

    THE GOLD LINES (STEP-14, `yc2_w27_s14` M43.C2.L-integration.V3.U04, s14-F6–F9): beside them, `gold` — the file's
    subject, company, kind of work and role, why now and what remains (the card lines code wrote at review time,
    0221; none on a review stored before), the move WHOLE as recommended (who, what, for whom, by when, to — a
    shown move only), the alternative and the stop rule as the check held them, and the window with where it
    came from."""
    words = checked.words
    headline = words.headline or (checked.question if checked.fate == HELD else None) \
        or review.frames.primary
    move = review.next_move
    shown = move is not None and checked.fate == SHOWN and bool(words.headline)
    days, source = _window(review, lines, eval_time)
    gold = {"subject": lines.subject if lines else None, "company": lines.company if lines else None,
            "kind_of_work": lines.kind_of_work if lines else None, "role": lines.role if lines else None,
            "why_now": lines.why_now if lines else None, "what_remains": list(lines.what_remains) if lines else [],
            "recommended": {"who": move.who, "what": words.headline, "for_whom": move.for_whom,
                            "by_when": move.by_when.isoformat() if move.by_when else None,
                            "to": words.to} if shown else None,
            "alternative": words.alternative, "wait_or_stop": words.wait_or_stop,
            "window": {"days": days, "from": source, "said": WINDOW_SAID[source]}}
    return {"artifact_kind": "draft_message" if words.draft else "none",
            "fallback": {"headline": _braces(headline), "situation": _braces(words.situation or "")},
            "draft": words.draft, "sources": sources_of(checked), "gold": gold}


#: What a card says its situation is: the expert's reading of the file — an inference, said so.
SITUATION_IS = "the expert's reading of the file — an inference, not a quote"
#: What done looks like, and what doing nothing costs: the expert's judgement — inferences, said so.
DONE_WHEN_IS = "what done looks like, as the expert judges it — an inference, not a quote"
DO_NOTHING_IS = "what doing nothing costs, as the expert judges it — an inference, not a quote"
#: The cost of doing nothing when the check withheld the expert's words for it (M35.C3.L-integration.V2.U05,
#: crosscheck X03): the card still says one — this, never the words that did not stand.
DO_NOTHING_WITHHELD = "Not stated: what the expert said doing nothing costs did not stand against the file."


def sources_of(checked: CheckedReview) -> dict[str, Any]:
    """Where each of the card's sentences came from (STEP-13 §5, M35.C3.L-interface.V3.U03): the headline
    the ids its move rests on and their quotes — or, a held file, the question and why it is asked; the
    situation, what done looks like and what doing nothing costs labelled the expert's judgement (an
    inference); the draft whom it goes to AND what it stands on — the ids and quotes of the move's ground,
    as the check held it (M35.C3.L-integration.V2.U05, crosscheck X24: a recipient is no source). Read by
    `deliver/card_builder`."""
    words, out = checked.words, {}
    if checked.fate == HELD:
        out["headline"] = {"question": checked.question, "because": checked.because}
    elif words.headline:
        out["headline"] = {"evidence": list(words.evidence), "quotes": list(words.quotes)}
    if words.situation:
        out["situation"] = {"inference": SITUATION_IS}
    if words.draft:
        out["draft"] = {"to": words.to, "evidence": list(words.evidence), "quotes": list(words.quotes)}
    if words.done_when:
        out["done_when"] = {"inference": DONE_WHEN_IS}
    out["do_nothing"] = {"inference": DO_NOTHING_IS} if words.do_nothing else \
        {"inference": DO_NOTHING_WITHHELD}
    return out


def capability_for(review: ExpertReview, checked: CheckedReview, *, root_entity_type: str, domain: str,
                   eval_time: datetime, live_delivery_enabled: bool = False,
                   card_lines: CardLines | None = None) -> CapabilityManifest:
    """The expert's capability for one review — one reader, the constraint gate, one play — its version
    the manifest's own content address (see the module docstring)."""
    constraint = ReasonerSpec("core.constraint", "1.0.0", dependencies=(READER_ID,),
                              input_kind="candidate_plays", output_kind="candidate_checks",
                              failure_policy=FailurePolicy.REQUIRED)
    manifest = CapabilityManifest(
        capability_id=CAPABILITY_ID, version=DECIDE_VERSION, domain=domain,
        root_entity_type=root_entity_type,
        goal=Goal(CAPABILITY_ID, "What this file needs next, as its review judged it",
                  success_criteria=(_done(review, checked),)),
        reasoners=(READER_SPEC, constraint),
        plays=(_play(review, checked, eval_time, card_lines),),
        ranking_weights=RANKING_WEIGHTS_V2,
        policies=("read_only",),
        live_delivery_enabled=live_delivery_enabled,
        # The card's "cost of ignoring": the CHECKED words (crosscheck X03), never the review's raw scenario.
        do_nothing_consequence=checked.words.do_nothing or DO_NOTHING_WITHHELD,
        expiry_hours=EXPIRY_HOURS,
        metadata={
            CONFIDENCE_AUTHORITY_KEY: READER_ID,
            LANE_KEY: ADAPTER,
            # D1: the appraisal's stakes, measured — never the formula's neutral fallback.
            SITUATION_IMPORTANCE_KEY: {"importance_bp": LEVEL_BP[review.appraisal.stakes],
                                       "fallback": False, "source": "expert_appraisal"},
            "situation_type": "file_review",
            "render": _render(review, checked, lines=card_lines, eval_time=eval_time),
        })
    content = {key: value for key, value in manifest.to_semantic_dict().items() if key != "version"}
    return replace(manifest, version=f"{DECIDE_VERSION}.{semantic_hash(content)[:16]}")


def context_for(row: store.StoredReview, *, org_id: str, root_entity_type: str, eval_time: datetime,
                graph_version: int) -> ContextSnapshot:
    """The file, as what decides: the mode the check leaves, the review's levels and the move the check
    let stand, which review, what its standing facts cite, and what the check found."""
    review, checked = row.review, row.checked
    move = review.next_move
    cited = checked.cited
    facts: dict[str, Any] = {
        F_MODE: {"value": mode_of(review, checked)},
        F_STAKES: {"value": review.appraisal.stakes},
        F_URGENCY: {"value": review.appraisal.urgency},
        F_REVERSIBILITY: {"value": review.appraisal.reversibility},
        F_REVIEW: {"value": {"file_id": row.file_id, "fingerprint": row.fingerprint, "model": row.model,
                             "prompt_version": row.prompt_version,
                             "dossier_digest": row.dossier_digest}},
        F_CITED: {"value": list(cited)},
        F_CHECK: {"value": {"fate": checked.fate, "because": checked.because,
                            "question": checked.question, "version": checked.version}},
    }
    if move is not None and checked.fate == SHOWN and checked.words.headline:
        facts[F_NEXT_MOVE] = {"value": {"who": move.who, "what": checked.words.headline,
                                        "for_whom": move.for_whom, "to": checked.words.to,
                                        "by_when": move.by_when.isoformat() if move.by_when else None}}
    evidence = tuple(build_evidence_ref(
        org_id=org_id, entity_ref=row.file_id, field=F_CITED, value=item, source_ref=item,
        # Each source event is its own origin; code's readings assert none, and so can never raise.
        independence_group=f"event:{item}" if is_event(item) else None)
        for item in cited)
    return ContextSnapshot(
        org_id=org_id, graph_version=int(graph_version), root_entity_id=row.file_id,
        root_entity_type=root_entity_type, evaluation_time=eval_time,
        selector_version=SELECTOR_VERSION, facts=facts, evidence=evidence)


def request_for(row: store.StoredReview, *, org_id: str, root_entity_type: str, domain: str,
                eval_time: datetime, graph_version: int, mode: ExecutionMode = ExecutionMode.LIVE,
                live_delivery_enabled: bool = False,
                config_snapshot_id: str | None = None) -> ReasoningRequest:
    """One audited Layer 4 request for one file, from its VALID review, through its check. Raises
    ValueError for any other row: only a valid review may be read for a decision (`migrations/0197`), and
    only through a check that let something stand (0200, STEP-13)."""
    if row.status != store.VALID or row.review is None:
        raise ValueError(f"only a valid review decides — file {row.file_id} fingerprint "
                         f"{row.fingerprint} is {row.status}")
    if row.checked is None or row.checked.fate == REFUSED:
        raise ValueError(f"only a checked review decides — file {row.file_id} fingerprint "
                         f"{row.fingerprint} has {'no check' if row.checked is None else 'nothing standing'}")
    return ReasoningRequest(
        org_id=org_id,
        capability=capability_for(row.review, row.checked, root_entity_type=root_entity_type,
                                  domain=domain, eval_time=eval_time,
                                  live_delivery_enabled=live_delivery_enabled, card_lines=row.card_lines),
        context=context_for(row, org_id=org_id, root_entity_type=root_entity_type,
                            eval_time=eval_time, graph_version=graph_version),
        evaluation_time=eval_time, trigger_kind=TRIGGER_KIND,
        trigger_ref=decision_ref(row.fingerprint, row.checked.version),
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

    _spec = READER_SPEC

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    @staticmethod
    def _confidence(request: ReasoningRequest) -> tuple[int, tuple[str, ...]]:
        """The confidence the cited source events earn, and those events' refs. See the module docstring."""
        events = tuple(sorted(ref.evidence_id for ref in request.context.evidence
                              if is_event(ref.value)))
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
        mode = str(_value(request, F_MODE))
        outcome = OUTCOME_OF[mode]           # one table: the reader ends the run where it says
        if outcome == DecisionOutcome.INSUFFICIENT_CONTEXT:
            # A question must be answered before anyone moves: the run is insufficient on the answer,
            # and it ends here — nothing may stand behind a move nobody can make yet.
            return ReasonerResult(
                reasoner_id=READER_ID, reasoner_version=DECIDE_VERSION,
                status=ResultStatus.INSUFFICIENT_CONTEXT, missing_fields=(F_ANSWER,),
                reason_codes=(f"{MODE_MARKER}:{mode}",))
        confidence, events = self._confidence(request)
        urgency = LEVEL_BP[str(_value(request, F_URGENCY))]
        cited = tuple(ref.evidence_id for ref in request.context.evidence)
        return ReasonerResult(
            reasoner_id=READER_ID, reasoner_version=DECIDE_VERSION, status=ResultStatus.COMPLETED,
            # The gate: a file that needs nothing from the founder ends the run here (NO_ACTION).
            matched=outcome != DecisionOutcome.NO_ACTION,
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
            # Execution ended the run: `find_out` and `nothing` end it at the reader, as
            # `OUTCOME_OF` says (INSUFFICIENT_CONTEXT, NO_ACTION); a required fact missing or a unit
            # failed ends it too. A fact about the run, recorded as it is.
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


__all__ = ["ADAPTER", "CAPABILITY_ID", "DECIDE_VERSION", "DONE_WHEN_IS", "DO_NOTHING_IS", "DO_NOTHING_WITHHELD",
           "EXPIRY_HOURS", "F_ANSWER", "F_CHECK",
           "KIND_SEPARATOR",
           "ExpertDecisionMaker", "LEVEL_BP", "MODE_MARKER", "MOVE_PLAY", "NO_EVENT_BP",
           "ONE_EVENT_BP", "OUTCOME_OF", "READER_ID", "READER_SPEC", "ReviewReader", "TRIGGER_KIND",
           "WATCH_PLAY",
           "DECISION_REF_SEPARATOR", "capability_for", "check_version_of", "cited_ids", "context_for",
           "decide", "decision_ref", "fingerprint_of", "is_event", "is_expert",
           "mode_of", "orchestrator", "sources_of",
           "request_for"]
