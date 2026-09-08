"""Wave Z6 · seam OUT E1 — the critique endpoint's engine half (doc 06 OUT-1, DLG-10).

An external agent is about to do something. It asks GeniOS what it thinks. GeniOS scores the
proposal against **the same weights, the same corpus doctrine and the same situation evidence** its
own candidates faced, and answers `proceed`, `modify` or `hold` — **advisory, always**. The agent
executes; GeniOS never does. That asymmetry is the whole safety property of this seam and it is
enforced at the `CritiqueVerdict` constructor (Z0), not by this module's good behaviour.

WHAT MAKES THIS A CRITIQUE RATHER THAN AN OPINION
-------------------------------------------------
Everything the verdict claims is read off a **persisted, hash-verified reasoning run** for the
target — `reason/store.py`'s `load_replay_bundle`, which fails closed on a tampered payload and
refuses a run whose bounded context has been swept. So:

  * the situation's urgency and importance come from the run's own candidates — never from the
    agent, which is why `params` naming a situation term is REFUSED rather than ignored (an agent
    that could declare its own urgency could raise its own score);
  * the corpus verdicts come from the manifest's weld (`metadata["weld"]["rule_verdicts"]`), the
    same records `decision_maker` turns into `constraints_applied`;
  * the utility comes from `decision_maker.score_candidate` — literally the same function, on the
    same `ranking_weights`, with the same 70/30 override demotion;
  * the elimination is performed by `decision_maker.evaluate_candidates` — literally the same
    Decision Evaluator, so "the corpus removed the agent's action" is the same event, produced by
    the same code, as "the corpus removed one of ours".

If no such run exists, this module **refuses**. It does not reason from scratch, and it does not
answer from the proposal alone: a verdict with no situation behind it is an opinion wearing a
receipt's clothes, and doc 06 is explicit that an unscoped critique is exactly that.

WHAT THE AGENT MAY DECLARE, AND WHAT IT MAY NOT
------------------------------------------------
A proposal is not an authored play: nobody scored its impact, effort, success or risk. The agent
may declare them in `params` (`impact_bp`, `success_probability_bp`, `effort_bp`, `risk_bp`,
integer basis points, floats refused at the contract boundary). Anything it does not declare is
**ABSENT, never defaulted** — `decision_maker.effective_weights` redistributes the missing share
over the components that ARE present, exactly as doc 04 E1's honesty guard does for an absent
importance, and every absence is named in the receipt. A neutral 5,000 substituted for an
undeclared impact is the "every card scores 50" defect arriving through a new door.

The two SITUATION components — `urgency` and `importance` — are read from the run and are refused
if the agent declares them. This is the only input validation here that is a safety rule rather
than a type check.

SCOPE: WHEN DOES A CORPUS RULE APPLY TO SOMEBODY ELSE'S ACTION
---------------------------------------------------------------
A compiled rule's `when` is a predicate over the SITUATION; its scope is the plays of the
capability the doctrine governs (`rule_compiler._plays_by_capability`). So a fired blocking rule
whose scope intersects the plays THIS manifest declares is doctrine about *acting on this situation
within this capability's remit* — and an agent proposing to act on that same situation is inside
that remit. That is the mapping used here, and it is recorded on every verdict
(`receipt["rules_consulted"]`) so it can be argued with rather than assumed.

Its cost is stated rather than hidden: a rule that governs a capability blocks every proposal
against that situation, including one whose shape the doctrine would not have cared about. The
alternative — matching the proposal's `kind` against a rule's action taxonomy — cannot be built,
because the corpus has no such taxonomy: `severity`, `when`, `spans` and `owner_capability` are all
a rule declares. Over-blocking is ADVISORY and names its rule, so the agent can see it and
overrule; under-blocking is silent, and a doctrine that silently fails to apply is the defect this
whole layer exists to remove. Where a rule is UNEVALUABLE it neither fires nor blocks and is
receipted `rule_unevaluable` — L3-Y1's law, honoured at this consumer too.

THE RATIONALE, AND THE R-3 SEAM
--------------------------------
Doc 06 says the rationale is R-3-narrated and evidence-bound. R-sites are Z4's; this module takes a
`narrator` and works without one. The default rationale is composed from the receipt and is
**digit-free by construction**: every number in this answer is a typed field (`utility_bp`,
`confidence_bp`), so a sentence carrying digits could only be restating or contradicting one. A
supplied narrator is subjected to the same rule plus a grounding check (it must name something the
receipt names), and its failure is a labelled fallback, never a silent one — `rationale_source`
says which of the two the caller is reading.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

from genios_engine.contracts.reasoning import (
    TEMPLATE_FALLBACK,
    CandidateCheck,
    CandidateDisposition,
    CheckOutcome,
    CritiqueVerdict,
    ExternalCandidate,
    bare_numbers,
)
from genios_engine.reason.decision_maker import (
    FORMULA_UTILITY_COMPONENT,
    IMPORTANCE_COMPONENT,
    PRIORITY_OVERRIDE_COMPONENT,
    WELD_KEY,
    ProposedCandidate,
    effective_weights,
    evaluate_candidates,
    ranking_model_is_v2,
    score_candidate,
)
from genios_engine.reason.adapters.rule_compiler import BLOCKING, POLICY_BLOCK_REASON, WARNING
from genios_engine.reason.replay import request_from_replay_bundle
from genios_engine.reason.store import (
    ContextPayloadExpired,
    ReasoningStore,
    ReasoningStoreError,
    ReplayIntegrityError,
)

#: Bumped when anything that can change a verdict for unchanged inputs changes. It travels on every
#: receipt: an agent keeping its own record of what GeniOS told it needs to know which scorer said
#: it, and a fleet of agents comparing notes across a deploy needs it more.
CRITIQUE_VERSION = "1.0.0"

#: The evaluator id stamped on every check this seam produces. NOT `core.constraint`: that unit did
#: not run for the proposal, and a check claiming a unit that never executed is a forged receipt.
#: The reason code IS shared with it (`tenant_policy_block`), because the elimination is the same
#: event for the same reason and two vocabularies for one fact is how attribution rots.
CRITIQUE_EVALUATOR_ID = "seam.critique"

#: The check stage. `policy` is the stage `core.constraint`'s eliminations carry, and the ordering
#: `decision_maker.ordered_checks` imposes is by stage first — so a critique's checks sort exactly
#: where the same doctrine sorts on a decision.
CRITIQUE_CHECK_STAGE = "policy"

#: What the agent may declare about ITS OWN action, mapped to the ranking component it feeds.
#: The names are `PlayDefinition`'s, so an agent that reads the play contract already knows them.
DECLARABLE_COMPONENTS: Mapping[str, str] = {
    "impact": "impact_bp",
    "success": "success_probability_bp",
    "effort": "effort_bp",
    "risk": "risk_bp",
}

#: The components that belong to the SITUATION and are read from the run. An agent that could
#: declare these could raise its own score, so naming one is a refusal rather than an override.
SITUATION_COMPONENTS: tuple[str, ...] = ("urgency", IMPORTANCE_COMPONENT)

#: Every param key this seam will read. Anything else the agent sends travels through untouched
#: (it is the agent's own payload, and this endpoint is not the place to have opinions about it).
_DECLARED_KEYS = frozenset(DECLARABLE_COMPONENTS.values())
_REFUSED_KEYS = frozenset({"urgency_bp", "importance_bp", "priority_override_bp",
                           "final_utility_bp", "utility_bp", "confidence_bp"})

# ── refusal reason codes ─────────────────────────────────────────────────────────────────────
#: Nothing has ever been reasoned about this target, so there is no situation to critique against.
NO_REASONED_SITUATION = "no_reasoned_situation_for_target"
#: The run exists and its bounded context has been swept past its TTL. The digest can still say
#: what the decision saw; it cannot rebuild the request a scorer needs, so this refuses rather than
#: scoring against a reconstruction.
CONTEXT_EXPIRED = "target_context_payload_expired"
#: The run ranked nothing, so there is no field to compare a proposal against.
NO_FIELD = "target_run_ranked_no_candidates"
#: The target's capability is on the five-weight model, which cannot express an absent component:
#: `_weighted_utility`'s legacy branch reads all five directly. Scoring a proposal there would mean
#: inventing the four numbers the agent did not declare. doc 07 makes `ranking_v2` this feature's
#: precondition for exactly this reason.
RANKING_MODEL_V1 = "target_ranked_on_five_weight_model"
#: The audit row did not verify. `store` fails closed and so does this.
INTEGRITY = "target_run_failed_integrity_check"
#: The agent declared a component that belongs to the situation.
AGENT_DECLARED_SITUATION_TERM = "agent_declared_a_situation_component"

#: Why a fired blocking rule reaches a proposal at all — recorded per rule, see the module docstring.
SCOPE_REASON = "doctrine_governs_this_capability"
#: An UNKNOWN predicate neither fires nor blocks; it is recorded, and that record is the whole of it.
UNEVALUABLE_REASON = "rule_unevaluable"
#: A component the agent did not declare. Reweighed, never defaulted.
ABSENT_COMPONENT_REASON = "component_not_declared"

#: The three verdicts, restated as constants so a caller never spells one.
PROCEED, MODIFY, HOLD = "proceed", "modify", "hold"


class CritiqueRefused(Exception):
    """This seam cannot answer, and says which of the named reasons applies.

    An exception rather than a `CritiqueVerdict` carrying "we could not tell": every verdict this
    module returns is a scored claim about a real situation, and a refusal that arrived in the same
    shape as an answer would eventually be read as one.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class CritiqueOutcome:
    """The verdict and everything that produced it.

    Two objects rather than one because the verdict is the CONTRACT — the shape doc 07 prints and
    the agent's client parses — while the receipt is the argument, and an argument that had to live
    inside a closed contract would either bloat it or be dropped. Nothing in the receipt can move a
    verdict; it is the record of the verdict already reached.
    """

    verdict: CritiqueVerdict
    receipt: Mapping[str, Any] = field(default_factory=dict)


