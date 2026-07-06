"""Module bootstrap — load each installed module at app startup and register
its decide() handler + graph_view handler with the v2 intelligence router.

Called once from app/main.py on FastAPI startup. Per g-i-5 §1:
- Loader reads manifest.json + rules + graph fragment
- Engine has no module-specific code — modules register themselves via this
  bootstrap and the intelligence router dispatches by module_id

Sales is the MVP module (per spec g-i-5 §1.1). Others land as design partners arrive.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api.intelligence import (
    register_graph_view_handler,
    register_query_handler,
)
from core.decision import DecideRequest, DecideResult, decide
from core.neural.gateway import GatewayValidationError


class _NeuralGapConclusion(BaseModel):
    """Default schema for module gap-fill LLM responses.

    Engine's symbolic pass returns this when rules can't reach a conclusion.
    The neural pass must produce the same shape so the decision row downstream
    treats it identically.

    Requirements enforced by Pydantic + the retry-on-empty loop in
    `_query_with_neural_retry`:
    - `conclusion` MUST be non-empty (min_length=1). The fail-fast property
      blocks the LLM from punting with `""` — that was the dominant quality
      bug (67% empty rate). When the LLM truly has nothing to say it should
      respond with an explicit "insufficient data" conclusion, NOT empty.
    - `recommended_action` is a single concrete next-step the integrator
      (Hermes/langchain/customer agent) can act on. Generic verbs like
      "review" / "consider" are accepted but discouraged in the prompt.
    - `rationale` is the chain-of-reasoning, capped to keep envelopes small.
    """

    conclusion: str = Field(min_length=1, description="Short answer label, non-empty")
    rationale: str = Field(
        default="", max_length=500,
        description="One-line reason using ONLY the facts supplied — no invention",
    )
    recommended_action: str = Field(
        default="", max_length=240,
        description="Concrete next step the caller can act on",
    )
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


_DEFAULT_NEURAL_SYSTEM_PROMPT = (
    "You are an analyst inside GeniOS — a hybrid neuro-symbolic engine. "
    "The symbolic rule engine has run and could not reach a confident "
    "conclusion for the user's query. Your job is to produce a SHORT, "
    "grounded conclusion plus a concrete recommended_action using the "
    "facts supplied. "
    "RULES: "
    "(1) Do NOT invent facts not in the input. "
    "(2) Do NOT return an empty conclusion — if the facts genuinely don't "
    "support a useful answer, set conclusion to a short label like "
    "\"insufficient_data\" or \"need_more_facts\" and explain in rationale "
    "what's missing. "
    "(3) recommended_action must be a single, concrete next step the "
    "caller can act on (e.g. \"send firm reminder to GoBlue Logistics\", "
    "\"schedule discovery call with CFO\"). Avoid vague verbs alone "
    "(\"review\", \"consider\") — pair them with the target. "
    "(4) Prefer specifics from the facts (names, numbers, days) over "
    "generic language."
)
from core.delivery.envelope import (
    AsOfPin,
    Envelope,
    EnvelopeRoute,
    EnvelopeTriggeredBy,
    build_envelope,
)
from core.foundations.telemetry import get_logger
from core.modules_framework.loader import ModulePackage, load_module_package
from core.neural.client import LLMClient
from core.neural.cost_guard import CostGuard
from core.neural.gateway import Gateway
from core.reasoning.rule_loader import RuleSet

log = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "modules"


def bootstrap_modules() -> dict[str, ModulePackage]:
    """Load every module in modules/ and register its handlers. Returns {id: package}.

    Modules that fail to load are LOGGED but don't block boot — engine still
    works for other modules + non-intelligence routes.
    """
    loaded: dict[str, ModulePackage] = {}
    if not MODULES_DIR.exists():
        log.warning("modules_dir_missing", path=str(MODULES_DIR))
        return loaded

    for entry in sorted(MODULES_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("__"):
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            pkg = load_module_package(entry)
            _register_pkg(pkg)
            loaded[pkg.manifest.id] = pkg
            log.info(
                "module_loaded",
                module_id=pkg.manifest.id,
                version=pkg.manifest.version,
                maturity=pkg.manifest.maturity,
                rules=len(pkg.ruleset.rules),
            )
        except Exception as e:
            log.exception("module_load_failed", module=entry.name, error=str(e))

    return loaded


def _register_pkg(pkg: ModulePackage) -> None:
    """Wire the package's ruleset into the v2 intelligence query handler."""
    mid = pkg.manifest.id
    ruleset: RuleSet = pkg.ruleset

    # Module-specific system prompt overrides the generic default when
    # declared in manifest.json. Captured in closure so query_handler
    # doesn't re-read the manifest on every request.
    system_prompt = pkg.manifest.neural_prompt or _DEFAULT_NEURAL_SYSTEM_PROMPT

    def query_handler(
        session: Session,
        org_id: str,
        query: dict[str, Any],
        facts: dict[str, Any],
        user_id: str | None,
    ) -> Envelope:
        """Per-request dispatcher: runs the engine using THIS module's rules."""
        gateway = Gateway(llm=LLMClient(), cost_guard=CostGuard())
        # Neural fallback wiring — without these the gateway hits
        # "symbolic_default_no_neural" and LLM never runs, so every
        # unresolved query returns confidence=0.20/conclusion="" with
        # zero credits deducted. We supply a module-agnostic default
        # prompt + schema so symbolic-unresolved queries actually
        # escalate to Haiku gap-fill (1 credit per call).
        gap_desc = (
            query.get("q") or query.get("question") or query.get("kind") or "Decide the user's question"
            if isinstance(query, dict) else "Decide the user's question"
        )
        # Retry-on-empty / retry-on-schema-fail policy. The Pydantic schema
        # enforces conclusion.min_length=1, so an LLM that returns `""`
        # bubbles a GatewayValidationError. Retrying ONCE with a stronger
        # prompt + the schema spec embedded gets the answer >90% of the
        # time in practice. If the second attempt still fails we surface a
        # graceful "insufficient_data" envelope rather than a 500 — that
        # preserves the contract Hermes/langchain consumers depend on.
        # Enrich the caller's facts with the queried entity's OWN stored graph
        # facts (uploaded CSVs, synced email) so the engine reasons over the
        # org's data — not just what the caller re-supplies each request.
        facts = _enrich_facts_from_graph(session, org_id, query, facts)

        result = _decide_with_retry(
            session=session,
            gateway=gateway,
            ruleset=ruleset,
            org_id=org_id,
            query=query,
            facts=facts,
            user_id=user_id,
            module_id=mid,
            gap_desc=gap_desc,
            system_prompt=system_prompt,
        )

        # Persist query facts to the graph so future queries about these
        # entities get a non-zero grounding_score. Without this every query
        # is stateless — facts vanish after the call and the confidence
        # ceiling stays stuck at 0.54 (NEURAL_PATH_WEIGHTS with grounding=0).
        # Persistence only fires when the LLM gave a useful answer; skip
        # the insufficient_data and empty conclusion cases so junk doesn't
        # pollute the org's graph.
        if (
            result.conclusion
            and result.conclusion.strip().lower() not in ("insufficient_data", "need_more_facts")
        ):
            _persist_query_facts_to_graph(
                org_id=org_id, module_id=mid, facts=facts
            )

        recommendation: dict[str, Any] = {"conclusion": result.conclusion}
        if isinstance(result.recommendation_extras, dict):
            recommendation.update(result.recommendation_extras)
        return build_envelope(
            org_id=org_id,
            decision_id=result.decision_id,
            recommendation=recommendation,
            confidence=result.confidence,
            derivation=[
                _step_to_dict(step) for step in result.proof.steps
            ]
            if result.proof
            else [],
            uncertainty=[],
            route=_to_envelope_route(result.route),
            triggered_by=EnvelopeTriggeredBy.QUERY,
            as_of_version=result.as_of_version,
            as_of_timestamp=datetime.now(UTC),
        )

    register_query_handler(mid, query_handler)

    def graph_view_handler(
        session: Session,
        org_id: str,
        center_node_ids: list[str],
        hops: int,
    ) -> dict[str, Any]:
        """v1: returns module's static graph fragment as a snapshot view."""
        return {
            "module_id": mid,
            "center_node_ids": center_node_ids,
            "hops": hops,
            "fragment": pkg.graph_fragment,
        }

    register_graph_view_handler(mid, graph_view_handler)


