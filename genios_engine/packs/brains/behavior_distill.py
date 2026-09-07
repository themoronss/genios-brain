"""N-4 · Behavior-Brain distillation (CLG-10) — Layer 2.4's numbers become a behaviour pattern.

**THE DIVISION, AND IT IS THE WHOLE UNIT.** Layer 2.4 already computed the arithmetic: a `Trend`
is an integer slope over a dense series, its coverage is an integer ratio, its confidence is an
integer basis point, and every one of those is reproducible by hand from `metric_history`. This
module READS those numbers off the facts L2.4 published and never recomputes one of them. What it
adds is a SENTENCE — and the sentence's numbers are templated in from the validated integers,
never emitted by a model. That split is Law 1 (L3 never decides) and the standing model doctrine
(the model constructs meaning; deterministic systems decide when it becomes authoritative) in one
place: if the model wrote "about two weeks", nobody could say which reading it came from.

**WHAT THIS MODULE MAY NOT DO.**

* It may not write a brain. It returns `LearningObject` proposals and hands them to the EXISTING
  Layer 6 pipeline, which persists at a governed state, applies `learning_policies`' floors and
  publishes a version. `feedback/brain_pipeline.py` is the only driver.
* It may not invent a threshold. Every floor CLG-10 applies is either a Layer 6 promotion floor
  (`min_observations`, `min_distinct_days`, `min_distinct_entities`, `min_confidence_bp`,
  `max_noise_bp`) or a number Layer 2.4 already published under its own name
  (`COVERAGE_FLOOR_BP`). The single number this module owns is `BEHAVIOR_MIN_WINDOW_DAYS`, and
  doc 02 states it: *"pattern from 2 weeks of data → 60-day window gate"*.
* It may not use a clock. `eval_time` is a parameter, and NOTHING derived from it reaches either
  the proposed value or the evidence — because both are hashed into the object's identity, so a
  clock in either would mint a new proposal every single run and turn a stable pattern into
  weekly version noise. The value's freshness question is answered by `observed_through`, which
  is a series boundary, not a reading of the wall clock.

**CLG-10 — which L2.4 findings qualify as a pattern.** Stated once, as data, in `qualify()`:

1. the metric is **behaviour-eligible** — not every trend is a habit (`BEHAVIOR_ELIGIBLE_METRICS`);
2. the direction is a **direction**, never one of L2.4's two refusals (`DIRECTIONAL`);
3. each reading covers at least `BEHAVIOR_MIN_WINDOW_DAYS` of real time;
4. each reading's coverage clears L2.4's own `COVERAGE_FLOOR_BP` — a series full of holes
   describes the weeks we happened to observe;
5. the cohort clears the Layer 6 floors: enough observations, over enough periods, across enough
   distinct entities. The third is the one that stops "the same account, ten times" from wearing
   the clothes of a company habit, and it is the tenant's own `min_distinct_entities` — this
   module does not get to pick a friendlier number.

**WHY THE SUBJECT IS `behavior:<metric>:<node>`.** `packs/compiler/runtime_brains.py` selects a
learned entry when its subject key, or any COLON SEGMENT of it, matches something the situation
names — a capability, an object, or an entity. A cohort-level subject (`behavior:<metric>:
<direction>`) matches nothing a situation ever names, so it would compile into no package: Law 4's
inventory-not-intelligence, reproduced inside the brain that was supposed to fix it. One entry per
participating entity, each carrying the COHORT's evidence and roster and that entity's own
reading, is readable the moment a situation mentions that account — and it is still one pattern,
because every entry states the same cohort.

**DECAY.** A published pattern that stops recurring is superseded by its own absence: each batch
re-reads the same facts, and a subject that no longer qualifies while its metric is STILL BEING
MEASURED produces a lapse proposal — a real measurement, through the same floors, superseding the
claim with "this is no longer true". A subject whose series went dark produces nothing, because
there is nothing to measure; `scripts/brain_content_report.py` names those instead of hiding them.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.analytic import DIRECTIONAL, TrendDirection
from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.context.analytic.trend import COVERAGE_FLOOR_BP, TREND_FACT_PREFIX

#: The unit name every proposal from here carries. `learning_objects.unit` is how the content
#: report attributes an entry to "distilled", so it is a constant, not a literal at a call site.
BEHAVIOR_UNIT = "behavior_distillation"

#: The subject namespace. First segment, so `behavior:` never collides with another producer's
#: keys and the report can count this module's entries with one prefix match.
BEHAVIOR_SUBJECT_PREFIX = "behavior"

#: Doc 02's own gate: *"pattern from 2 weeks of data → 60-day window gate"*. The one threshold
#: this module owns, and it is a floor on the OBSERVED WINDOW, not on the number of readings —
#: sixty daily readings of one week are still one week.
BEHAVIOR_MIN_WINDOW_DAYS = 60

#: Per-run ceiling on published entries. The cohort roster is what it multiplies by, and an org
#: with ten thousand accounts trending together would otherwise turn one weekly batch into ten
#: thousand brain writes. Deterministic tail: readings are ordered, so the same batch truncates
#: at the same place.
MAX_BEHAVIOR_ENTRIES_PER_RUN = 200

#: WHICH METRICS ARE A HABIT. The Behavior brain holds *what this company actually does* — its
#: own conduct — and half of L2.4's registry measures the world's conduct instead. An inbound
#: count is what THEY did; a ticket count is demand arriving; a deal's stage age is a state, not
#: an act. Reading those as "how this company behaves" is the exact editorialising doc 02 forbids.
#: Spelled as literals rather than imported from `sampler.TrendedMetric` so this module stays
#: cheap to import; `tests/packs/brains/test_behavior_distill.py` asserts every id below is a
#: registered metric, which is what makes a rename a build failure rather than a silent nothing.
BEHAVIOR_ELIGIBLE_METRICS: frozenset[str] = frozenset({
    "engagement.outbound_count_28d",         # how much this company reaches out
    "relationship.response_latency_hours",   # how fast this company answers
    "account.contact_breadth",               # how many people it engages per account
    "account.open_commitment_count",         # how many promises it carries
    "account.overdue_commitment_count",      # how it follows through on them
    "support.backlog_age_p50_days",          # how it works its queue
})

#: Words a DESCRIPTION does not contain. Doc 02's failure mode is *"model editorialises
#: ('founder is a bottleneck')"* — the brain records what happens, Layer 4 draws the conclusion.
#: Matched on whole words against the lowercased template, so "blocker" is refused and
#: "blocked_count" (a metric name) is not.
JUDGMENT_LEXICON: frozenset[str] = frozenset({
    "bad", "badly", "bottleneck", "careless", "concerning", "dangerous", "disappointing",
    "excellent", "fails", "failing", "good", "great", "healthy", "impressive", "inefficient",
    "lazy", "must", "needs", "neglected", "poor", "poorly", "problem", "problematic", "risky",
    "should", "slow", "sloppy", "terrible", "troubling", "unacceptable", "urgent", "weak",
    "worrying", "worse", "worst",
})

#: The only placeholders a template may carry. A model that names anything else is refused rather
#: than repaired — an unknown placeholder means the model was writing about numbers we did not
#: give it.
TEMPLATE_FIELDS: frozenset[str] = frozenset({
    "metric", "direction", "entities", "weeks", "periods", "slope_bp", "streak", "coverage_bp",
})

#: A statement is one sentence about one measurement. The cap is what stops a "label" from
#: becoming a paragraph of reasoning that nobody validated.
MAX_TEMPLATE_LENGTH = 240

#: The deterministic statement, per direction. THE DEFAULT, not the fallback of last resort: with
#: no labeler configured this module still produces a complete, honest sentence, which is why the
#: whole pipeline is testable and runnable with zero model calls.
DEFAULT_TEMPLATES: Mapping[str, str] = {
    TrendDirection.RISING.value:
        "{metric} has been rising across {entities} accounts over {weeks} weeks "
        "({slope_bp} bp per period, {streak} consecutive periods, coverage {coverage_bp} bp).",
    TrendDirection.DECLINING.value:
        "{metric} has been declining across {entities} accounts over {weeks} weeks "
        "({slope_bp} bp per period, {streak} consecutive periods, coverage {coverage_bp} bp).",
}

#: The lapse statement. Same shape, same templating rule, and it is never model-labelled: a
#: retraction says exactly one thing and there is nothing for a model to add to it. Per-entity,
#: because a retraction retracts the entry it supersedes and that entry is one account's.
LAPSE_TEMPLATE = ("{metric} is no longer {direction} for this account; the reading over "
                  "{weeks} weeks now says otherwise.")

_DAYS_PER_WEEK = 7


# =================================================================================================
# READING L2.4 — typed, and it recomputes nothing
# =================================================================================================

@dataclass(frozen=True, slots=True)
class TrendReading:
    """One published `derived.trend.<metric>` fact, read as it was written.

    Every number here came out of `trend.trend_fact_value` and is carried, not derived. The
    `fact_version_id` is the receipt: a reader who doubts the pattern can select that one row.
    """

    fact_version_id: str
    subject_node_id: str
    metric: str
    direction: str
    relative_slope_bp: int
    streak_periods: int
    point_count: int
    coverage_ratio_bp: int
    trend_confidence_bp: int
    first_period: datetime
    last_period: datetime
    periods: int

    @property
    def window_days(self) -> int:
        """Whole days between the first and last observed period. Integer seconds, no float."""
        return max(0, int((self.last_period - self.first_period).total_seconds()) // 86_400)

    def as_evidence(self) -> dict[str, Any]:
        """This entity's own reading, as it goes into the published value."""
        return {"subject_node_id": self.subject_node_id,
                "fact_version_id": self.fact_version_id,
                "relative_slope_bp": self.relative_slope_bp,
                "streak_periods": self.streak_periods,
                "point_count": self.point_count,
                "coverage_ratio_bp": self.coverage_ratio_bp,
                "trend_confidence_bp": self.trend_confidence_bp,
                "periods": self.periods,
                "observed_from": self.first_period.isoformat(),
                "observed_through": self.last_period.isoformat()}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, str):
        import json
        return json.loads(value)
    return value or {}


