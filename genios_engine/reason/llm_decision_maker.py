"""Layer 4 · Part 3, TEST MODE — the Decision Maker as a language model.

**What this replaces, and only while switched on.** `decision_maker.DecisionMaker.decide` is fully
deterministic: Rule 11 composes the confidence, a weighted formula (plus the 70/30 corpus prior)
scores every play, the ranker orders them, the 4,500 bp floor turns thin decisions into DEFER, and
a rule conflict abstains. With `GENIOS_L4_LLM_DECISION_MAKER=true` all of that judgement is handed
to one model call per decision instead:

* **the model decides** — act now (DECISION) or not yet (DEFER), how good each play is (its
  utility), and how sure it is (confidence). Rank follows the model's scores.
* **what stays deterministic is not judgement** — the units' own findings, the play list the
  corpus authored, and the plays a unit's hard policy check ELIMINATED (consent, read-only, a
  blocking rule). The model is shown those, and it cannot select one: the contract refuses an
  eliminated winner, and the store refuses a winner without its passing policy check.

The deterministic code is untouched and still runs whenever the switch is off, for every org not
listed in `GENIOS_L4_LLM_DECISION_MAKER_ORGS`, and for every terminal run (a gate miss, a required
unit that failed, missing required context — facts about execution, decided by the orchestrator).

**Failure is DEFER, never the formula.** A missing key, an exhausted budget, a network error or an
answer that fails validation after one corrected retry all DEFER with a reason code. Falling back
to the formula would make a test of "what does the model decide" silently measure the formula.

Every candidate this module builds carries `score_components["llm_utility"]`. That key is how
`reason/store.py` recognises an LLM-made decision and skips only its "re-derive the rank from the
formula" check — a check that by definition cannot pass for a decision the formula did not make.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    CheckOutcome,
    DecisionOutcome,
    ReasonerResult,
    ReasoningDecision,
)
from genios_engine.platform.canonical import semantic_hash

_log = logging.getLogger(__name__)

#: Bumped whenever the prompt or the answer schema changes; it is inside the cache key.
PROMPT_VERSION = "l4-llm-decision.v1"

#: The score component every LLM-built candidate carries. `reason/store.py` reads it.
LLM_UTILITY_COMPONENT = "llm_utility"

#: Uncertainty codes, written only on DEFER — a DEFER never becomes a card.
LLM_DEFERRED_REASON = "llm_deferred"
LLM_UNAVAILABLE_REASON = "llm_decision_unavailable"

#: `llm_costs.purpose` for every call this module makes.
COST_PURPOSE = "l4_llm_decision"

_MAX_TOKENS = 900
_CACHE_CAP = 4_096
_RATIONALE_CAP = 600

_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_calls_by_org_day: dict[tuple[str, str], int] = {}
_lock = threading.Lock()
_cost_store: Any = None


# =================================================================================================
# THE SWITCH
# =================================================================================================

def _settings():
    from genios_engine.platform.config import get_settings
    return get_settings()


def enabled_for(org_id: str) -> bool:
    """Is the LLM decision maker on for this org? Off unless the switch says otherwise."""
    try:
        settings = _settings()
    except Exception:      # noqa: BLE001 — no settings means no switch, means the formula
        return False
    if not getattr(settings, "l4_llm_decision_maker", False):
        return False
    allowed = {item.strip() for item in
               str(getattr(settings, "l4_llm_decision_maker_orgs", "") or "").split(",")
               if item.strip()}
    return not allowed or str(org_id) in allowed


_clients: dict[tuple[str, str], Any] = {}

#: Models that REJECT sampling parameters with a 400 (Sonnet 5, Opus 5 / 4.8 / 4.7, Fable).
#: `context/llm/client.LLMClient` always sends `temperature=0`, which is right for Haiku and would
#: turn every decision on these models into a DEFER, so decisions use their own thin client.
_NO_SAMPLING_PREFIXES = ("claude-sonnet-5", "claude-opus-5", "claude-opus-4-8",
                         "claude-opus-4-7", "claude-fable")


def request_kwargs(model: str) -> dict[str, Any]:
    """The model-specific part of one decision request.

    Newer models: no sampling parameters, and thinking OFF — the answer is a small JSON object
    and thinking tokens would be billed without being read (Fable cannot disable it, so it is
    left to its default there). Haiku-class: `temperature=0`, as every other engine call.
    """
    if str(model).startswith(_NO_SAMPLING_PREFIXES):
        return {} if str(model).startswith("claude-fable") else {"thinking": {"type": "disabled"}}
    return {"temperature": 0}


class DecisionClient:
    """The Anthropic call for decisions. Same `.model` / `.call()` shape as `LLMClient`."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model
        self._client: Any = None

    def call(self, prompt: str, *, max_tokens: int = 900):
        from genios_engine.context.llm.client import LLMResult
        from genios_engine.context.llm.parse import parse_json_lenient, strip_code_fence
        try:
            if self._client is None:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self._api_key, timeout=60.0, max_retries=2)
            resp = self._client.messages.create(
                model=self.model, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}], **request_kwargs(self.model))
        except Exception as exc:      # noqa: BLE001 — surfaced as a failed result, never raised
            return LLMResult(parsed={}, raw="", ok=False, error=str(exc)[:400], model=self.model)
        raw = strip_code_fence("".join(b.text for b in resp.content
                                       if getattr(b, "type", None) == "text").strip())
        it = getattr(resp.usage, "input_tokens", 0)
        ot = getattr(resp.usage, "output_tokens", 0)
        parsed = parse_json_lenient(raw)
        if parsed is None:
            return LLMResult(parsed={}, raw=raw, input_tokens=it, output_tokens=ot,
                             model=self.model, ok=False, error="unparseable JSON")
        return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                         model=self.model)


