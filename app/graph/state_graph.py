"""
State Graph Query Layer

Provides functions to query and interact with the State Entities table.
Handles structured business state: GST filings, payments, invoices, orders, compliance.

Author: GeniOS Team
Version: 2.2
Last Updated: 2026-03-18
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

# ──────────────────────────────────────────────────────────────────────────────
# Query Functions - Read State
# ──────────────────────────────────────────────────────────────────────────────


def get_state_by_type(db: Session, org_id: str, entity_type: str) -> List[Dict]:
    """
    Get all state entities of a specific type for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        entity_type: Type of entity (GST, PAYMENT, INVOICE, ORDER, COMPLIANCE)

    Returns:
        List of state entities ordered by updated_at DESC
    """
    result = db.execute(
        text(
            """
            SELECT 
                id::text as id,
                entity_type,
                entity_id,
                status,
                amount,
                vendor,
                reference_id,
                due_date,
                event_date,
                created_at,
                updated_at,
                metadata
            FROM state_entities
            WHERE org_id = :org_id AND entity_type = :entity_type
            ORDER BY updated_at DESC
        """
        ),
        {"org_id": org_id, "entity_type": entity_type},
    ).fetchall()

    return [dict(row._mapping) for row in result]


def get_latest_state(db: Session, org_id: str, entity_id: str) -> Optional[Dict]:
    """
    Get the latest state for a specific entity.

    Args:
        db: Database session
        org_id: Organization ID
        entity_id: Entity identifier (e.g., "GST_Q2_2025", "PAYMENT_UTR_123")

    Returns:
        State entity dict or None if not found
    """
    result = db.execute(
        text(
            """
            SELECT 
                id::text as id,
                entity_type,
                entity_id,
                status,
                amount,
                vendor,
                reference_id,
                due_date,
                event_date,
                source_email_id,
                created_at,
                updated_at,
                metadata
            FROM state_entities
            WHERE org_id = :org_id AND entity_id = :entity_id
            LIMIT 1
        """
        ),
        {"org_id": org_id, "entity_id": entity_id},
    ).fetchone()

    if result:
        return dict(result._mapping)
    return None


def get_overdue_items(db: Session, org_id: str) -> List[Dict]:
    """
    Get all overdue items (status='OVERDUE') for an organization.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        List of overdue state entities sorted by due_date ASC
    """
    result = db.execute(
        text(
            """
            SELECT 
                id::text as id,
                entity_type,
                entity_id,
                status,
                amount,
                vendor,
                reference_id,
                due_date,
                event_date,
                created_at,
                updated_at,
                EXTRACT(DAY FROM NOW() - due_date) as days_overdue
            FROM state_entities
            WHERE org_id = :org_id AND status = 'OVERDUE'
            ORDER BY due_date ASC
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    return [dict(row._mapping) for row in result]


def get_due_soon_items(db: Session, org_id: str, days_ahead: int = 7) -> List[Dict]:
    """
    Get items due within N days (PENDING status).

    Args:
        db: Database session
        org_id: Organization ID
        days_ahead: Number of days to look ahead (default: 7)

    Returns:
        List of state entities due soon, sorted by due_date ASC
    """
    result = db.execute(
        text(
            """
            SELECT 
                id::text as id,
                entity_type,
                entity_id,
                status,
                amount,
                vendor,
                reference_id,
                due_date,
                event_date,
                created_at,
                updated_at,
                EXTRACT(DAY FROM due_date - NOW()) as days_until_due
            FROM state_entities
            WHERE org_id = :org_id 
                AND status = 'PENDING'
                AND due_date IS NOT NULL
                AND due_date >= NOW()
                AND due_date <= NOW() + INTERVAL '1 day' * :days_ahead
            ORDER BY due_date ASC
        """
        ),
        {"org_id": org_id, "days_ahead": days_ahead},
    ).fetchall()

    return [dict(row._mapping) for row in result]


def get_recent_events(db: Session, org_id: str, limit: int = 10) -> List[Dict]:
    """
    Get recently updated state entities.

    Args:
        db: Database session
        org_id: Organization ID
        limit: Maximum number of results

    Returns:
        List of recent state entities
    """
    result = db.execute(
        text(
            """
            SELECT 
                id::text as id,
                entity_type,
                entity_id,
                status,
                amount,
                vendor,
                reference_id,
                due_date,
                event_date,
                created_at,
                updated_at
            FROM state_entities
            WHERE org_id = :org_id
            ORDER BY updated_at DESC
            LIMIT :limit
        """
        ),
        {"org_id": org_id, "limit": limit},
    ).fetchall()

    return [dict(row._mapping) for row in result]