def _step_to_dict(step: Any) -> dict[str, Any]:
    """ProofStep → derivation step dict for the envelope."""
    return {
        "rule_id": getattr(step, "rule_id", None) or "?",
        "conclusion": getattr(step, "conclusion", ""),
        "matched_facts": getattr(step, "matched_facts", {}) or {},
    }


def _enrich_facts_from_graph(
    session: Session, org_id: str, query: Any, facts: Any
) -> Any:
    """Merge the queried entity's OWN stored graph facts into the engine's flat
    facts dict.

    Historically the engine reasoned ONLY over the caller's request.facts, so a
    query never saw the org's ingested data (uploaded CSVs, synced email). When
    the query names a subject, load that subject's persisted facts and merge them
    UNDER the caller's facts — explicit caller values always win. Values are
    coerced to the types the rules expect (shared with the proactive path).

    Safe + additive: only the flat-dict ("shape B") case is touched, and any
    failure returns the facts unchanged (never breaks a query).
    """
    try:
        if not isinstance(facts, dict) or isinstance(facts.get("facts"), list):
            return facts
        subject = None
        if isinstance(query, dict):
            for k in ("subject", "entity", "entity_name", "contact", "account",
                      "account_name", "deal", "deal_name", "company", "name"):
                v = query.get(k)
                if isinstance(v, str) and v.strip():
                    subject = v.strip()
                    break
        if not subject:
            return facts

        from sqlalchemy import text as _t

        from core.proactive.pipeline import _coerce_fact_value

        rows = session.execute(
            _t("""
                SELECT predicate, object
                FROM facts
                WHERE org_id = :org AND LOWER(subject) = LOWER(:subj)
                ORDER BY created_at DESC
            """),
            {"org": org_id, "subj": subject},
        ).fetchall()
        if not rows:
            return facts

        enriched: dict[str, Any] = {}
        for r in rows:
            if r.predicate not in enriched:            # most-recent value wins
                enriched[r.predicate] = _coerce_fact_value(r.predicate, r.object)
        enriched.update(facts)                          # caller facts always win
        return enriched
    except Exception:
        return facts


