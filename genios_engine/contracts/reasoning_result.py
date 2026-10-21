"""GeniOS-008 L2 Group A · what one Layer 2 run is asked, what it returns, and what it leaves behind.

`speedrun008/GeniOS-008/layer-2-reasoning/02-PLAN.md` §2 and Rohit's L2 spec §11 (`05-SPEC-layer-2.md`).
The new architecture makes the LLM the reasoning engine: one bounded judgment pass reads the signals, the
company's context, its history and the domain's expertise, and returns a STRUCTURED result. This module is
that structure, in four parts:

  L2Request          what is asked — the subject, the trigger (closed), the bundles, the instant. The old
                     `contracts/reasoning.ReasoningRequest` is bound to a capability manifest and a
                     per-situation `ContextSnapshot` (the old flow, where L3 forms situations first); the
                     L2 run is not, so it gets its own request rather than a manifest it would have to fake.
  L2Judgment         the half of the answer the STEP-12 `ExpertReview` did not have: options, history used,
                     second-order consequences, the intervention mode, the decision need, confidence in SIX
                     dimensions, proposed situation mutations, evidence needs, coverage limitations, an open
                     conflict, a request for more depth.
  ReasoningResult    `ExpertReview` (facts, inferences, patterns, hypotheses, unknowns, frames, expected vs
                     actual, scenarios, appraisal, next move) + `L2Judgment` + what code adds: the refs it
                     was reasoned on, the depth, the lane, the check's fate, the problems, the receipt ref.
                     The spec's field names are properties over the two halves, so a reader asks
                     `result.alternative_frames`, never `result.review.frames.rivals`.
  ReasoningReceipt   the audit record: versions, depth and why, groups run and skipped with reasons, tool
                     results, model, prompt, validation, needs raised, how the run ended, output hash.

⛔ THE REVIEW HALF IS REUSED, NOT COPIED. `ExpertReview.from_mapping` and `validate` and the STEP-13 claim
check (`reason/expert/verify`) already hold every fact, inference, pattern and move to the dossier it was
written from. A second copy of those rules here would drift from the first on the first fix.

⛔ CONFIDENCE IS SIX LEVELS WITH REASONS, NEVER A NUMBER (spec §9, "Confidence ek hi number kyun nahi hona
chahiye?"). There is no composite. `contracts/situation.ConfidenceVector` measures DATA quality
(freshness, identity, consistency) and stays a tool input; it is not this.

⛔ THE LANE IS CODE'S. A lane is a route, and routing stays outside the model (L2-Q1 default;
`reason/output_lane` doctrine): `lane_for` derives it from the mode, the conflict and the confidence.

Pure and frozen: no I/O, no clock, no model.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .expert_review import (REVERSIBILITY, DossierCatalogue, ExpertReview, _items, _list, _mapping,
                            _one_of, _text, _texts, number_tokens)

REASONING_RESULT_VERSION = "reasoning-result.v1"

#: What may start a run (spec §5). Closed: a free-string trigger is how the old lanes ended up with
#: `legacy.rule_scan` and `capability.graph_scan` meaning the same thing.
TRIGGER_BUNDLE = "bundle"
TRIGGER_NEW_EVIDENCE = "new_evidence"
TRIGGER_DEADLINE_CROSSED = "deadline_crossed"
TRIGGER_EXPECTED_REPLY_ABSENT = "expected_reply_absent"
TRIGGER_OWNER_CHANGE = "owner_change"
TRIGGER_OUTCOME = "outcome"
TRIGGER_HUMAN_ASK = "human_ask"
TRIGGERS: tuple[str, ...] = (TRIGGER_BUNDLE, TRIGGER_NEW_EVIDENCE, TRIGGER_DEADLINE_CROSSED,
                             TRIGGER_EXPECTED_REPLY_ABSENT, TRIGGER_OWNER_CHANGE, TRIGGER_OUTCOME,
                             TRIGGER_HUMAN_ASK)

#: Reasoning depth (spec §8): "proposed operational policy", chosen by `reason/l2/plan` from measured
#: inputs and recorded in the receipt with why.
DEPTH_NONE = "none"
DEPTH_SHALLOW = "shallow"
DEPTH_STANDARD = "standard"
DEPTH_DEEP = "deep"
DEPTHS: tuple[str, ...] = (DEPTH_NONE, DEPTH_SHALLOW, DEPTH_STANDARD, DEPTH_DEEP)

#: The six confidence dimensions (spec §9, field table §11) and their levels.
CONFIDENCE_DIMENSIONS: tuple[str, ...] = ("evidence", "framing", "temporal", "causal", "authority",
                                          "coverage")
CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low", "unknown")

#: How to intervene (spec §11 `intervention_mode`). Finer than the review's five `mode`s, and held
#: consistent with them by `MODE_FITS`.
INTERVENTION_MODES: tuple[str, ...] = ("observe", "monitor", "gather_evidence", "clarify", "contain",
                                       "escalate", "prepare_decision", "plan", "verify", "abstain")
#: Which intervention modes each review mode allows. An `act` review that says `abstain` contradicts
#: itself, and the reader would get two answers from one run.
MODE_FITS: Mapping[str, frozenset[str]] = {
    "act": frozenset({"contain", "escalate", "prepare_decision", "plan", "verify", "clarify"}),
    "find_out": frozenset({"gather_evidence", "clarify", "verify"}),
    "wait": frozenset({"monitor", "observe"}),
    "nothing": frozenset({"observe", "abstain", "monitor"}),
    "blocked": frozenset({"monitor", "escalate", "clarify", "gather_evidence"}),
}

#: What L2 may PROPOSE to Layer 3 about a situation (spec §11 `proposed_mutations`). Proposals only:
#: L3's admission decides (ADMIT / HOLD / REJECT).
MUTATION_OPS: tuple[str, ...] = ("create", "update", "merge", "close", "link")
#: The ops that act on a situation that already exists, and so must name it.
MUTATION_NEEDS_REF: frozenset[str] = frozenset({"update", "merge", "close", "link"})

#: The lanes (`contracts/reasoning.OutputLane` values), as literals so this module stays leaf-pure.
LANE_DECISION = "decision"
LANE_INVESTIGATION = "investigation"
LANE_CONFLICT = "conflict"
LANE_MONITOR = "monitor"
LANE_SUPPRESS = "suppress"
LANES: tuple[str, ...] = (LANE_DECISION, LANE_INVESTIGATION, LANE_CONFLICT, LANE_MONITOR, LANE_SUPPRESS)

#: How a run ended (receipt `termination`).
ENDED_RESULT = "result"                  # a checked result
ENDED_UNCHANGED = "unchanged"            # the change gate: nothing material moved, no call
ENDED_REFUSED = "refused"                # the model's answer refused on substance
ENDED_FAILED = "failed"                  # the call failed, or the answer stayed misshapen
ENDED_TRUNCATED = "truncated"
ENDED_OVER_BUDGET = "over_budget"        # carried; incomplete, never forced
ENDS: tuple[str, ...] = (ENDED_RESULT, ENDED_UNCHANGED, ENDED_REFUSED, ENDED_FAILED, ENDED_TRUNCATED,
                         ENDED_OVER_BUDGET)

#: The problems `validate_judgment` names. STRUCTURAL ones refuse the answer (one repair); the rest
#: drop the line, or mark the result `review_required`.
MODE_MISMATCH = "mode_mismatch"
UNPRINTED_REF = "unprinted_ref"
NUMBER_NOT_PRINTED = "number_not_in_dossier"
MUTATION_WITHOUT_EVIDENCE = "mutation_without_evidence"
MUTATION_WITHOUT_TARGET = "mutation_without_target"
DECISION_WITHOUT_OWNER = "decision_without_owner"
MOVE_IN_THE_PAST = "move_in_the_past"
NO_OPTION = "no_option"
STRUCTURAL: frozenset[str] = frozenset({MODE_MISMATCH})
#: Problems a person must look at before anything moves on this result (spec §15 `review_required`).
NEEDS_REVIEW: frozenset[str] = frozenset({DECISION_WITHOUT_OWNER, MOVE_IN_THE_PAST})


def stable_ref(prefix: str, payload: Any) -> str:
    """A content address: the same payload, the same ref, on any machine."""
    body = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(body.encode('utf-8')).hexdigest()[:32]}"


# ── the request ────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class L2Request:
    """What one run is asked. `request_id` is derived — the same subject, trigger, bundles and inputs
    fingerprint are the same request, and a request already answered is answered by its stored result."""

    org_id: str
    subject_ref: str                 # `file:<node>` or `seed:<thread or subject key>`
    trigger: str
    eval_time: datetime
    bundle_ids: tuple[str, ...] = ()
    question: str = "what does this mean, and what is the best next move?"
    fingerprint: str = ""
    request_id: str = ""

    def __post_init__(self) -> None:
        if self.trigger not in TRIGGERS:
            raise ValueError(f"a run's trigger is one of {TRIGGERS}, not {self.trigger!r}")
        if not self.subject_ref or ":" not in self.subject_ref:
            raise ValueError("a run reasons about a subject: `file:<id>` or `seed:<key>`")
        if self.eval_time.tzinfo is None:
            raise ValueError("eval_time is an aware instant")
        expected = stable_ref("l2req", {"org": self.org_id, "subject": self.subject_ref,
                                        "trigger": self.trigger, "bundles": sorted(self.bundle_ids),
                                        "fingerprint": self.fingerprint})
        if self.request_id and self.request_id != expected:
            raise ValueError("request_id does not match the request")
        object.__setattr__(self, "request_id", expected)


# ── the judgment half ──────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class HistoryUse:
    case: str                        # which past case, in words
    applies: bool
    why: str                         # why it does or does not apply now
    based_on: tuple[str, ...]        # ids the dossier printed


@dataclass(frozen=True, slots=True)
class Option:
    option: str
    benefit: str
    downside: str
    reversibility: str               # one of REVERSIBILITY
    affects: str                     # who is affected
    would_change: str                # the evidence that would change the choice


@dataclass(frozen=True, slots=True)
class DecisionNeed:
    needed: bool
    who: str | None = None           # who must decide, as the dossier names them
    what: str | None = None


@dataclass(frozen=True, slots=True)
class ConfidenceDimension:
    level: str                       # one of CONFIDENCE_LEVELS
    reason: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProposedMutation:
    op: str                          # one of MUTATION_OPS
    situation: str                   # the situation, in words
    why: str
    evidence: tuple[str, ...]
    situation_ref: str | None = None  # the existing situation an update / merge / close / link names


@dataclass(frozen=True, slots=True)
class RaisedNeed:
    question: str
    why_it_matters: str
    decision_changing: bool
    subject_ref: str | None = None   # `thread:…`, `document:…`, `signal:…` — what L1 can fetch
    acceptable_sources: tuple[str, ...] = ()
    unacceptable_sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpenConflict:
    about: str
    between: tuple[str, ...]         # the ids that disagree


@dataclass(frozen=True, slots=True)
class L2Judgment:
    intervention_mode: str
    confidence: Mapping[str, ConfidenceDimension]
    options: tuple[Option, ...] = ()
    history_used: tuple[HistoryUse, ...] = ()
    second_order: tuple[str, ...] = ()
    decision_need: DecisionNeed = field(default_factory=lambda: DecisionNeed(needed=False))
    proposed_mutations: tuple[ProposedMutation, ...] = ()
    evidence_needs: tuple[RaisedNeed, ...] = ()
    coverage_limitations: tuple[str, ...] = ()
    open_conflict: OpenConflict | None = None
    deeper: str | None = None        # the model asking for more depth, and why — None when it does not

    #: The keys this half reads from the model's answer; the rest of the answer is the review's.
    KEYS = ("intervention_mode", "confidence", "options", "history_used", "second_order", "decision_need",
            "proposed_mutations", "evidence_needs", "coverage_limitations", "open_conflict", "deeper")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "L2Judgment":
        """The judgment half of the model's answer, or ValueError naming what is malformed — the one
        error a caller may repair once, as `ExpertReview.from_mapping`'s."""
        if not isinstance(raw, Mapping):
            raise ValueError("an L2 judgment is an object")
        conf_raw = _mapping(raw.get("confidence"), "confidence")
        confidence: dict[str, ConfidenceDimension] = {}
        for dim in CONFIDENCE_DIMENSIONS:
            d = _mapping(conf_raw.get(dim), f"confidence.{dim}")
            if not d:
                raise ValueError(f"confidence says {dim}: every one of {CONFIDENCE_DIMENSIONS}, each a "
                                 "level and its reason — `unknown` with why is an answer, silence is not")
            confidence[dim] = ConfidenceDimension(
                level=_one_of(d.get("level"), CONFIDENCE_LEVELS, f"confidence.{dim}.level"),
                reason=_text(d.get("reason"), f"why {dim} confidence is what it is"),
                evidence=_texts(d.get("evidence"), f"confidence.{dim}.evidence"))
        dn = _mapping(raw.get("decision_need"), "decision_need")
        oc = raw.get("open_conflict")
        conflict = None
        if oc:
            oc = _mapping(oc, "open_conflict")
            conflict = OpenConflict(about=_text(oc.get("about"), "what the conflict is about"),
                                    between=_texts(oc.get("between"), "what disagrees", at_least=2))
        return cls(
            intervention_mode=_one_of(raw.get("intervention_mode"), INTERVENTION_MODES, "intervention_mode"),
            confidence=confidence,
            options=tuple(Option(option=_text(o.get("option"), "an option"),
                                 benefit=_text(o.get("benefit"), "an option's benefit"),
                                 downside=_text(o.get("downside"), "an option's downside"),
                                 reversibility=_one_of(o.get("reversibility"), REVERSIBILITY,
                                                       "an option's reversibility"),
                                 affects=_text(o.get("affects"), "who an option affects"),
                                 would_change=_text(o.get("would_change"), "what would change the choice"))
                          for o in _items(raw.get("options"), "options", "an option")),
            history_used=tuple(HistoryUse(case=_text(h.get("case"), "a past case"),
                                          applies=bool(h.get("applies")),
                                          why=_text(h.get("why"), "why a past case does or does not apply"),
                                          based_on=_texts(h.get("based_on"), "what a past case rests on"))
                               for h in _items(raw.get("history_used"), "history_used", "a past case")),
            second_order=_texts(raw.get("second_order"), "a second-order consequence"),
            decision_need=DecisionNeed(needed=bool(dn.get("needed")),
                                       who=_text(dn.get("who"), "who decides", required=False) or None,
                                       what=_text(dn.get("what"), "what is decided", required=False) or None),
            proposed_mutations=tuple(
                ProposedMutation(op=_one_of(m.get("op"), MUTATION_OPS, "a mutation's op"),
                                 situation=_text(m.get("situation"), "the situation a mutation is about"),
                                 why=_text(m.get("why"), "why the mutation"),
                                 evidence=_texts(m.get("evidence"), "a mutation's evidence"),
                                 situation_ref=_text(m.get("situation_ref"), "the situation it names",
                                                     required=False) or None)
                for m in _items(raw.get("proposed_mutations"), "proposed_mutations", "a mutation")),
            evidence_needs=tuple(
                RaisedNeed(question=_text(n.get("question"), "a need's question"),
                           why_it_matters=_text(n.get("why_it_matters"), "why a need matters"),
                           decision_changing=bool(n.get("decision_changing")),
                           subject_ref=_text(n.get("subject_ref"), "what a need is about",
                                             required=False) or None,
                           acceptable_sources=_texts(n.get("acceptable_sources"), "acceptable sources"),
                           unacceptable_sources=_texts(n.get("unacceptable_sources"), "unacceptable sources"))
                for n in _items(raw.get("evidence_needs"), "evidence_needs", "an evidence need")),
            coverage_limitations=_texts(raw.get("coverage_limitations"), "a coverage limitation"),
            open_conflict=conflict,
            deeper=_text(raw.get("deeper"), "why more depth", required=False) or None)

    def as_mapping(self) -> dict[str, Any]:
        dn, oc = self.decision_need, self.open_conflict
        return {
            "intervention_mode": self.intervention_mode,
            "confidence": {k: {"level": v.level, "reason": v.reason, "evidence": list(v.evidence)}
                           for k, v in self.confidence.items()},
            "options": [{"option": o.option, "benefit": o.benefit, "downside": o.downside,
                         "reversibility": o.reversibility, "affects": o.affects,
                         "would_change": o.would_change} for o in self.options],
            "history_used": [{"case": h.case, "applies": h.applies, "why": h.why,
                              "based_on": list(h.based_on)} for h in self.history_used],
            "second_order": list(self.second_order),
            "decision_need": {"needed": dn.needed, "who": dn.who, "what": dn.what},
            "proposed_mutations": [{"op": m.op, "situation": m.situation, "why": m.why,
                                    "evidence": list(m.evidence), "situation_ref": m.situation_ref}
                                   for m in self.proposed_mutations],
            "evidence_needs": [{"question": n.question, "why_it_matters": n.why_it_matters,
                                "decision_changing": n.decision_changing, "subject_ref": n.subject_ref,
                                "acceptable_sources": list(n.acceptable_sources),
                                "unacceptable_sources": list(n.unacceptable_sources)}
                               for n in self.evidence_needs],
            "coverage_limitations": list(self.coverage_limitations),
            "open_conflict": None if oc is None else {"about": oc.about, "between": list(oc.between)},
            "deeper": self.deeper,
        }

    def texts(self) -> tuple[str, ...]:
        """Every text this half writes — what its numbers are read off, as `ExpertReview.texts`."""
        out: list[str] = [d.reason for d in self.confidence.values()]
        out += [t for o in self.options for t in (o.option, o.benefit, o.downside, o.affects, o.would_change)]
        out += [t for h in self.history_used for t in (h.case, h.why)]
        out += list(self.second_order)
        out += [self.decision_need.who or "", self.decision_need.what or ""]
        out += [t for m in self.proposed_mutations for t in (m.situation, m.why)]
        out += [t for n in self.evidence_needs for t in (n.question, n.why_it_matters)]
        out += list(self.coverage_limitations)
        if self.open_conflict is not None:
            out.append(self.open_conflict.about)
        if self.deeper:
            out.append(self.deeper)
        return tuple(t for t in out if t)


