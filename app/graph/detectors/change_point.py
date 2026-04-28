"""
Engagement change-point detector — Phase 3 Task 3.3.

The audit asked for PELT-style change-point detection. We implement the
same intent with a rolling-window z-score instead of pulling in `ruptures`
or `pyod` — fewer deps, same signal for our data shape (sparse per-contact
interaction series rarely justify true PELT).

Logic per contact:
  1. Pull interaction timestamps for the last 90 days.
  2. Compute the inter-arrival gap (days between consecutive interactions)
     for the historical window (older than 14 days).
  3. Compare the *current silence* (NOW − last interaction) against
     historical mean + 2*std.
  4. If current_silence > mean + 2*std AND historical sample is
     statistically meaningful (>= 5 gaps), fire a change-point insight.

Filters out:
  - Contacts with too few interactions (need >= 6 to compute baseline).
  - Broadcast / newsletter / bot contacts.
  - Contacts already covered by the rule-based disengagement detector
    in the last 7 days (dedup at the detector layer; the push-gate also
    dedups, but suppressing here saves an LLM-reasoning round trip).
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import List, Dict

from sqlalchemy import text


_MIN_GAPS = 5            # minimum baseline samples before we trust the mean
_Z_THRESHOLD = 2.0       # standard deviations beyond the mean
_LOOKBACK_DAYS = 90
_BASELINE_CUTOFF_DAYS = 14   # the "normal" window excludes the last 14 days


def _detect_engagement_change_point(db, org_id: str) -> List[Dict]:
    """Per-contact statistical break in interaction frequency."""
    # Pull contacts that actually have enough activity to bother analysing.
    # The cardinality guard (interaction_count >= 6) keeps the query cheap.
    candidates = db.execute(
        text("""
            SELECT c.id, c.name, c.company, c.relationship_stage,
                   c.last_interaction_at, c.sentiment_trend
            FROM contacts c
            WHERE c.org_id = :org_id
              AND c.is_archived IS NOT TRUE
              AND c.is_bidirectional IS TRUE
              AND COALESCE(c.classification_override, c.classification, 'unknown')
                  NOT IN ('newsletter', 'bot', 'transactional')
              AND COALESCE(c.interaction_count, 0) >= 6
              AND c.last_interaction_at IS NOT NULL
              AND c.last_interaction_at > NOW() - (INTERVAL '1 day' * :lookback)
            LIMIT 100
        """),
        {"org_id": org_id, "lookback": _LOOKBACK_DAYS},
    ).fetchall()

    insights: List[Dict] = []
    now = datetime.now(timezone.utc)

    for contact in candidates:
        # Skip if disengagement detector probably already covered this in
        # the last 7 days — avoid duplicate "they went quiet" alerts.
        recent_disengage = db.execute(
            text("""
                SELECT 1 FROM insights
                WHERE org_id = :org_id
                  AND contact_id = :cid
                  AND category IN ('email_silence', 'attachment_ghosting', 'reengagement')
                  AND generated_at > NOW() - INTERVAL '7 days'
                LIMIT 1
            """),
            {"org_id": org_id, "cid": str(contact.id)},
        ).fetchone()
        if recent_disengage:
            continue

        # Gather interaction timestamps; we only need the last 90 days.
        ts_rows = db.execute(
            text("""
                SELECT interaction_at FROM interactions
                WHERE contact_id = :cid
                  AND org_id = :org_id
                  AND interaction_at > NOW() - (INTERVAL '1 day' * :lookback)
                ORDER BY interaction_at ASC
            """),
            {"cid": str(contact.id), "org_id": org_id, "lookback": _LOOKBACK_DAYS},
        ).fetchall()

        timestamps = [r.interaction_at for r in ts_rows if r.interaction_at]
        if len(timestamps) < _MIN_GAPS + 1:
            continue

        # Build inter-arrival gaps in days, skipping anything inside the
        # baseline-cutoff window (those points belong to "current state",
        # not to the historical baseline).
        baseline_cutoff = now - _td_days(_BASELINE_CUTOFF_DAYS)
        baseline_ts = [t for t in timestamps if t < baseline_cutoff]
        if len(baseline_ts) < _MIN_GAPS + 1:
            continue

        gaps = [
            (baseline_ts[i] - baseline_ts[i - 1]).total_seconds() / 86400.0
            for i in range(1, len(baseline_ts))
        ]
        if len(gaps) < _MIN_GAPS:
            continue

        mean_gap = statistics.fmean(gaps)
        # stdev is undefined for n=1; guard.
        try:
            std_gap = statistics.stdev(gaps)
        except statistics.StatisticsError:
            continue
        if std_gap == 0:
            # Constant cadence — use a small floor so the threshold isn't 0.
            std_gap = max(mean_gap * 0.25, 1.0)

        last_at = contact.last_interaction_at
        if last_at and getattr(last_at, "tzinfo", None) is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        current_silence_days = (now - last_at).total_seconds() / 86400.0

        threshold = mean_gap + _Z_THRESHOLD * std_gap
        if current_silence_days <= threshold:
            continue

        z = (current_silence_days - mean_gap) / std_gap
        days_int = int(round(current_silence_days))
        mean_int = int(round(mean_gap))

        is_warm = (contact.relationship_stage or "").upper() in ("ACTIVE", "WARM", "NEEDS_ATTENTION")
        priority = "P1" if is_warm else "P2"
        title_name = contact.name or "Contact"

        insights.append({
            "insight_type": "anomaly",
            "priority": priority,
            "category": "engagement_change_point",
            "title": f"{title_name} — engagement break (z={z:.1f}σ)",
            "detail": (
                f"{title_name} normally responds about every {mean_int} day(s), "
                f"but it has been {days_int} day(s) since their last interaction. "
                f"This is {z:.1f} standard deviations beyond their typical cadence. "
                "Consider a soft check-in before the relationship cools further."
            ),
            "contact_id": str(contact.id),
            "contact_name": title_name,
            "metadata": {
                "z_score": round(z, 2),
                "current_silence_days": days_int,
                "baseline_mean_days": round(mean_gap, 2),
                "baseline_std_days": round(std_gap, 2),
                "baseline_samples": len(gaps),
                "stage": contact.relationship_stage,
            },
        })

    return insights


def _td_days(n: int):
    """Lazy import to keep the module head clean."""
    from datetime import timedelta
    return timedelta(days=n)


CHANGE_POINT_DETECTORS = [
    _detect_engagement_change_point,
]