def _persist_query_facts_to_graph(
    *,
    org_id: str,
    module_id: str,
    facts: Any,
) -> None:
    """Emit query facts to the memory bus so g-i-3 writes FactRow entries.

    Query facts arrive in one of two shapes:
      A) `{"facts": [{"subject": S, "predicate": P, "object": O}, ...]}`
      B) flat `{S1: {P1: V1, ...}, ...}` (rare, custom callers)

    We normalize to per-subject groups → emit one MemoryItem per subject
    with a StructuredFactsHint so the existing ingest subscriber persists
    them directly (no LLM extract). Failures are swallowed and logged —
    persistence is best-effort and must not break the query path.
    """
    from hashlib import sha256

    from core.foundations.db import get_session
    from core.memory.types import (
        MemoryItem,
        MemoryItemMetadata,
        StructuredFactsHint,
    )
    from core.worldmodel.ingest_subscriber import _ingest_structured

    # Normalize input to {subject: {predicate: object}} groups.
    grouped: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    if isinstance(facts, dict):
        inner = facts.get("facts") if "facts" in facts else None
        if isinstance(inner, list):
            candidates = [c for c in inner if isinstance(c, dict)]
        elif inner is None:
            # Shape B: treat each top-level key as a subject with attribute dict
            for k, v in facts.items():
                if isinstance(v, dict):
                    grouped[str(k)] = {str(pk): pv for pk, pv in v.items()}
                else:
                    grouped.setdefault("_query_root_", {})[str(k)] = v
    elif isinstance(facts, list):
        candidates = [c for c in facts if isinstance(c, dict)]

    for t in candidates:
        s = t.get("subject")
        p = t.get("predicate")
        o = t.get("object")
        if not s or not p:
            continue
        grouped.setdefault(str(s), {})[str(p)] = o

    if not grouped:
        return

    ts = datetime.now(UTC)
    # Call `_ingest_structured` directly with a fresh session — the
    # memory_bus subscriber resolves org_id via the `connections` table,
    # and our synthetic source_id ("genios-query:*") has no connection
    # row, so going through the bus would silently skip every insert.
    # The direct call uses the org_id we already know and writes the
    # FactRow + NodeRow under the same idempotency rules the CSV ingest
    # path uses.
    try:
        with get_session() as session:
            for subject, fact_map in grouped.items():
                digest = sha256(
                    f"{org_id}|{module_id}|{subject}|{sorted(fact_map.items())}".encode()
                ).hexdigest()[:16]
                item = MemoryItem(
                    item_id=f"query:{module_id}:{digest}",
                    source_id=f"genios-query:{module_id}",
                    source_type="genios_query",
                    content=(
                        f"{subject} — "
                        + ", ".join(f"{k}={v}" for k, v in fact_map.items())
                    )[:1000],
                    metadata=MemoryItemMetadata(
                        timestamp=ts,
                        owner=None,
                        source_confidence=0.95,  # caller-asserted, slightly under 1.0
                        tags=[f"module:{module_id}", "channel:intelligence_query"],
                        structured_facts=StructuredFactsHint(
                            entity_name=subject,
                            entity_type="entity",
                            secondary_entity_id=None,
                            entity_attributes={},
                            facts=fact_map,
                            edge_predicate=None,
                        ),
                    ),
                )
                _ingest_structured(session, item, org_id, item.metadata.structured_facts)
            session.commit()
    except Exception as e:
        log.warning(
            "query_fact_persist_failed",
            org_id=org_id,
            module_id=module_id,
            error=str(e)[:200],
        )


