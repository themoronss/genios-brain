"""LLM gateway — symbolic-first routing + targeted gap-fill.

Per MD g-i-2 §2.2.1 routing decision:
    def route(query, symbolic_result):
        if symbolic_result.resolved and symbolic_result.certainty == HARD:
            return SYMBOLIC                 # no LLM call - the cheap default
        if symbolic_result.has_gap or symbolic_result.ambiguous:
            return NEURAL_GAP_FILL          # targeted call, scoped to gap ONLY
        return SYMBOLIC                     # default safe

LLM never "does the decision". It fills a specific named gap. Prompt is built
from system_prompt + the gap + grounded facts ONLY.

Output validation (mandatory, per acceptance criteria):
- Schema-checked via caller-provided Pydantic model
- Constraint-validated against guardrails (caller wires)
- Unvalidated output NEVER propagates

Tracked metric: symbolic_resolution_rate = symbolic_resolved / total_decisions.
The gateway emits a `route_chosen` log event on every routing decision so g-i-8
telemetry can aggregate the ratio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from core.foundations.telemetry import get_logger
from core.neural.client import LLMCall, LLMClient, LLMResponse
from core.neural.cost_guard import BudgetExceededError, CostGuard
from core.reasoning.rule_engine import ChainResult

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class RoutingChoice(StrEnum):
    SYMBOLIC = "symbolic"
    NEURAL_GAP_FILL = "neural_gap_fill"
    HALTED = "halted"  # cost guard tripped — no LLM call possible


@dataclass(frozen=True)
class GatewayDecision:
    """Output of Gateway.route(). Carries the routing choice + (if neural) the LLM output."""

    route: RoutingChoice
    symbolic_result: ChainResult
    llm_response: LLMResponse | None
    parsed_output: BaseModel | None  # validated against caller's schema
    reason: str


class GatewayValidationError(Exception):
    """LLM output failed schema or constraint validation."""


class Gateway:
    """Symbolic-first decision router with constraint-validated neural gap-fill."""

    def __init__(self, llm: LLMClient, cost_guard: CostGuard) -> None:
        self._llm = llm
        self._cost_guard = cost_guard

    # ── public API ────────────────────────────────────────────────────────

    def route(
        self,
        *,
        org_id: str,
        symbolic_result: ChainResult,
        # neural-fallback config:
        gap_description: str | None = None,
        gap_facts: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        output_schema: type[T] | None = None,
        validate_fn: ValidationFn[T] | None = None,
        max_tokens: int = 512,
    ) -> GatewayDecision:
        """Route a decision. Symbolic-first; LLM only on gap.

        For neural path, caller MUST provide gap_description + system_prompt + output_schema.
        validate_fn (optional) runs after schema check — typically wraps guardrails.constraints.check.
        """
        # Step 1: symbolic resolved + hard-constrained -> done
        if symbolic_result.resolved and symbolic_result.has_hard:
            self._log_route(org_id, RoutingChoice.SYMBOLIC, reason="symbolic_hard")
            return GatewayDecision(
                route=RoutingChoice.SYMBOLIC,
                symbolic_result=symbolic_result,
                llm_response=None,
                parsed_output=None,
                reason="symbolic resolved with hard constraint",
            )

        # Step 2: symbolic resolved (no hard) -> still symbolic by default
        if symbolic_result.resolved:
            self._log_route(org_id, RoutingChoice.SYMBOLIC, reason="symbolic_soft")
            return GatewayDecision(
                route=RoutingChoice.SYMBOLIC,
                symbolic_result=symbolic_result,
                llm_response=None,
                parsed_output=None,
                reason="symbolic resolved (no hard constraint)",
            )

        # Step 3: unresolved -> try neural gap-fill if caller provided the wiring
        if gap_description is None or system_prompt is None or output_schema is None:
            self._log_route(org_id, RoutingChoice.SYMBOLIC, reason="symbolic_default_no_neural")
            return GatewayDecision(
                route=RoutingChoice.SYMBOLIC,
                symbolic_result=symbolic_result,
                llm_response=None,
                parsed_output=None,
                reason="symbolic default (caller did not supply neural fallback)",
            )

        # Cost-guard pre-call
        try:
            self._cost_guard.require_capacity(org_id)
        except BudgetExceededError as e:
            self._log_route(org_id, RoutingChoice.HALTED, reason=str(e))
            return GatewayDecision(
                route=RoutingChoice.HALTED,
                symbolic_result=symbolic_result,
                llm_response=None,
                parsed_output=None,
                reason=f"halted by cost guard: {e}",
            )

        # Step 4: LLM call (Haiku for gap-fill per Group 3 lock)
        prompt = self._build_gap_prompt(
            gap_description=gap_description,
            gap_facts=gap_facts or {},
            output_schema=output_schema,
        )
        call = LLMCall(
            model="haiku",
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=max_tokens,
            org_id=org_id,
            purpose="gap_fill",
        )
        resp = self._llm.call(call)
        self._cost_guard.charge(org_id, resp.cost_usd)

        # Step 5: parse + validate
        try:
            parsed = self._parse_output(resp.text, output_schema)
        except GatewayValidationError as e:
            self._log_route(org_id, RoutingChoice.NEURAL_GAP_FILL, reason=f"output_rejected: {e}")
            raise

        if validate_fn is not None:
            ok, why = validate_fn(parsed)
            if not ok:
                self._log_route(
                    org_id,
                    RoutingChoice.NEURAL_GAP_FILL,
                    reason=f"constraint_rejected: {why}",
                )
                raise GatewayValidationError(f"LLM output rejected by constraint validator: {why}")

        self._log_route(org_id, RoutingChoice.NEURAL_GAP_FILL, reason="ok")
        return GatewayDecision(
            route=RoutingChoice.NEURAL_GAP_FILL,
            symbolic_result=symbolic_result,
            llm_response=resp,
            parsed_output=parsed,
            reason="neural gap-fill (validated)",
        )

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_gap_prompt(
        *,
        gap_description: str,
        gap_facts: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> str:
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        facts_json = json.dumps(gap_facts, default=str, indent=2)
        return (
            f"Gap to fill:\n{gap_description}\n\n"
            f"Grounded facts:\n{facts_json}\n\n"
            f"Output JSON ONLY matching this schema (no prose, no fences):\n{schema_json}\n"
        )

    @staticmethod
    def _parse_output(raw: str, schema: type[T]) -> T:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip().removesuffix("```").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise GatewayValidationError(f"LLM returned unparseable JSON: {text[:200]}") from e
        try:
            return schema.model_validate(data)
        except ValidationError as e:
            raise GatewayValidationError(f"LLM output failed schema: {e}") from e

    @staticmethod
    def _log_route(org_id: str, route: RoutingChoice, *, reason: str) -> None:
        log.info("route_chosen", org_id=org_id, route=route.value, reason=reason)


# Caller-supplied constraint validator. Returns (ok, reason).
# Typically wraps guardrails.constraints.check + grounding.verify.
from collections.abc import Callable  # noqa: E402 — kept at end to avoid earlier import noise

ValidationFn = Callable[[T], tuple[bool, str]]
