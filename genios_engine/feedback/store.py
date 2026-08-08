"""Layer 6 · Phase 2 — the Learning Selector (``load_batch``, Part 2).

Reads a bounded 28-day, tenant-scoped cohort from the input seams and hands the analysis units a
typed, lineage-checked batch. Every accepted fact is tenant-scoped, time-bounded and tied to
verifiable source identity; a malformed or lineage-less row is isolated, not fabricated into
org-visible evidence, and never fails the whole run. An empty seam simply yields nothing, so its
unit emits nothing — silence is not a signal.

Seams (only what exists is read; a missing seam is empty, per the spec):
  · Layer 5 outcomes        ``execution_outcomes``      — succeeded / neutral / negative labels
  · Layer 5.2 delivery       ``DeliveryFact``            — receipt-backed engagement only
  · Enterprise events        ``graph_source_refs → source_events`` — with lineage
  · Explicit card feedback   ``canonical_judgments``     — terminal verdicts (when present)
  · Explicit memory/events   ``learning_event_inbox``    — trusted structured (0046 hardening)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.feedback.delivery_facts import DeliveryFact, load_delivery_facts

#: The bounded cohort window. Older evidence is out of scope for a run — learning is recent.
COHORT_DAYS = 28


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute(text("select to_regclass('public.'||:t)"), {"t": name}).scalar())


@dataclass(frozen=True, slots=True)
class LearningBatch:
    """The typed, lineage-checked cohort one learning run analyses. Empty lists are legitimate."""

    org_id: str
    since: datetime
    outcomes: tuple[dict, ...] = ()
    feedback: tuple[dict, ...] = ()
    delivery: tuple[DeliveryFact, ...] = ()
    enterprise: tuple[dict, ...] = ()
    inbox: tuple[dict, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.outcomes or self.feedback or self.delivery
                    or self.enterprise or self.inbox)

    def counts(self) -> dict[str, int]:
        return {"outcomes": len(self.outcomes), "feedback": len(self.feedback),
                "delivery": len(self.delivery), "enterprise": len(self.enterprise),
                "inbox": len(self.inbox)}


def _load_outcomes(conn, org_id: str, since: datetime) -> tuple[dict, ...]:
    """Layer 5 outcomes. `completed_unproven` stays neutral — never fabricated into success."""
    rows = conn.execute(text(
        "select execution_id, capability_id, capability_version, play_id, label, terminal_state, "
        "reason_code, subject_ref, reminders_sent, escalations_fired, seconds_to_close, "
        "progress_bp, closed_at from execution_outcomes "
        "where org_id = :o and closed_at >= :s order by closed_at desc limit 5000"),
        {"o": org_id, "s": since}).mappings().all()
    return tuple(dict(r) for r in rows)


def _load_enterprise(conn, org_id: str, since: datetime) -> tuple[dict, ...]:
    """Enterprise events, but only with intact ``graph_source_refs → source_events`` lineage.

    A row without a resolvable source event is isolated (not returned) rather than promoted to an
    org-visible fact — the join itself is the lineage check.
    """
    rows = conn.execute(text(
        "select r.source_ref_id, r.source, r.independence_group, r.event_id, "
        "e.object_type, e.internal_kind, e.occurred_at "
        "from graph_source_refs r join source_events e "
        "  on e.org_id = r.org_id and e.event_id = r.event_id "
        "where r.org_id = :o and e.occurred_at >= :s "
        "order by e.occurred_at desc limit 5000"),
        {"o": org_id, "s": since}).mappings().all()
    return tuple(dict(r) for r in rows)


def _load_feedback(conn, org_id: str, since: datetime) -> tuple[dict, ...]:
    """Terminal card verdicts, when the canonical ledger exists. Empty otherwise (an empty seam)."""
    if not _table_exists(conn, "canonical_judgments"):
        return ()
    try:
        rows = conn.execute(text(
            "select * from canonical_judgments where org_id = :o and created_at >= :s "
            "order by created_at desc limit 5000"), {"o": org_id, "s": since}).mappings().all()
        return tuple(dict(r) for r in rows)
    except Exception:  # noqa: BLE001 — a shape mismatch isolates the seam, never fails the run
        return ()


def _load_inbox(conn, org_id: str, since: datetime) -> tuple[dict, ...]:
    """Trusted structured events/memory — arrives with the 0046 hardening (`learning_event_inbox`)."""
    if not _table_exists(conn, "learning_event_inbox"):
        return ()
    rows = conn.execute(text(
        "select * from learning_event_inbox where org_id = :o and observed_at >= :s "
        "order by observed_at desc limit 5000"), {"o": org_id, "s": since}).mappings().all()
    return tuple(dict(r) for r in rows)


def load_batch(conn, *, org_id: str, now: datetime,
               cohort_days: int = COHORT_DAYS) -> LearningBatch:
    """Assemble the bounded cohort for one tenant. Each seam is read independently and defensively."""
    since = now - timedelta(days=cohort_days)
    return LearningBatch(
        org_id=org_id, since=since,
        outcomes=_load_outcomes(conn, org_id, since),
        feedback=_load_feedback(conn, org_id, since),
        delivery=tuple(load_delivery_facts(conn, org_id=org_id, since=since)),
        enterprise=_load_enterprise(conn, org_id, since),
        inbox=_load_inbox(conn, org_id, since))


__all__ = ["COHORT_DAYS", "LearningBatch", "load_batch"]