def _to_envelope_route(route: Any) -> EnvelopeRoute:
    """Engine Route → EnvelopeRoute. Both are str enums with same values."""
    val = getattr(route, "value", route)
    if val == "autonomous":
        return EnvelopeRoute.AUTONOMOUS
    if val == "flag":
        return EnvelopeRoute.FLAG
    return EnvelopeRoute.NOTIFY


_RETRY_PROMPT_SUFFIX = (
    "\n\nIMPORTANT: A prior attempt produced an output that failed schema "
    "validation (likely empty conclusion or missing recommended_action). "
    "You MUST return a non-empty conclusion and a concrete recommended_action. "
    "If facts genuinely don't support a useful answer, set conclusion to "
    "\"insufficient_data\" and use rationale to state precisely what's "
    "missing (e.g. \"need contract_value, last_response_date\")."
)


def _decide_with_retry(
    *,
    session: Session,
    gateway: Gateway,
    ruleset: RuleSet,
    org_id: str,
    query: dict[str, Any],
    facts: dict[str, Any],
    user_id: str | None,
    module_id: str,
    gap_desc: str,
    system_prompt: str = _DEFAULT_NEURAL_SYSTEM_PROMPT,
) -> DecideResult:
    """Run `decide()` with one retry on GatewayValidationError.

    The Pydantic schema enforces non-empty conclusion (`min_length=1`); when
    the LLM returns `{"conclusion": ""}` the gateway raises and `decide()`
    bubbles the error up. We retry once with a stronger prompt that
    explicitly instructs the model to either answer or return
    `"insufficient_data"`. If the retry also fails, we synthesize a graceful
    `DecideResult` so the FastAPI handler returns 200 with a clear envelope
    instead of a 500 — Hermes/langchain consumers can route on it.
    """

    def _build_request(system_prompt: str) -> DecideRequest:
        return DecideRequest(
            org_id=org_id,
            query=query,
            facts=facts,
            ruleset=ruleset,
            module_id=module_id,
            user_id=user_id,
            gap_description=gap_desc,
            gap_facts=facts if isinstance(facts, dict) else {"facts": facts},
            neural_system_prompt=system_prompt,
            neural_output_schema=_NeuralGapConclusion,
        )

    try:
        return decide(session, gateway=gateway, request=_build_request(system_prompt))
    except GatewayValidationError as first_err:
        log.warning(
            "neural_query_first_attempt_rejected",
            module_id=module_id,
            org_id=org_id,
            error=str(first_err)[:200],
        )

    # Retry once with the suffix. Use the same gateway so the cost_guard +
    # billing path still meter the second call (customer pays for both
    # attempts — empirically <5% of queries take this branch).
    try:
        return decide(
            session,
            gateway=gateway,
            request=_build_request(system_prompt + _RETRY_PROMPT_SUFFIX),
        )
    except GatewayValidationError as final_err:
        log.warning(
            "neural_query_retry_rejected_synthesizing_envelope",
            module_id=module_id,
            org_id=org_id,
            error=str(final_err)[:200],
        )

    # Both attempts failed schema validation — return a graceful envelope
    # so the customer integration doesn't crash. We don't persist this as a
    # DecisionRow (it never reached `decide()`'s emit step), which is fine
    # for now since 500s would have lost the row too; if we need an audit
    # trail for these cases we can add a manual insert here later.
    from uuid import uuid4

    from core.delivery.envelope import build_envelope  # noqa: F401  (kept local to avoid cycles)
    from core.reasoning.rule_loader import ProofTree as _ProofTree
    from core.reflection.human_flag import Route as _Route
    from core.reflection.human_flag import RoutingDecision as _RoutingDecision

    return DecideResult(
        decision_id=str(uuid4()),
        conclusion="insufficient_data",
        path="neural",
        route=_Route.FLAG,
        confidence=0.10,
        confidence_breakdown={
            "constraint_pass": True,
            "grounding_score": 0.0,
            "consistency_score": 0.0,
            "symbolic_support": 0.0,
            "llm_validation_score": 0.0,
            "weights": {},
        },
        proof=_ProofTree(steps=[], final_conclusion="insufficient_data"),
        grounding_score=0.0,
        grounding_refs=[],
        routing=_RoutingDecision(
            route=_Route.FLAG,
            confidence=0.10,
            reason="neural output failed schema validation after retry",
        ),
        reflected=False,
        as_of_version=0,
        halted_by_cost_guard=False,
        recommendation_extras={
            "rationale": "LLM produced invalid/empty output twice — human review needed.",
            "recommended_action": "Inspect query + provided facts; engine could not synthesize an answer.",
        },
    )


# AsOfPin import retained for callers that import from this module
__all__ = ["AsOfPin", "bootstrap_modules", "build_envelope"]