def _printed(ref: str, catalogue: DossierCatalogue, facts: int) -> bool:
    if ref.startswith("fact:"):
        try:
            return 1 <= int(ref.split(":", 1)[1]) <= facts
        except ValueError:
            return False
    return ref in catalogue.evidence_ids


def validate_judgment(review: ExpertReview, judgment: L2Judgment, catalogue: DossierCatalogue, *,
                      as_of: datetime | None = None) -> tuple[tuple[str, str], ...]:
    """Every way the judgment half says more than its dossier holds, or contradicts its review.

    Structure (refused, one repair): an intervention mode the review's mode does not allow. Each other
    problem names one line; `ReasoningResult.review_required` is set by the authority and time ones.
    """
    problems: list[tuple[str, str]] = []
    facts = len(review.facts)
    if judgment.intervention_mode not in MODE_FITS.get(review.mode, frozenset()):
        problems.append((MODE_MISMATCH, f"mode {review.mode} does not allow {judgment.intervention_mode}"))
    for dim, d in judgment.confidence.items():
        for ref in d.evidence:
            if not _printed(ref, catalogue, facts):
                problems.append((UNPRINTED_REF, f"confidence.{dim} cites {ref}"))
    for n, h in enumerate(judgment.history_used, start=1):
        for ref in h.based_on:
            if not _printed(ref, catalogue, facts):
                problems.append((UNPRINTED_REF, f"past case {n} rests on {ref}"))
    for n, m in enumerate(judgment.proposed_mutations, start=1):
        if not m.evidence:
            problems.append((MUTATION_WITHOUT_EVIDENCE, f"mutation {n} ({m.op})"))
        for ref in m.evidence:
            if not _printed(ref, catalogue, facts):
                problems.append((UNPRINTED_REF, f"mutation {n} cites {ref}"))
        if m.op in MUTATION_NEEDS_REF and (not m.situation_ref or m.situation_ref not in catalogue.evidence_ids):
            problems.append((MUTATION_WITHOUT_TARGET, f"mutation {n} ({m.op}) names no situation the dossier printed"))
    if judgment.open_conflict is not None:
        for ref in judgment.open_conflict.between:
            if not _printed(ref, catalogue, facts):
                problems.append((UNPRINTED_REF, f"the conflict cites {ref}"))
    if review.mode in ("act", "find_out") and not judgment.options:
        problems.append((NO_OPTION, f"a {review.mode} result names no option"))
    if judgment.decision_need.needed and not judgment.decision_need.who:
        problems.append((DECISION_WITHOUT_OWNER, "a decision is needed and nobody is named to make it"))
    move = review.next_move
    if as_of is not None and move is not None and move.by_when is not None and move.by_when < as_of.date():
        problems.append((MOVE_IN_THE_PAST, f"the next move is due {move.by_when.isoformat()}, before the run"))
    stated = frozenset().union(*(number_tokens(t) for t in judgment.texts())) if judgment.texts() else frozenset()
    for number in sorted(stated - catalogue.numbers):
        problems.append((NUMBER_NOT_PRINTED, number))
    return tuple(problems)


