"""Data quality and graph health detectors."""

from sqlalchemy import text
from typing import List, Dict


def _detect_low_confidence_contacts(db, org_id: str) -> List[Dict]:
    """Contacts with category_confidence < 0.6 — entity type classification uncertain."""
    result = db.execute(
        text("""
            SELECT COUNT(*) AS count
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.category_confidence IS NOT NULL
            AND c.category_confidence < 0.6
            AND c.interaction_count >= 3
            AND (c.is_archived = FALSE OR c.is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0] or result[0] == 0:
        return []

    count = int(result[0])
    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "low_confidence_contacts",
        "title": f"{count} contact{'s' if count != 1 else ''} with uncertain categorization",
        "detail": f"{count} contacts have a category confidence below 60%. Their investor/customer/vendor classification may be wrong. Review their entity type in the graph.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"count": count},
    }]


def _detect_contacts_missing_company(db, org_id: str) -> List[Dict]:
    """Contacts with no company info — incomplete graph nodes reduce accuracy."""
    result = db.execute(
        text("""
            SELECT COUNT(*) AS count
            FROM contacts
            WHERE org_id = :org_id
            AND (company IS NULL OR company = '')
            AND interaction_count >= 3
            AND entity_type != 'self'
            AND (is_archived = FALSE OR is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0]:
        return []

    count = int(result[0])
    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "missing_company_info",
        "title": f"{count} contact{'s' if count != 1 else ''} missing company info",
        "detail": f"{count} active contacts have no company associated. Enriching company data improves graph clustering and entity type accuracy.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"count": count},
    }]


def _detect_contacts_needing_enrichment(db, org_id: str) -> List[Dict]:
    """Active/warm contacts with 5+ interactions but low confidence score."""
    result = db.execute(
        text("""
            SELECT COUNT(*) AS count
            FROM contacts
            WHERE org_id = :org_id
            AND category_confidence < 0.55
            AND interaction_count >= 5
            AND relationship_stage IN ('ACTIVE', 'WARM')
            AND (is_archived = FALSE OR is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0] or result[0] == 0:
        return []

    count = int(result[0])
    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "enrichment_needed",
        "title": f"{count} active contact{'s' if count != 1 else ''} need manual enrichment",
        "detail": f"{count} active contacts have low classification confidence (<55%). Visit the Review page to manually tag their entity type and improve graph accuracy.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"count": count},
    }]


def _detect_entity_type_missing(db, org_id: str) -> List[Dict]:
    """Contacts still tagged as 'other' with 5+ interactions — likely misclassified."""
    result = db.execute(
        text("""
            SELECT COUNT(*) AS count
            FROM contacts
            WHERE org_id = :org_id
            AND (entity_type = 'other' OR entity_type IS NULL)
            AND interaction_count >= 5
            AND (is_archived = FALSE OR is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0] or result[0] == 0:
        return []

    count = int(result[0])
    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "entity_type_missing",
        "title": f"{count} contact{'s' if count != 1 else ''} still classified as 'other'",
        "detail": f"{count} active contacts are classified as generic 'other' despite significant interaction history. Classifying them correctly improves graph insights.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"count": count},
    }]


def _detect_pending_merge_queue(db, org_id: str) -> List[Dict]:
    """Notify when merge queue has unreviewed duplicate candidates."""
    result = db.execute(
        text("""
            SELECT COUNT(*) AS count
            FROM merge_queue
            WHERE org_id = :org_id
            AND status = 'pending'
        """),
        {"org_id": org_id}
    ).fetchone()

    if not result or not result[0] or result[0] == 0:
        return []

    count = int(result[0])
    return [{
        "insight_type": "relationship",
        "priority": "P3",
        "category": "merge_queue_pending",
        "title": f"{count} potential duplicate contact{'s' if count != 1 else ''} pending review",
        "detail": f"The entity resolution engine found {count} likely duplicate contacts. Visit the Review page to merge or dismiss them.",
        "contact_id": None,
        "contact_name": None,
        "metadata": {"count": count},
    }]


DATA_QUALITY_DETECTORS = [
    _detect_low_confidence_contacts,
    _detect_contacts_missing_company,
    _detect_contacts_needing_enrichment,
    _detect_entity_type_missing,
    _detect_pending_merge_queue,
]