def client():
    """The Anthropic client for decisions, or None when no key is configured.

    One per (key, model) for the life of the process, so a sweep of hundreds of decisions reuses
    one connection pool instead of opening one per decision.
    """
    try:
        settings = _settings()
        if not getattr(settings, "use_real_llm", False) or not settings.anthropic_api_key:
            return None
        model = (str(getattr(settings, "l4_llm_decision_model", "") or "").strip()
                 or settings.anthropic_model)
        key = (settings.anthropic_api_key, model)
        with _lock:
            if key not in _clients:
                _clients[key] = DecisionClient(api_key=settings.anthropic_api_key, model=model)
            return _clients[key]
    except Exception:      # noqa: BLE001 — an unbuildable client is a DEFER, not a crash
        _log.exception("could not build the L4 LLM decision client")
        return None


def _daily_cap() -> int:
    try:
        return int(getattr(_settings(), "l4_llm_decision_max_calls_per_org_day", 400) or 0)
    except Exception:      # noqa: BLE001
        return 400


def _take_budget(org_id: str) -> bool:
    """One call from this org's in-process daily allowance. 0 = unlimited."""
    cap = _daily_cap()
    day = datetime.now(timezone.utc).date().isoformat()
    with _lock:
        key = (str(org_id), day)
        used = _calls_by_org_day.get(key, 0)
        if cap > 0 and used >= cap:
            return False
        _calls_by_org_day[key] = used + 1
        return True


def _record_cost(*, org_id: str, model: str, subject_ref: str, input_tokens: int,
                 output_tokens: int, success: bool, error: str | None) -> None:
    """Into `llm_costs`, like every other call in the engine. Never fails the decision."""
    global _cost_store
    try:
        if _cost_store is None:
            from genios_engine.platform.wiring import make_graph_store
            _cost_store = make_graph_store() or False
        if not _cost_store:
            return
        _cost_store.record_cost(org_id=org_id, model=model, purpose=COST_PURPOSE,
                                input_tokens=int(input_tokens or 0),
                                output_tokens=int(output_tokens or 0),
                                success=success, error=error, subject_ref=subject_ref)
    except Exception:      # noqa: BLE001
        _log.exception("could not record L4 LLM decision cost for org=%s", org_id)


# =================================================================================================
# WHAT THE MODEL IS SHOWN
# =================================================================================================

def _short(value: Any, limit: int = 240) -> str:
    try:
        text = value if isinstance(value, str) else json.dumps(value, default=str,
                                                               ensure_ascii=False)
    except Exception:      # noqa: BLE001
        text = str(value)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fact_value(record: Any) -> Any:
    if isinstance(record, Mapping):
        for key in ("value", "value_bp"):
            if key in record:
                return record[key]
    return record