# =================================================================================================
# reading the target run
# =================================================================================================

def latest_reasoned_run(engine, *, org_id: str, target_ref: str) -> str | None:
    """The most recent completed run whose ROOT NODE is the target, or None.

    Ordered by `evaluation_time desc, run_id desc` — the second term is not decoration: two runs of
    one sweep share an evaluation time exactly, and a critique that answered from "whichever row
    the planner returned first" would be a different verdict on a re-ask with nothing changed.

    Outcomes are filtered to the three that RANKED something. A `failed` or `insufficient_context`
    run has no field, and `blocked` is kept deliberately: a run where the corpus eliminated every
    authored option is precisely the situation an agent's proposal most needs judging against.
    """
    from sqlalchemy import text

    if engine is None:
        return None
    with engine.connect() as conn:
        return conn.execute(text(
            "select rr.run_id from reasoning_runs rr "
            "join reasoning_run_outputs ro on ro.org_id=rr.org_id and ro.run_id=rr.run_id "
            "where rr.org_id=:o and rr.root_node_id=:t and rr.status='completed' "
            "and ro.outcome_kind in ('decision','blocked','defer') "
            "order by rr.evaluation_time desc, rr.run_id desc limit 1"),
            {"o": org_id, "t": target_ref}).scalar()


def load_target(store: ReasoningStore, *, org_id: str, run_id: str) -> Mapping[str, Any]:
    """The hash-verified bundle, with this seam's refusals in place of the store's exceptions."""
    try:
        bundle = store.load_replay_bundle(org_id=org_id, run_id=run_id)
    except ContextPayloadExpired as exc:
        raise CritiqueRefused(CONTEXT_EXPIRED, str(exc)) from None
    except ReplayIntegrityError as exc:
        raise CritiqueRefused(INTEGRITY, str(exc)) from None
    except ReasoningStoreError as exc:
        raise CritiqueRefused(NO_REASONED_SITUATION, str(exc)) from None
    if not bundle.get("candidates"):
        raise CritiqueRefused(NO_FIELD, run_id)
    return bundle


