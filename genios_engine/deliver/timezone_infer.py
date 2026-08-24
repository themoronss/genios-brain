"""Infer an org's timezone from its own outbound activity, so quiet hours mean something.

`AttentionProfile.timezone` fell back to UTC and the only configured source was
`delivery_preferences.tz_name`, a table with zero rows. Every tenant's politeness window was
therefore evaluated in UTC — which for an India-based founder places 21:00–08:00 at 02:30–13:30
IST: it covers his entire working morning and leaves his real evening uncovered.

Asking during onboarding is the right answer and `orgs.timezone` (migration 0066) is where that
lands. This module is what fills the column for every org that already exists, from evidence
those orgs already gave us: people send mail while they are awake. A send-hour histogram in UTC
is a shifted copy of a working day, and the shift IS the offset.

Deterministic, no model, no network. The result is written to `orgs.timezone` rather than
recomputed per delivery, so it is inspectable, overridable, and explains itself.
"""
from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

#: Candidate zones, not offsets — a fixed offset would get India's :30 wrong and drop DST
#: entirely, so a message polite in January would wake somebody in July. Deliberately a
#: shortlist of business zones rather than all ~600: with a few hundred events the histogram
#: cannot distinguish neighbours, and pretending otherwise would be false precision.
CANDIDATE_ZONES: tuple[str, ...] = (
    "Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney",
    "Europe/London", "Europe/Berlin", "Europe/Moscow", "America/New_York", "America/Chicago",
    "America/Denver", "America/Los_Angeles", "America/Sao_Paulo", "Africa/Lagos", "UTC",
)

#: Local hours a working day plausibly spans. Used ONLY as an admissibility filter — a zone that
#: puts a third of someone's mail at 3am is not a candidate. It is deliberately NOT the ranking
#: function: as a 16-hour step it saturates at 1.0 for every zone within a few hours of the truth.
WAKING_START, WAKING_END = 7, 23

#: The ranking kernel, as (hour, weight) knots interpolated linearly and read circularly.
#:
#: It scores the NIGHT BEING EMPTY, not the day being centred. That distinction is the whole
#: robustness of this: everybody sleeps at roughly the same local time, while founders keep wildly
#: different working hours — a cosine peaking at 13:30 quietly assumes a 9-to-5 and shifts the
#: answer eastward for anyone who works 10am to 10pm.
NIGHT_KERNEL: tuple[tuple[float, float], ...] = (
    (0.0, -1.0), (5.0, -1.0), (8.0, 1.0), (22.0, 1.0), (24.0, -1.0),
)

#: How far apart, in hours, tied candidates may be before the tie is refused.
#:
#: Calibrated against what refusing COSTS, not against a notion of tidiness. Refusing leaves
#: `orgs.timezone` NULL, and NULL falls back to UTC — 5.5 hours wrong for an Indian founder, 8
#: for a Californian. The median pick below is bounded by the spread (NOT by half of it: the true
#: offset can sit at an edge of an asymmetric contender set), so a 4-hour tie can still be ~2.5
#: hours off — comfortably better than the fallback it would otherwise defer to, which is the
#: only comparison that decides whether inferring at all was worth it. Beyond this width the
#: wrong pick stops being an improvement and the honest answer is to keep the question open.
MAX_AMBIGUOUS_OFFSET_HOURS = 4.0

#: Below this many timestamps the histogram is noise. Returning None is the honest answer —
#: an inferred zone that is wrong is worse than a recorded absence, because it stops anyone
#: from asking.
MIN_EVENTS = 40

#: How much better the winner must be — than UTC, AND than the runner-up. A zone that explains
#: the data no better than the next candidate is not a measurement, and picking one anyway is
#: how a Kolkata founder was assigned Asia/Tokyo: every zone within a few hours scored exactly
#: 1.0 on the old step function and `sorted(reverse=True)` broke the tie on the zone NAME.
#: Quiet hours 21:00-08:00 Tokyo is 17:30-04:30 IST — it mutes his entire evening, which is
#: strictly worse than the UTC default it was replacing.
MIN_MARGIN = 0.05


def _offset_spread(sample: datetime, zones: list[str]) -> float:
    """Hours between the earliest and latest UTC offset among these zones."""
    offsets = [sample.astimezone(ZoneInfo(z)).utcoffset().total_seconds() / 3600.0
               for z in zones]
    return max(offsets) - min(offsets) if offsets else 0.0


def awake_fraction(timestamps: list[datetime], zone: str) -> float:
    """Fraction of activity inside waking hours — the admissibility filter, not the ranking."""
    tz = ZoneInfo(zone)
    if not timestamps:
        return 0.0
    awake = sum(1 for t in timestamps if WAKING_START <= t.astimezone(tz).hour < WAKING_END)
    return awake / len(timestamps)


def _kernel(hour: float) -> float:
    """`NIGHT_KERNEL` interpolated at this local hour."""
    for (h0, w0), (h1, w1) in zip(NIGHT_KERNEL, NIGHT_KERNEL[1:]):
        if h0 <= hour <= h1:
            return w0 if h1 == h0 else w0 + (w1 - w0) * (hour - h0) / (h1 - h0)
    return -1.0


