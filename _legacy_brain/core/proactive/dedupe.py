"""Insight dedupe — signature + hysteresis + stale-retract.

Per MD g-i-4 §1.1.1:
- signature = (type, primary_entity, root_cause_edge)
- if sig seen in last window AND not materially changed: SUPPRESS (or increment
  "still-true" counter, don't re-push)
- Flapping (insight toggles on/off across cycles) -> HYSTERESIS (require N consecutive
  cycles before push/withdraw)
- Stale-retract: insight whose underlying facts went stale -> auto-retract
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.proactive.store import InsightRow
from core.proactive.types import Insight, InsightSignature

log = get_logger(__name__)


# Hysteresis: require N consecutive cycles before pushing (anti-flap)
DEFAULT_HYSTERESIS_CYCLES = 2

# Suppression window: same signature within this -> drop
DEFAULT_SUPPRESS_WINDOW_HOURS = 24


@dataclass(frozen=True)
class DedupeResult:
    """Outcome of running a batch through dedupe."""

    kept: list[Insight]
    suppressed_as_duplicate: list[Insight]
    suppressed_for_hysteresis: list[Insight]
    suppressed_as_stale: list[Insight]


def dedupe_batch(
    session: Session,
    *,
    candidates: list[Insight],
    suppress_window: timedelta | None = None,
    hysteresis_cycles: int = DEFAULT_HYSTERESIS_CYCLES,
    valid_signatures_in_subgraph: Iterable[InsightSignature] | None = None,
) -> DedupeResult:
    """Apply dedupe rules to a candidate batch from generate.py.

    Args:
        candidates: raw insights from generate.generate_for_subgraph
        suppress_window: how far back to look for prior signatures (default 24h)
        hysteresis_cycles: insights need to fire this many cycles in a row before delivery
        valid_signatures_in_subgraph: optional whitelist; signatures NOT in here are stale.
            Caller derives from the current subgraph; anything we've seen in DB whose facts
            no longer exist in the active subgraph is auto-retracted.
    """
    window = suppress_window or timedelta(hours=DEFAULT_SUPPRESS_WINDOW_HOURS)
    now = datetime.now(UTC)
    since = now - window

    kept: list[Insight] = []
    suppressed_dup: list[Insight] = []
    suppressed_hyst: list[Insight] = []

    for ins in candidates:
        sig_hash = ins.signature.hash()
        recent_count = _count_recent_with_signature(
            session, org_id=ins.org_id, sig_hash=sig_hash, since=since
        )

        if recent_count >= 1 and not _materially_changed(ins, session=session, sig_hash=sig_hash):
            suppressed_dup.append(ins)
            log.debug(
                "insight_suppressed_duplicate",
                org_id=ins.org_id,
                signature=sig_hash,
                recent_count=recent_count,
            )
            continue

        # Hysteresis: require N consecutive cycles before pushing
        if hysteresis_cycles > 1 and recent_count < (hysteresis_cycles - 1):
            suppressed_hyst.append(ins)
            log.debug(
                "insight_held_for_hysteresis",
                org_id=ins.org_id,
                signature=sig_hash,
                consecutive=recent_count + 1,
                needed=hysteresis_cycles,
            )
            continue

        kept.append(ins)

    # Stale-retract: any signature from DB no longer in the current subgraph is retracted
    stale: list[Insight] = []
    if valid_signatures_in_subgraph is not None:
        valid_hashes = {s.hash() for s in valid_signatures_in_subgraph}
        org_ids = {i.org_id for i in candidates}
        for org_id in org_ids:
            stale.extend(
                _find_recently_pushed_signatures_not_in(
                    session, org_id=org_id, since=since, valid_hashes=valid_hashes
                )
            )

    return DedupeResult(
        kept=kept,
        suppressed_as_duplicate=suppressed_dup,
        suppressed_for_hysteresis=suppressed_hyst,
        suppressed_as_stale=stale,
    )


# ─── internals ──────────────────────────────────────────────────────────────


def _count_recent_with_signature(
    session: Session, *, org_id: str, sig_hash: str, since: datetime
) -> int:
    rows = session.execute(
        select(InsightRow)
        .where(InsightRow.org_id == org_id)
        .where(InsightRow.signature_hash == sig_hash)
        .where(InsightRow.created_at >= since)
    ).all()
    return len(rows)


def _materially_changed(insight: Insight, *, session: Session, sig_hash: str) -> bool:
    """Has the underlying derivation changed since last time?

    v1: compare derivation chain length + last rule fired. If both match, treat as same.
    """
    latest = session.execute(
        select(InsightRow)
        .where(InsightRow.org_id == insight.org_id)
        .where(InsightRow.signature_hash == sig_hash)
        .order_by(InsightRow.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return True
    prev_chain = (
        latest.derivation_chain_jsonb.get("steps", [])
        if isinstance(latest.derivation_chain_jsonb, dict)
        else []
    )
    if len(prev_chain) != len(insight.derivation_chain):
        return True
    if prev_chain and insight.derivation_chain:
        prev_rule = prev_chain[-1].get("rule_id") if isinstance(prev_chain[-1], dict) else None
        new_rule = insight.derivation_chain[-1].get("rule_id")
        return bool(prev_rule != new_rule)
    return False


def _find_recently_pushed_signatures_not_in(
    session: Session,
    *,
    org_id: str,
    since: datetime,
    valid_hashes: set[str],
) -> list[Insight]:
    """Find insights pushed in window whose signature is no longer 'live' (stale-retract)."""
    rows = (
        session.execute(
            select(InsightRow)
            .where(InsightRow.org_id == org_id)
            .where(InsightRow.created_at >= since)
        )
        .scalars()
        .all()
    )

    out: list[Insight] = []
    seen: set[str] = set()
    for r in rows:
        if r.signature_hash in valid_hashes or r.signature_hash in seen:
            continue
        seen.add(r.signature_hash)
        # We re-hydrate just enough to surface for retraction notification
        try:
            from core.proactive.types import InsightType

            out.append(
                Insight(
                    id=r.id,
                    org_id=r.org_id,
                    type=InsightType(r.type),
                    primary_entity=r.primary_entity,
                    root_cause_edge=r.root_cause_edge,
                    derivation_chain=[],
                    grounding_refs=list(r.grounding_refs_jsonb or []),
                    created_at=r.created_at,
                )
            )
        except (ValueError, KeyError):  # malformed legacy row, skip
            continue
    return out
