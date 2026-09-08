"""Category 1 · Situation Understanding — the Timeline Unit.

Answers one question: *what shape does this situation have over time?*

Most of GeniOS reads the present — is engagement low, is the deal open, is anyone waiting.  The
timeline reads the *sequence*: when things happened, how far apart, whether the rhythm is
tightening or unravelling, and whether the last event is older than the rhythm this relationship
declared for itself.  Two situations with an identical present can have opposite shapes — a deal
quiet for nine days after eleven exchanges in a fortnight is a break in a strong rhythm; a deal
quiet for nine days after two emails ever never had a rhythm to break.  Only the ordering tells
them apart, and acting on the present alone treats those two as the same situation.

Three separate claims, therefore three plugins, because they fail independently:

* **ordering** — how many events are known, how recent the newest is, how wide the timeline is,
  and what a typical gap looks like.  The only plugin that needs no declared intent.
* **cadence** — the newest event measured against a cadence somebody actually declared.  Without
  a declared cadence there is no such thing as overdue, so the plugin says nothing rather than
  inventing a norm from thin air.
* **trend** — whether the closed gaps have been shortening or stretching.  Needs at least three
  events; with two you have one gap and no trend, and reporting a trend from one gap would be a
  fabrication dressed as arithmetic.
* **deadline pressure** — how close the nearest material date is.  The other three claims read
  the past; this one reads the future, and it is the only thing in the engine that can say a
  situation is urgent because of *when something is due* rather than because of how long it has
  been quiet.

**Why urgency is published here (DLG-04).**  `urgency_bp` is resolved by the Decision Maker
through `core.priority`, whose `MaximumUrgencyPlugin` was built to take the loudest reading any
prior unit reported — and until now, on the compiled lane, no prior unit reported one at all, so
every situation carried the neutral 5,000bp midpoint and every card ranked the same.  A midpoint
is not a measurement.  This unit already parses the dates, so this unit computes the ladder; the
priority unit still owns the published authority and still resolves max-wins across sources, and
nothing in `priority.py` changes.

**No date is 0, never 5,000.**  An undated situation is not half urgent, it is undated, and a
ladder that manufactured pressure out of an absent deadline would be inventing exactly the
evidence the rest of the engine refuses to invent.

**Why this is not `core.temporal`.**  `core.temporal` measures how far one deal's engagement has
fallen and how long since it was last touched — a magnitude for a single relationship.  This unit
never publishes `drop_bp`; it publishes the arrangement of events in time.  It reads `drop_bp` in
one place only — as corroboration for a decay reason code — and that reading can never move a
number here, so adding `core.temporal` to a plan can never silently re-score the timeline.

The unit reports shape.  It never says "follow up now" or ranks which silence matters most; that
synthesis is the Decision Maker's, and keeping it out of here is what keeps the shape auditable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.reasoning import Finding

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, evidence_ids, fact_value, parse_time

# The timestamp facts Layer 2 is known to publish for the entity families this unit serves.  Any
# of them may be absent — an absent field contributes nothing rather than a zero — and a
# capability with different field names overrides the list through `timeline_fields`.
DEFAULT_TIMELINE_FIELDS: tuple[str, ...] = (
    "deal.last_inbound",
    "deal.last_outbound",
    "thread.last_inbound",
    "thread.last_outbound",
)

# An optional explicit event log: a list of records, each carrying its own moment.  When Layer 2
# can supply the real sequence, it beats reconstructing a shape from four "last seen" anchors.
EVENT_LIST_FIELD = "timeline.events"

# A cadence the business declared for this relationship ("we review this account weekly").  It is a
# statement of intent, not an observation, which is why breaching it means something.
CADENCE_FACT = "timeline.cadence_hours"

# The dated commitments a situation can be materially late for. Deliberately short and
# domain-free: which fields carry a renewal, a close date or a contractual deadline is a reading
# that belongs to the L3 manifest (`deadline_fields`), not to a core unit.
DEFAULT_DEADLINE_FIELDS: tuple[str, ...] = ("commitment.due_at",)

#: The urgency ladder (doc 02 U5), as (hours remaining at or below which the band applies, bp).
#: Read top-down; the first row whose bound is not exceeded wins. Bands rather than a curve
#: because the number is consumed as a rank input and a smooth function would produce a thousand
#: indistinguishable levels of "next month", none of which any human would act on differently.
URGENCY_LADDER: tuple[tuple[int, int], ...] = (
    (0, 10_000),        # already due, or past due
    (48, 9_000),        # within two days
    (168, 7_500),       # within a week
    (336, 6_000),       # within a fortnight
    (720, 4_000),       # within a month
    (2_160, 2_000),     # within a quarter
)

#: Anything beyond the last ladder rung. Not zero: a dated obligation a year out is still a dated
#: obligation, and it must outrank a situation with no date at all.
URGENCY_BEYOND_BP = 500

#: No material date was found. The one reading that is a measured absence rather than a distance.
URGENCY_UNDATED_BP = 0

#: How much of a reading a date's own certainty band earns, as (numerator, denominator) — L1's
#: rule, carried through rather than re-derived. EXACT and RANGE are taken at full weight (a RANGE
#: is read at its EARLIEST bound, which is when the obligation first becomes live); RELATIVE is
#: halved, because "soon" is a heuristic window ALG-09 guessed and half-trusting it is the honest
#: reading. UNRESOLVED carries no window at all and is skipped entirely — there is nothing to
#: ladder.
CERTAINTY_WEIGHT: Mapping[str, tuple[int, int]] = {
    "exact": (1, 1),
    "range": (1, 1),
    "relative": (1, 2),
}

_CERTAINTY_KEYS: tuple[str, ...] = ("certainty",)
_WINDOW_START_KEYS: tuple[str, ...] = ("earliest", "start", "from")

_MOMENT_KEYS: tuple[str, ...] = ("occurred_at", "at", "timestamp", "time")
_LABEL_KEYS: tuple[str, ...] = ("event_id", "id", "kind", "type", "label")
_MAX_CADENCE_HOURS = 8_760  # one year; beyond that "overdue" stops being a useful reading

# Neutral trend: gaps that neither shortened nor stretched.  Acceleration is expressed around this
# midpoint so that a single number carries both directions without a separate sign field.
STEADY_BP = 5_000


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Capability tuning arrives as integer basis points; anything else is an authoring bug.

    Raising rather than defaulting is deliberate: a mistyped threshold that silently falls back to
    the default would ship a capability that scores differently from what its author reviewed.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_hours(view: UnitView, key: str) -> int | None:
    """A duration in whole hours — the one tuning value that is honestly not a ratio."""
    value = view.config.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) \
            or not 1 <= value <= _MAX_CADENCE_HOURS:
        raise ValueError(
            f"{key} must be a whole number of hours between 1 and {_MAX_CADENCE_HOURS}")
    return value


def _config_fields(view: UnitView) -> tuple[str, ...]:
    """Which timestamp facts make up this capability's timeline."""
    raw = view.config.get("timeline_fields")
    if raw is None:
        return DEFAULT_TIMELINE_FIELDS
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
        raise ValueError("timeline_fields must be a list of fact field names")
    fields = tuple(str(item).strip() for item in raw)
    if any(not name for name in fields):
        raise ValueError("timeline_fields must not contain empty field names")
    return fields


