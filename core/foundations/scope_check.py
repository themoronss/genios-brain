"""End-to-end scope enforcement audit (g-i-8).

The acceptance criterion is: "data outside scope NEVER reaches an agent."
Two layers already enforce this at the source:
- g-i-1 `ScopeEnforcer` at ingest (post-fetch drop, with per-record audit)
- g-i-2 emit pipeline only references grounded facts

This module is the BELT on top of those suspenders: for any emitted decision,
walk its `grounding_refs` and verify every ref traces back to a real FactRow
that belongs to the same org. A ref that doesn't resolve = a smuggled ref.

Designed to be run periodically (nightly) and on-demand from the audit API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.graph.store import FactRow

log = get_logger(__name__)


@dataclass(frozen=True)
class ScopeViolation:
    """A grounding ref that doesn't trace back to a same-org fact."""

    decision_id: str
    grounding_ref: str
    reason: str  # "ref_not_in_facts" | "wrong_org"


@dataclass
class ScopeAuditReport:
    org_id: str
    audited_at: datetime
    decisions_checked: int = 0
    refs_checked: int = 0
    violations: list[ScopeViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


def audit_decisions(
    session: Session,
    *,
    org_id: str,
    since: datetime | None = None,
) -> ScopeAuditReport:
    """Walk recent decisions and verify every grounding_ref resolves to a same-org FactRow."""
    since = since or (datetime.now(UTC) - timedelta(days=7))

    decisions = list(
        session.execute(
            select(DecisionRow)
            .where(DecisionRow.org_id == org_id)
            .where(DecisionRow.created_at >= since)
        )
        .scalars()
        .all()
    )

    report = ScopeAuditReport(org_id=org_id, audited_at=datetime.now(UTC))

    all_refs: set[str] = set()
    for d in decisions:
        for r in d.grounding_refs_jsonb or []:
            all_refs.add(r)

    # Bulk lookup: facts in this org with matching source_item_ids
    in_org_refs: set[str] = set()
    any_org_refs: set[str] = set()
    if all_refs:
        in_org_rows = (
            session.execute(
                select(FactRow.source_item_id)
                .where(FactRow.org_id == org_id)
                .where(FactRow.source_item_id.in_(all_refs))
                .distinct()
            )
            .scalars()
            .all()
        )
        in_org_refs = set(in_org_rows)
        any_org_rows = (
            session.execute(
                select(FactRow.source_item_id)
                .where(FactRow.source_item_id.in_(all_refs))
                .distinct()
            )
            .scalars()
            .all()
        )
        any_org_refs = set(any_org_rows)

    for d in decisions:
        report.decisions_checked += 1
        for ref in d.grounding_refs_jsonb or []:
            report.refs_checked += 1
            if ref in in_org_refs:
                continue
            if ref in any_org_refs:
                report.violations.append(
                    ScopeViolation(
                        decision_id=d.id,
                        grounding_ref=ref,
                        reason="wrong_org",
                    )
                )
            else:
                report.violations.append(
                    ScopeViolation(
                        decision_id=d.id,
                        grounding_ref=ref,
                        reason="ref_not_in_facts",
                    )
                )

    audit.record_db(
        session,
        org_id=org_id,
        actor_type="system",
        actor_id="scope_audit",
        action="data_accessed",
        target_type="decisions",
        target_id=org_id,
        metadata={
            "decisions_checked": report.decisions_checked,
            "refs_checked": report.refs_checked,
            "violations": len(report.violations),
        },
    )
    log.info(
        "scope_audit_complete",
        org_id=org_id,
        decisions=report.decisions_checked,
        refs=report.refs_checked,
        violations=len(report.violations),
    )
    return report
