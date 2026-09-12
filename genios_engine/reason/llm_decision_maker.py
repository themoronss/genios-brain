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
    ResultStatus,
)
from genios_engine.platform.canonical import semantic_hash

_log = logging.getLogger(__name__)

#: Bumped whenever the prompt or the answer schema changes; it is inside the cache key.
#: v2: the subject and its messages lead the prompt; units give conclusions, not scores.
#: v3: past-dated scheduling threads are closed. v4: the formula's own reading is the baseline.
#: v5: R-1's job folded in — the hedge vocabulary, the stance classes, and unresolved conflicts.
PROMPT_VERSION = "l4-llm-decision.v5"

#: R-1 (`reason/interpretation.py`) in the decision maker's own words. R-1 gates a model call on a
#: CLOSED hedge list and asks for one of six stances; its reading reaches no unit at all, so in this
#: mode the decision maker does that reading itself, from the same list and the same six meanings,
#: on the whole message rather than one sentence — no extra call.
def _stance_rules() -> list[str]:
    from genios_engine.reason.interpretation import CLASSIFICATION_MEANINGS, HEDGE_MARKERS
    stances = "; ".join(f"{name.lower().replace('_', ' ')} = {meaning}"
                        for name, meaning in CLASSIFICATION_MEANINGS.items())
    return [
        "- A hedge is not a commitment. Words like " + ", ".join(f"'{m}'" for m in HEDGE_MARKERS)
        + " mean the writer has NOT committed.",
        f"- Read each message's stance as one of: {stances}.",
        "- Only 'commitment made' or 'decision made' is something to hold anyone to. Never raise "
        "confidence on a hedge or on speculation.",
    ]

#: Units whose ELIMINATE is a scoring judgement, not safety. In this mode the model makes that
#: judgement, so these are shown as advice and do not remove a play. Policy, consent and
#: unsafe-claim eliminations still bind.
ADVISORY_EVALUATORS = frozenset({"legacy.score_gate"})

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


def enabled_for(org_id: str, mode: Any = None) -> bool:
    """Is the LLM decision maker on for this org, in this execution mode? FAILS CLOSED.

    The allow-list must name the org, or be `*` for every org — an empty list enables nobody.
    A run that cannot deliver (any mode but LIVE: shadow, simulation, replay) is measurement, and
    measurement does not buy a model call unless `l4_llm_shadow_paid` says it may. `mode=None`
    is treated as LIVE, for callers that have no request.
    """
    try:
        settings = _settings()
    except Exception:      # noqa: BLE001 — no settings means no switch, means the formula
        return False
    if not getattr(settings, "l4_llm_decision_maker", False):
        return False
    allowed = {item.strip() for item in
               str(getattr(settings, "l4_llm_decision_maker_orgs", "") or "").split(",")
               if item.strip()}
    if "*" not in allowed and str(org_id) not in allowed:
        return False
    live = mode is None or str(getattr(mode, "value", mode)) == "live"
    return live or bool(getattr(settings, "l4_llm_shadow_paid", False))


