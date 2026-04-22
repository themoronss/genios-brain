"""Commitment, state entity, and deal-related detectors."""

from sqlalchemy import text
from typing import List, Dict


def _detect_overdue_commitments(db, org_id: str) -> List[Dict]:
    """Open commitments past their due date."""
    results = db.execute(
        text("""
            SELECT c.id, c.name, cm.commit_text, cm.due_date, cm.owner,
                EXTRACT(DAY FROM (NOW() - cm.due_date)) as days_overdue
            FROM commitments cm
            JOIN contacts c ON cm.contact_id = c.id
            WHERE cm.org_id = :org_id
            AND cm.status = 'OPEN'
            AND cm.due_date < NOW()
            ORDER BY cm.due_date ASC
            LIMIT 20
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P1",
        "category": "overdue_commitment",
        "title": f"Overdue: {r[2][:60]} — {int(r[5] or 0)} days past due",
        "detail": f"Commitment to {r[1]} ({r[4]}): \"{r[2]}\". Due {r[3].strftime('%b %d') if r[3] else 'unknown'}. {int(r[5] or 0)} days overdue.",
        "contact_id": str(r[0]),
        "contact_name": r[1],
        "metadata": {"commit_text": r[2], "days_overdue": int(r[5] or 0), "owner": r[4]},
    } for r in results]


def _detect_stalled_deals(db, org_id: str) -> List[Dict]:
    """State entities (payments/invoices) that are PENDING too long."""
    results = db.execute(
        text("""
            SELECT entity_type, entity_id, vendor, amount, due_date, status,
                EXTRACT(DAY FROM (NOW() - updated_at)) as days_stalled
            FROM state_entities
            WHERE org_id = :org_id
            AND status = 'PENDING'
            AND updated_at < NOW() - INTERVAL '7 days'
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P2",
        "category": "stalled_state",
        "title": f"{r[0]} {r[1]} stalled {int(r[6] or 0)} days — still {r[5]}",
        "detail": f"{r[0]} for {r[2] or 'Unknown'} (amount: {r[3] or 'N/A'}) has been {r[5]} for {int(r[6] or 0)} days.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"entity_type": r[0], "entity_id": r[1], "days_stalled": int(r[6] or 0)},
    } for r in results]


def _detect_open_commitments_summary(db, org_id: str) -> List[Dict]:
    """Summary insight: total open commitments count."""
    result = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'OPEN') as open_count,
                COUNT(*) FILTER (WHERE status = 'OVERDUE') as overdue_count,
                COUNT(*) FILTER (WHERE status = 'SOFT') as soft_count
            FROM commitments
            WHERE org_id = :org_id
            AND status IN ('OPEN', 'OVERDUE', 'SOFT')
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or (not result[0] and not result[1]):
        return []

    open_count = result[0] or 0
    overdue_count = result[1] or 0
    soft_count = result[2] or 0
    total = open_count + overdue_count

    if total == 0:
        return []

    priority = "P1" if overdue_count > 0 else "P3"

    return [{
        "insight_type": "state",
        "priority": priority,
        "category": "commitment_summary",
        "title": f"{total} open commitment(s) — {overdue_count} overdue",
        "detail": f"Open: {open_count}, Overdue: {overdue_count}, Soft/tentative: {soft_count}. Review and resolve overdue items.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"open": open_count, "overdue": overdue_count, "soft": soft_count},
    }]


def _detect_commitment_blockers(db, org_id: str) -> List[Dict]:
    """Commitments that are overdue AND high-priority — likely block deals."""
    results = db.execute(
        text("""
            SELECT cm.id, c.id AS contact_id, c.name, cm.commit_text,
                cm.due_date,
                EXTRACT(DAY FROM NOW() - cm.due_date)::int AS days_overdue
            FROM commitments cm
            JOIN contacts c ON cm.contact_id = c.id
            WHERE c.org_id = :org_id
            AND cm.status IN ('OPEN', 'OVERDUE')
            AND cm.due_date < NOW()
            AND cm.due_date IS NOT NULL
            ORDER BY cm.due_date ASC
            LIMIT 5
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P1",
        "category": "commitment_blocker",
        "title": f"Overdue commitment to {r[2]}: {(r[3] or '')[:60]}",
        "detail": f"Commitment to {r[2]} is {int(r[5] or 0)} day{'s' if int(r[5] or 0) != 1 else ''} overdue. This may be blocking the relationship from progressing.",
        "contact_id": str(r[1]),
        "contact_name": r[2],
        "metadata": {"days_overdue": int(r[5] or 0), "commitment_text": r[3], "due_date": str(r[4])},
    } for r in results]


def _detect_long_pending_state_entities(db, org_id: str) -> List[Dict]:
    """State entities (invoices/payments/contracts) pending > 14 days."""
    results = db.execute(
        text("""
            SELECT entity_type, entity_id, vendor, amount, status,
                EXTRACT(DAY FROM NOW() - updated_at)::int AS days_pending
            FROM state_entities
            WHERE org_id = :org_id
            AND status = 'PENDING'
            AND updated_at < NOW() - INTERVAL '14 days'
            ORDER BY updated_at ASC
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P2",
        "category": "long_pending_state",
        "title": f"{r[0]} {r[1]} from {r[2] or 'Unknown'} — pending {int(r[5] or 0)} days",
        "detail": f"A {r[0]} for {r[2] or 'Unknown'} (amount: {r[3] or 'N/A'}) has been pending for {int(r[5] or 0)} days. Follow up to resolve.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"entity_type": r[0], "entity_id": r[1], "days_pending": int(r[5] or 0), "amount": str(r[3] or "")},
    } for r in results]


def _detect_vendor_invoice_overdue(db, org_id: str) -> List[Dict]:
    """Vendor state entities with overdue invoices."""
    results = db.execute(
        text("""
            SELECT entity_type, entity_id, vendor, amount, due_date,
                EXTRACT(DAY FROM NOW() - due_date)::int AS days_overdue
            FROM state_entities
            WHERE org_id = :org_id
            AND entity_type IN ('invoice', 'payment')
            AND status = 'PENDING'
            AND due_date IS NOT NULL
            AND due_date < NOW()
            ORDER BY due_date ASC
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    return [{
        "insight_type": "state",
        "priority": "P1",
        "category": "vendor_invoice_overdue",
        "title": f"Overdue {r[0]}: {r[2] or 'Unknown'} — {int(r[5] or 0)} days past due",
        "detail": f"{r[0].capitalize()} from {r[2] or 'Unknown'} (amount: {r[3] or 'N/A'}) is {int(r[5] or 0)} days overdue. This may affect vendor relationships.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"entity_type": r[0], "vendor": r[2], "days_overdue": int(r[5] or 0), "amount": str(r[3] or "")},
    } for r in results]


COMMITMENT_DETECTORS = [
    _detect_overdue_commitments,
    _detect_stalled_deals,
    _detect_open_commitments_summary,
    _detect_commitment_blockers,
    _detect_long_pending_state_entities,
    _detect_vendor_invoice_overdue,
]
