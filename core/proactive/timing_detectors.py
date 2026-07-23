"""Timing detectors — v2 port of the 3 high-value time-based signals.

WHY this exists:

  The old System-B detector fleet (`app/graph/detectors/*`) queried v1 tables
  that were dropped in migration 0015 (contacts / interactions / commitments /
  state_entities / engagement_health). It produced nothing and was retired.
  Three of those detectors were genuinely valuable — they fire on the passage
  of TIME, not on a fact change, so the module rulesets in `pipeline.py`
  (which key off `facts` predicates) can't see them. This module re-ports
  exactly those three onto the v2 schema.

WHAT this module does — 3 detectors, all reading v2 directly:

  1. going_cold        — `graph_nodes` (type='entity') whose `last_seen` age
                         crosses a threshold. >14d = cooling, >30d = cold.
  2. role_change       — an entity's most-recent role/works_at/title fact
                         (from `facts`, by created_at) differs from the prior
                         value. Fires on the change.
  3. overdue_commitment — commitment facts with a due/due_on/due_date predicate
                         whose date is in the past, and whose status is not
                         done/closed/paid.

HOW it's wired:

  Called from `core.proactive.pipeline.run_all_for_org` alongside the module
  rulesets, so all three triggers (bus event subscriber, hourly Celery
  `task_proactive_scan`, and the `/v1/scan` route) run these detectors on the
  same cadence, org-scoped, inside the caller's transaction (we never commit).

  Every fired signal is persisted as a `proactive_insights` row using the exact
  `InsightRow` shape the pipeline + hypothesizer use, and guarded by the same
  24h signature-dedupe window — so dashboard / MCP / dedupe all treat these
  identically to any other proactive insight. No new tables, no fabricated
  scores (no sentiment / confidence-invention): every field is derived from
  data actually present in `graph_nodes` / `facts`.

Plan alignment: g-i-4 (proactive emit). Same `proactive_insights` sink,
same 24h dedupe window (MD §1.1.1), same InsightType taxonomy.
"""

from __future__ import annotations

import hashlib
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.proactive.store import InsightRow

log = get_logger(__name__)


# 24h idempotency — identical to pipeline.SUPPRESS_WINDOW_HOURS. A signal that
# already fired for the same (detector, subject) within this window is skipped.
SUPPRESS_WINDOW_HOURS = 24

# going_cold thresholds (days since last_seen).
COOLING_AGE_DAYS = 14
COLD_AGE_DAYS = 30

# Predicates that represent a person's role/title/employer. Compared over time
# for role_change. Open-vocabulary (see worldmodel/extract.py style guide), so
# we accept the common variants the extractor emits.
_ROLE_PREDICATES = ("role", "title", "works_at", "worked_at", "reports_to")

# Predicates that carry a commitment's due date (worldmodel extract verbs +
# csv_ingest mapping). Object is expected to be an ISO date string.
_DUE_PREDICATES = ("due_on", "due_date", "due", "expires_on")

# Status values that mean the commitment is resolved — never overdue.
_DONE_STATUSES = frozenset({"done", "closed", "paid", "won", "resolved", "completed", "cancelled"})


def _signature_hash(*, detector: str, subject: str, discriminator: str = "") -> str:
    """Deterministic 32-char signature for the 24h dedupe window.

    detector + subject is the primary key of a signal; `discriminator` lets a
    detector distinguish materially-different firings on the same subject
    (e.g. role_change carrying the new value so a SECOND role change re-fires).
    """
    raw = f"timing|{detector}|{subject}|{discriminator}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _seen_signatures(session: Session, org_id: str) -> set[str]:
    """Signatures already emitted for this org inside the suppression window."""
    cutoff = datetime.now(UTC) - timedelta(hours=SUPPRESS_WINDOW_HOURS)
    return {
        row[0]
        for row in session.execute(
            text(
                """
                SELECT signature_hash
                FROM proactive_insights
                WHERE org_id = :org
                  AND created_at >= :cutoff
                """
            ),
            {"org": org_id, "cutoff": cutoff},
        ).fetchall()
    }