def drop_unprinted(judgment: L2Judgment, catalogue: DossierCatalogue, facts: int) -> L2Judgment:
    """The judgment with every line that cites what the dossier never printed DROPPED — the STEP-13
    rule (`06` D59): a line that fails drops and the result stays."""
    def ok(refs: tuple[str, ...]) -> bool:
        return all(_printed(r, catalogue, facts) for r in refs)

    conflict = judgment.open_conflict
    if conflict is not None and not ok(conflict.between):
        conflict = None
    return L2Judgment(
        intervention_mode=judgment.intervention_mode,
        confidence={k: ConfidenceDimension(v.level, v.reason,
                                           tuple(r for r in v.evidence if _printed(r, catalogue, facts)))
                    for k, v in judgment.confidence.items()},
        options=judgment.options,
        history_used=tuple(h for h in judgment.history_used if ok(h.based_on)),
        second_order=judgment.second_order,
        decision_need=judgment.decision_need,
        proposed_mutations=tuple(m for m in judgment.proposed_mutations
                                 if m.evidence and ok(m.evidence)
                                 and (m.op not in MUTATION_NEEDS_REF
                                      or (m.situation_ref and m.situation_ref in catalogue.evidence_ids))),
        evidence_needs=judgment.evidence_needs,
        coverage_limitations=judgment.coverage_limitations,
        open_conflict=conflict,
        deeper=judgment.deeper)