def get_state_summary(db: Session, org_id: str) -> Dict:
    """
    Get summary statistics of state entities.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        Dict with counts by status and entity type
    """
    result = db.execute(
        text(
            """
            SELECT 
                entity_type,
                status,
                COUNT(*) as count,
                COALESCE(SUM(amount), 0) as total_amount
            FROM state_entities
            WHERE org_id = :org_id
            GROUP BY entity_type, status
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    summary = {"by_type": {}, "by_status": {}, "total_items": 0, "total_amount": 0.0}

    for row in result:
        entity_type = row[0]
        status = row[1]
        count = row[2]
        amount = float(row[3] or 0)

        # By type
        if entity_type not in summary["by_type"]:
            summary["by_type"][entity_type] = {}
        summary["by_type"][entity_type][status] = count

        # By status
        if status not in summary["by_status"]:
            summary["by_status"][status] = 0
        summary["by_status"][status] += count

        # Totals
        summary["total_items"] += count
        summary["total_amount"] += amount

    return summary


# ──────────────────────────────────────────────────────────────────────────────
# Lifecycle Management Functions - Update State
# ──────────────────────────────────────────────────────────────────────────────


def mark_overdue_items(db: Session, org_id: Optional[str] = None) -> int:
    """
    Mark all PENDING items with passed due_date as OVERDUE.
    Runs as daily cron job.

    Args:
        db: Database session
        org_id: Optional - if provided, only update that org; otherwise update all

    Returns:
        Number of items marked as OVERDUE
    """
    where_clause = "WHERE status = 'PENDING' AND due_date < NOW()"
    if org_id:
        where_clause += " AND org_id = :org_id"

    # Get count before update
    count_result = db.execute(
        text(f"SELECT COUNT(*) FROM state_entities {where_clause}"),
        {"org_id": org_id} if org_id else {},
    ).fetchone()
    count = count_result[0] if count_result else 0

    # Update
    db.execute(
        text(
            f"""
            UPDATE state_entities
            SET status = 'OVERDUE', updated_at = NOW()
            {where_clause}
        """
        ),
        {"org_id": org_id} if org_id else {},
    )
    db.commit()

    return count


def transition_state_status(
    db: Session,
    org_id: str,
    entity_id: str,
    new_status: str,
    metadata_update: Optional[Dict] = None,
) -> bool:
    """
    Transition an entity to a new status.

    Args:
        db: Database session
        org_id: Organization ID
        entity_id: Entity ID
        new_status: New status (PENDING, FILED, CONFIRMED, OVERDUE, HISTORICAL)
        metadata_update: Optional dict to merge with existing metadata

    Returns:
        True if successful, False if entity not found
    """
    # Check if entity exists
    existing = get_latest_state(db, org_id, entity_id)
    if not existing:
        return False

    # Prepare metadata update
    metadata_json = "metadata"
    if metadata_update:
        metadata_json = f"jsonb_set(metadata, '{{}}', '{metadata_update}'::jsonb)"

    db.execute(
        text(
            f"""
            UPDATE state_entities
            SET 
                status = :new_status,
                updated_at = NOW(),
                metadata = {metadata_json}
            WHERE org_id = :org_id AND entity_id = :entity_id
        """
        ),
        {"org_id": org_id, "entity_id": entity_id, "new_status": new_status},
    )
    db.commit()

    return True


# ──────────────────────────────────────────────────────────────────────────────
# Specialized Query Functions
# ──────────────────────────────────────────────────────────────────────────────


def is_gst_filed(db: Session, org_id: str, period: str, year: int) -> Optional[Dict]:
    """
    Check if GST for a specific period/year is filed.

    Args:
        db: Database session
        org_id: Organization ID
        period: Period (Q1, Q2, Q3, Q4)
        year: Year

    Returns:
        State entity dict if filed, None otherwise
    """
    entity_id = f"GST_{period}_{year}"
    return get_latest_state(db, org_id, entity_id)


def get_gst_status(db: Session, org_id: str) -> List[Dict]:
    """Get all GST filings for an organization."""
    return get_state_by_type(db, org_id, "GST")


def get_payment_status(db: Session, org_id: str, utr: str) -> Optional[Dict]:
    """Get status of a specific payment by UTR."""
    entity_id = f"PAYMENT_{utr}"
    return get_latest_state(db, org_id, entity_id)


def get_pending_payments(db: Session, org_id: str) -> List[Dict]:
    """Get all pending payments."""
    result = db.execute(
        text(
            """
            SELECT 
                id::text as id,
                entity_type,
                entity_id,
                status,
                amount,
                vendor,
                reference_id,
                due_date,
                EXTRACT(DAY FROM NOW() - due_date) as days_overdue
            FROM state_entities
            WHERE org_id = :org_id 
                AND entity_type = 'PAYMENT'
                AND status IN ('PENDING', 'OVERDUE')
            ORDER BY due_date ASC
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    return [dict(row._mapping) for row in result]


def get_invoices_status(db: Session, org_id: str) -> List[Dict]:
    """Get all invoices status."""
    return get_state_by_type(db, org_id, "INVOICE")
