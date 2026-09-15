"""L2.7 · 566 analytic facts, and not one of them was ever a card's subject.

L2.4 measures every node against its own history and its cohort, and publishes the verdicts as
`derived.trend.*`, `derived.anomaly.*` and `derived.cohort_position.*`. Six of BLG-18's importance
modifiers read them. That is the whole of their reach: they can make an existing card rank higher
and they can never BE one. Measured on the pilot 2026-09-15 — 264 trend facts, 264 anomaly facts,
38 cohort positions, and a feed in which "this relationship has been going quiet for three
sampling periods" appears nowhere, because no reading takes the stratum as its subject.

THE DETECTOR ALREADY DECIDED; THIS ONLY REPORTS. No threshold is declared in this module and none
may be. `trend` publishes a `direction` from its own closed vocabulary, `anomaly` publishes
`flagged` from its own two-condition conjunction, and `cohort_position` publishes either a
position or a `refused`. Each of those is a verdict reached against the tenant's OWN measured
history by code that already owns the question. A second opinion here — "but only if the slope is
steep enough" — would be a rule tuned on whoever we looked at last, applied to a customer we have
never seen.

WHAT IS ADMITTED IS WHAT THE DETECTOR CALLED A MOVEMENT. `FLAT` is a measurement and not a
situation: it says the thing did not move, which is the answer to a question nobody asked. The two
insufficiency directions are refusals and belong on the quality surface that reports coverage, not
in a feed of things to act on — a card reading "we cannot tell you about this account" for 94
accounts is the flood this layer exists to prevent.

COVERAGE TRAVELS WITH THE CLAIM. Every trend carries `coverage_ratio_bp`, `gap_corrected` and the
periods it could not read, and on the pilot the largest movements are computed over series with a
silent source — four unknowable weeks with `gcal` reporting nothing. A card that says "going quiet
for three periods" without saying "and one of your calendars stopped reporting" is describing our
own blind spot as the customer's behaviour. That is the single worst output this stratum can
produce, and `analytic.coverage_ratio_bp` / `analytic.silent_sources` are carried onto the card so
it cannot be produced silently.

ORDERED BY THE DETECTOR'S OWN MAGNITUDE. `relative_slope_bp` and `z_like_bp` are numbers L2.4
computed; sorting by them picks which findings survive the per-sweep bound without this module
forming an opinion about which metric matters. A tenant whose steepest movement is in a metric we
have never heard of gets that one, which is the point.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.context.analytic.anomaly import ANOMALY_FACT_PREFIX
from genios_engine.context.analytic.comparator import POSITION_FACT_PREFIX as COHORT_POSITION_FACT_PREFIX
from genios_engine.context.analytic.trend import TREND_FACT_PREFIX

#: Its own anchor, for the same reason `stated_dependency` gives: one node carries several
#: readings and they resolve independently — a relationship can stop going quiet while its
#: contact breadth is still narrowing.
ANCHOR_ANALYTIC = "analytic_movement"

#: How many reach one feed from one sweep. A bound, not a filter: the ordering below decides
#: which, and it is the detector's number that orders them.
MAX_PER_SWEEP = 12

#: THE DETECTOR'S OWN WORD FOR "IT MOVED". Imported as strings rather than compared against
#: `TrendDirection` members so a direction added upstream fails loudly here as an unknown word
#: instead of being silently excluded by an enum this module pinned.
MOVED = ("rising", "declining")

_ROWS = ("select f.subject_node_id as node_id, f.field as field, f.value as value "
         "from graph_facts f where f.org_id = :o and f.status = 'active' "
         "and f.valid_to is null and (f.field like :trend or f.field like :anomaly "
         "or f.field like :cohort) order by f.subject_node_id, f.field")


def _payload(value: Any) -> Mapping | None:
    """One malformed row is one silent reading; an exception is every reading on the tenant."""
    if isinstance(value, (str, bytes)):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, Mapping) else None


def _metric_of(field: str, payload: Mapping) -> str:
    """The metric the fact is ABOUT. Taken from the payload, which is what the detector wrote,
    and falling back to the field suffix — never the other way round: the field name is a
    rendering of the metric and the payload is the metric itself."""
    stated = str(payload.get("metric") or "").strip()
    if stated:
        return stated
    for prefix in (TREND_FACT_PREFIX, ANOMALY_FACT_PREFIX, COHORT_POSITION_FACT_PREFIX):
        if field.startswith(prefix):
            return field[len(prefix):]
    return field


def _readable(metric: str) -> str:
    """`engagement.days_since_contact` → "days since contact".

    A RENDERING, NOT A VOCABULARY. There is no list of metrics here and no metric is privileged:
    the last dotted segment with its underscores opened out, whatever the segment happens to be.
    A tenant measuring something this engine has never seen gets a readable sentence about it,
    which is the difference between a renderer and a rule.
    """
    tail = metric.rsplit(".", 1)[-1] if "." in metric else metric
    return tail.replace("_", " ").strip() or metric


def gather_analytic_movements(conn, org_id: str) -> dict[str, object]:
    rows = conn.execute(text(_ROWS), {"o": org_id, "trend": f"{TREND_FACT_PREFIX}%",
                                      "anomaly": f"{ANOMALY_FACT_PREFIX}%",
                                      "cohort": f"{COHORT_POSITION_FACT_PREFIX}%"}
                        ).mappings().all()
    held: dict[str, object] = {}
    for row in rows:
        held.setdefault(str(row["node_id"]), []).append((str(row["field"]), row["value"]))
    return held


def _trend_finding(node_id: str, field: str, payload: Mapping, name: str) -> tuple | None:
    direction = str(payload.get("direction") or "").strip().lower()
    if direction not in MOVED:
        # FLAT is a measurement, and the two insufficiency words are refusals. Neither is a
        # thing that happened. See the module docstring.
        return None
    metric = _metric_of(field, payload)
    slope = int(payload.get("relative_slope_bp") or 0)
    streak = int(payload.get("streak_periods") or 0)

    facts: list[tuple[str, object, str]] = [
        ("analytic.metric", metric, "string"),
        ("analytic.kind", "trend", "enum"),
        ("analytic.direction", direction, "enum"),
        ("analytic.relative_slope_bp", abs(slope), "bp"),
        ("analytic.streak_periods", streak, "count"),
        ("analytic.point_count", int(payload.get("point_count") or 0), "count"),
    ]
    confidence = payload.get("trend_confidence_bp")
    if confidence is not None:
        facts.append(("analytic.trend_confidence_bp", int(confidence), "bp"))

    # THE CAVEAT IS PART OF THE CLAIM, not an annotation on it. A movement computed across weeks
    # a connector was silent is partly a measurement of our own coverage, and the card has to be
    # able to say which.
    coverage = payload.get("coverage_ratio_bp")
    if coverage is not None:
        facts.append(("analytic.coverage_ratio_bp", int(coverage), "bp"))
    if payload.get("gap_corrected"):
        facts.append(("analytic.gap_corrected", True, "bool"))
    reasons = payload.get("gap_reasons")
    silent = list(reasons.get("silent_sources") or ()) if isinstance(reasons, Mapping) else []
    if silent:
        facts.append(("analytic.silent_sources", ", ".join(str(s) for s in silent), "string"))
    unknowable = list(reasons.get("unknowable_periods") or ()) if isinstance(reasons, Mapping) else []
    if unknowable:
        facts.append(("analytic.unreadable_periods", len(unknowable), "count"))

    headline = f"{name}: {_readable(metric)} {direction}"
    return (abs(slope), node_id, f"trend:{node_id}:{metric}", headline, facts, metric)


def _anomaly_finding(node_id: str, field: str, payload: Mapping, name: str) -> tuple | None:
    if not payload.get("flagged"):
        # NOT A FILTER — the detector's own two-condition conjunction, read as it was written.
        # An unflagged measurement is carried on the fact for a reader who asks "why wasn't this
        # flagged"; it is not a thing that happened to the business.
        return None
    metric = _metric_of(field, payload)
    z = int(payload.get("z_like_bp") or 0)
    facts: list[tuple[str, object, str]] = [
        ("analytic.metric", metric, "string"),
        ("analytic.kind", "anomaly", "enum"),
        ("analytic.direction", str(payload.get("direction") or ""), "enum"),
        ("analytic.z_like_bp", z, "bp"),
        ("analytic.deviation_bp", int(payload.get("deviation_bp") or 0), "bp"),
        ("analytic.current_bp", int(payload.get("current_bp") or 0), "bp"),
        ("analytic.baseline_bp", int(payload.get("baseline_bp") or 0), "bp"),
        ("analytic.periods_used", int(payload.get("periods_used") or 0), "count"),
    ]
    headline = (f"{name}: {_readable(metric)} unlike its own baseline "
                f"({payload.get('direction') or 'moved'})")
    return (z, node_id, f"anomaly:{node_id}:{metric}", headline, facts, metric)


def _cohort_finding(node_id: str, field: str, payload: Mapping, name: str) -> tuple | None:
    if payload.get("refused"):
        # A refusal reaches the quality surface, not the feed. `insufficient_coverage` on 29 of
        # 48 cohort members is a statement about what we hold, and a card per member saying so is
        # 48 cards about one gap.
        return None
    percentile = payload.get("percentile_bp")
    if percentile is None:
        return None
    metric = _metric_of(field, payload)
    facts: list[tuple[str, object, str]] = [
        ("analytic.metric", metric, "string"),
        ("analytic.kind", "cohort_position", "enum"),
        ("analytic.percentile_bp", int(percentile), "bp"),
        ("analytic.population_size", int(payload.get("population_size") or 0), "count"),
    ]
    cohort = str(payload.get("cohort_id") or "").strip()
    if cohort:
        facts.append(("analytic.cohort_id", cohort, "string"))
    headline = f"{name}: {_readable(metric)} against its cohort"
    # ORDERED BY DISTANCE FROM THE MIDDLE, which is the cohort comparator's own statement of how
    # unusual a position is. A node at the median is the least interesting thing in its cohort.
    return (abs(int(percentile) - 5_000), node_id, f"cohort:{node_id}:{metric}",
            headline, facts, metric)


def read_analytic_movements(rows: Mapping[str, object], now: datetime,
                            names: Mapping[str, str] | None = None) -> list:
    """One finding per analytic verdict that says something MOVED.

    `now` is unused and required: every reading in this layer takes the sweep instant so a
    replay reproduces it, and a reading that quietly takes its own clock is the defect the
    signature exists to prevent.
    """
    from genios_engine.context.outreach_situations import _Finding

    builders = ((TREND_FACT_PREFIX, _trend_finding),
                (ANOMALY_FACT_PREFIX, _anomaly_finding),
                (COHORT_POSITION_FACT_PREFIX, _cohort_finding))

    candidates: list[tuple] = []
    for node_id, entries in rows.items():
        if str(node_id).startswith("_") or not isinstance(entries, list):
            continue
        name = str((names or {}).get(str(node_id)) or "").strip() or "this account"
        for field, value in entries:
            payload = _payload(value)
            if payload is None:
                continue
            for prefix, build in builders:
                if not field.startswith(prefix):
                    continue
                made = build(str(node_id), field, payload, name)
                if made is not None:
                    candidates.append(made)
                break

    # The detector's magnitude decides who survives the bound; the key and node break ties so a
    # replay of the same sweep produces the same feed.
    candidates.sort(key=lambda item: (-item[0], item[2]))

    findings: list = []
    for magnitude, node_id, key, headline, facts, metric in candidates[:MAX_PER_SWEEP]:
        findings.append(_Finding(
            anchor=ANCHOR_ANALYTIC,
            canonical_key=f"analytic:{key}",
            display_name=headline[:120],
            facts=facts,
            concerns_node=node_id,
            correlation_id=f"analytic:{key}",
            # DECLARED, BECAUSE THE STRATUM CANNOT SEE IT. L2.4 measures shape and never reads a
            # sentence: it knows the metric moved and has no access to what anybody said about
            # it. A card implying a cause would be supplying the one thing no detector produced.
            missing=["analytic.cause"],
            inputs={"reading": ANCHOR_ANALYTIC,
                    "derived_from": f"L2.4 analytic stratum, {metric}; the detector's own "
                                    f"verdict, ordered by the magnitude it computed"},
        ))
    return findings


__all__ = ["ANCHOR_ANALYTIC", "MAX_PER_SWEEP", "MOVED", "gather_analytic_movements",
           "read_analytic_movements"]