def _config_deadline_fields(view: UnitView) -> tuple[str, ...]:
    """Which facts carry a date this situation can be late for.

    Declared per capability. The default is the one dated obligation the platform itself writes;
    every domain-specific date — a renewal, a close date, a contractual cure period — is named in
    the L3 manifest, which is where the knowledge that those fields *are* deadlines lives.
    """
    raw = view.config.get("deadline_fields")
    if raw is None:
        return DEFAULT_DEADLINE_FIELDS
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
        raise ValueError("deadline_fields must be a list of fact field names")
    fields = tuple(str(item).strip() for item in raw)
    if any(not name for name in fields):
        raise ValueError("deadline_fields must not contain empty field names")
    return fields


def urgency_from_hours(hours: int) -> int:
    """The ladder: hours until a material date become one of seven bands of pressure."""
    for bound, value in URGENCY_LADDER:
        if hours <= bound:
            return value
    return URGENCY_BEYOND_BP


@dataclass(frozen=True, slots=True)
class _Event:
    """One dated thing that happened, carrying its source so evidence stays attributable."""

    at: datetime
    label: str
    field: str


@dataclass(frozen=True, slots=True)
class _MaterialDate:
    """One dated obligation, with the certainty band that says how much of it to believe."""

    at: datetime
    field: str
    certainty: str
    numerator: int
    denominator: int