def _facts_block(facts: Mapping[str, Any], cap: int) -> list[str]:
    lines = [f"- {name}: {_short(_fact_value(facts[name]))}" for name in sorted(facts)]
    if len(lines) > cap:
        lines = lines[:cap] + [f"- … {len(facts) - cap} more facts not shown"]
    return lines or ["- (none)"]


def _units_block(results: Sequence[ReasonerResult]) -> list[str]:
    lines = []
    for result in results:
        status = result.status.value
        head = f"- {result.reasoner_id} [{status}]"
        if result.matched is not None:
            head += f" matched={str(result.matched).lower()}"
        parts = [head]
        metrics = {k: v for k, v in result.metrics.items()
                   if isinstance(v, (int, float, str, bool)) and not isinstance(v, bool)}
        if metrics:
            parts.append("metrics " + _short(dict(list(sorted(metrics.items()))[:14]), 400))
        if result.findings:
            parts.append("findings " + _short([
                {"kind": item.kind, **({"value_bp": item.value_bp}
                                       if item.value_bp is not None else {}),
                 **({"reasons": list(item.reason_codes)} if item.reason_codes else {})}
                for item in result.findings[:8]], 400))
        if result.reason_codes:
            parts.append("reasons " + _short(list(result.reason_codes)[:8], 200))
        if result.missing_fields:
            parts.append("missing " + _short(list(result.missing_fields)[:8], 200))
        lines.append("; ".join(parts))
    return lines or ["- (no units ran)"]


def _plays_block(proposals: Sequence[Any]) -> list[str]:
    lines = []
    for item in proposals:
        play = item.play
        eliminated = item.disposition == CandidateDisposition.ELIMINATED
        why = sorted({check.reason_code for check in item.checks
                      if check.outcome == CheckOutcome.ELIMINATE})
        lines.append(
            f"- play_id={play.play_id} | {play.label} | steps: {_short(list(play.steps), 300)}"
            f" | authored impact={play.impact_bp} success={play.success_probability_bp}"
            f" effort={play.effort_bp} risk={play.risk_bp} (basis points, 0-10000)"
            + (f" | ELIMINATED by a hard policy check ({', '.join(why)}) — you may not choose it"
               if eliminated else ""))
    return lines