# ── the lane (code's) ──────────────────────────────────────────────────────────────────────────

#: Where each intervention mode routes when nothing overrides it.
_LANE_OF_MODE: Mapping[str, str] = {
    "observe": LANE_SUPPRESS, "abstain": LANE_SUPPRESS, "monitor": LANE_MONITOR,
    "gather_evidence": LANE_INVESTIGATION, "clarify": LANE_INVESTIGATION,
    "contain": LANE_DECISION, "escalate": LANE_DECISION, "prepare_decision": LANE_DECISION,
    "plan": LANE_DECISION, "verify": LANE_DECISION,
}
#: The dimensions a DECISION lane needs at medium or better: what the evidence shows, and that the
#: situation is read right. The levels' analogue of `output_lane.DEFAULT_DECISION_FLOOR_BP`.
DECISION_NEEDS = ("evidence", "framing")


def lane_for(judgment: L2Judgment) -> tuple[str, str]:
    """The lane and why. Pure, total, first match wins — the same order `reason/output_lane.route` keeps:
    an open conflict first, then the mode, then the confidence floor for a decision."""
    if judgment.open_conflict is not None:
        return LANE_CONFLICT, "two sources disagree and the disagreement is open; a ruling settles it"
    lane = _LANE_OF_MODE[judgment.intervention_mode]
    if lane != LANE_DECISION:
        return lane, f"the intervention is {judgment.intervention_mode}"
    weak = [d for d in DECISION_NEEDS if judgment.confidence[d].level in ("low", "unknown")]
    if weak:
        return LANE_MONITOR, (f"{judgment.intervention_mode} with {' and '.join(weak)} confidence low or "
                              "unknown: shown as something to watch, not something to do")
    return LANE_DECISION, f"{judgment.intervention_mode}, with evidence and framing confidence at medium or better"


