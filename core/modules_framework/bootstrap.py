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

from sqlalchemy.orm import Session

from core.api.intelligence import (
    register_graph_view_handler,
    register_query_handler,
)
from core.decision import DecideRequest, decide
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
                rules=len(pkg.ruleset.rules),
            )
        except Exception as e:
            log.exception("module_load_failed", module=entry.name, error=str(e))

    return loaded


def _register_pkg(pkg: ModulePackage) -> None:
    """Wire the package's ruleset into the v2 intelligence query handler."""
    mid = pkg.manifest.id
    ruleset: RuleSet = pkg.ruleset

    def query_handler(
        session: Session,
        org_id: str,
        query: dict[str, Any],
        facts: dict[str, Any],
        user_id: str | None,
    ) -> Envelope:
        """Per-request dispatcher: runs the engine using THIS module's rules."""
        gateway = Gateway(llm=LLMClient(), cost_guard=CostGuard())
        request = DecideRequest(
            org_id=org_id,
            query=query,
            facts=facts,
            ruleset=ruleset,
            module_id=mid,
            user_id=user_id,
        )
        result = decide(session, gateway=gateway, request=request)
        return build_envelope(
            org_id=org_id,
            decision_id=result.decision_id,
            recommendation={"conclusion": result.conclusion},
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


def _to_envelope_route(route: Any) -> EnvelopeRoute:
    """Engine Route → EnvelopeRoute. Both are str enums with same values."""
    val = getattr(route, "value", route)
    if val == "autonomous":
        return EnvelopeRoute.AUTONOMOUS
    if val == "flag":
        return EnvelopeRoute.FLAG
    return EnvelopeRoute.NOTIFY


# AsOfPin import retained for callers that import from this module
__all__ = ["bootstrap_modules", "AsOfPin", "build_envelope"]