def build_prompt(request: Any, results: Sequence[ReasonerResult], proposals: Sequence[Any],
                 uncertainty: Sequence[str], degraded: bool, importance_bp: int | None,
                 feedback: str | None = None) -> str:
    capability = request.capability
    context = request.context
    metadata = capability.metadata
    weld = metadata.get("weld") or {}
    situation = str(metadata.get("situation_type") or capability.capability_id)
    citations = [_short({"rule": c.get("rule_id") or c.get("claim_id"),
                         "quote": c.get("quote") or c.get("text")}, 300)
                 for c in (weld.get("citations") or ())[:6] if isinstance(c, Mapping)]
    conflicts = [_short({k: c.get(k) for k in ("left", "right", "left_role", "right_role")}, 200)
                 for c in (weld.get("conflicts") or ())[:4] if isinstance(c, Mapping)]
    eligible_ids = [item.play.play_id for item in proposals
                    if item.disposition == CandidateDisposition.ELIGIBLE]

    sections = [
        "You are the decision maker of GeniOS, an intelligence layer that tells a business owner "
        "what to do next. Other units have already analysed ONE situation. You decide.",
        "",
        "Decide two things:",
        "1. outcome — \"decision\" if the business should act on this now and the evidence is "
        "strong enough to put it in front of a busy person; \"defer\" if it is too thin, too "
        "stale, already handled, not worth their attention, or a human must supply something "
        "first.",
        "2. For EVERY eligible play, a utility score 0-10000: how good that move is for this "
        "situation right now. The highest-scoring play is the one recommended.",
        "Also give confidence_bp 0-10000: how sure you are this is right, given the evidence.",
        "",
        "Rules: judge only from what is written below. Do not invent facts, people, dates or "
        "amounts. Low confidence and thin evidence mean defer.",
        "",
        f"SITUATION: {situation}",
        f"capability: {capability.capability_id}@{capability.version} (domain {capability.domain})",
        f"goal: {_short(capability.goal.statement, 300)}",
        f"subject: {context.root_entity_type} {context.root_entity_id}",
        f"evaluated at: {request.evaluation_time.isoformat()}",
        f"if nobody acts: {_short(capability.do_nothing_consequence, 300)}",
    ]
    if importance_bp is not None:
        sections.append(f"situation importance measured upstream: {importance_bp} / 10000")
    sections += ["", "FACTS ABOUT THE SUBJECT:", *_facts_block(context.facts, 60)]
    if context.neighbor_facts:
        sections += ["", "FACTS ABOUT RELATED PEOPLE / THREADS:",
                     *_facts_block(context.neighbor_facts, 30)]
    if context.observations:
        sections += ["", "RECENT OBSERVATIONS:",
                     *[f"- {_short(item, 300)}" for item in context.observations[:15]]]
    sections += ["", "WHAT THE ANALYSIS UNITS FOUND:", *_units_block(results)]
    if citations:
        sections += ["", "AUTHORED EXPERT RULES THAT APPLY:", *[f"- {c}" for c in citations]]
    if conflicts:
        sections += ["", "AUTHORED RULES THAT CONTRADICT EACH OTHER HERE:",
                     *[f"- {c}" for c in conflicts]]
    gaps = sorted(set(context.missing_fields) | set(uncertainty))
    if gaps or degraded:
        sections += ["", "KNOWN GAPS:", *[f"- {_short(g, 160)}" for g in gaps[:20]]]
        if degraded:
            sections.append("- an optional analysis unit failed, so the picture is incomplete")
    sections += ["", "PLAYS YOU CAN RECOMMEND:", *_plays_block(proposals), "",
                 "Answer with ONLY this JSON object, no prose around it:",
                 json.dumps({
                     "outcome": "decision | defer",
                     "scores": {play_id: "<int 0-10000>" for play_id in eligible_ids},
                     "confidence_bp": "<int 0-10000>",
                     "rationale": "<one or two plain sentences: why this outcome and play>",
                     "missing": ["<what would change your mind, if anything>"],
                 }, ensure_ascii=False)]
    prompt = "\n".join(sections)
    if feedback:
        prompt += f"\n\nCORRECTION — your previous answer was refused. {feedback}"
    return prompt


# =================================================================================================
# WHAT THE MODEL MUST ANSWER
# =================================================================================================

class _Refused(Exception):
    pass