def _instant(value: Any) -> datetime | None:
    """An ISO string from a published fact back into an aware instant, or None if unreadable.

    Unreadable rather than raising: a malformed body is one fact's problem, and dropping the
    whole batch because one row is old-shaped is the failure mode the isolation rule forbids.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _int(value: Any) -> int | None:
    """An integer, or None. A float in a published body is a defect upstream, not a value to round."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def eligible_trend_fields() -> tuple[str, ...]:
    """The exact `graph_facts.field` values this module reads. Sorted, so the read is stable."""
    return tuple(sorted(f"{TREND_FACT_PREFIX}{metric}" for metric in BEHAVIOR_ELIGIBLE_METRICS))


_TREND_FACTS_SQL = text(
    "select fact_version_id, subject_node_id, field, value from graph_facts "
    "where org_id = :o and status = 'active' and valid_to is null "
    "  and field = any(cast(:fields as text[])) "
    "order by field, subject_node_id, fact_version_id")


def read_trend_readings(conn, *, org_id: str) -> tuple[TrendReading, ...]:
    """Every currently-true behaviour-eligible trend fact for this tenant.

    Reads only what L2.4 published and only the fields this module is allowed to read — the
    eligibility gate is applied in the SQL as well as in `qualify`, so an ineligible metric is
    never even carried into memory. A row whose body cannot be read as a trend is skipped; it is
    not this module's job to repair another writer's output.
    """
    rows = conn.execute(_TREND_FACTS_SQL,
                        {"o": org_id, "fields": list(eligible_trend_fields())}).mappings().all()
    out: list[TrendReading] = []
    for row in rows:
        body = _as_mapping(row["value"])
        series = _as_mapping(body.get("series"))
        first, last = _instant(series.get("first_period")), _instant(series.get("last_period"))
        numbers = {name: _int(body.get(name)) for name in
                   ("relative_slope_bp", "streak_periods", "point_count", "coverage_ratio_bp",
                    "trend_confidence_bp")}
        periods = _int(series.get("periods"))
        metric = body.get("metric")
        direction = body.get("direction")
        if (first is None or last is None or periods is None or not isinstance(metric, str)
                or not isinstance(direction, str) or any(v is None for v in numbers.values())):
            continue                      # an unreadable body is skipped, never guessed at
        out.append(TrendReading(
            fact_version_id=str(row["fact_version_id"]),
            subject_node_id=str(row["subject_node_id"]), metric=metric, direction=direction,
            first_period=first, last_period=last, periods=periods, **numbers))  # type: ignore[arg-type]
    return tuple(out)


