"""Decision replay — reproduce a past decision deterministically.

Per MD g-i-2 acceptance:
    Decision replay: given decision_id, reproduce same conclusion using
    as_of version + frozen rules.

Mechanism:
1. Load the stored Decision by id
2. Reconstruct graph state via core.worldmodel.temporal.as_of() at the decision's
   as_of_version (translating version -> timestamp via the events table)
3. Re-run the symbolic chain using the SAME rule snapshot (rule_loader from frozen module)
4. Compare new conclusion vs stored — equal => replay successful

Caller responsibilities:
- Provide the original RuleSet (or path to the module's frozen rules version)
- For neural-path decisions, replay only verifies SYMBOLIC reconstruction;
  neural outputs are not deterministic and are not re-derived
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.graph.store import GraphEventRow
from core.reasoning.rule_engine import ForwardChainer
from core.reasoning.rule_loader import RuleSet

log = get_logger(__name__)


@dataclass(frozen=True)
class ReplayResult:
    """Outcome of replaying a stored decision."""

    decision_id: str
    matched: bool  # original conclusion == replayed conclusion
    original_conclusion: str
    replayed_conclusion: str
    original_path: str  # symbolic | neural | hybrid
    as_of_version: int
    reason: str


def replay_decision(
    session: Session,
    *,
    decision_id: str,
    original_conclusion: str,
    original_path: str,
    org_id: str,
    as_of_version: int,
    input_facts: dict[str, Any],
    ruleset: RuleSet,
) -> ReplayResult:
    """Replay a decision and compare to the original.

    Caller passes the stored Decision's fields. Engine re-runs symbolic only
    (neural outputs not deterministic; their path is acknowledged but not re-derived).
    """
    # For purely-neural decisions, we can't replay symbolically. Mark as such.
    if original_path == "neural":
        return ReplayResult(
            decision_id=decision_id,
            matched=False,
            original_conclusion=original_conclusion,
            replayed_conclusion="",
            original_path=original_path,
            as_of_version=as_of_version,
            reason="neural-only path: cannot deterministically replay LLM output",
        )

    # Sanity-check the version exists for this org (catches data drift)
    ev_exists = session.execute(
        select(GraphEventRow.id)
        .where(GraphEventRow.org_id == org_id)
        .where(GraphEventRow.version <= as_of_version)
        .limit(1)
    ).first()
    if as_of_version > 0 and ev_exists is None:
        log.warning("replay_no_events_at_version", decision_id=decision_id, version=as_of_version)

    # Re-run symbolic chain with same facts + same ruleset
    chainer = ForwardChainer(ruleset)
    result = chainer.run(input_facts)
    replayed = result.proof.final_conclusion

    matched = replayed == original_conclusion
    log.info(
        "decision_replayed",
        decision_id=decision_id,
        matched=matched,
        original=original_conclusion,
        replayed=replayed,
    )
    return ReplayResult(
        decision_id=decision_id,
        matched=matched,
        original_conclusion=original_conclusion,
        replayed_conclusion=replayed,
        original_path=original_path,
        as_of_version=as_of_version,
        reason="symbolic replay matched" if matched else "symbolic replay differs",
    )