def _bp(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise _Refused(f"{label} must be an integer 0-10000, not a boolean")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not 0 <= value <= 10_000:
        raise _Refused(f"{label} must be an integer 0-10000")
    return value


def parse_answer(parsed: Mapping[str, Any], eligible_ids: Sequence[str]) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        raise _Refused("answer must be a JSON object")
    outcome = str(parsed.get("outcome") or "").strip().lower()
    if outcome not in {"decision", "defer"}:
        raise _Refused('outcome must be exactly "decision" or "defer"')
    scores = parsed.get("scores")
    if not isinstance(scores, Mapping):
        raise _Refused("scores must be an object keyed by play_id")
    if set(scores) != set(eligible_ids):
        raise _Refused(f"scores must have exactly these play_ids: {sorted(eligible_ids)}")
    clean_scores = {str(k): _bp(v, f"scores.{k}") for k, v in scores.items()}
    confidence = _bp(parsed.get("confidence_bp"), "confidence_bp")
    rationale = _short(parsed.get("rationale") or "", _RATIONALE_CAP)
    missing = parsed.get("missing") or []
    if not isinstance(missing, (list, tuple)):
        missing = [missing]
    missing = [_short(item, 160) for item in missing if str(item or "").strip()][:6]
    return {"outcome": outcome, "scores": clean_scores, "confidence_bp": confidence,
            "rationale": rationale, "missing": missing}


# =================================================================================================
# THE DECISION
# =================================================================================================

def _cache_key(request: Any, results: Sequence[ReasonerResult], uncertainty: Sequence[str],
               degraded: bool, model: str) -> str:
    """What the decision is ABOUT — never how the run was invoked.

    `request.semantic_hash` would be the obvious key and is wrong: a replay rebuilds the request
    with `mode=REPLAY` and no `request_id`, so the hash moves while the situation does not, the
    replay pays for a second call, and a model that answers even slightly differently turns an
    honest run into a replay mismatch. Only what the model is shown (and which model) is keyed.
    """
    return semantic_hash({"prompt": PROMPT_VERSION, "model": model,
                          "org_id": str(request.org_id),
                          "capability": request.capability.capability_snapshot_id,
                          "context": request.context.context_snapshot_id,
                          "evaluation_time": request.evaluation_time,
                          "results": [item.semantic_hash for item in results],
                          "uncertainty": sorted(set(str(u) for u in uncertainty)),
                          "degraded": bool(degraded)})


def _consult(request: Any, results: Sequence[ReasonerResult], proposals: Sequence[Any],
             uncertainty: Sequence[str], degraded: bool, importance_bp: int | None,
             llm: Any) -> tuple[dict[str, Any] | None, str | None]:
    """The model's validated answer, or (None, reason code)."""
    if llm is None:
        return None, "no_client"
    eligible_ids = [item.play.play_id for item in proposals
                    if item.disposition == CandidateDisposition.ELIGIBLE]
    model = str(getattr(llm, "model", "") or "unknown")
    key = _cache_key(request, results, uncertainty, degraded, model)
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return dict(hit), None
    if not _take_budget(request.org_id):
        return None, "daily_call_cap"

    subject_ref = (f"capability:{request.capability.capability_id}:"
                   f"{request.context.root_entity_id}")
    feedback: str | None = None
    last_reason = "no_answer"
    for _attempt in range(2):
        prompt = build_prompt(request, results, proposals, uncertainty, degraded,
                              importance_bp, feedback)
        try:
            res = llm.call(prompt, max_tokens=_MAX_TOKENS)
        except Exception as exc:      # noqa: BLE001 — a transport failure is a DEFER
            _record_cost(org_id=request.org_id, model=model, subject_ref=subject_ref,
                         input_tokens=0, output_tokens=0, success=False, error=str(exc)[:300])
            return None, "call_failed"
        _record_cost(org_id=request.org_id, model=model, subject_ref=subject_ref,
                     input_tokens=getattr(res, "input_tokens", 0),
                     output_tokens=getattr(res, "output_tokens", 0),
                     success=bool(getattr(res, "ok", False)),
                     error=getattr(res, "error", None))
        if not getattr(res, "ok", False):
            last_reason = "call_failed" if not getattr(res, "raw", "") else "unparseable"
            if last_reason == "call_failed":
                return None, last_reason
            feedback = "Your previous answer was not valid JSON. Return only the JSON object."
            continue
        try:
            answer = parse_answer(res.parsed, eligible_ids)
        except _Refused as refusal:
            last_reason = "invalid_answer"
            feedback = f"{refusal}. Follow the requested JSON shape exactly."
            continue
        answer["model"] = model
        with _lock:
            _cache[key] = dict(answer)
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_CAP:
                _cache.popitem(last=False)
        return answer, None
    return None, last_reason


def decide_with_llm(request: Any, results: Sequence[ReasonerResult], *,
                    uncertainty: Sequence[str], degraded: bool, llm: Any):
    """The LLM-made synthesis for one NON-terminal run. Same output type as the formula's."""
    from genios_engine.reason.adapters.rule_compiler import constraint_applications
    from genios_engine.reason import decision_maker as dm

    uncertainty = list(uncertainty)
    weld = request.capability.metadata.get(dm.WELD_KEY) or {}
    ranking_v2 = dm.ranking_model_is_v2(request)
    importance_bp = None
    if ranking_v2:
        importance_bp, importance_absent = dm.situation_importance(request)
        if importance_absent is not None:
            uncertainty.append(importance_absent)

    # The play field and the hard eliminations — the units' checks, not a judgement.
    urgency_bp, priority_override = dm.priority_metrics(results, request)
    adjustments = [item for result in results for item in result.adjustments]
    checks = [item for result in results for item in result.checks]
    proposals = dm.synthesize_candidates(request, adjustments, urgency_bp, priority_override,
                                         importance_bp)
    proposals = dm.evaluate_candidates(proposals, checks)
    eligible = [item for item in proposals if item.disposition == CandidateDisposition.ELIGIBLE]

    answer, failure = (None, "no_eligible_play") if not eligible else _consult(
        request, results, proposals, uncertainty, degraded, importance_bp, llm)

    if not eligible:
        # Every play was eliminated by a hard check: there is nothing to choose between.
        outcome = DecisionOutcome.BLOCKED
        scores: dict[str, int] = {}
        confidence_bp = 0
    elif answer is None:
        outcome = DecisionOutcome.DEFER
        uncertainty.append(f"{LLM_UNAVAILABLE_REASON}:{failure}")
        scores = {item.play.play_id: 0 for item in eligible}
        confidence_bp = 0
    else:
        outcome = (DecisionOutcome.DECISION if answer["outcome"] == "decision"
                   else DecisionOutcome.DEFER)
        if outcome == DecisionOutcome.DEFER:
            uncertainty.append(LLM_DEFERRED_REASON)
        scores = answer["scores"]
        confidence_bp = answer["confidence_bp"]

    ordered = sorted(eligible, key=lambda item: (-scores.get(item.play.play_id, 0),
                                                 item.play.play_id))
    rank_of = {item.play.play_id: rank for rank, item in enumerate(ordered, start=1)}
    judged = []
    for item in proposals:
        play_id = item.play.play_id
        score = (scores.get(play_id, 0)
                 if item.disposition == CandidateDisposition.ELIGIBLE else 0)
        judged.append(replace(
            item, components={**item.components, LLM_UTILITY_COMPONENT: score},
            utility_bp=score, rank_position=rank_of.get(play_id)))
    # Ranked survivors first, eliminated last by play id — the shape `rank_candidates` produces.
    judged.sort(key=lambda i: (i.rank_position is None, i.rank_position or 0, i.play.play_id))

    candidates = dm.build_candidate_objects(judged, confidence_bp, dm.aggregate_evidence(results))
    if answer is not None:
        # The model's own words travel with the winner, for the card and for the test review.
        top = candidates[0] if candidates and candidates[0].rank_position == 1 else None
        if top is not None:
            candidates = (replace(top, parameters={
                **dict(top.parameters),
                "llm_rationale": answer["rationale"],
                "llm_missing": list(answer["missing"]),
                "llm_model": answer.get("model", ""),
            }),) + tuple(candidates[1:])

    selected = next((item for item in candidates
                     if item.disposition == CandidateDisposition.ELIGIBLE), None)
    play_by_id = {play.play_id: play for play in request.capability.plays}
    decision = ReasoningDecision(
        outcome=outcome,
        capability_id=request.capability.capability_id,
        capability_version=request.capability.version,
        context_snapshot_id=request.context.context_snapshot_id,
        candidates=candidates,
        selected_candidate_id=(selected.candidate_id if outcome == DecisionOutcome.DECISION
                               and selected is not None else None),
        confidence_bp=confidence_bp,
        uncertainty=tuple(uncertainty),
        do_nothing_consequence=request.capability.do_nothing_consequence,
        expires_at=request.evaluation_time + timedelta(hours=request.capability.expiry_hours),
        outcome_window_days=(play_by_id[selected.play_id].window_days
                             if outcome == DecisionOutcome.DECISION
                             and selected is not None else None),
        citations=tuple(weld.get("citations") or ()),
        constraints_applied=constraint_applications(weld.get("rule_verdicts") or (), candidates),
        ranking_weights_version=(dm.RANKING_WEIGHTS_V2_VERSION if ranking_v2 else None),
        do_nothing=(dm.do_nothing_record(request, results) if ranking_v2 else {}),
    )
    return dm.DecisionSynthesis(candidates=candidates, decision=decision, confidence=None)


def is_llm_decided(candidates: Sequence[Mapping[str, Any]]) -> bool:
    """Did this module build these persisted candidate rows? Read by `reason/store.py`."""
    return any(LLM_UTILITY_COMPONENT in (item.get("score_components") or {})
               for item in candidates)


def _reset_for_tests() -> None:
    global _cost_store
    with _lock:
        _cache.clear()
        _calls_by_org_day.clear()
    _cost_store = None


__all__ = ["COST_PURPOSE", "LLM_DEFERRED_REASON", "LLM_UNAVAILABLE_REASON",
           "LLM_UTILITY_COMPONENT", "PROMPT_VERSION", "build_prompt", "client",
           "decide_with_llm", "enabled_for", "is_llm_decided", "parse_answer"]
