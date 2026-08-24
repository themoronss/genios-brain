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

    ``entity_id`` (the fact's ``subject_node_id``, when the ref points at a fact) lets a unit tell
    "10 observations about 10 different companies" apart from "10 observations about the same one"
    — a ref with no fact behind it (edge- or observation-sourced) carries ``entity_id = None``, and
    a unit that needs entity diversity must treat that as unknown, not as a distinct entity.
    """
    rows = conn.execute(text(
        "select r.source_ref_id, r.source, r.independence_group, r.event_id, "
        "gf.subject_node_id as entity_id, "
        "e.object_type, e.internal_kind, e.occurred_at "
        "from graph_source_refs r join source_events e "
        "  on e.org_id = r.org_id and e.event_id = r.event_id "
        "left join graph_facts gf "
        "  on gf.org_id = r.org_id and gf.fact_version_id = r.fact_version_id "
        "where r.org_id = :o and e.occurred_at >= :s "
        "order by e.occurred_at desc limit 5000"),
        {"o": org_id, "s": since}).mappings().all()

    # The inner join above IS the lineage check, and an inner join drops rows in silence. A ref
    # whose source event is gone was deliberately withheld from learning — that is the no-silent-
    # drop contract's exact subject — and until now the withholding left no trace, so "isolated
    # for missing lineage" and "never existed" were the same observation. Count them and record
    # the isolation, in the ledger migration 0046 created for it and nothing ever wrote to.
    dropped = conn.execute(text(
        "select count(*) from graph_source_refs r "
        "where r.org_id = :o and not exists ("
        "  select 1 from source_events e where e.org_id = r.org_id and e.event_id = r.event_id)"),
        {"o": org_id}).scalar() or 0
    if dropped:
        _record_rejection(conn, org_id, "enterprise.lineage",
                          f"lineage_unresolvable: {dropped} refs have no source event")
    return tuple(dict(r) for r in rows)


#: Optional seams whose ledger is not yet created by a migration. They read as empty (an empty seam
#: emits nothing) and are wired to their real table the moment that migration lands — the feedback
#: verdict ledger (calibration's `canonical_judgments`) and the 0046 hardening `learning_event_inbox`.
#: The table name is resolved at runtime through ``_read_optional_seam`` so we never bake a
#: not-yet-created table into a SQL string the reference-ratchet would (correctly) reject.
#: `canonical_judgments` was never a table. It is a CTE defined inside
#: `AUDITED_CARD_JUDGMENTS_CTES` (reason/authority.py) and consumed only by
#: `feedback/calibrate.py`, so `to_regclass('public.canonical_judgments')` returns NULL and the
#: seam silently resolved to nothing, forever. No migration could ever have fixed it — the name
#: belongs to a query, not to storage — so every plan that treated this as "the table is missing"
#: was chasing something that could not exist.
#:
#: The real ledger of human judgments is `card_feedback_verdicts` (migration 0034).
_OPTIONAL_FEEDBACK_TABLE = "card_feedback_verdicts"
_OPTIONAL_INBOX_TABLE = "learning_event_inbox"


def _read_optional_seam(conn, table: str, org_id: str, since: datetime, time_col: str) -> tuple[dict, ...]:
    if not _table_exists(conn, table):
        return ()
    try:
        # `order by 1` orders by whatever column happens to sit first, which is not a contract —
        # a column reordering silently changes which 5000 rows a learning run sees. Order by the
        # time column the caller named, which is the only ordering that means anything here.
        stmt = text(f"select * from {table} where org_id = :o and {time_col} >= :s "  # noqa: S608
                    f"order by {time_col} desc limit 5000")
        return tuple(dict(r) for r in conn.execute(stmt, {"o": org_id, "s": since}).mappings())
    except Exception as exc:  # noqa: BLE001 — a shape mismatch isolates the seam, never fails the run
        # Isolate, but LEAVE A RECORD. `learning_input_rejections` exists (migration 0046) and
        # its own comment calls it "sanitized isolation of a malformed/lineage-less input" — and
        # nothing in the codebase ever wrote to it. So the layer's isolation ledger recorded
        # nothing, and an input the system deliberately quarantined was indistinguishable from
        # one that never arrived. That is the no-silent-drop contract failing in the one place
        # built to uphold it.
        _record_rejection(conn, org_id, table, f"{type(exc).__name__}: {exc}"[:400])
        return ()


def _record_rejection(conn, org_id: str, seam: str, reason: str) -> None:
    """Note that a seam was isolated, without letting the note itself break the run.

    Best-effort by design: a learning run must not fail because its own audit write failed, and
    the alternative — raising here — would turn a recoverable seam problem into a lost run.
    """
    try:
        from genios_engine.platform.ids import new_id
        conn.execute(text(
            "insert into learning_input_rejections "
            "(id, org_id, seam, source_ref, reason_code, created_at) "
            "values (:id, :o, :seam, :ref, :code, now())"),
            {"id": new_id("lrej"), "o": org_id, "seam": seam,
             # the seam is the source; the exception text is the code, truncated to the column's
             # purpose (a reason, not a stack trace)
             "ref": seam, "code": reason[:200]})
    except Exception:      # noqa: BLE001 — an audit row is never worth losing the run over
        pass


def _load_feedback(conn, org_id: str, since: datetime) -> tuple[dict, ...]:
    """Terminal card verdicts, once the canonical verdict ledger exists. Empty otherwise."""
    return _read_optional_seam(conn, _OPTIONAL_FEEDBACK_TABLE, org_id, since, "created_at")


def _load_inbox(conn, org_id: str, since: datetime) -> tuple[dict, ...]:
    """Trusted structured events/memory — attaches with the 0046 hardening `learning_event_inbox`."""
    return _read_optional_seam(conn, _OPTIONAL_INBOX_TABLE, org_id, since, "observed_at")


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