def enabled_for_request(request: Any) -> bool:
    """`enabled_for` for one reasoning request: its org and its execution mode."""
    return enabled_for(getattr(request, "org_id", ""), getattr(request, "mode", None))


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
                 output_tokens: int, success: bool, error: str | None,
                 purpose: str = COST_PURPOSE) -> None:
    """Into `llm_costs`, like every other call in the engine. Never fails the decision."""
    global _cost_store
    try:
        if _cost_store is None:
            from genios_engine.platform.wiring import make_graph_store
            _cost_store = make_graph_store() or False
        if not _cost_store:
            return
        _cost_store.record_cost(org_id=org_id, model=model, purpose=purpose,
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
    """What the analysis units CONCLUDED — their reason codes, never their internal scores.

    v1 printed every unit's raw basis-point metrics, and the model deferred on them: it read
    `evidence_sufficiency_bp: 0` and `ungrounded_claim_count: 2` (internal bookkeeping about how a
    score was composed) as "the evidence is thin", while the actual email was not in the prompt at
    all. Units that concluded nothing, or could not run for lack of an optional input, are left
    out rather than listed as gaps.
    """
    lines = []
    for result in results:
        if result.status != ResultStatus.COMPLETED:
            continue
        codes = sorted({code for code in result.reason_codes}
                       | {code for f in result.findings for code in f.reason_codes})
        if not codes:
            continue
        lines.append(f"- {result.reasoner_id}: {', '.join(codes[:8])}")
    return lines or ["- (nothing notable)"]


def _plays_block(proposals: Sequence[Any]) -> list[str]:
    lines = []
    for item in proposals:
        play = item.play
        eliminated = item.disposition == CandidateDisposition.ELIMINATED
        binding = sorted({check.reason_code for check in item.checks
                          if check.outcome == CheckOutcome.ELIMINATE
                          and check.evaluator_id not in ADVISORY_EVALUATORS})
        advisory = [check for check in item.checks if check.outcome == CheckOutcome.ELIMINATE
                    and check.evaluator_id in ADVISORY_EVALUATORS]
        note = ""
        if eliminated:
            note = (f" | BLOCKED by a safety/policy check ({', '.join(binding)}) — "
                    "you may not choose it")
        elif advisory:
            detail = dict(advisory[0].detail or {})
            note = (" | note: a legacy scoring rule rated this below its threshold "
                    f"(score {detail.get('score')} < {detail.get('score_min')}); that rule is "
                    "advice, not a veto — judge it yourself")
        components = ", ".join(f"{name} {item.components[name]}" for name in
                               ("importance", "impact", "urgency", "success", "effort", "risk")
                               if name in item.components)
        lines.append(f"- play_id={play.play_id} | {play.label} | "
                     f"steps: {_short(list(play.steps), 300)} | formula utility "
                     f"{item.utility_bp} ({components}){note}")
    return lines


_DEFAULT_BANDS = {"high": 70, "critical": 85}      # deliver/bands.band's own default


def _bands(request: Any) -> dict[str, int]:
    """The pack's urgency-band cuts on the 0-100 card score, as the card builder applies them."""
    for spec in request.capability.reasoners:
        if spec.reasoner_id == "legacy.rule":
            cuts = ((spec.config.get("scoring") or {}).get("bands") or {})
            if cuts:
                return {"high": int(cuts.get("high", 70)), "critical": int(cuts.get("critical", 85))}
    return dict(_DEFAULT_BANDS)


def _formula_block(request: Any, results: Sequence[ReasonerResult]) -> list[str]:
    """How the deterministic engine scored this — the baseline the model calibrates against.

    v1-v3 gave the model no scale, and it answered ~8500 for nearly everything: the card score is
    utility/100, the general pack cuts CRITICAL at 60, so every card read critical and the queue
    lost its order. The formula's reading is shown as data, not as an answer to copy.
    """
    from genios_engine.reason import decision_maker as dm

    lines: list[str] = []
    done = {r.reasoner_id: r for r in results if r.status == ResultStatus.COMPLETED}
    rule = done.get("legacy.rule")
    if rule is not None and "legacy_score" in rule.metrics:
        m = rule.metrics
        lines.append(
            f"- the rule's score S = {m.get('legacy_score')}/100, from "
            "S = Confidence x (0.45 Urgency + 0.35 Impact + 0.20 Recency): "
            f"Urgency {int(m.get('urgency_bp', 0)) // 100}, Impact {int(m.get('impact_bp', 0)) // 100}, "
            f"Recency {int(m.get('recency_bp', 0)) // 100}, "
            f"Confidence {int(m.get('confidence_bp', 0)) // 100}% (extraction 50%, freshness 30%, "
            "corroboration 20%)")
    gate = done.get("legacy.score_gate")
    if gate is not None:
        g = gate.metrics
        lines.append(f"- the rule's own bar: S >= {g.get('score_min')} and Confidence >= "
                     f"{int(g.get('confidence_min_bp', 0)) // 100}%")
    floor_bp, _source = dm.resolve_confidence_floor(request)
    lines.append(f"- the formula only recommends acting when confidence >= {floor_bp}")
    bands = _bands(request)
    lines.append(f"- a card's score is utility/100 and orders the founder's queue: >= "
                 f"{bands['critical'] * 100} shows as CRITICAL, >= {bands['high'] * 100} as HIGH, "
                 "below that STANDARD")
    return lines


# ── What a human would look at: the subject, and what the mailbox actually says ───────────────

#: Fact prefixes that describe the business; the `derived.*` series are engine bookkeeping.
_BUSINESS_PREFIXES = ("party.", "thread.", "commitment.", "person.", "company.", "deal.",
                      "meeting.", "campaign.", "contact.", "account.", "relationship.",
                      "invoice.", "contract.", "task.")
_L1_KEYS = ("intent", "stance", "topics", "questions", "commitments", "roles",
            "implied_actions", "scheduling_proposals", "decision_states", "amounts")
_MAX_EVENTS = 4
_LOAD_ENGINE: Any = None


def _engine():
    global _LOAD_ENGINE
    if _LOAD_ENGINE is None:
        try:
            from genios_engine.platform.wiring import make_graph_store
            store = make_graph_store()
            _LOAD_ENGINE = store.engine if store is not None else False
        except Exception:      # noqa: BLE001
            _LOAD_ENGINE = False
    return _LOAD_ENGINE or None


def _l1_summary(output: Mapping[str, Any]) -> str:
    """One extracted message, as the handful of things a reader needs — quotes kept verbatim."""
    parts = []
    exchange = output.get("exchange_intent")
    if isinstance(exchange, Mapping) and exchange.get("category"):
        parts.append(f"kind={exchange.get('category')}")
    for key in _L1_KEYS:
        value = output.get(key)
        if not value:
            continue
        if key == "commitments":
            value = [{"who": c.get("actor"), "promised": c.get("action"), "due": c.get("due"),
                      "quote": ((c.get("evidence") or [{}])[0] or {}).get("quote")}
                     for c in value[:3] if isinstance(c, Mapping)]
        elif key == "roles":
            value = [f"{r.get('party')}: {r.get('role')}" for r in value[:4]
                     if isinstance(r, Mapping)]
        elif isinstance(value, list):
            value = value[:4]
        parts.append(f"{key}={_short(value, 260)}")
    return "; ".join(parts)


def business_context(request: Any) -> list[str]:
    """The subject and its latest messages, read-only from the graph. Empty when unavailable.

    The decision is only as good as what the model is shown, and the reasoning snapshot carries
    the two or three fields a RULE needed — for an unanswered email, "ball in court" and a date.
    The name, the role and what the person actually wrote are all in the graph already (the card
    builder shows them); this is that, for the decision. Never raises: no database means the
    prompt simply goes without it.
    """
    engine = _engine()
    node_id = str(request.context.root_entity_id)
    org_id = str(request.org_id)
    if engine is None:
        return []
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            node = conn.execute(text(
                "select node_type, display_name from graph_nodes where org_id=:o and node_id=:n "
                "and valid_to is null order by version desc limit 1"),
                {"o": org_id, "n": node_id}).first()
            facts = conn.execute(text(
                "select field, value from graph_facts where org_id=:o and subject_node_id=:n "
                "and valid_to is null and status='active' order by field"),
                {"o": org_id, "n": node_id}).fetchall()
            events = conn.execute(text(
                "select se.occurred_at, se.actor, se.object_type, e.output "
                "from source_events se join l1_extraction_results e "
                "on e.org_id=se.org_id and e.event_id=se.event_id "
                "where se.org_id=:o and se.event_id in (select distinct created_by_event_id "
                "from graph_facts where org_id=:o and subject_node_id=:n "
                "and created_by_event_id is not null) "
                "order by se.occurred_at desc limit :k"),
                {"o": org_id, "n": node_id, "k": _MAX_EVENTS}).fetchall()
    except Exception:      # noqa: BLE001 — context is an aid to the decision, never a reason to lose it
        _log.exception("could not load business context for %s", node_id)
        return []
    lines: list[str] = []
    if node is not None:
        lines.append(f"- this is a {node.node_type}: {node.display_name or '(unnamed)'}")
    for row in facts:
        if str(row.field).startswith(_BUSINESS_PREFIXES):
            lines.append(f"- {row.field}: {_short(row.value, 200)}")
    for row in events:
        actor = row.actor if isinstance(row.actor, Mapping) else {}
        who = actor.get("name") or actor.get("email") or actor.get("id") or "unknown sender"
        when = row.occurred_at.date().isoformat() if row.occurred_at else "?"
        summary = _l1_summary(row.output if isinstance(row.output, Mapping) else {})
        if summary:
            lines.append(f"- message {when} from {who}: {summary}")
    return lines[:40]


def build_prompt(request: Any, results: Sequence[ReasonerResult], proposals: Sequence[Any],
                 uncertainty: Sequence[str], degraded: bool, importance_bp: int | None,
                 feedback: str | None = None, business: Sequence[str] = ()) -> str:
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
        "You are the chief of staff of a busy founder. GeniOS has flagged ONE situation from "
        "their inbox and calendar. Decide whether it belongs in front of them today, and what "
        "they should do about it.",
        "",
        "Decide:",
        "1. outcome — \"decision\" if a good chief of staff would put this in front of the founder "
        "now; \"defer\" if it is noise (automated or promotional mail), already handled, has "
        "nothing for us to do, or you genuinely cannot tell what it is about.",
        "2. For EVERY eligible play, a utility 0-10000 on the SAME scale as the engine's formula "
        "(shown below). START from the formula's utility for that play and move it only for a "
        "reason the formula cannot see — who the person is, what they actually asked, whether it "
        "was already handled. Keep most moves within about 2000; if you move more, say why in the "
        "rationale. The utility becomes the card's rank in today's queue, so do not give "
        "everything the same high number: CRITICAL is for what truly needs the founder today. "
        "The Wait play should win when acting now adds little.",
        "3. confidence_bp 0-10000: how strong the evidence is. Start from the rule's own "
        "confidence; raise it only when the messages clearly confirm the situation, lower it when "
        "they are unclear or contradict it.",
        "",
        "How to judge:",
        "- What stays owed: a direct question or request a real person sent us, or a promise WE "
        "made. Time does not close these — being weeks old makes them MORE urgent, not less, "
        "unless the facts show they were answered, done or called off.",
        "- What time DOES close: a meeting invitation, confirmation or reschedule is about one "
        "specific date. If that date has passed and nothing after it shows something still owed "
        "(a question, a request, a promise), the thread is over — defer. Do not treat an "
        "unanswered calendar invite for a past date as an obligation.",
        "- A due time of 18:29:59 UTC is an 'end of day' placeholder, not a scheduled meeting.",
        *_stance_rules(),
        "- Where the record disagrees with itself (listed below), say which reading you trust and "
        "why; if you cannot tell, lower confidence rather than picking one silently.",
        "- Judge the business situation from the facts and messages below. Do not invent facts, "
        "people, dates or amounts.",
        "- Fields that are simply not recorded are not a reason to defer when the situation is "
        "already clear without them.",
        "",
        f"SITUATION: {situation.replace('_', ' ')} — {_short(capability.goal.statement, 300)}",
        f"evaluated at: {request.evaluation_time.date().isoformat()}",
        f"if nobody acts: {_short(capability.do_nothing_consequence, 300)}",
    ]
    if importance_bp is not None:
        sections.append(f"situation importance measured upstream: {importance_bp} / 10000")
    if business:
        sections += ["", "WHO AND WHAT (from the graph and the mailbox, latest first):",
                     *business]
    # R-1's second trigger: a disagreement Layer 1 recorded and nobody settled. Shown on its own so
    # the model weighs both readings instead of meeting them as two unremarkable facts.
    disagreements = [f"- {name[len('situation.conflict.'):]}: {_short(context.facts[name], 240)}"
                     for name in sorted(context.facts) if name.startswith("situation.conflict.")]
    if disagreements:
        sections += ["", "WHERE THE RECORD DISAGREES:", *disagreements]
    # R-1's readings (`reason/llm_interpretation.py`), on their own so they read as what they are:
    # a model's reading of the wording, which the contract forbids from raising confidence.
    readings = []
    for name in sorted(context.facts):
        if not name.startswith("interpretation."):
            continue
        record = context.facts[name]
        value = record.get("value") if isinstance(record, Mapping) else None
        if isinstance(value, Mapping):
            readings.append(f"- {name[len('interpretation.'):]}: "
                            f"{str(value.get('classification', '')).lower().replace('_', ' ')} "
                            f"(confidence {value.get('confidence_bp')}) — "
                            f"\"{_short(value.get('span'), 200)}\"")
    if readings:
        sections += ["", "R1 — HOW THE WORDING READS (a reading, not a fact; it cannot raise "
                         "confidence):", *readings]
    rule_facts = {name: record for name, record in context.facts.items()
                  if not name.startswith(("interpretation.", "situation.conflict."))}
    sections += ["", "FACTS THE RULE USED:", *_facts_block(rule_facts, 40)]
    if context.neighbor_facts:
        sections += ["", "FACTS ABOUT RELATED PEOPLE / THREADS:",
                     *_facts_block(context.neighbor_facts, 25)]
    sections += ["", "WHAT THE ANALYSIS FOUND:", *_units_block(results)]
    sections += ["", "HOW THE ENGINE'S FORMULA SCORED THIS (your baseline, not your answer):",
                 *_formula_block(request, results)]
    if citations:
        sections += ["", "AUTHORED EXPERT RULES THAT APPLY:", *[f"- {c}" for c in citations]]
    if conflicts:
        sections += ["", "AUTHORED RULES THAT CONTRADICT EACH OTHER HERE:",
                     *[f"- {c}" for c in conflicts]]
    required_missing = sorted(set(context.missing_fields) & set(capability.required_fields))
    if required_missing:
        sections += ["", "REQUIRED INFORMATION THAT IS MISSING:",
                     *[f"- {g}" for g in required_missing]]
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

