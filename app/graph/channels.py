"""
Phase 1, Item #6: channel preference helper.

Aggregates a contact's last-90d interactions into logical channels and
recommends the one with the highest reply-rate, with a minimum-samples
guard so a single lucky reply doesn't dominate.

The recommendation is data-driven only: never hard-coded. If the contact
has no usable history the function returns recommended=None and the caller
falls back to the generic action verb path.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# interaction_type values are subtypes (see migration 025 + migration 096);
# this map collapses them into the logical channel a recommendation surfaces.
CHANNEL_MAP = {
    "email_reply": "email",
    "email_one_way": "email",
    "cc": "email",
    "commitment": "email",
    "slack_dm": "slack",
    "slack_mention": "slack",
    "meeting": "meeting",
    "jira_issue": "jira",
    "file_shared": "file",
    "doc_shared": "file",
    "call": "call",
    "sms": "sms",
    "other": "other",
}

# Minimum (sent+replies) interactions on a channel before it can be
# recommended. Prevents one-off replies from dominating the recommendation.
_MIN_SAMPLES = 2


def get_contact_channel_profile(contact_id: str, db: Session) -> dict:
    """Return channel mix + recommended channel for the contact.

    Result shape:
        {
            "recommended": "email" | "call" | ... | None,
            "channels": [
                {"channel": str, "success_rate": float,
                 "samples": int, "last_used": datetime | None},
                ...
            ],
            "reason": "<human-readable rationale>",
        }
    """
    try:
        rows = db.execute(
            text(
                """
                SELECT
                  interaction_type,
                  COUNT(*) FILTER (WHERE direction = 'inbound')  AS replies,
                  COUNT(*) FILTER (WHERE direction = 'outbound') AS sent,
                  MAX(interaction_at) AS last_used
                FROM interactions
                WHERE contact_id = :cid
                  AND interaction_at > NOW() - INTERVAL '90 days'
                GROUP BY interaction_type
                """
            ),
            {"cid": contact_id},
        ).fetchall()
    except Exception as e:
        logger.debug(f"channel profile query failed for contact {contact_id}: {e}")
        return {"recommended": None, "channels": [], "reason": "query_error"}

    # Bucket subtypes into logical channels.
    buckets: dict[str, dict] = {}
    for r in rows:
        ch = CHANNEL_MAP.get(r.interaction_type, "other")
        b = buckets.setdefault(ch, {"replies": 0, "sent": 0, "last_used": None})
        b["replies"] += int(r.replies or 0)
        b["sent"] += int(r.sent or 0)
        if r.last_used and (b["last_used"] is None or r.last_used > b["last_used"]):
            b["last_used"] = r.last_used

    channels: list[dict] = []
    for ch, b in buckets.items():
        if ch == "other":
            # 'other' is opaque (post-migration this should drain over time);
            # never recommend it because the actor can't decide what to do.
            continue
        total = b["sent"] + b["replies"]
        if total < _MIN_SAMPLES:
            continue
        sent = b["sent"]
        replies = b["replies"]
        # success_rate = replies / sent if outbound exists; 1.0 if only inbound
        # (they reach out without prompting → channel works without effort).
        rate = (replies / sent) if sent > 0 else 1.0
        channels.append(
            {
                "channel": ch,
                "success_rate": round(rate, 2),
                "samples": total,
                "last_used": b["last_used"],
            }
        )

    if not channels:
        return {"recommended": None, "channels": [], "reason": "insufficient_data"}

    # Sort by success_rate desc, then by sample count, then by recency.
    channels.sort(
        key=lambda c: (
            -c["success_rate"],
            -c["samples"],
            -(c["last_used"].timestamp() if c["last_used"] else 0),
        )
    )

    top = channels[0]
    reason = (
        f"highest reply rate ({int(top['success_rate'] * 100)}%) "
        f"over {top['samples']} interactions"
    )
    return {"recommended": top["channel"], "channels": channels, "reason": reason}


def channel_action_verb(channel: Optional[str]) -> str:
    """Map a channel to the imperative verb the LLM should prefer."""
    return {
        "email": "Email",
        "call": "Call",
        "sms": "Text",
        "slack": "DM",
        "meeting": "Schedule a meeting with",
        "jira": "Comment on the Jira issue with",
        "file": "Share an update document with",
    }.get(channel or "", "Reach out to")