# =================================================================================================
# CLG-10 — the gate. Stated as data, applied in one function, and every refusal is named.
# =================================================================================================

@dataclass(frozen=True, slots=True)
class GateRefusal:
    """One reading (or one cohort) that did not qualify, and why. Counted, never silent."""

    reason: str
    metric: str
    direction: str
    subject_node_id: str | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class BehaviorPattern:
    """A cohort of readings that cleared CLG-10 — the measurement a statement may be written about."""

    metric: str
    direction: str
    readings: tuple[TrendReading, ...]
    observations: int
    distinct_periods: int
    distinct_entities: int
    confidence_bp: int
    noise_bp: int
    window_days: int
    slope_bp: int
    streak_periods: int
    coverage_bp: int
    observed_from: datetime
    observed_through: datetime

    @property
    def weeks(self) -> int:
        return self.window_days // _DAYS_PER_WEEK

    def template_values(self) -> dict[str, Any]:
        """The ONLY numbers a statement may carry. Every one of them is a measurement."""
        return {"metric": self.metric, "direction": self.direction,
                "entities": self.distinct_entities, "weeks": self.weeks,
                "periods": self.distinct_periods, "slope_bp": self.slope_bp,
                "streak": self.streak_periods, "coverage_bp": self.coverage_bp}