def score_zone(timestamps: list[datetime], zone: str) -> float:
    """How plausible this zone's local night is, given when the org actually acts. Range [-1, 1].

    Continuous, which is the point: the original measure was "is the local hour between 7 and 23",
    a 16-hour step that saturated at 1.0 for every zone within a few hours of the truth. With
    every candidate tied, `sorted(reverse=True)` fell through to comparing zone NAMES, and a
    Kolkata founder was assigned Asia/Tokyo — quiet hours 21:00-08:00 Tokyo is 17:30-04:30 IST,
    muting his entire evening. Strictly worse than the UTC default it replaced, and ranking by
    name is not an inference.
    """
    tz = ZoneInfo(zone)
    if not timestamps:
        return 0.0
    total = 0.0
    for t in timestamps:
        local = t.astimezone(tz)
        total += _kernel(local.hour + local.minute / 60.0)
    return total / len(timestamps)


def infer_zone(timestamps: list[datetime]) -> tuple[str | None, dict]:
    """Best-fitting zone and the evidence for it, or (None, why-not)."""
    if len(timestamps) < MIN_EVENTS:
        return None, {"reason": "insufficient_activity", "events": len(timestamps),
                      "required": MIN_EVENTS}
    # Admissible zones first: one that puts a third of somebody's mail at 3am is not a candidate
    # however well the cosine happens to score it.
    admissible = [z for z in CANDIDATE_ZONES if awake_fraction(timestamps, z) >= 0.75]
    if not admissible:
        return None, {"reason": "no_plausible_working_day", "events": len(timestamps)}

    # Sort on the score ALONE, with the zone name only as a stable final tiebreak for
    # reproducibility — never as a discriminator, because a tie is refused below.
    scored = sorted(((score_zone(timestamps, z), z) for z in admissible),
                    key=lambda pair: (-pair[0], pair[1]))
    best_score, best_zone = scored[0]
    utc_score = score_zone(timestamps, "UTC")
    runner_score, runner_zone = scored[1] if len(scored) > 1 else (None, None)

    if best_zone != "UTC" and best_score - utc_score < MIN_MARGIN:
        return None, {"reason": "no_better_than_utc", "best": best_zone,
                      "best_score": round(best_score, 3), "utc_score": round(utc_score, 3)}

    # An ambiguity only matters if it MOVES the answer. This exists to set quiet hours, so the
    # question is not "are two zones tied" but "would picking the wrong one of them put the
    # window in the wrong place". Kolkata and Dubai are 90 minutes apart and score within noise
    # of each other on symmetric working hours — refusing there would leave the column NULL and
    # fall straight back to UTC, which is 5.5 hours wrong. Kolkata and Tokyo are 3.5 apart, and
    # that is the confusion that produced a founder muted through his own evening.
    sample = timestamps[0]
    contenders = [z for score, z in scored if best_score - score < MIN_MARGIN]
    spread = _offset_spread(sample, contenders)
    if spread > MAX_AMBIGUOUS_OFFSET_HOURS:
        return None, {"reason": "ambiguous_between_zones", "best": best_zone,
                      "contenders": contenders, "offset_spread_hours": round(spread, 2),
                      "best_score": round(best_score, 3), "events": len(timestamps)}
    if len(contenders) > 1:
        # Within a tolerable tie, take the MEDIAN offset rather than the highest score. The
        # scores are indistinguishable by construction here, so picking the nominal winner is
        # picking noise; the median minimises how wrong we can be about any of them.
        contenders = sorted(
            contenders,
            key=lambda z: sample.astimezone(ZoneInfo(z)).utcoffset().total_seconds())
        best_zone = contenders[len(contenders) // 2]
        best_score = next(sc for sc, z in scored if z == best_zone)

    return best_zone, {"reason": "inferred_from_activity", "events": len(timestamps),
                       "score": round(best_score, 3), "utc_score": round(utc_score, 3),
                       "awake_fraction": round(awake_fraction(timestamps, best_zone), 3),
                       "runner_up": runner_zone,
                       "runner_up_score": round(runner_score, 3) if runner_score is not None else None}


def outbound_timestamps(conn, org_id: str, limit: int = 2000) -> list[datetime]:
    """When this org's OWN people acted.

    Outbound only. Inbound mail is when the rest of the world is awake, which is a histogram of
    everyone else's timezone and would pull every org toward whoever mails them most.
    """
    rows = conn.execute(text(
        "select se.occurred_at from source_events se "
        "where se.org_id = :o and se.occurred_at is not null "
        "  and lower(se.actor->>'email') in ("
        "     select lower(email) from org_seats where org_id = :o and email is not null "
        "     union select lower(email) from orgs where id = :o and email is not null) "
        "order by se.occurred_at desc limit :l"), {"o": org_id, "l": limit}).all()
    return [r[0] for r in rows if r[0] is not None]


def infer_and_store(conn, org_id: str, *, overwrite: bool = False) -> dict:
    """Fill `orgs.timezone` from activity. Never clobbers a set value unless asked — a human
    who typed a zone outranks a histogram, always."""
    current = conn.execute(text("select timezone from orgs where id=:o"),
                           {"o": org_id}).scalar()
    if current and not overwrite:
        return {"org_id": org_id, "timezone": current, "reason": "already_set"}
    zone, evidence = infer_zone(outbound_timestamps(conn, org_id))
    if zone:
        conn.execute(text("update orgs set timezone=:tz where id=:o"),
                     {"tz": zone, "o": org_id})
    return {"org_id": org_id, "timezone": zone, **evidence}


__all__ = ["CANDIDATE_ZONES", "DAY_CENTRE_HOUR", "MAX_AMBIGUOUS_OFFSET_HOURS", "MIN_EVENTS", "awake_fraction",
           "infer_zone", "infer_and_store", "outbound_timestamps", "score_zone"]