def _certainty_of(record: Mapping[str, Any]) -> str | None:
    """The declared certainty band, or None when the record does not carry one this unit trusts.

    A record with no `certainty` key is a plain normalised timestamp — L1 resolved it and stored
    an instant — and is read as EXACT. A record whose band is UNRESOLVED, or is a word this unit
    does not know, yields None and the date is dropped: an unrecognised certainty is an unread
    one, and reading it as EXACT is precisely the fabrication `ResolvedDate` exists to prevent.
    """
    for key in _CERTAINTY_KEYS:
        if key in record:
            band = str(record[key] or "").strip().lower()
            return band if band in CERTAINTY_WEIGHT else None
    return "exact"


def _material_date(view: UnitView, field: str) -> _MaterialDate | None:
    """Read one declared date field as an instant plus a weight, or None if it says nothing.

    Two shapes arrive here and both are read without re-parsing anything L1 already resolved: a
    normalised timestamp (EXACT), or a `ResolvedDate`-shaped record carrying a window and a
    certainty band, which is read at its EARLIEST bound — the moment the obligation first becomes
    live. Malformed data returns None rather than raising: bad *config* is an authoring fault and
    raises, bad *data* is a fact of life and must not take a whole reasoning run down with it.
    """
    raw = fact_value(view.request, field)
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        certainty = _certainty_of(raw)
        if certainty is None:
            return None                    # UNRESOLVED or unknown: there is no window to ladder
        at: datetime | None = None
        for key in _WINDOW_START_KEYS + _MOMENT_KEYS:
            if raw.get(key) is not None:
                at = _moment(raw[key], f"{field}.{key}")
                break
        if at is None:
            return None
        numerator, denominator = CERTAINTY_WEIGHT[certainty]
        return _MaterialDate(at=at, field=field, certainty=certainty,
                             numerator=numerator, denominator=denominator)
    at = _moment(raw, field)
    if at is None:
        return None
    return _MaterialDate(at=at, field=field, certainty="exact", numerator=1, denominator=1)


def _hours_between(earlier: datetime, later: datetime) -> int:
    """Whole hours, truncated. Sub-hour precision is noise at a timeline's timescales."""
    return int((later - earlier).total_seconds()) // 3600


def _signed_hours(moment: datetime, reference: datetime) -> int:
    """Whole hours from `reference` to `moment` — negative once the moment is in the past.

    `_hours_between` truncates toward zero, which would read a deadline missed by ninety minutes
    as one hour late and a deadline missed by thirty minutes as not late at all. Floor division on
    the signed second count keeps "past" strictly negative on both sides of the hour.
    """
    return int((moment - reference).total_seconds()) // 3600


def _moment(entry: Any, label: str) -> datetime | None:
    """Pull the moment out of an event record, or None if it has none we can trust."""
    if isinstance(entry, Mapping):
        for key in _MOMENT_KEYS:
            if key in entry:
                try:
                    return parse_time(entry[key], f"{label}.{key}")
                except ValueError:
                    return None            # malformed timestamp: drop the event, never guess one
        return None
    try:
        return parse_time(entry, label)
    except ValueError:
        return None