def _lower_median(values: Sequence[int]) -> int:
    """The LOWER middle element of a sorted sequence.

    Not `statistics.median`: on an even-length sequence that averages the two middles, which puts
    a float inside a measure. The same choice `context/analytic/sampler.py` makes, for the same
    reason — a summary that is always an element of the series it summarises is one a reader can
    go and check. Robust where a mean is not: one weak member of a nine-member cohort moves this
    by one rank, so adding a tenth reading cannot collapse a pattern the other nine support.
    """
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def _reading_refusal(reading: TrendReading) -> str:
    """CLG-10 steps 2-4, per reading. Returns a reason code, or "" when the reading qualifies."""
    if reading.metric not in BEHAVIOR_ELIGIBLE_METRICS:
        return "metric_not_behavior_eligible"
    try:
        direction = TrendDirection(reading.direction)
    except ValueError:
        return "unknown_direction"
    if direction not in DIRECTIONAL:
        # FLAT and the two refusals. A refusal is L2.4 saying it cannot see enough; reading it as
        # a habit is exactly the coverage-gap-as-decline fault, one layer up.
        return "direction_is_not_a_claim"
    if reading.window_days < BEHAVIOR_MIN_WINDOW_DAYS:
        return "window_below_floor"
    if reading.coverage_ratio_bp < COVERAGE_FLOOR_BP:
        return "coverage_below_floor"
    return ""


