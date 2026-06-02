"""Narrator — LLM as TRANSLATOR only (proof tree -> plain prose).

Per MD g-i-6 §6.1.1 (HARD RULE):
- LLM may improve readability
- LLM MAY NOT introduce a fact / number / reason the engine didn't produce
- Ungrounded sentence -> reject and regenerate (max MAX_REGEN_ATTEMPTS)
- If still ungrounded after retries -> error surfaced; artifact NOT shipped

Output is verified with core.artifacts.grounding (which delegates to
core.guardrails.grounding — same verifier used elsewhere). Conservative by
design: false-positives blocked, false-negatives possible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.artifacts.grounding import GroundingVerification, verify_grounding_of_claims
from core.artifacts.trace import Trace
from core.foundations.config import MAX_REGEN_ATTEMPTS
from core.foundations.telemetry import get_logger
from core.neural.client import LLMCall, LLMClient

log = get_logger(__name__)


class NarratorRejected(Exception):
    """All regen attempts produced ungrounded output. Artifact NOT shippable."""


@dataclass(frozen=True)
class NarratorResult:
    """Successful narration. Prose is verified-grounded."""

    prose: str
    attempts: int
    grounding: GroundingVerification


_SYS_PROMPT = """You translate a structured proof tree into plain readable prose.

HARD RULES:
- ONLY use facts and rule conclusions provided in the proof tree.
- DO NOT introduce numbers, names, dates, or claims not present in the proof tree.
- DO NOT invent counterfactuals (those come from a separate symbolic system).
- Output 2-4 sentences. No headings, no bullet lists.

If you cannot translate without inventing something, output exactly:
INSUFFICIENT_PROOF
"""


def narrate(
    session: Session,
    *,
    trace: Trace,
    llm: LLMClient,
    rejections_logger: RejectionLogger | None = None,
) -> NarratorResult:
    """Translate a trace into prose. Validates grounding. Retries on failure.

    Args:
        session: SQLAlchemy session — used by grounding verifier
        trace: the engine's full trace payload
        llm: shared LLMClient (cost tracked + audit logged by client itself)
        rejections_logger: optional callable to persist rejection events for observability

    Raises:
        NarratorRejected: if MAX_REGEN_ATTEMPTS exhausted without a grounded output.
    """
    prompt = _build_user_prompt(trace)
    last_grounding: GroundingVerification | None = None

    for attempt in range(MAX_REGEN_ATTEMPTS):
        call = LLMCall(
            model="haiku",  # translator role — Haiku is the right cost/quality
            system_prompt=_SYS_PROMPT,
            user_prompt=prompt,
            max_tokens=256,
            temperature=0.0,
            org_id=trace.org_id,
            purpose="narrator",
        )
        resp = llm.call(call)
        prose = resp.text.strip()

        if prose == "INSUFFICIENT_PROOF":
            log.info(
                "narrator_self_refused",
                decision_id=trace.decision_id,
                attempt=attempt + 1,
            )
            if rejections_logger is not None:
                rejections_logger(
                    decision_id=trace.decision_id,
                    org_id=trace.org_id,
                    rejected_claim="(narrator self-refused)",
                    reason="LLM said INSUFFICIENT_PROOF",
                    retry_count=attempt + 1,
                )
            continue

        # Verify grounding of every sentence-claim
        sentences = _split_sentences(prose)
        verification = verify_grounding_of_claims(session, org_id=trace.org_id, claims=sentences)
        last_grounding = verification

        if verification.all_grounded:
            log.info(
                "narrator_grounded",
                decision_id=trace.decision_id,
                attempts=attempt + 1,
                grounding_score=verification.grounding_score,
            )
            return NarratorResult(prose=prose, attempts=attempt + 1, grounding=verification)

        log.warning(
            "narrator_ungrounded_retry",
            decision_id=trace.decision_id,
            attempt=attempt + 1,
            ungrounded_count=len(verification.ungrounded_claims),
        )
        if rejections_logger is not None:
            for claim in verification.ungrounded_claims:
                rejections_logger(
                    decision_id=trace.decision_id,
                    org_id=trace.org_id,
                    rejected_claim=claim,
                    reason="ungrounded sentence",
                    retry_count=attempt + 1,
                )

    raise NarratorRejected(
        f"Narrator could not produce grounded prose after {MAX_REGEN_ATTEMPTS} attempts "
        f"for decision {trace.decision_id}. "
        f"Last ungrounded: {last_grounding.ungrounded_claims if last_grounding else []}"
    )


# ─── helpers ────────────────────────────────────────────────────────────────


# Caller-supplied logger signature
class RejectionLogger:
    """Callable protocol — persists narrator rejection events for observability."""

    def __call__(
        self,
        *,
        decision_id: str,
        org_id: str,
        rejected_claim: str,
        reason: str,
        retry_count: int,
    ) -> None: ...


def _build_user_prompt(trace: Trace) -> str:
    """Render the trace into a structured prompt for the LLM."""
    parts: list[str] = []
    parts.append("PROOF TREE:\n")

    if trace.source_facts:
        parts.append("Source facts:")
        for f in trace.source_facts:
            parts.append(f"  - {f.subject} {f.predicate} {f.object} (source: {f.source_item_id})")
        parts.append("")

    if trace.rules_fired:
        parts.append("Rules fired (in order):")
        for r in trace.rules_fired:
            parts.append(f"  - {r.id} (priority {r.priority}) -> conclusion: '{r.conclusion}'")
        parts.append("")

    if trace.graph_path:
        parts.append("Graph path:")
        for e in trace.graph_path:
            parts.append(
                f"  - {e.from_node} -[{e.edge_type}, weight={e.weight:.2f} via {e.weight_source}]-> {e.to_node}"
            )
        parts.append("")

    parts.append(f"Confidence: {trace.confidence.overall:.2f}")
    if trace.uncertainty:
        parts.append("Known uncertainties (must NOT be hidden):")
        for u in trace.uncertainty:
            parts.append(f"  - [{u.kind.value}, severity={u.severity}] {u.detail}")

    parts.append("\nTranslate the above into 2-4 plain-English sentences for a sales rep.")
    return "\n".join(parts)


def _split_sentences(prose: str) -> list[str]:
    """Crude sentence split — good enough for grounding check on short LLM outputs."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose) if s.strip()]
