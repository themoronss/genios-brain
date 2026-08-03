"""Cluster corrections that no existing rule covered -> propose new rule to a human.

Per MD g-i-3 §3.2.1:
- cluster corrections by input_context similarity
- if a cluster is large AND no existing rule covered those cases:
    emit CandidateRule(description, supporting_corrections) -> human authors it
- NEVER auto-write hard rules

The clusterer is intentionally simple (token-overlap-based) for v1; a smarter
similarity (embedding-based) can come later if needed. The key property is
"recurring uncovered pattern -> human's attention," not the choice of metric.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.worldmodel.store import CandidateRuleRow, CorrectionRow

log = get_logger(__name__)


# Minimum cluster size before we propose a rule (anti-noise)
DEFAULT_MIN_CLUSTER_SIZE = 5

# Similarity threshold for clustering (Jaccard on token sets)
DEFAULT_SIMILARITY_THRESHOLD = 0.6

# Cap on candidate rules per detection cycle
DEFAULT_MAX_CANDIDATES_PER_CYCLE = 5


@dataclass(frozen=True)
class Cluster:
    """A group of similar uncovered corrections."""

    correction_ids: list[str]
    centroid_tokens: set[str]
    size: int


def detect_candidate_rules(
    session: Session,
    *,
    org_id: str,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_candidates: int = DEFAULT_MAX_CANDIDATES_PER_CYCLE,
) -> list[CandidateRuleRow]:
    """Scan recent uncovered corrections; cluster; emit CandidateRule rows.

    "Uncovered" = correction.rule_ids was empty (no rule fired on the engine
    decision the human overrode).
    """
    uncovered = _load_uncovered_corrections(session, org_id=org_id)
    if len(uncovered) < min_cluster_size:
        return []

    clusters = _cluster(uncovered, threshold=similarity_threshold, min_size=min_cluster_size)
    if not clusters:
        return []

    # Cap (anti-spam) — rank by cluster size desc
    clusters.sort(key=lambda c: c.size, reverse=True)
    clusters = clusters[:max_candidates]

    new_rows: list[CandidateRuleRow] = []
    for cluster in clusters:
        if _candidate_already_exists(session, org_id=org_id, tokens=cluster.centroid_tokens):
            log.info(
                "rule_gap_skip_existing_cluster",
                tokens=sorted(cluster.centroid_tokens),
            )
            continue
        description = _describe(cluster)
        row = CandidateRuleRow(
            org_id=org_id,
            description=description,
            supporting_correction_ids=list(cluster.correction_ids),
            status="proposed",
        )
        session.add(row)
        new_rows.append(row)

    if new_rows:
        session.flush()
        for row in new_rows:
            audit.record(
                org_id=org_id,
                actor_type="system",
                actor_id="rule_gap.detect",
                action="config_changed",
                target_type="candidate_rule",
                target_id=row.id,
                metadata={
                    "supporting_corrections_count": len(row.supporting_correction_ids),
                    "description": row.description[:120],
                },
            )

    return new_rows


# ─── internals ──────────────────────────────────────────────────────────────


def _load_uncovered_corrections(session: Session, *, org_id: str) -> list[CorrectionRow]:
    """Load recent corrections that no rule fired on (rule_ids empty)."""
    rows = (
        session.execute(
            select(CorrectionRow)
            .where(CorrectionRow.org_id == org_id)
            .order_by(CorrectionRow.timestamp.desc())
            .limit(500)
        )
        .scalars()
        .all()
    )
    return [r for r in rows if not r.rule_ids]


def _cluster(
    corrections: Iterable[CorrectionRow],
    *,
    threshold: float,
    min_size: int,
) -> list[Cluster]:
    """Greedy clustering by Jaccard similarity on input_context tokens."""
    members: list[tuple[CorrectionRow, set[str]]] = [
        (c, _tokenize(c.input_context)) for c in corrections
    ]
    clusters: list[Cluster] = []
    visited: set[str] = set()

    for c, tokens in members:
        if c.id in visited:
            continue
        cluster_ids = [c.id]
        cluster_tokens = set(tokens)
        visited.add(c.id)

        for other, other_tokens in members:
            if other.id in visited:
                continue
            if _jaccard(cluster_tokens, other_tokens) >= threshold:
                cluster_ids.append(other.id)
                cluster_tokens |= other_tokens
                visited.add(other.id)

        if len(cluster_ids) >= min_size:
            clusters.append(
                Cluster(
                    correction_ids=cluster_ids,
                    centroid_tokens=cluster_tokens,
                    size=len(cluster_ids),
                )
            )
    return clusters


def _candidate_already_exists(session: Session, *, org_id: str, tokens: set[str]) -> bool:
    """Cheap dup check: existing proposed CandidateRule with > 50% token overlap."""
    rows = (
        session.execute(
            select(CandidateRuleRow)
            .where(CandidateRuleRow.org_id == org_id)
            .where(CandidateRuleRow.status == "proposed")
        )
        .scalars()
        .all()
    )
    for r in rows:
        existing_tokens = set(_safe_split(r.description))
        if _jaccard(existing_tokens, tokens) > 0.5:
            return True
    return False


def _describe(cluster: Cluster) -> str:
    """Human-readable proposal text."""
    tokens = sorted(cluster.centroid_tokens)[:12]
    return (
        f"Recurring uncovered pattern across {cluster.size} corrections; "
        f"key terms: {', '.join(tokens)}"
    )


def _tokenize(context: dict[str, Any]) -> set[str]:
    """Flatten context to a token set for similarity comparison."""
    tokens: set[str] = set()
    _collect(context, tokens)
    return tokens


def _collect(node: Any, tokens: set[str]) -> None:
    if isinstance(node, dict):
        for v in node.values():
            _collect(v, tokens)
    elif isinstance(node, list):
        for v in node:
            _collect(v, tokens)
    elif isinstance(node, str):
        for t in node.lower().split():
            t = t.strip(".,;:!?()[]{}\"'")
            if len(t) >= 3:
                tokens.add(t)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _safe_split(s: str) -> list[str]:
    return [t.strip(".,;:!?()[]{}\"'") for t in s.lower().split() if len(t) >= 3]