def qualify(readings: Sequence[TrendReading], *, policy: LearningPolicy
            ) -> tuple[tuple[BehaviorPattern, ...], tuple[GateRefusal, ...]]:
    """CLG-10. Group qualifying readings into (metric, direction) cohorts and apply the floors.

    The per-reading steps run first so a refusal names the reading it refused; the cohort steps
    then apply the tenant's OWN Layer 6 floors. `min_distinct_entities` is applied here even
    though `validate_learning` only enforces it for the Organization target: a behaviour pattern
    is a claim about how the company acts, and one account acting alone is that account's story.
    """
    refusals: list[GateRefusal] = []
    cohorts: dict[tuple[str, str], list[TrendReading]] = {}
    for reading in readings:
        reason = _reading_refusal(reading)
        if reason:
            refusals.append(GateRefusal(reason, reading.metric, reading.direction,
                                        reading.subject_node_id))
            continue
        cohorts.setdefault((reading.metric, reading.direction), []).append(reading)

    patterns: list[BehaviorPattern] = []
    for (metric, direction), members in sorted(cohorts.items()):
        members.sort(key=lambda r: r.subject_node_id)
        entities = {r.subject_node_id for r in members}
        observations = sum(r.point_count for r in members)
        # Every member has been watched for at least this many periods. The conservative reading
        # of "distinct days": a union of ISO-week boundaries we did not store per-reading would be
        # a number this module inferred rather than one L2.4 published.
        distinct_periods = min(r.periods for r in members)
        confidence_bp = _lower_median([r.trend_confidence_bp for r in members])
        coverage_bp = _lower_median([r.coverage_ratio_bp for r in members])
        # The holes in the series ARE the noise: a cohort 40% unobserved is 4000 bp of noise,
        # which is exactly the tenant's default ceiling. One number, two floors, no new threshold.
        noise_bp = 10_000 - coverage_bp
        detail = (f"observations={observations} periods={distinct_periods} "
                  f"entities={len(entities)} confidence_bp={confidence_bp} noise_bp={noise_bp}")
        if observations < policy.min_observations:
            refusals.append(GateRefusal("insufficient_observations", metric, direction,
                                        detail=detail))
            continue
        if distinct_periods < policy.min_distinct_days:
            refusals.append(GateRefusal("insufficient_distinct_periods", metric, direction,
                                        detail=detail))
            continue
        if len(entities) < policy.min_distinct_entities:
            refusals.append(GateRefusal("insufficient_distinct_entities", metric, direction,
                                        detail=detail))
            continue
        if confidence_bp < policy.min_confidence_bp:
            refusals.append(GateRefusal("below_confidence_floor", metric, direction, detail=detail))
            continue
        if noise_bp > policy.max_noise_bp:
            refusals.append(GateRefusal("too_noisy", metric, direction, detail=detail))
            continue
        patterns.append(BehaviorPattern(
            metric=metric, direction=direction, readings=tuple(members),
            observations=observations, distinct_periods=distinct_periods,
            distinct_entities=len(entities), confidence_bp=confidence_bp, noise_bp=noise_bp,
            window_days=max(r.window_days for r in members),
            slope_bp=_lower_median([r.relative_slope_bp for r in members]),
            streak_periods=_lower_median([r.streak_periods for r in members]),
            coverage_bp=coverage_bp,
            observed_from=min(r.first_period for r in members),
            observed_through=max(r.last_period for r in members)))
    return tuple(patterns), tuple(refusals)


# =================================================================================================
# THE MODEL SITE (T1) — it labels, and the label is a TEMPLATE
# =================================================================================================

@dataclass(frozen=True, slots=True)
class LabelRequest:
    """What the model is shown: the measurement, the vocabulary, and the default it must beat."""

    metric: str
    direction: str
    values: Mapping[str, Any]
    default_template: str


#: A labeler takes the request and returns a candidate TEMPLATE, or None to decline. It never
#: returns a finished sentence, because a finished sentence contains numbers the model wrote.
Labeler = Callable[[LabelRequest], "str | None"]


def build_label_prompt(request: LabelRequest) -> str:
    """The N-4 prompt. Numbers are shown as NAMES, never as values — that is the whole design.

    A model that is never shown "41" cannot write "about forty"; the placeholders it returns are
    filled by `render_statement` from integers this process validated. Deterministic text (no
    clock, no ids) so the same measurement produces the same prompt and a cache is meaningful.
    """
    fields = ", ".join(sorted(TEMPLATE_FIELDS))
    return (
        "You are labelling a measurement that has already been computed. Do not compute, rank, "
        "score or judge anything.\n"
        f"metric: {request.metric}\n"
        f"direction: {request.direction}\n"
        f"available placeholders (use only these, in curly braces): {fields}\n"
        "Write ONE descriptive sentence as a TEMPLATE. Rules:\n"
        "  - no digits anywhere; every number must be a placeholder\n"
        "  - describe what happens, never whether it is good, bad, risky or urgent\n"
        "  - no recommendation, no cause, no conclusion\n"
        f"  - at most {MAX_TEMPLATE_LENGTH} characters\n"
        f"For reference, the deterministic default is: {request.default_template}\n"
        'Reply with JSON only: {"template": "..."}')