def judgment_hold(lane: str, problems: tuple[tuple[str, str], ...]) -> str | None:
    """L3 audit (21 Oct 2026) · why the judgment says a move must not be shown as one to make — a
    `contracts/claim_check.JUDGMENT_HOLDS` reason for the claim check — or None. Pure, first match wins: an
    open conflict (a ruling settles it), then what `review_required` names (a person looks first), then an act
    on low evidence or framing confidence (`lane_for`'s monitor). The check holds only an act's shown move."""
    from .claim_check import MOVE_DATE_PASSED, NO_DECIDER, OPEN_CONFLICT, WEAK_GROUND
    kinds = {kind for kind, _ in problems}
    if lane == LANE_CONFLICT:
        return OPEN_CONFLICT
    if DECISION_WITHOUT_OWNER in kinds:
        return NO_DECIDER
    if MOVE_IN_THE_PAST in kinds:
        return MOVE_DATE_PASSED
    if lane == LANE_MONITOR:
        return WEAK_GROUND
    return None


# ── the result ─────────────────────────────────────────────────────────────────────────────────

def _checked_from(raw: Any) -> Any:
    if raw is None:
        return None
    from .claim_check import CheckedReview
    return CheckedReview.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    request_ref: str
    subject_ref: str
    context_ref: str                 # the snapshot it read — `graph@<revision>`, or `graph@unknown`
    expertise_ref: str               # the expertise package's hash
    depth: str
    review: ExpertReview
    judgment: L2Judgment
    lane: str
    lane_reason: str
    check_fate: str | None = None    # the STEP-13 claim check's fate
    problems: tuple[tuple[str, str], ...] = ()
    receipt_ref: str = ""
    version: str = REASONING_RESULT_VERSION
    #: L2 rebuild A7 · the claim check's whole answer (`contracts.claim_check.CheckedReview`): the card's words
    #: AS CHECKED — the only words that may reach a founder — and the verdict on every line. Kept so a card is
    #: built from what stood, never from the raw review a dropped line is still in. None on rows written before.
    checked: Any = None

    # The spec's names (§11), over the two halves.
    @property
    def facts(self):
        return self.review.facts

    @property
    def inferences(self):
        return self.review.inferences

    @property
    def hypotheses(self):
        return self.review.hypotheses

    @property
    def unknowns(self):
        return self.review.unknowns

    @property
    def frame(self) -> str:
        return self.review.frames.primary

    @property
    def alternative_frames(self) -> tuple[str, ...]:
        return self.review.frames.rivals

    @property
    def expected_vs_actual(self):
        return self.review.expected_vs_actual

    @property
    def history_used(self):
        return self.judgment.history_used

    @property
    def consequences(self) -> dict[str, Any]:
        s = self.review.scenarios
        return {"do_nothing": s.do_nothing, "act": s.act, "best": s.best, "worst": s.worst,
                "second_order": list(self.judgment.second_order)}

    @property
    def options(self):
        return self.judgment.options

    @property
    def intervention_mode(self) -> str:
        return self.judgment.intervention_mode

    @property
    def best_next_move(self):
        return self.review.next_move

    @property
    def decision_need(self):
        return self.judgment.decision_need

    @property
    def confidence(self):
        return self.judgment.confidence

    @property
    def proposed_mutations(self):
        return self.judgment.proposed_mutations

    @property
    def evidence_needs(self):
        return self.judgment.evidence_needs

    @property
    def coverage_limitations(self):
        return self.judgment.coverage_limitations

    @property
    def review_required(self) -> bool:
        return any(kind in NEEDS_REVIEW for kind, _ in self.problems)

    def as_mapping(self) -> dict[str, Any]:
        return {"version": self.version, "request_ref": self.request_ref, "subject_ref": self.subject_ref,
                "context_ref": self.context_ref, "expertise_ref": self.expertise_ref, "depth": self.depth,
                "review": self.review.as_mapping(), "judgment": self.judgment.as_mapping(),
                "lane": self.lane, "lane_reason": self.lane_reason, "check_fate": self.check_fate,
                "problems": [list(p) for p in self.problems], "receipt_ref": self.receipt_ref,
                # Named only when there is one, so a result from before A7 hashes as it did.
                **({"checked": self.checked.as_mapping()} if self.checked is not None else {})}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ReasoningResult":
        """What `as_mapping` wrote, read back — the replay's door: no model, the same result."""
        return cls(request_ref=str(raw["request_ref"]), subject_ref=str(raw["subject_ref"]),
                   context_ref=str(raw["context_ref"]), expertise_ref=str(raw["expertise_ref"]),
                   depth=str(raw["depth"]), review=ExpertReview.from_mapping(raw["review"]),
                   judgment=L2Judgment.from_mapping(raw["judgment"]), lane=str(raw["lane"]),
                   lane_reason=str(raw["lane_reason"]), check_fate=raw.get("check_fate"),
                   problems=tuple(tuple(p) for p in _list(raw.get("problems"), "problems")),
                   receipt_ref=str(raw.get("receipt_ref") or ""),
                   version=str(raw.get("version") or REASONING_RESULT_VERSION),
                   checked=_checked_from(raw.get("checked")))

    def output_hash(self) -> str:
        return stable_ref("l2out", self.as_mapping())


