"""Signal-score computation for contact_facts.

Spec §7.5 rule 4:
  base = 0.5
  +0.2  named participant (fact references a specific person/entity)
  +0.1  structured (source is not raw email body — calendar, doc, thread link)
  +0.1  recent (< 30d old)
  -0.2  promo / broadcast signal
  -0.1  cc-only (user was only on CC, not To)

Clamped to [0, 1]. Deterministic — safe to recompute on any column update.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

_RECENT_CUTOFF_DAYS = 30


def compute_signal_score(
    *,
    is_named_participant: bool = False,
    is_structured: bool = False,
    fact_created_at: Optional[datetime] = None,
    is_promo: bool = False,
    is_cc_only: bool = False,
) -> float:
    score = 0.5
    if is_named_participant:
        score += 0.2
    if is_structured:
        score += 0.1
    if fact_created_at is not None:
        created = fact_created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - created) <= timedelta(days=_RECENT_CUTOFF_DAYS):
            score += 0.1
    if is_promo:
        score -= 0.2
    if is_cc_only:
        score -= 0.1
    return max(0.0, min(1.0, round(score, 4)))


def signal_from_interaction(interaction: dict) -> float:
    """Convenience: derive signals from the interaction record we already have."""
    source = (interaction.get("source") or "").lower()
    intent = (interaction.get("intent") or "").lower()
    direction = (interaction.get("direction") or "").lower()

    is_structured = source in ("calendar", "doc", "docs", "drive", "sheets", "thread_link", "jira", "notion")
    is_promo = intent in ("promotion", "broadcast", "newsletter") or bool(interaction.get("is_broadcast"))
    is_cc_only = direction == "cc"
    is_named_participant = bool(interaction.get("mentioned_people"))
    created = interaction.get("interaction_at") or interaction.get("date")

    return compute_signal_score(
        is_named_participant=is_named_participant,
        is_structured=is_structured,
        fact_created_at=created if isinstance(created, datetime) else None,
        is_promo=is_promo,
        is_cc_only=is_cc_only,
    )