def check_template(candidate: Any) -> str:
    """Validate a candidate template. Returns a refusal reason, or "" when it is acceptable.

    Five refusals, and each one is a rule from doc 02: a template must be text, must be short,
    must carry no digit (numbers are templated, never generated), must name only placeholders we
    supplied, and must not editorialise.
    """
    if not isinstance(candidate, str) or not candidate.strip():
        return "empty_template"
    text_value = candidate.strip()
    if len(text_value) > MAX_TEMPLATE_LENGTH:
        return "template_too_long"
    if any(ch.isdigit() for ch in text_value):
        return "digit_in_template"
    names = _placeholder_names(text_value)
    if names is None:
        return "malformed_placeholder"
    if not names <= TEMPLATE_FIELDS:
        return "unknown_placeholder"
    words = {word.strip(".,;:!?()[]'\"").lower() for word in text_value.split()}
    if words & JUDGMENT_LEXICON:
        return "judgment_word"
    return ""


def _placeholder_names(template: str) -> frozenset[str] | None:
    """The `{name}` fields in a template, or None if the braces do not parse.

    `string.Formatter` rather than a regex: it is the same parser `str.format` will use, so a
    template that passes here cannot fail at render time with a different opinion about braces.
    """
    from string import Formatter

    try:
        parsed = list(Formatter().parse(template))
    except ValueError:
        return None
    names: set[str] = set()
    for _literal, field, _spec, _conv in parsed:
        if field is None:
            continue
        if not field or not field.isidentifier():
            return None                       # positional, indexed or attribute access: refused
        names.add(field)
    return frozenset(names)


def render_statement(template: str, values: Mapping[str, Any]) -> str:
    """Fill a validated template from validated integers. The ONLY place a number enters a sentence."""
    return template.format(**values)


def label_pattern(pattern: BehaviorPattern, *, labeler: Labeler | None = None
                  ) -> tuple[str, str, str]:
    """Return (statement, labeler_id, refusal_reason) for one pattern.

    With no labeler, or on any refusal, the deterministic template is used and the reason is
    reported rather than swallowed — a model that keeps producing judgment words is a fact the
    operator should see in the run counts, not a silence.
    """
    default = DEFAULT_TEMPLATES[pattern.direction]
    values = pattern.template_values()
    if labeler is None:
        return render_statement(default, values), "deterministic", ""
    request = LabelRequest(metric=pattern.metric, direction=pattern.direction, values=values,
                           default_template=default)
    try:
        candidate = labeler(request)
    except Exception as exc:                  # noqa: BLE001 — a model outage is a refusal, not a crash
        return render_statement(default, values), "deterministic", f"labeler_error:{type(exc).__name__}"
    reason = check_template(candidate)
    if reason:
        return render_statement(default, values), "deterministic", reason
    assert isinstance(candidate, str)
    try:
        rendered = render_statement(candidate.strip(), values)
    except (KeyError, IndexError, ValueError):
        return render_statement(default, values), "deterministic", "render_failed"
    return rendered, "model", ""


def llm_labeler(client: Any, *, max_tokens: int = 300) -> Labeler:
    """Adapt an `LLMClient` into a `Labeler`. The adapter reads ONE key and trusts nothing else.

    Kept here rather than inside `label_pattern` so the unit is fully exercisable — and fully
    runnable in production — with no model at all: N-4 is a T1 site whose deterministic default
    is a complete answer, not a stub.
    """
    def _label(request: LabelRequest) -> str | None:
        result = client.call(build_label_prompt(request), max_tokens=max_tokens)
        if not getattr(result, "ok", False):
            return None
        value = (getattr(result, "parsed", None) or {}).get("template")
        return value if isinstance(value, str) else None
    return _label


# =================================================================================================
# THE PROPOSALS — everything above becomes a LearningObject, and nothing else
# =================================================================================================

def behavior_subject(metric: str, subject_node_id: str) -> str:
    """`behavior:<metric>:<node>` — see the module docstring for why the node is a segment."""
    return f"{BEHAVIOR_SUBJECT_PREFIX}:{metric}:{subject_node_id}"


def _evidence(pattern: BehaviorPattern, reading: TrendReading) -> LearningEvidence:
    """The cohort's integers, with this entity's fact as the receipt.

    `positive` is the observation count and `negative` is zero because a measurement is not a
    graded outcome — confidence is carried explicitly from L2.4's own trend confidence, so
    nothing here can inflate it. No field is derived from the clock: evidence is hashed into the
    object's identity, and a clock in the identity is weekly version noise by construction.
    """
    return LearningEvidence(
        observations=pattern.observations,
        distinct_days=pattern.distinct_periods, positive=pattern.observations, negative=0,
        confidence_bp=pattern.confidence_bp, noise_bp=pattern.noise_bp,
        distinct_entities=pattern.distinct_entities,
        independent_refs=len(pattern.readings),
        source_refs=(reading.fact_version_id,) + tuple(
            r.fact_version_id for r in pattern.readings if r is not reading))