def _entry_label(entry: Any, ordinal: int) -> str:
    """A stable tiebreaker for two events at the same instant — never iteration position alone."""
    if isinstance(entry, Mapping):
        for key in _LABEL_KEYS:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return f"{EVENT_LIST_FIELD}#{ordinal:04d}"


def _known_events(view: UnitView) -> tuple[_Event, ...]:
    """Every event this unit can date, ordered oldest first.

    Two rules earn their place here.  **Future timestamps are excluded**: a scheduled meeting has
    not happened, and letting it in would make the newest "event" something nobody has done yet.
    **Identical instants collapse to one event**: `deal.last_inbound` and `thread.last_inbound` are
    routinely the same message seen through two joins, and counting it twice would invent an extra
    event and a zero-hour gap that never existed.
    """
    now = view.request.evaluation_time
    collected: list[_Event] = []

    raw_events = fact_value(view.request, EVENT_LIST_FIELD)
    if isinstance(raw_events, (tuple, list)):
        for ordinal, entry in enumerate(raw_events):
            label = _entry_label(entry, ordinal)
            at = _moment(entry, label)
            if at is not None and at <= now:
                collected.append(_Event(at=at, label=label, field=EVENT_LIST_FIELD))

    for name in sorted(_config_fields(view)):
        at = _moment(fact_value(view.request, name), name)
        if at is not None and at <= now:
            collected.append(_Event(at=at, label=name, field=name))

    deduped: dict[datetime, _Event] = {}
    for event in sorted(collected, key=lambda item: (item.at, item.label, item.field)):
        deduped.setdefault(event.at, event)
    return tuple(sorted(deduped.values(), key=lambda item: (item.at, item.label)))


def _gaps(events: Sequence[_Event]) -> tuple[int, ...]:
    """Closed intervals between consecutive events, oldest gap first.

    The stretch of silence since the newest event is deliberately *not* a gap: it is still open,
    and may close tomorrow.  Treating it as a gap would let a live situation look like a dead one.
    """
    return tuple(_hours_between(events[index].at, events[index + 1].at)
                 for index in range(len(events) - 1))