# ── history and the receipt ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class HistoricalCase:
    """One comparable past piece of work, and how it ended — read, never inferred."""
    case_id: str                     # the id the dossier prints for it
    subject: str
    work_kind: str | None
    outcome: str | None              # how it ended, as recorded — None while it has not
    last_touch: datetime | None
    summary: str


@dataclass(frozen=True, slots=True)
class HistoricalContext:
    """Spec §7 (*proposed*): what the company has seen before that bears on this run."""
    cases: tuple[HistoricalCase, ...] = ()
    judged_before: tuple[str, ...] = ()   # this subject's own earlier judgments, as printed lines


@dataclass(frozen=True, slots=True)
class ReasoningReceipt:
    """The durable audit record of one run (spec §14). Never the raw chain of thought."""
    request_ref: str
    org_id: str
    subject_ref: str
    trigger: str
    context_ref: str
    expertise_ref: str
    depth: str
    depth_why: tuple[str, ...]
    groups_run: tuple[str, ...]
    groups_skipped: Mapping[str, str]
    tool_results: Mapping[str, Any]
    model: str | None
    prompt_version: str
    calls: int
    termination: str
    validation: tuple[tuple[str, str], ...] = ()
    needs_raised: tuple[str, ...] = ()
    output_hash: str | None = None
    cost_micro_usd: int = 0
    bundle_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.termination not in ENDS:
            raise ValueError(f"a run ends as one of {ENDS}, not {self.termination!r}")
        if self.depth not in DEPTHS:
            raise ValueError(f"depth is one of {DEPTHS}, not {self.depth!r}")

    def as_mapping(self) -> dict[str, Any]:
        return {"request_ref": self.request_ref, "org_id": self.org_id, "subject_ref": self.subject_ref,
                "trigger": self.trigger, "context_ref": self.context_ref, "expertise_ref": self.expertise_ref,
                "depth": self.depth, "depth_why": list(self.depth_why), "groups_run": list(self.groups_run),
                "groups_skipped": dict(self.groups_skipped), "tool_results": dict(self.tool_results),
                "model": self.model, "prompt_version": self.prompt_version, "calls": self.calls,
                "termination": self.termination, "validation": [list(v) for v in self.validation],
                "needs_raised": list(self.needs_raised), "output_hash": self.output_hash,
                "cost_micro_usd": self.cost_micro_usd, "bundle_ids": list(self.bundle_ids)}

    @property
    def ref(self) -> str:
        return stable_ref("l2rcpt", {"request": self.request_ref, "end": self.termination,
                                     "out": self.output_hash})