def _value(pattern: BehaviorPattern, reading: TrendReading, statement: str, labeler_id: str,
           *, active: bool) -> dict[str, Any]:
    """The published brain value. Descriptive only, clock-free, and it names its own cohort."""
    return {
        "kind": "behavior_pattern",
        "active": active,
        "pattern_statement": statement,
        "statement_source": labeler_id,
        "metric": pattern.metric,
        "direction": pattern.direction,
        "subject_node_id": reading.subject_node_id,
        "cohort": {"entities": pattern.distinct_entities, "observations": pattern.observations,
                   "periods": pattern.distinct_periods, "window_days": pattern.window_days,
                   "slope_bp": pattern.slope_bp, "streak_periods": pattern.streak_periods,
                   "coverage_bp": pattern.coverage_bp,
                   "members": [r.subject_node_id for r in pattern.readings]},
        "reading": reading.as_evidence(),
        "confidence_bp": pattern.confidence_bp,
        "observed_from": pattern.observed_from.isoformat(),
        "observed_through": pattern.observed_through.isoformat(),
    }


def _proposal(pattern: BehaviorPattern, reading: TrendReading, *, org_id: str,
              policy: LearningPolicy, statement: str, labeler_id: str,
              active: bool) -> LearningObject:
    return LearningObject(
        org_id=org_id, unit=BEHAVIOR_UNIT, target=LearningTarget.BEHAVIOR,
        subject=behavior_subject(pattern.metric, reading.subject_node_id),
        proposed_value=_value(pattern, reading, statement, labeler_id, active=active),
        evidence=_evidence(pattern, reading),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        # Not identity-bearing (see `LearningObject.identity`), and taken from the SERIES rather
        # than from `now` so the ledger says when the behaviour was observed, not when we looked.
        first_seen_at=pattern.observed_from, last_seen_at=pattern.observed_through,
        policy_key=policy.policy_key)


_PUBLISHED_SUBJECTS_SQL = text(
    "select subject, value from learned_brain_entries "
    "where org_id = :o and brain = 'behavior' and active and subject like :prefix "
    "order by subject")


def published_behavior_subjects(conn, *, org_id: str) -> dict[str, Mapping[str, Any]]:
    """The tenant's currently-active behaviour entries from THIS module, keyed by subject."""
    rows = conn.execute(_PUBLISHED_SUBJECTS_SQL,
                        {"o": org_id, "prefix": f"{BEHAVIOR_SUBJECT_PREFIX}:%"}).mappings().all()
    return {str(r["subject"]): _as_mapping(r["value"]) for r in rows}


def _lapse_pattern(reading: TrendReading, published: Mapping[str, Any],
                   policy: LearningPolicy) -> BehaviorPattern | None:
    """The measurement that RETRACTS a published pattern, or None when we cannot measure one.

    The retraction is itself evidence: the same node, the same metric, still being sampled, now
    reading something other than the claim on file. It goes through the identical floors — a
    lapse that could not clear them would be a retraction on no better ground than the claim.
    """
    claimed = str(published.get("direction") or "")
    if not claimed or reading.direction == claimed:
        return None                            # still true; nothing to retract
    if reading.window_days < BEHAVIOR_MIN_WINDOW_DAYS:
        return None                            # too little time to say the habit stopped
    observations = reading.point_count
    if (observations < policy.min_observations or reading.periods < policy.min_distinct_days
            or reading.trend_confidence_bp < policy.min_confidence_bp
            or 10_000 - reading.coverage_ratio_bp > policy.max_noise_bp):
        return None
    # ONE entity, and the floors are the same ones. A retraction retracts one published entry, so
    # the entity floor that governs a cross-account CLAIM does not govern its withdrawal — but
    # every floor about the strength of the reading itself still does, or the retraction would
    # rest on worse evidence than the claim it deletes.
    return BehaviorPattern(
        metric=reading.metric, direction=claimed, readings=(reading,), observations=observations,
        distinct_periods=reading.periods, distinct_entities=1,
        confidence_bp=reading.trend_confidence_bp, noise_bp=10_000 - reading.coverage_ratio_bp,
        window_days=reading.window_days, slope_bp=reading.relative_slope_bp,
        streak_periods=reading.streak_periods, coverage_bp=reading.coverage_ratio_bp,
        observed_from=reading.first_period, observed_through=reading.last_period)