# =================================================================================================
# the situation's own terms, read off the run
# =================================================================================================

def candidate_rows(candidates: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    """Persisted rows and in-memory `DecisionCandidate`s, read as one shape.

    The store hands back mappings (`final_utility_bp`, `disposition` as a string) and the
    orchestrator hands back frozen dataclasses (`utility_bp`, `disposition` as an enum). Both are
    the same field, and a seam that only understood one of them would force its future in-process
    caller to serialise a decision through Postgres to ask a question about it.
    """
    rows: list[Mapping[str, Any]] = []
    for item in candidates:
        if isinstance(item, Mapping):
            rows.append(item)
            continue
        disposition = getattr(item, "disposition", None)
        rows.append({
            "play_id": getattr(item, "play_id", None),
            "disposition": getattr(disposition, "value", disposition),
            "final_utility_bp": getattr(item, "utility_bp", None),
            "score_components": dict(getattr(item, "score_components", {}) or {}),
        })
    return tuple(rows)


def situation_terms(candidates: Sequence[Mapping[str, Any]]) -> tuple[dict[str, int], int | None]:
    """`{urgency, importance}` and the priority override, as this run scored its own field.

    Taken from the persisted candidates rather than recomputed, because they are what the decision
    was actually made with — and read across ALL of them with an equality check rather than off the
    first, because `synthesize_candidates` gives every candidate of a run the same situation terms
    by construction. If that ever stops being true the assumption fails loudly here instead of
    silently picking one candidate's urgency to judge a stranger's action by.
    """
    terms: dict[str, int] = {}
    override: int | None = None
    for name in (*SITUATION_COMPONENTS, PRIORITY_OVERRIDE_COMPONENT):
        seen = {int(row["score_components"][name]) for row in candidates
                if name in (row.get("score_components") or {})}
        if not seen:
            continue
        if len(seen) > 1:
            raise CritiqueRefused(
                NO_FIELD, f"the run's candidates disagree about {name}: {sorted(seen)}")
        value = seen.pop()
        if name == PRIORITY_OVERRIDE_COMPONENT:
            override = value
        else:
            terms[name] = value
    return terms, override


def declared_terms(proposal: ExternalCandidate) -> tuple[dict[str, int], tuple[str, ...]]:
    """What the agent said about its own action, and what it left unsaid.

    `require_bp` is not called here: `ExternalCandidate.params` has already been through
    `canonicalize`, which refuses a float outright, and the range check belongs to the same place
    the type check does. What IS enforced here is the boundary — an agent declaring a situation
    term is refused, loudly, rather than having its number quietly dropped.
    """
    params = proposal.params or {}
    trespass = sorted(set(params) & _REFUSED_KEYS)
    if trespass:
        raise CritiqueRefused(
            AGENT_DECLARED_SITUATION_TERM,
            f"{trespass} belong to the situation and are read from its reasoning run")
    declared: dict[str, int] = {}
    absent: list[str] = []
    for component, key in DECLARABLE_COMPONENTS.items():
        raw = params.get(key)
        if raw is None:
            absent.append(f"{ABSENT_COMPONENT_REASON}:{component}")
            continue
        if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 10_000:
            raise CritiqueRefused(
                AGENT_DECLARED_SITUATION_TERM,
                f"{key} must be integer basis points between 0 and 10000, got {raw!r}")
        declared[component] = raw
    return declared, tuple(sorted(absent))


# =================================================================================================
# the corpus, applied to somebody else's action
# =================================================================================================

def _weld(capability) -> Mapping[str, Any]:
    weld = capability.metadata.get(WELD_KEY)
    return weld if isinstance(weld, Mapping) else {}


def rules_against(capability, proposal_id: str) -> tuple[tuple[CandidateCheck, ...],
                                                         tuple[Mapping[str, Any], ...]]:
    """The compiled corpus, read as checks against ONE external proposal.

    Returns the eliminating checks and the full consultation record — every rule the manifest
    carries, whether it fired, whether it reached this proposal, and why. The record is returned in
    full rather than filtered because "no rule blocked you" and "no rule could be evaluated" are
    different answers and an agent acting on the first when the second is true is acting on silence.
    """
    declared = {play.play_id for play in capability.plays}
    checks: list[CandidateCheck] = []
    consulted: list[dict[str, Any]] = []
    for verdict in _weld(capability).get("rule_verdicts") or ():
        if not isinstance(verdict, Mapping):
            continue
        severity = str(verdict.get("severity") or "")
        outcome = str(verdict.get("outcome") or "")
        scope = set(verdict.get("blocked_play_ids") or ()) | set(
            verdict.get("warned_play_ids") or ())
        governs = bool(scope & declared)
        record = {
            "rule_id": str(verdict.get("rule_id") or ""),
            "severity": severity,
            "outcome": outcome,
            "statement": str(verdict.get("statement") or ""),
            "statement_hash": str(verdict.get("statement_hash") or ""),
            "source_ref": str(verdict.get("source_ref") or ""),
            "owner_capability": str(verdict.get("owner_capability") or ""),
            "scope_play_ids": sorted(scope & declared),
            "applies": False,
            "reason": "",
        }
        if outcome == "unevaluable":
            record["reason"] = UNEVALUABLE_REASON
            record["missing"] = list(verdict.get("missing") or ())
        elif outcome != "fired":
            record["reason"] = "rule_satisfied"
        elif not governs:
            record["reason"] = "doctrine_governs_another_capability"
        else:
            record["applies"] = True
            record["reason"] = SCOPE_REASON
            if severity == BLOCKING:
                checks.append(CandidateCheck(
                    play_id=proposal_id,
                    stage=CRITIQUE_CHECK_STAGE,
                    outcome=CheckOutcome.ELIMINATE,
                    reason_code=POLICY_BLOCK_REASON,
                    evaluator_id=CRITIQUE_EVALUATOR_ID,
                    evaluator_version=CRITIQUE_VERSION,
                    detail={"rule_id": record["rule_id"], "severity": severity,
                            "statement": record["statement"],
                            "statement_hash": record["statement_hash"],
                            "source_ref": record["source_ref"],
                            "scope_play_ids": record["scope_play_ids"],
                            "scope_reason": SCOPE_REASON}))
            elif severity != WARNING:            # an unknown severity annotates and never blocks
                record["applies"] = False
                record["reason"] = f"unknown_severity_{severity or 'unstated'}"
        consulted.append(record)
    consulted.sort(key=lambda item: (item["rule_id"], item["statement_hash"]))
    return tuple(checks), tuple(consulted)


# =================================================================================================
# scoring — the same scorer, on the same weights
# =================================================================================================

@dataclass(frozen=True, slots=True)
class _ProposalPlay:
    """The shape `evaluate_candidates` reads off a candidate: an id and a version.

    A stand-in for a `PlayDefinition` and deliberately NOT one: an external proposal is not an
    authored play, and constructing one would put an agent's draft into the type the action space
    is closed to. What this exists for is to run the proposal through the REAL Decision Evaluator
    rather than through a copy of its rule.
    """

    play_id: str
    version: str = CRITIQUE_VERSION


def score_proposal(request: Any, *, situation: Mapping[str, int], declared: Mapping[str, int],
                   override: int | None) -> tuple[int, dict[str, int], Mapping[str, int]]:
    """The proposal's utility, through `decision_maker.score_candidate` itself.

    The override travels with it. That looks odd for a candidate the corpus never authored, and it
    is the only choice that keeps the answer meaningful: the authored plays this proposal is being
    compared against were all scored WITH the corpus's authored priority as a 70/30 prior, so
    dropping it here would compare two numbers produced by two different models and call the
    difference a judgement about the draft.
    """
    if not ranking_model_is_v2(request):
        raise CritiqueRefused(
            RANKING_MODEL_V1,
            f"{request.capability.capability_id}@{request.capability.version}")
    components: dict[str, int] = {**situation, **declared}
    utility = score_candidate(request, components, override)
    weights = effective_weights(request.capability.ranking_weights, components)
    return utility, components, weights


def best_authored(candidates: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The run's own winner among the candidates that survived its checks.

    `rank_candidates`' total order, restated over persisted rows: utility descending, play id
    ascending. Eliminated candidates are excluded — an option the corpus removed is not an
    alternative we may offer an agent, and offering one would be this seam handing back the exact
    action Layer 3 refused.
    """
    eligible = [row for row in candidates
                if str(row.get("disposition")) == CandidateDisposition.ELIGIBLE.value]
    if not eligible:
        return None
    return sorted(eligible, key=lambda row: (-int(row["final_utility_bp"]),
                                             str(row["play_id"])))[0]


# =================================================================================================
# the answer
# =================================================================================================

def _sentence(text_: str) -> str:
    """The authored statement's first sentence, for a rationale that quotes rather than paraphrases."""
    head = text_.strip().split(". ")[0].strip()
    return head if head.endswith(".") else f"{head}."


def compose_rationale(*, verdict: str, applied: Sequence[Mapping[str, Any]],
                      warnings: Sequence[Mapping[str, Any]],
                      unevaluable: Sequence[Mapping[str, Any]],
                      alternative: str | None, absent: Sequence[str]) -> str:
    """The deterministic rationale: evidence-bound, digit-free, and never a paraphrase of doctrine.

    Digit-free is a rule and not a habit — every number in this answer is a typed field, so a digit
    in the prose can only restate one (noise) or disagree with one (a bug that reads as a sentence).
    `bare_numbers` from the bundle contract is the same check Z4's gauntlet runs, reused here rather
    than re-implemented.
    """
    parts: list[str] = []
    if verdict == HOLD:
        rules = ", ".join(item["rule_id"] for item in applied)
        parts.append(f"Hold. Authored doctrine blocks this action in this situation: {rules}.")
        parts.extend(_sentence(item["statement"]) for item in applied if item.get("statement"))
    elif verdict == MODIFY and alternative is not None:
        parts.append("Modify. An authored play scores higher than this proposal against the same "
                     f"situation evidence: {alternative}.")
    elif verdict == MODIFY:
        parts.append("Modify. No rule blocks this action, and authored doctrine cautions against "
                     "it here.")
    else:
        parts.append("Proceed. No authored rule blocks this action in this situation, and no "
                     "authored play outscores it against the same evidence.")
    if warnings:
        cautions = ", ".join(item["rule_id"] for item in warnings)
        parts.append(f"Cautioned by: {cautions}.")
    if unevaluable:
        names = ", ".join(item["rule_id"] for item in unevaluable)
        parts.append(f"Could not be evaluated on this situation and therefore neither fired nor "
                     f"passed: {names}.")
    if absent:
        missing = ", ".join(sorted(item.split(":", 1)[1] for item in absent))
        parts.append(f"Scored without a declared {missing}; the remaining weights were "
                     "redistributed rather than a neutral value assumed.")
    return " ".join(parts)


def unquoted_numbers(text_: str, grounds: Sequence[str]) -> tuple[str, ...]:
    """Digit runs in a rationale that are NOT part of something it quotes.

    The rule is "no COMPUTED number in the prose", not "no digit": every number this seam computes
    is a typed field (`utility_bp`, `confidence_bp`), so a digit in a sentence can only restate one
    (noise) or disagree with one (a bug that reads as a sentence). But a rule id or an authored
    statement may legitimately contain a digit, and refusing those would forbid quoting doctrine
    accurately — which is the one thing this rationale exists to do. So the grounds are removed
    first and `bare_numbers` — V-4's own detector, reused rather than re-implemented — is asked
    about what is left.
    """
    remainder = str(text_ or "")
    for ground in sorted((item for item in grounds if item), key=len, reverse=True):
        remainder = remainder.replace(ground, " ")
    return bare_numbers(remainder)


def _narrated(narrator: Callable[[Mapping[str, Any]], str] | None,
              receipt: Mapping[str, Any], grounds: Sequence[str]) -> tuple[str | None, str]:
    """R-3's seam. A narrator that fails ANY check is a labelled fallback, never a silent one.

    Three checks, in order, and none of them is about style: it must produce prose at all, it must
    not invent a number, and it must NAME something the receipt names. The third is the grounding
    check — a fluent paragraph about a situation, containing no rule id and no play id, is exactly
    the output this layer is being rebuilt to stop shipping.
    """
    if narrator is None:
        return None, TEMPLATE_FALLBACK
    try:
        text_ = narrator(receipt)
    except Exception:                                  # noqa: BLE001 — a model is not a dependency
        return None, TEMPLATE_FALLBACK
    if not isinstance(text_, str) or not text_.strip():
        return None, TEMPLATE_FALLBACK
    if unquoted_numbers(text_, grounds):
        return None, TEMPLATE_FALLBACK
    if not any(ground and ground in text_ for ground in grounds):
        return None, TEMPLATE_FALLBACK
    return text_.strip(), f"llm:{getattr(narrator, 'generation', 'unnamed')}"


def critique_proposal(*, request: Any, candidates: Sequence[Mapping[str, Any]],
                      confidence_bp: int, proposal: ExternalCandidate,
                      narrator: Callable[[Mapping[str, Any]], str] | None = None,
                      ) -> CritiqueOutcome:
    """Score one external proposal against one reasoned situation. Pure: no clock, no database.

    The order is the decision maker's own and the order is the safety property, exactly as it is in
    `build_candidates`: checks are applied BEFORE anything is compared on score, so an action the
    corpus forbids can never be recommended and then quietly demoted.
    """
    rows = candidate_rows(candidates)
    situation, override = situation_terms(rows)
    declared, absent = declared_terms(proposal)
    utility_bp, components, weights = score_proposal(
        request, situation=situation, declared=declared, override=override)

    checks, consulted = rules_against(request.capability, proposal.proposal_id)
    judged = evaluate_candidates(
        (ProposedCandidate(play=_ProposalPlay(proposal.proposal_id), components=components,
                           utility_bp=utility_bp),),
        checks)[0]

    applied = [item for item in consulted if item["applies"] and item["severity"] == BLOCKING]
    warnings = [item for item in consulted if item["applies"] and item["severity"] == WARNING]
    unevaluable = [item for item in consulted if item["reason"] == UNEVALUABLE_REASON]
    winner = best_authored(rows)
    outscored = (winner is not None
                 and (-int(winner["final_utility_bp"]), str(winner["play_id"]))
                 < (-utility_bp, proposal.proposal_id))

    if judged.disposition == CandidateDisposition.ELIMINATED:
        verdict_name, alternative = HOLD, (str(winner["play_id"]) if winner is not None else None)
    elif outscored:
        verdict_name, alternative = MODIFY, str(winner["play_id"])
    elif warnings:
        verdict_name, alternative = MODIFY, None
    else:
        verdict_name, alternative = PROCEED, None

    failing = tuple(item["rule_id"] for item in applied)
    receipt: dict[str, Any] = {
        "critique_version": CRITIQUE_VERSION,
        "capability_id": request.capability.capability_id,
        "capability_version": request.capability.version,
        "context_snapshot_id": request.context.context_snapshot_id,
        "ranking_weights_version": request.capability.ranking_weights_version,
        "components": dict(sorted(components.items())),
        "effective_weights": dict(sorted(weights.items())),
        "absent_components": list(absent),
        "formula_utility_bp": components.get(FORMULA_UTILITY_COMPONENT),
        "priority_override_bp": override,
        "rules_consulted": [dict(item) for item in consulted],
        "eliminating_checks": [
            {"rule_id": check.detail.get("rule_id"), "reason_code": check.reason_code,
             "evaluator_id": check.evaluator_id, "stage": check.stage,
             "scope_play_ids": list(check.detail.get("scope_play_ids") or ())}
            for check in checks],
        "best_authored": (None if winner is None else
                          {"play_id": str(winner["play_id"]),
                           "utility_bp": int(winner["final_utility_bp"])}),
        "proposal": {"proposal_id": proposal.proposal_id, "agent_id": proposal.agent_id,
                     "kind": proposal.kind, "target_ref": proposal.target_ref,
                     "draft_chars": len(proposal.draft)},
    }
    # Everything the rationale may legitimately quote: the ids it names and the authored words it
    # reproduces. Used twice — to let a quoted statement carry its own digits, and as the grounding
    # set a narrator must land inside.
    grounds = ([item["rule_id"] for item in applied + warnings + unevaluable]
               + [item["statement"] for item in applied]
               + [alternative or ""])
    narrated, source = _narrated(narrator, receipt, grounds)
    rationale = narrated or compose_rationale(
        verdict=verdict_name, applied=applied, warnings=warnings, unevaluable=unevaluable,
        alternative=alternative, absent=absent)
    receipt["rationale_source"] = source

    verdict = CritiqueVerdict(
        verdict=verdict_name,
        failing_checks=failing,
        # A hold names the doctrine, never an alternative it did not clear. The winner of a field
        # where every option was eliminated is nothing, and on a `hold` the surviving authored play
        # is the one thing an agent could safely be pointed at — so it travels on `hold` only when
        # one actually survived, and never on a `proceed` that outranked it.
        winning_alternative=(alternative if verdict_name in (HOLD, MODIFY) else None),
        utility_bp=utility_bp,
        confidence_bp=confidence_bp,
        rationale=rationale)
    return CritiqueOutcome(verdict=verdict, receipt=receipt)


def critique_target(*, store: ReasoningStore, org_id: str, proposal: ExternalCandidate,
                    narrator: Callable[[Mapping[str, Any]], str] | None = None,
                    ) -> CritiqueOutcome:
    """The whole seam: resolve the target's run, verify it, and score the proposal against it."""
    run_id = latest_reasoned_run(store.engine, org_id=org_id, target_ref=proposal.target_ref)
    if run_id is None:
        raise CritiqueRefused(NO_REASONED_SITUATION, proposal.target_ref)
    bundle = load_target(store, org_id=org_id, run_id=run_id)
    request = request_from_replay_bundle(bundle)
    output = bundle.get("output") or {}
    outcome = critique_proposal(
        request=request, candidates=bundle["candidates"],
        confidence_bp=int(output.get("confidence_bp") or 0),
        proposal=proposal, narrator=narrator)
    receipt = dict(outcome.receipt)
    receipt["evidence"] = {
        "run_id": run_id,
        "decision_id": ((output.get("decision_core") or {}).get("contract_decision_id")),
        "decision_hash": output.get("decision_hash"),
        "outcome_kind": output.get("outcome_kind"),
        "evaluation_time": str(bundle["run"]["evaluation_time"]),
        "replay_mode": bundle.get("replay_mode"),
    }
    return CritiqueOutcome(verdict=outcome.verdict, receipt=receipt)


__all__ = ["ABSENT_COMPONENT_REASON", "AGENT_DECLARED_SITUATION_TERM", "CONTEXT_EXPIRED",
           "CRITIQUE_CHECK_STAGE", "CRITIQUE_EVALUATOR_ID", "CRITIQUE_VERSION",
           "DECLARABLE_COMPONENTS", "HOLD", "INTEGRITY", "MODIFY", "NO_FIELD",
           "NO_REASONED_SITUATION", "PROCEED", "RANKING_MODEL_V1", "SCOPE_REASON",
           "SITUATION_COMPONENTS", "UNEVALUABLE_REASON", "CritiqueOutcome", "CritiqueRefused",
           "best_authored", "candidate_rows", "compose_rationale", "critique_proposal", "critique_target",
           "declared_terms", "latest_reasoned_run", "load_target", "rules_against",
           "score_proposal", "situation_terms", "unquoted_numbers"]