def _age_days(ts: datetime | None) -> float | None:
    """Whole-and-fractional days between `ts` and now (UTC-aware). None-safe."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return (datetime.now(UTC) - ts).total_seconds() / 86400.0


def _parse_iso_date(raw: str) -> datetime | None:
    """Best-effort ISO date/datetime parse. Returns None on anything unparseable
    (relative dates like 'by Friday' are intentionally skipped — we only fire on
    a concrete past date, never a guess)."""
    if not raw:
        return None
    s = raw.strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        pass
    # date-only fallback
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _insight_row(
    *,
    org_id: str,
    detector: str,
    itype: str,
    priority: str,
    subject: str,
    title: str,
    category: str,
    memory_view: str,
    genios_view: str,
    signature_hash: str,
    matched_facts: dict[str, Any],
    grounding_refs: list[str],
) -> InsightRow:
    """Build a proactive_insights row in the exact shape pipeline/hypothesizer use.

    delivery_route is always 'notify' — timing signals surface to a human, they
    never fire an autonomous action (mirrors the hypothesizer's contract).
    """
    return InsightRow(
        id=str(_uuid.uuid4()),
        org_id=org_id,
        type=itype,  # InsightType taxonomy: "risk" | "opportunity" | ...
        primary_entity=subject,
        root_cause_edge="",  # signal is fact/node-derived, no single graph edge
        derivation_chain_jsonb=[
            {
                "rule_id": f"timing:{detector}",
                "rule_module": "timing_detectors",
                "conclusion": category,
                "matched_facts": matched_facts,
                "reason": genios_view,
                "hard": False,
            }
        ],
        foresight_jsonb=None,
        scores_jsonb={
            "rule_id": f"timing:{detector}",
            "priority": priority,          # low | medium | high
            "title": title,
            "category": category,
            "client_name": subject,
            "memory_view": memory_view,
            "genios_view": genios_view,
        },
        grounding_refs_jsonb=grounding_refs,
        signature_hash=signature_hash,
        delivery_route="notify",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Detector 1 — going_cold
# ─────────────────────────────────────────────────────────────────────────────


def _detect_going_cold(
    session: Session, *, org_id: str, seen: set[str]
) -> list[InsightRow]:
    """Entities whose last_seen age crosses the cooling/cold thresholds.

    Priority scales with age: >COLD_AGE_DAYS = high, else medium. The signature
    includes the band so an entity that goes from cooling -> cold re-fires once
    (a genuinely new, more-urgent state), but does not re-fire every scan while
    it stays in the same band.
    """
    rows = session.execute(
        text(
            """
            SELECT id, canonical_name, last_seen
            FROM graph_nodes
            WHERE org_id = :org
              AND type = 'entity'
              AND last_seen < :cutoff
            ORDER BY last_seen ASC
            LIMIT 100
            """
        ),
        {
            "org": org_id,
            "cutoff": datetime.now(UTC) - timedelta(days=COOLING_AGE_DAYS),
        },
    ).fetchall()

    out: list[InsightRow] = []
    for r in rows:
        name = r.canonical_name
        age = _age_days(r.last_seen)
        if age is None:
            continue
        band = "cold" if age >= COLD_AGE_DAYS else "cooling"
        priority = "high" if band == "cold" else "medium"
        sig = _signature_hash(detector="going_cold", subject=name, discriminator=band)
        if sig in seen:
            continue
        seen.add(sig)
        age_i = int(age)
        title = f"{name} going {band} — no activity in {age_i} days"
        memory_view = f"{name}: last_seen {age_i}d ago (threshold {band})"
        genios_view = (
            f"No new memory item has referenced {name} in {age_i} days. "
            f"Entity crossed the {band} threshold "
            f"({COLD_AGE_DAYS if band == 'cold' else COOLING_AGE_DAYS}d). "
            f"Relationship may be cooling — consider re-engaging."
        )
        out.append(
            _insight_row(
                org_id=org_id,
                detector="going_cold",
                itype="risk",
                priority=priority,
                subject=name,
                title=title,
                category="going_cold",
                memory_view=memory_view,
                genios_view=genios_view,
                signature_hash=sig,
                matched_facts={"last_seen_age_days": age_i, "band": band},
                grounding_refs=[str(r.id)],
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Detector 2 — role_change
# ─────────────────────────────────────────────────────────────────────────────


def _detect_role_change(
    session: Session, *, org_id: str, seen: set[str]
) -> list[InsightRow]:
    """Fire when an entity's most-recent role/works_at/title fact differs from
    the immediately-prior value for the SAME predicate.

    We compare the two most-recent facts per (subject, predicate); if their
    objects differ, the role changed. The signature carries the new value so a
    later, further change re-fires once rather than being suppressed as a dup.
    """
    rows = session.execute(
        text(
            """
            SELECT subject, predicate, object, created_at
            FROM facts
            WHERE org_id = :org
              AND predicate = ANY(:preds)
            ORDER BY subject, predicate, created_at DESC
            """
        ),
        {"org": org_id, "preds": list(_ROLE_PREDICATES)},
    ).fetchall()

    # Group ordered rows into (subject, predicate) -> [objects newest-first].
    grouped: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        grouped.setdefault((r.subject, r.predicate), []).append(r.object)

    out: list[InsightRow] = []
    for (subject, predicate), objects in grouped.items():
        if len(objects) < 2:
            continue  # need at least a prior + a current to detect a change
        new_val = (objects[0] or "").strip()
        old_val = (objects[1] or "").strip()
        if not new_val or not old_val or new_val == old_val:
            continue
        sig = _signature_hash(
            detector="role_change", subject=subject, discriminator=f"{predicate}={new_val}"
        )
        if sig in seen:
            continue
        seen.add(sig)
        title = f"{subject} {predicate} changed: {old_val} → {new_val}"
        memory_view = f"{subject}: {predicate} {old_val} → {new_val}"
        genios_view = (
            f"Most recent '{predicate}' fact for {subject} is '{new_val}', "
            f"previously '{old_val}'. Role/employer change — reclassify the "
            f"relationship or update ownership if intentional."
        )
        out.append(
            _insight_row(
                org_id=org_id,
                detector="role_change",
                itype="opportunity",
                priority="medium",
                subject=subject,
                title=title,
                category="role_change",
                memory_view=memory_view,
                genios_view=genios_view,
                signature_hash=sig,
                matched_facts={
                    "predicate": predicate,
                    "old_value": old_val,
                    "new_value": new_val,
                },
                grounding_refs=[subject],
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Detector 3 — overdue_commitment
# ─────────────────────────────────────────────────────────────────────────────


def _detect_overdue_commitment(
    session: Session, *, org_id: str, seen: set[str]
) -> list[InsightRow]:
    """Commitment subjects with a due-date predicate in the past and a status
    that is not resolved.

    A commitment subject is any `facts.subject` carrying one of the due-date
    predicates. We resolve its most-recent due date and its most-recent status
    (both from `facts`), and fire if due < now and status not in done-set.
    """
    rows = session.execute(
        text(
            """
            SELECT subject, predicate, object, created_at
            FROM facts
            WHERE org_id = :org
              AND (predicate = ANY(:due_preds) OR predicate = 'status')
            ORDER BY subject, predicate, created_at DESC
            """
        ),
        {"org": org_id, "due_preds": list(_DUE_PREDICATES)},
    ).fetchall()

    # Per subject: newest due-date (across the due predicates) + newest status.
    due_by_subject: dict[str, tuple[str, datetime]] = {}   # subject -> (predicate, due_dt)
    status_by_subject: dict[str, str] = {}
    for r in rows:
        if r.predicate == "status":
            # rows are newest-first per (subject, predicate); keep the first seen.
            status_by_subject.setdefault(r.subject, (r.object or "").strip().lower())
            continue
        if r.subject in due_by_subject:
            continue  # already have the newest due date for this subject
        due_dt = _parse_iso_date(r.object)
        if due_dt is not None:
            due_by_subject[r.subject] = (r.predicate, due_dt)

    now = datetime.now(UTC)
    out: list[InsightRow] = []
    for subject, (predicate, due_dt) in due_by_subject.items():
        if due_dt >= now:
            continue  # not overdue
        status = status_by_subject.get(subject, "")
        if status in _DONE_STATUSES:
            continue  # resolved — not overdue
        days_overdue = int((now - due_dt).total_seconds() / 86400.0)
        sig = _signature_hash(detector="overdue_commitment", subject=subject)
        if sig in seen:
            continue
        seen.add(sig)
        priority = "high" if days_overdue >= 7 else "medium"
        due_str = due_dt.date().isoformat()
        title = f"Overdue: {subject} — {days_overdue} day(s) past due"
        memory_view = (
            f"{subject}: {predicate}={due_str} · status={status or 'n/a'} · "
            f"{days_overdue}d overdue"
        )
        # Founder-facing copy: plain language, no internal field jargon
        # ("status='unset'") — say what it is and what to do.
        genios_view = (
            f"{subject} slipped {days_overdue} days past its {due_str} due date "
            f"with no resolution — chase it today or close it out."
        )
        out.append(
            _insight_row(
                org_id=org_id,
                detector="overdue_commitment",
                itype="risk",
                priority=priority,
                subject=subject,
                title=title,
                category="overdue_commitment",
                memory_view=memory_view,
                genios_view=genios_view,
                signature_hash=sig,
                matched_facts={
                    "due_predicate": predicate,
                    "due_date": due_str,
                    "status": status,
                    "days_overdue": days_overdue,
                },
                grounding_refs=[subject],
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


_DETECTORS = (
    ("going_cold", _detect_going_cold),
    ("role_change", _detect_role_change),
    ("overdue_commitment", _detect_overdue_commitment),
)


def run_timing_detectors(session: Session, *, org_id: str) -> dict[str, Any]:
    """Run all 3 timing detectors for one org, persist survivors, return a summary.

    Reads v2 directly (`graph_nodes` + `facts`), writes `proactive_insights`
    rows in the pipeline's shape, applies the shared 24h signature dedupe.
    Does NOT commit — the caller owns the transaction (same contract as
    `pipeline.run_for_org` / `hypothesizer.generate_hypotheses_for_org`).
    """
    seen = _seen_signatures(session, org_id)
    per_detector: dict[str, int] = {}
    emitted_total = 0

    for name, fn in _DETECTORS:
        try:
            new_rows = fn(session, org_id=org_id, seen=seen)
        except Exception as e:  # one detector failing must not sink the others
            log.warning(
                "timing_detector_failed", org_id=org_id, detector=name, error=str(e)
            )
            per_detector[name] = 0
            continue
        for row in new_rows:
            session.add(row)
        per_detector[name] = len(new_rows)
        emitted_total += len(new_rows)

    if emitted_total:
        session.flush()

    log.info(
        "timing_detectors_run",
        org_id=org_id,
        emitted=emitted_total,
        going_cold=per_detector.get("going_cold", 0),
        role_change=per_detector.get("role_change", 0),
        overdue_commitment=per_detector.get("overdue_commitment", 0),
    )

    return {
        "insights_fired": emitted_total,
        "by_detector": per_detector,
    }
