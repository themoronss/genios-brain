"""
Inbound acknowledgement detector — Phase 3 Task 3.1.

Surfaces emails the user received but never replied to. The promise of an
"external brain" is that the user should never manually track which inbound
threads are still waiting on them. This detector closes that gap.

Fires when:
  - direction='inbound' interaction in last 14 days
  - more than 48 hours since that inbound
  - no outbound interaction to the same contact since
  - contact is NOT broadcast / newsletter / bot / transactional
  - contact has at least one bidirectional interaction historically
    (filters out unsolicited cold email noise)

Severity: P2 by default; P1 if the contact has stage WARM/ACTIVE or a
prior open commitment, since silence on warm contacts costs more.
"""
from sqlalchemy import text
from typing import List, Dict


def _detect_unacknowledged_inbound(db, org_id: str) -> List[Dict]:
    """
    Pull inbound emails from the last 14 days that have been sitting >48h
    without an outbound reply, and bubble them as actionable insights.
    """
    rows = db.execute(
        text("""
            WITH last_inbound AS (
                -- Most recent inbound per contact within the look-back window
                SELECT DISTINCT ON (i.contact_id)
                       i.contact_id,
                       i.id            AS interaction_id,
                       i.subject,
                       i.summary,
                       i.interaction_at,
                       i.intent
                FROM interactions i
                WHERE i.org_id = :org_id
                  AND i.direction = 'inbound'
                  AND i.interaction_at >  NOW() - INTERVAL '14 days'
                  AND i.interaction_at <  NOW() - INTERVAL '48 hours'
                ORDER BY i.contact_id, i.interaction_at DESC
            )
            SELECT li.contact_id,
                   li.interaction_id,
                   li.subject,
                   li.summary,
                   li.interaction_at,
                   li.intent,
                   c.name,
                   c.company,
                   c.relationship_stage,
                   COALESCE(c.classification_override, c.classification, 'unknown') AS classification,
                   (SELECT COUNT(*) FROM commitments cm
                      WHERE cm.contact_id = c.id AND cm.status = 'OPEN') AS open_commitments,
                   c.is_bidirectional
            FROM last_inbound li
            JOIN contacts c ON c.id = li.contact_id
            WHERE c.is_archived IS NOT TRUE
              -- Real person, not broadcast / automated.
              -- We use classification=real_person rather than is_bidirectional
              -- because the bidirectional flag often lags the data (a contact
              -- that's mostly inbound until you reply once is still flagged
              -- one-way). classification is set by the classify task.
              AND COALESCE(c.classification_override, c.classification, 'unknown') = 'real_person'
              -- No outbound to this contact since the inbound landed
              AND NOT EXISTS (
                  SELECT 1 FROM interactions out_i
                  WHERE out_i.contact_id = li.contact_id
                    AND out_i.org_id     = :org_id
                    AND out_i.direction  = 'outbound'
                    AND out_i.interaction_at > li.interaction_at
              )
            ORDER BY li.interaction_at ASC
            LIMIT 25
        """),
        {"org_id": org_id},
    ).fetchall()

    insights: List[Dict] = []
    for r in rows:
        days_silent = max(0, (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            - r.interaction_at
        ).days) if r.interaction_at and getattr(r.interaction_at, "tzinfo", None) else None

        # Lift severity for warm/active relationships and contacts with
        # open commitments — silence there has bigger downside.
        is_warm = (r.relationship_stage or "").upper() in ("ACTIVE", "WARM", "NEEDS_ATTENTION")
        priority = "P1" if (is_warm or (r.open_commitments or 0) > 0) else "P2"

        title_name = r.name or "Contact"
        subject_str = (r.subject or "(no subject)").strip()[:80]
        summary_hint = (r.summary or "").strip()
        days_part = f"{days_silent} days" if days_silent else "more than 2 days"

        detail_parts = [
            f"{title_name} sent you '{subject_str}' {days_part} ago and you haven't replied yet."
        ]
        if summary_hint:
            detail_parts.append(f"Their message: {summary_hint[:200]}")
        if (r.open_commitments or 0) > 0:
            detail_parts.append(
                f"You also have {r.open_commitments} open commitment(s) with them."
            )
        detail_parts.append("Send a brief acknowledgement so the thread doesn't go cold.")

        insights.append({
            "insight_type": "relationship",
            "priority": priority,
            "category": "unacknowledged_inbound",
            "title": f"{title_name} — waiting on your reply",
            "detail": " ".join(detail_parts),
            "contact_id": str(r.contact_id),
            "contact_name": title_name,
            "metadata": {
                "interaction_id": str(r.interaction_id),
                "subject": subject_str,
                "days_silent": days_silent,
                "intent": r.intent,
                "stage": r.relationship_stage,
                "open_commitments": r.open_commitments or 0,
            },
        })

    return insights


INBOUND_ACK_DETECTORS = [
    _detect_unacknowledged_inbound,
]