def _median(values: Sequence[int]) -> int:
    """Median, not mean: one dormant summer must not redefine what a normal gap looks like."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return divide_half_up(ordered[middle - 1] + ordered[middle], 2)


def _evidence(view: UnitView, events: Sequence[_Event]) -> tuple[str, ...]:
    return evidence_ids(view.request, *{event.field for event in events})


class EventOrderingPlugin:
    """How many events are known, how recent the newest is, and how far apart they normally fall.

    This is the base layer every other timeline claim stands on, and the one honest thing this unit
    can say when nothing else is declared.  It is silent when no event can be dated, because a
    timeline of zero events has no recency, no span, and no typical gap — only absence, which the
    unit reports as `event_count: 0` rather than as a shape.
    """

    plugin_id = "event_ordering"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        events = _known_events(view)
        if not events:
            return ()
        latest_age = _hours_between(events[-1].at, view.request.evaluation_time)
        span = _hours_between(events[0].at, events[-1].at)
        metrics: dict[str, int] = {
            "event_count": len(events),
            "latest_age_hours": latest_age,
            "span_hours": span,
        }
        codes: list[str] = []
        gaps = _gaps(events)
        if gaps:
            metrics["gap_hours"] = _median(gaps)
            metrics["max_gap_hours"] = max(gaps)
            # The current silence has already outlasted the longest silence this relationship ever
            # recovered from.  A fact about the shape, not a verdict on what to do about it.
            if latest_age > max(gaps):
                codes.append("silence_exceeds_prior_gaps")
        else:
            codes.append("timeline_single_event")
        return (Observation(
            plugin_id=self.plugin_id,
            kind="timeline.ordering",
            metrics=metrics,
            evidence_ids=_evidence(view, events),
            reason_codes=tuple(codes),
        ),)


class CadenceAdherencePlugin:
    """Is the newest event older than the rhythm somebody declared for this relationship?

    Overdue is meaningless without a declaration — "three weeks quiet" is negligence on a weekly
    account and completely normal on a quarterly one.  So this plugin speaks only when a cadence
    exists as a fact (per relationship) or as capability config (per capability), and stays silent
    otherwise rather than inventing a norm the business never agreed to.

    A full cadence period past due reads as 10,000bp: being one whole period late is as late as the
    metric needs to distinguish, and everything beyond it is equally, maximally overdue.
    """

    plugin_id = "cadence_adherence"

    def _declared_hours(self, view: UnitView) -> int | None:
        raw = fact_value(view.request, CADENCE_FACT)
        if not isinstance(raw, bool) and isinstance(raw, int) \
                and 1 <= raw <= _MAX_CADENCE_HOURS:
            return raw
        # A malformed or absent per-relationship cadence falls back to the capability declaration;
        # bad *data* must not raise, whereas bad *config* does (see _config_hours).
        return _config_hours(view, "expected_cadence_hours")

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        cadence = self._declared_hours(view)
        if cadence is None:
            return ()
        events = _known_events(view)
        if not events:
            return ()
        age = _hours_between(events[-1].at, view.request.evaluation_time)
        overdue = max(0, age - cadence)
        breach = clamp_bp(divide_half_up(overdue * 10_000, cadence))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="timeline.cadence",
            metrics={"cadence_hours": cadence, "overdue_hours": overdue, "breach_bp": breach},
            evidence_ids=_evidence(view, events[-1:]),
            reason_codes=("cadence_breached",) if overdue > 0 else ("cadence_on_track",),
        ),)


class TrendDirectionPlugin:
    """Are the gaps tightening or stretching?

    Momentum is a derivative, not a level: a deal with three exchanges a week and slowing is a
    different situation from one with three exchanges a week and speeding up, even though both look
    identically busy today.  The oldest half of the closed gaps is compared with the newest half;
    on an odd count the pivot gap belongs to neither side, so it cannot be double-counted.

    Reported around a 5,000bp midpoint — above is accelerating, below is decaying — with each side
    scaled by its own larger term so both directions are bounded and symmetric.  Fewer than three
    events means fewer than two gaps, which is not a trend, and the plugin says nothing.
    """

    plugin_id = "trend_direction"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        gaps = _gaps(_known_events(view))
        if len(gaps) < 2:
            return ()
        split = len(gaps) // 2
        earlier = gaps[:split]
        recent = gaps[len(gaps) - split:]
        earlier_mean = divide_half_up(sum(earlier), len(earlier))
        recent_mean = divide_half_up(sum(recent), len(recent))
        if earlier_mean <= 0:
            # Every earlier event landed inside the same hour: there is no baseline interval to
            # compare against, so a ratio would be an artefact of rounding rather than a trend.
            if recent_mean <= 0:
                acceleration = STEADY_BP
            else:
                acceleration = 0
        elif recent_mean <= 0:
            acceleration = 10_000              # the rhythm collapsed to back-to-back activity
        elif recent_mean < earlier_mean:
            acceleration = STEADY_BP + divide_half_up(
                (earlier_mean - recent_mean) * STEADY_BP, earlier_mean)
        elif recent_mean > earlier_mean:
            acceleration = STEADY_BP - divide_half_up(
                (recent_mean - earlier_mean) * STEADY_BP, recent_mean)
        else:
            acceleration = STEADY_BP
        acceleration = clamp_bp(acceleration)
        if acceleration > STEADY_BP:
            code = "timeline_accelerating"
        elif acceleration < STEADY_BP:
            code = "timeline_decaying"
        else:
            code = "timeline_steady"
        return (Observation(
            plugin_id=self.plugin_id,
            kind="timeline.trend",
            metrics={"acceleration_bp": acceleration, "earlier_gap_hours": earlier_mean,
                     "recent_gap_hours": recent_mean, "gap_sample": len(gaps)},
            reason_codes=(code,),
        ),)


class MaterialDeadlinePlugin:
    """How close the nearest thing this situation is contractually late for actually is.

    Every other claim in this unit reads backwards — how long since, how far apart, tightening or
    stretching. This one reads forwards, and it is the only reading in the engine that can say a
    situation is urgent because something is *due*. Without it the compiled lane had no urgency
    source at all: `core.priority` resolves the maximum any prior unit reported, no prior unit
    reported one, and the whole org sat on the neutral 5,000bp midpoint — which is how 104 of 115
    cards ended up at an identical score.

    Three judgements are deliberate:

    **The nearest date does not automatically win — the strongest reading does.** Dates are
    laddered one at a time and the maximum is published, so a firm deadline in three weeks is not
    outranked by a vague "sometime soon" that happens to resolve nearer. Where two readings tie,
    the nearer date wins, then the field name; the winner can never depend on mapping order.

    **Certainty is a discount, not a filter.** A RELATIVE date is halved rather than dropped: the
    source really did say something was coming, and throwing that away would be as wrong as
    treating "soon" as a contract. UNRESOLVED carries no window and *is* dropped, because there is
    no distance to measure.

    **An absent date is a measured zero, published with a reason.** The plugin always speaks. If
    it stayed silent the unit would publish no `urgency_bp`, the priority unit would fall back to
    its neutral midpoint, and the exact defect this plugin exists to end would come back through
    the door it was chased out of.
    """

    plugin_id = "material_deadline"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        fields = _config_deadline_fields(view)
        readings = {name: _material_date(view, name) for name in sorted(set(fields))}
        dated = tuple(item for item in readings.values() if item is not None)
        if not dated:
            # THREE STATES, NOT TWO, and the third is the one that hid a real defect for a whole
            # wave. A field that carried nothing is an UNDATED situation and the ladder's measured
            # 0 is the right reading. A field that carried a value this unit could not read as a
            # date is UNKNOWN: something said a date was there and the reading failed. Publishing
            # 0 for both made them the same number, and the number that hid was the second one --
            # `commitment.due_at` arriving as a NAIVE ISO timestamp, refused by `parse_time`,
            # swallowed by `_moment`'s `except ValueError`, and reported as "no material date" on
            # every decision in the org.
            #
            # UNKNOWN publishes no `urgency_bp` at all. `core.priority`'s MaximumUrgencyPlugin
            # reads an absent reading as 0 for the maximum -- so nothing is manufactured -- while
            # the reason code and the count make the difference visible to anyone reading the
            # trace, which a shared 0 never could.
            unreadable = tuple(name for name, item in readings.items()
                               if item is None and fact_value(view.request, name) is not None)
            if unreadable:
                return (Observation(
                    plugin_id=self.plugin_id,
                    kind="timeline.deadline",
                    metrics={"unreadable_field_count": len(unreadable),
                             "dated_field_count": 0},
                    reason_codes=("material_date_unreadable",),
                ),)
            return (Observation(
                plugin_id=self.plugin_id,
                kind="timeline.deadline",
                metrics={"urgency_bp": URGENCY_UNDATED_BP, "dated_field_count": 0},
                reason_codes=("no_material_date",),
            ),)
        # (reading, hours) per date, then a total order: strongest reading, then nearest, then
        # field name. Sorting on the negated hours would break on a date already past, so the
        # ordering is expressed as a max over an explicitly signed key instead.
        scored = tuple(sorted(
            ((divide_half_up(urgency_from_hours(
                _signed_hours(item.at, view.request.evaluation_time)) * item.numerator,
                item.denominator),
              _signed_hours(item.at, view.request.evaluation_time), item.field, item.certainty)
             for item in dated),
            key=lambda row: (-row[0], row[1], row[2])))
        urgency, hours, field, certainty = scored[0]
        codes = ["deadline_overdue" if hours <= 0 else "deadline_ahead"]
        if certainty != "exact":
            codes.append(f"deadline_certainty_{certainty}")
        return (Observation(
            plugin_id=self.plugin_id,
            kind="timeline.deadline",
            metrics={"urgency_bp": clamp_bp(urgency), "deadline_hours": hours,
                     "dated_field_count": len(dated)},
            evidence_ids=evidence_ids(view.request, *{item.field for item in dated}),
            reason_codes=tuple(codes),
        ),)


class TimelineUnit(ReasoningUnit):
    """Situation Understanding · the shape and order of the situation over time.

    Publishes only what it could actually observe.  A metric that is absent means "unknown", and
    downstream readers get their own default from `prior_metric`; emitting a zero for a gap nobody
    measured is indistinguishable from a measured zero, and something would eventually act on it.
    """

    unit_id = "core.timeline"
    version = "1.0.0"
    category = UnitCategory.SITUATION_UNDERSTANDING
    #: Metrics this unit publishes as a SOURCE for a metric another unit is the AUTHORITY on.
    #: Declaring it is what separates a legitimate composition from a second publisher nobody
    #: noticed: `tests/test_unit_roster.py` refuses any unit that publishes `urgency_bp` without
    #: naming the authority that resolves it, and `core.priority` resolves max-wins across sources.
    resolves_through: Mapping[str, str] = {"urgency_bp": "core.priority"}
    #: `urgency_bp` is DECLARED here and RESOLVED by `core.priority`, which remains the Decision
    #: Maker's named authority for it (`decision_maker.PRIORITY_AUTHORITY`). This unit is a
    #: SOURCE: it measures the distance to a dated obligation and publishes the reading, and the
    #: priority unit's `MaximumUrgencyPlugin` takes the loudest reading across every source. Two
    #: sources feeding one authority is the design; two authorities would not be.
    publishes = ("event_count", "elapsed_hours", "span_hours", "gap_hours", "max_gap_hours",
                 "cadence_hours", "cadence_breach_bp", "overdue_hours", "acceleration_bp",
                 "urgency_bp", "deadline_hours")
    plugins = (CadenceAdherencePlugin(), EventOrderingPlugin(), MaterialDeadlinePlugin(),
               TrendDirectionPlugin())

    @staticmethod
    def _by_kind(observations: Sequence[Observation], kind: str) -> Observation | None:
        for item in observations:
            if item.kind == kind:
                return item
        return None

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Republish each plugin's measurement under the unit's stable names.

        Deliberately no blending.  Recency, cadence breach and trend answer different questions and
        combining them into one "timeline score" would destroy exactly the distinction the unit
        exists to make — an overdue-but-accelerating situation is not the average of the two.
        """
        del view
        metrics: dict[str, int] = {"event_count": 0}

        ordering = self._by_kind(observations, "timeline.ordering")
        if ordering is not None:
            metrics["event_count"] = int(ordering.metrics["event_count"])
            metrics["elapsed_hours"] = int(ordering.metrics["latest_age_hours"])
            metrics["span_hours"] = int(ordering.metrics["span_hours"])
            if "gap_hours" in ordering.metrics:
                metrics["gap_hours"] = int(ordering.metrics["gap_hours"])
                metrics["max_gap_hours"] = int(ordering.metrics["max_gap_hours"])

        cadence = self._by_kind(observations, "timeline.cadence")
        if cadence is not None:
            metrics["cadence_hours"] = int(cadence.metrics["cadence_hours"])
            metrics["overdue_hours"] = int(cadence.metrics["overdue_hours"])
            metrics["cadence_breach_bp"] = clamp_bp(int(cadence.metrics["breach_bp"]))

        trend = self._by_kind(observations, "timeline.trend")
        if trend is not None:
            metrics["acceleration_bp"] = clamp_bp(int(trend.metrics["acceleration_bp"]))

        deadline = self._by_kind(observations, "timeline.deadline")
        if deadline is not None:
            # ABSENT means unknown, exactly as this unit's docstring states for every other
            # metric. The deadline plugin withholds `urgency_bp` only when a declared date was
            # present and unreadable, and republishing a 0 here would undo that distinction one
            # line after the plugin drew it.
            if "urgency_bp" in deadline.metrics:
                metrics["urgency_bp"] = clamp_bp(int(deadline.metrics["urgency_bp"]))
            if "deadline_hours" in deadline.metrics:
                metrics["deadline_hours"] = int(deadline.metrics["deadline_hours"])
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means the timeline's shape is broken, not that anything should be done.

        Broken is either of two independent things: the situation is materially past a cadence its
        owner declared, or its rhythm is measurably unravelling.  They are ORed rather than summed
        because either one alone is a real break — a weekly account nine days silent is late even
        if its historical gaps were shrinking.

        With no datable event the verdict is `None`, not `False`: "we cannot see the shape" and
        "the shape is fine" are different claims, and collapsing them would let an empty snapshot
        read as a healthy one.
        """
        if not observations:
            return Verdict(matched=None, metrics=dict(metrics))

        breach_threshold = _config_bp(view, "cadence_breach_threshold_bp", 2_000)
        decay_threshold = _config_bp(view, "decay_threshold_bp", 3_000)
        breached = "cadence_breach_bp" in metrics \
            and metrics["cadence_breach_bp"] >= breach_threshold
        decaying = "acceleration_bp" in metrics and metrics["acceleration_bp"] <= decay_threshold

        codes = {code for item in observations for code in item.reason_codes}
        if breached:
            codes.add("cadence_materially_overdue")
        if decaying:
            codes.add("timeline_shape_decaying")
            # Corroboration only. `core.temporal` measures engagement collapse for one deal; when
            # it agrees with a stretching timeline the pairing is worth naming, but it must never
            # move a number here, or adding that unit to a plan would silently re-score this one.
            if view.prior_metric("core.temporal", "drop_bp", 0) >= _config_bp(
                    view, "corroborating_drop_bp", 5_000):
                codes.add("decay_corroborated_by_engagement_drop")

        matched_by_kind: dict[str, bool | None] = {
            "timeline.ordering": None,
            "timeline.cadence": breached,
            "timeline.trend": decaying,
            # Deadline pressure is a magnitude, not a break. `matched` on this unit means the
            # rhythm is broken; whether 9,000bp of urgency should provoke an action is a ranking
            # question, and answering it here would make the timeline a second decision authority.
            "timeline.deadline": None,
        }
        findings = tuple(Finding(
            finding_id=f"timeline.{item.plugin_id}",
            kind="timeline",
            matched=matched_by_kind.get(item.kind),
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations)
        # The deadline plugin always speaks, so "we could not see the shape" can no longer be
        # inferred from an empty observation list. It is inferred from the absence of a SHAPE
        # observation instead — otherwise a situation with a due date and no datable event would
        # report a healthy rhythm it never had.
        shape_seen = any(item.kind != "timeline.deadline" for item in observations)
        return Verdict(
            matched=bool(breached or decaying) if shape_seen else None,
            metrics=dict(metrics),
            findings=findings,
            reason_codes=tuple(sorted(codes)),
        )


__all__ = ["CERTAINTY_WEIGHT", "CadenceAdherencePlugin", "DEFAULT_DEADLINE_FIELDS",
           "EventOrderingPlugin", "MaterialDeadlinePlugin", "TimelineUnit",
           "TrendDirectionPlugin", "URGENCY_BEYOND_BP", "URGENCY_LADDER", "URGENCY_UNDATED_BP",
           "urgency_from_hours"]
