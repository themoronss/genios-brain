"""Entity resolution — BLOCK -> SCORE -> DECIDE -> reversible MERGE.

Per MD g-i-3 §3.1.1:
- BLOCK    group candidates by cheap key (normalized name token, email domain, type)
           — avoids O(N^2) comparison
- SCORE    similarity(e1,e2) = w1*name + w2*attribute_overlap + w3*shared_source_context
- DECIDE   theta_auto -> auto-merge | theta_review..theta_auto -> FLAG human | else distinct
- MERGE    reversible — entity_merges row captures it; unmerge restores both nodes

Bias: theta_auto HIGH (false-merge worse than false-split). Two real "John Doe"s -> keep separate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.graph.store import NodeRow
from core.worldmodel.store import EntityMergeRow

log = get_logger(__name__)

# Thresholds — bias toward false-split (safer than false-merge for company data)
THETA_AUTO_MERGE = 0.92
THETA_REVIEW = 0.75

# Score weights — sum to 1.0
W_NAME = 0.5
W_ATTRIBUTES = 0.3
W_CONTEXT = 0.2


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResolutionDecision:
    """Outcome of comparing two nodes."""

    a_id: str
    b_id: str
    score: float
    verdict: Literal["auto_merge", "flag_for_human", "distinct"]
    reason: str


@dataclass(frozen=True)
class MergeRecord:
    """Audit row for a completed merge. Used by unmerge() to restore state."""

    merge_id: str
    merged_into: str
    merged_from: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# BLOCK — cheap key grouping
# ─────────────────────────────────────────────────────────────────────────────


def blocking_key(node: NodeRow) -> str:
    """Cheap key to group potential duplicates.

    Strategy: first token of canonical_name + type + first email domain from attributes.
    Two nodes share a block if their key matches -> only then we SCORE.
    """
    name_token = _first_token(node.canonical_name)
    email_domain = _email_domain(node.attributes)
    return f"{node.type}|{name_token}|{email_domain}"


def block_candidates(nodes: Iterable[NodeRow]) -> dict[str, list[NodeRow]]:
    """Group nodes by blocking key. Only same-block nodes get scored."""
    blocks: dict[str, list[NodeRow]] = {}
    for n in nodes:
        blocks.setdefault(blocking_key(n), []).append(n)
    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# SCORE — similarity
# ─────────────────────────────────────────────────────────────────────────────


def similarity(a: NodeRow, b: NodeRow) -> float:
    """Weighted similarity in [0,1]. Higher = more likely the same entity."""
    name_sim = _name_similarity(a.canonical_name, b.canonical_name)
    attr_overlap = _attribute_overlap(a.attributes, b.attributes)
    shared_ctx = _shared_source_context(a.source_item_ids, b.source_item_ids)
    return W_NAME * name_sim + W_ATTRIBUTES * attr_overlap + W_CONTEXT * shared_ctx


# ─────────────────────────────────────────────────────────────────────────────
# DECIDE
# ─────────────────────────────────────────────────────────────────────────────


def decide(a: NodeRow, b: NodeRow) -> ResolutionDecision:
    """Compare a pair within a block. Returns the verdict (no DB writes here)."""
    s = similarity(a, b)
    if s >= THETA_AUTO_MERGE:
        verdict: Literal["auto_merge", "flag_for_human", "distinct"] = "auto_merge"
        reason = "name+attrs+context strongly overlap"
    elif s >= THETA_REVIEW:
        verdict = "flag_for_human"
        reason = "moderate overlap; ambiguous"
    else:
        verdict = "distinct"
        reason = "low overlap"
    return ResolutionDecision(a_id=a.id, b_id=b.id, score=s, verdict=verdict, reason=reason)


# ─────────────────────────────────────────────────────────────────────────────
# MERGE (reversible)
# ─────────────────────────────────────────────────────────────────────────────


def merge(
    session: Session,
    *,
    org_id: str,
    keep_id: str,
    absorb_ids: list[str],
    merged_by: str,
) -> MergeRecord:
    """Merge absorb_ids INTO keep_id. Records the merge for reversibility.

    Post-conditions:
    - keep_id node accumulates aliases + source_item_ids from absorbed nodes
    - absorbed node rows are deleted (FK CASCADE moves edges if needed — caller
      is expected to repoint edges in a separate step; this function only mutates
      the node rows + writes the EntityMergeRow)
    """
    if keep_id in absorb_ids:
        raise ValueError("keep_id cannot also be in absorb_ids")

    keep = session.get(NodeRow, keep_id)
    if keep is None or keep.org_id != org_id:
        raise KeyError(f"keep node {keep_id} not found in org {org_id}")

    absorbed_snapshot: list[dict[str, object]] = []
    for aid in absorb_ids:
        absorb = session.get(NodeRow, aid)
        if absorb is None or absorb.org_id != org_id:
            raise KeyError(f"absorb node {aid} not found in org {org_id}")

        # Snapshot for reversibility (whole row, not just id)
        absorbed_snapshot.append(
            {
                "id": absorb.id,
                "canonical_name": absorb.canonical_name,
                "aliases": list(absorb.aliases),
                "attributes": dict(absorb.attributes),
                "source_item_ids": list(absorb.source_item_ids),
                "type": absorb.type,
                "org_unit": absorb.org_unit,
                "first_seen": absorb.first_seen.isoformat(),
                "last_seen": absorb.last_seen.isoformat(),
            }
        )

        # Accumulate aliases + source ids
        keep.aliases = sorted(set(keep.aliases) | {absorb.canonical_name} | set(absorb.aliases))
        keep.source_item_ids = sorted(set(keep.source_item_ids) | set(absorb.source_item_ids))
        keep.last_seen = max(keep.last_seen, absorb.last_seen)

        session.delete(absorb)

    merge_row = EntityMergeRow(
        org_id=org_id,
        merged_into=keep_id,
        merged_from=absorbed_snapshot,
        merged_by=merged_by,
    )
    session.add(merge_row)
    session.flush()

    audit.record(
        org_id=org_id,
        actor_type="user" if merged_by.startswith("user:") else "system",
        actor_id=merged_by,
        action="config_changed",
        target_type="entity",
        target_id=keep_id,
        metadata={
            "op": "merge",
            "merged_into": keep_id,
            "absorbed_count": len(absorb_ids),
            "merge_id": merge_row.id,
        },
    )

    return MergeRecord(merge_id=merge_row.id, merged_into=keep_id, merged_from=absorb_ids)


def unmerge(session: Session, *, merge_id: str, reversed_by: str) -> list[str]:
    """Reverse a merge. Restores absorbed nodes from snapshot. Returns restored ids.

    Note: edges that were repointed to keep_id are NOT auto-repointed back — caller
    must handle if edge fidelity matters. The MD design accepts this: structural
    rollback restores the snapshot; full edge-rollback is a separate concern.
    """
    merge_row = session.get(EntityMergeRow, merge_id)
    if merge_row is None:
        raise KeyError(f"merge {merge_id} not found")
    if merge_row.reversed_at is not None:
        raise RuntimeError(f"merge {merge_id} already reversed at {merge_row.reversed_at}")

    restored_ids: list[str] = []
    for snap in merge_row.merged_from:
        restored = NodeRow(
            id=str(snap["id"]),
            org_id=merge_row.org_id,
            org_unit=str(snap["org_unit"]),
            type=str(snap["type"]),
            canonical_name=str(snap["canonical_name"]),
            aliases=list(snap.get("aliases", [])),
            attributes=dict(snap.get("attributes", {})),
            source_item_ids=list(snap.get("source_item_ids", [])),
            first_seen=datetime.fromisoformat(str(snap["first_seen"])),
            last_seen=datetime.fromisoformat(str(snap["last_seen"])),
        )
        session.add(restored)
        restored_ids.append(restored.id)

    merge_row.reversed_at = datetime.now(UTC)
    merge_row.reversed_by = reversed_by

    audit.record(
        org_id=merge_row.org_id,
        actor_type="user" if reversed_by.startswith("user:") else "system",
        actor_id=reversed_by,
        action="config_changed",
        target_type="entity",
        target_id=merge_row.merged_into,
        metadata={"op": "unmerge", "merge_id": merge_id, "restored_count": len(restored_ids)},
    )
    return restored_ids


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _first_token(name: str) -> str:
    name = (name or "").strip().lower()
    if not name:
        return ""
    return name.split()[0]


def _email_domain(attrs: dict[str, object]) -> str:
    email = str(attrs.get("email", "")).lower()
    if "@" in email:
        return email.split("@", 1)[1]
    return ""


def _name_similarity(a: str, b: str) -> float:
    """Jaro-Winkler-style normalized similarity in [0,1] via rapidfuzz."""
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a, b) / 100.0


def _attribute_overlap(a: dict[str, object], b: dict[str, object]) -> float:
    """Fraction of shared key-value pairs (case-insensitive string compare)."""
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    matches = sum(1 for k in keys if str(a[k]).lower() == str(b[k]).lower())
    return matches / max(len(a), len(b))


def _shared_source_context(a_ids: list[str], b_ids: list[str]) -> float:
    """Jaccard over source_item_ids — same emails/docs suggest same person."""
    if not a_ids and not b_ids:
        return 0.0
    set_a = set(a_ids)
    set_b = set(b_ids)
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)