def distill(conn, *, org_id: str, policy: LearningPolicy,
            labeler: Labeler | None = None,
            limit: int = MAX_BEHAVIOR_ENTRIES_PER_RUN
            ) -> tuple[tuple[LearningObject, ...], tuple[GateRefusal, ...]]:
    """N-4, end to end: read L2.4's facts, gate them, label them, propose. Writes NOTHING.

    THERE IS NO `now`, and that absence is the point. Every number that reaches a proposal is a
    measurement L2.4 published; nothing is compared against the wall clock, so the same facts
    produce the same content-addressed proposal on any day — which is what lets `persist` answer
    "unchanged" and `publish_brain` answer "no_material_change" instead of minting a version a
    week. Staleness is answered by `observed_through`, a series boundary.

    Returns the proposals and every refusal, because a batch that proposed nothing because
    everything was refused and a batch that had nothing to read are different states, and the
    counts are the only place an operator can tell them apart.
    """
    readings = read_trend_readings(conn, org_id=org_id)
    patterns, refusals = qualify(readings, policy=policy)

    proposals: list[LearningObject] = []
    labeled: list[GateRefusal] = list(refusals)
    claimed_subjects: set[str] = set()
    for pattern in patterns:
        statement, labeler_id, refusal = label_pattern(pattern, labeler=labeler)
        if refusal:
            labeled.append(GateRefusal(f"label_refused:{refusal}", pattern.metric,
                                       pattern.direction))
        for reading in pattern.readings:
            if len(proposals) >= limit:
                labeled.append(GateRefusal("entry_cap_reached", pattern.metric, pattern.direction,
                                           reading.subject_node_id))
                break
            claimed_subjects.add(behavior_subject(pattern.metric, reading.subject_node_id))
            proposals.append(_proposal(pattern, reading, org_id=org_id, policy=policy,
                                       statement=statement, labeler_id=labeler_id, active=True))

    # DECAY. Anything published by this module that this batch did not re-claim, but whose metric
    # is still being measured on that node, is retracted through the same floors.
    published = published_behavior_subjects(conn, org_id=org_id)
    by_subject = {behavior_subject(r.metric, r.subject_node_id): r for r in readings}
    for subject, value in published.items():
        if subject in claimed_subjects or not value.get("active", True):
            continue
        reading = by_subject.get(subject)
        if reading is None:
            labeled.append(GateRefusal("series_went_dark", str(value.get("metric") or "?"),
                                       str(value.get("direction") or "?"), detail=subject))
            continue
        pattern = _lapse_pattern(reading, value, policy)
        if pattern is None:
            labeled.append(GateRefusal("lapse_not_measurable", reading.metric, reading.direction,
                                       reading.subject_node_id))
            continue
        statement = render_statement(LAPSE_TEMPLATE, pattern.template_values())
        proposals.append(_proposal(pattern, reading, org_id=org_id, policy=policy,
                                   statement=statement, labeler_id="deterministic", active=False))
    return tuple(proposals), tuple(labeled)


__all__ = ["BEHAVIOR_ELIGIBLE_METRICS", "BEHAVIOR_MIN_WINDOW_DAYS", "BEHAVIOR_SUBJECT_PREFIX",
           "BEHAVIOR_UNIT", "DEFAULT_TEMPLATES", "JUDGMENT_LEXICON", "LAPSE_TEMPLATE",
           "MAX_BEHAVIOR_ENTRIES_PER_RUN", "MAX_TEMPLATE_LENGTH", "TEMPLATE_FIELDS",
           "BehaviorPattern", "GateRefusal", "LabelRequest", "Labeler", "TrendReading",
           "behavior_subject", "build_label_prompt", "check_template", "distill",
           "eligible_trend_fields", "label_pattern", "llm_labeler",
           "published_behavior_subjects", "qualify", "read_trend_readings", "render_statement"]