__all__ = ["CONFIDENCE_DIMENSIONS", "CONFIDENCE_LEVELS", "ConfidenceDimension", "DECISION_NEEDS",
           "DEPTHS", "DEPTH_DEEP", "DEPTH_NONE", "DEPTH_SHALLOW", "DEPTH_STANDARD", "DecisionNeed", "ENDS",
           "ENDED_FAILED", "ENDED_OVER_BUDGET", "ENDED_REFUSED", "ENDED_RESULT", "ENDED_TRUNCATED",
           "ENDED_UNCHANGED", "HistoricalCase", "HistoricalContext", "HistoryUse", "INTERVENTION_MODES",
           "L2Judgment", "L2Request", "LANES", "LANE_CONFLICT", "LANE_DECISION", "LANE_INVESTIGATION",
           "LANE_MONITOR", "LANE_SUPPRESS", "MODE_FITS", "MODE_MISMATCH", "MUTATION_OPS", "NEEDS_REVIEW",
           "OpenConflict", "Option", "ProposedMutation", "REASONING_RESULT_VERSION", "RaisedNeed",
           "ReasoningReceipt", "ReasoningResult", "STRUCTURAL", "TRIGGERS", "drop_unprinted", "judgment_hold",
           "lane_for", "stable_ref", "validate_judgment"]