def _debug_dump(request: Any, attempt: int, prompt: str, res: Any, tag: str = "dm") -> None:
    """With `GENIOS_L4_LLM_DECISION_DEBUG_DIR` set, write each prompt and answer to a file.

    For local debugging only: a DEFER's reason is in the answer, and whether the prompt misled
    the model is only visible next to the prompt it answered. Never fails the decision.
    """
    import os
    folder = os.environ.get("GENIOS_L4_LLM_DECISION_DEBUG_DIR", "").strip()
    if not folder:
        return
    try:
        os.makedirs(folder, exist_ok=True)
        name = (f"{tag}__{request.capability.capability_id}__{request.context.root_entity_id}"
                f"__{attempt}.json").replace("/", "_")
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            json.dump({"capability": request.capability.capability_id,
                       "subject": request.context.root_entity_id, "attempt": attempt,
                       "prompt": prompt, "raw": getattr(res, "raw", ""),
                       "parsed": getattr(res, "parsed", None), "ok": getattr(res, "ok", None),
                       "error": getattr(res, "error", None)},
                      handle, ensure_ascii=False, indent=1, default=str)
    except Exception:      # noqa: BLE001
        _log.exception("could not write the L4 LLM decision debug dump")


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
    business = business_context(request)
    key = semantic_hash({"base": _cache_key(request, results, uncertainty, degraded, model),
                         "business": list(business)})
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
    for attempt in range(2):
        prompt = build_prompt(request, results, proposals, uncertainty, degraded,
                              importance_bp, feedback, business=business)
        try:
            res = llm.call(prompt, max_tokens=_MAX_TOKENS)
        except Exception as exc:      # noqa: BLE001 — a transport failure is a DEFER
            _record_cost(org_id=request.org_id, model=model, subject_ref=subject_ref,
                         input_tokens=0, output_tokens=0, success=False, error=str(exc)[:300])
            return None, "call_failed"
        _debug_dump(request, attempt, prompt, res)
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
    # Only safety/policy eliminations bind. A scoring-threshold rule (`legacy.score_gate`) is a
    # judgement the model now makes, so it is shown as advice — and every check still travels on
    # its candidate, because the store verifies checks against the units' own outputs.
    binding = [item for item in checks if item.evaluator_id not in ADVISORY_EVALUATORS]
    proposals = [replace(item, checks=dm.ordered_checks(
                     [c for c in checks if c.play_id == item.play.play_id]))
                 for item in dm.evaluate_candidates(proposals, binding)]
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
           "decide_with_llm", "enabled_for", "enabled_for_request", "is_llm_decided",
           "parse_answer"]
