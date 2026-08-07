"""Category 3 · Optimization — the Resource Unit.

Answers one question: *do we actually have what this would take?*

Everything else in Layer 4 reasons about whether something is worth doing. This unit reasons about
whether it can be done at all with the capacity the organisation has declared: is there a named
owner, is that owner actually available, is that owner already carrying more commitments than they
can serve, and is there any budget or clock left before the window closes.

Three separate claims, three plugins, because they fail for different reasons and are evidenced by
different facts. An owner on leave is not the same problem as an owner with forty open items, and
neither is the same problem as a deadline six hours away — folding them into one "feasibility
score" would produce a number nobody could act on.

**Why this unit never eliminates a play.** Running short of capacity is a caution, not a policy
violation. A saturated owner can still be the right person to send one email, and a human reading
the card is a better judge of that than a threshold. Policy elimination belongs to
`core.constraint`; this unit only ever raises a `precondition` WARN so the shortfall travels with
the candidate and is visible at the point of decision.

**Facts this unit reads, all optional.** `deal.owner`, `owner.availability_bp`, `owner.status`,
`owner.load_bp`, `owner.open_items`, `team.load_bp`, `team.open_items`, `budget.remaining_minor`,
`budget.total_minor`, and a configurable deadline field (default `commitment.due_at`). Layer 2 may
supply none of them. Where a fact is absent the responsible plugin contributes nothing, and the
unit reports capacity as *unknown* rather than as zero — an unmeasured owner is not an unavailable
one, and a fabricated zero would quietly make every play look infeasible.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import CandidateCheck, CheckOutcome, Finding

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import (basis_points, clamp_bp, divide_half_up, evidence_ids, fact_value, integer,
                     parse_time)

# Statuses a source system may report for the person who would carry the work out. Read as a
# closed vocabulary on purpose: an unrecognised status means "we do not know", not "available",
# because guessing availability upward is the failure mode that puts work on someone who is on
# parental leave.
_AVAILABLE_STATUSES = frozenset({"available", "active", "working", "online", "in_office"})
_REDUCED_STATUSES = frozenset({"busy", "limited", "partial", "overloaded", "stretched"})
_UNAVAILABLE_STATUSES = frozenset({"out_of_office", "ooo", "on_leave", "unavailable", "inactive",
                                   "departed", "offboarded"})


def _config_bp(view: UnitView, key: str, default: int) -> int:
    """Per-capability tuning must be integer basis points; anything else is a deployment fault."""
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_count(view: UnitView, key: str, default: int) -> int:
    """A denominator (items of capacity, hours of window) — must be a positive integer.

    Zero would make the ratio undefined, and a unit that divides by a misconfigured zero would
    fail a whole run over a manifest typo, so it is rejected where it is authored instead.
    """
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _ratio_bp(part: int, whole: int) -> int:
    """What fraction of `whole` is left, in basis points, saturating at both ends."""
    return clamp_bp(divide_half_up(min(max(part, 0), whole) * 10_000, whole))


def _optional_int(request: Any, field: str) -> int | None:
    """Read an integer fact, treating a malformed one as unsaid rather than as zero."""
    raw = fact_value(request, field)
    if raw is None:
        return None
    try:
        return integer(raw, field)
    except ValueError:
        return None


class OwnerAvailabilityPlugin:
    """Is there a named human, and is that human actually available?

    Capacity in a services business is a person before it is a budget line. Two distinct claims
    live here because they are answered by different facts: *nobody owns this* (an assignment gap
    the organisation can close in seconds) and *the owner is away* (a gap only time closes).

    An empty owner field that Layer 2 did in fact capture is evidence of zero capacity — someone
    looked and there was no one. An owner field that was never captured is silence, and silence
    stays silence.
    """

    plugin_id = "owner_availability"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        request = view.request
        owner_captured = "deal.owner" in request.context.facts
        owner = str(fact_value(request, "deal.owner") or "").strip()
        if owner_captured and not owner:
            return (Observation(
                plugin_id=self.plugin_id,
                kind="resource.owner_unassigned",
                metrics={"capacity_bp": 0},
                evidence_ids=evidence_ids(request, "deal.owner"),
                reason_codes=("no_owner_to_execute",),
            ),)
        availability = self._declared_availability(view)
        if availability is None:
            return ()                      # nothing was declared; do not invent an availability
        return (Observation(
            plugin_id=self.plugin_id,
            kind="resource.owner_availability",
            metrics={"capacity_bp": availability},
            evidence_ids=evidence_ids(request, "deal.owner", "owner.availability_bp",
                                      "owner.status"),
            reason_codes=("owner_availability_declared",),
        ),)

    def _declared_availability(self, view: UnitView) -> int | None:
        """An explicit basis-point figure outranks a status word, because it is more specific.

        A status is a coarse label a CRM applied; a number is what someone measured. When only
        the label exists it is mapped conservatively — "busy" is a real reduction, not a rounding
        error, and the reduction is tunable per capability because a busy account manager and a
        busy surgeon are not equally busy.
        """
        raw = fact_value(view.request, "owner.availability_bp")
        if raw is not None:
            try:
                return basis_points(raw, "owner.availability_bp")
            except ValueError:
                return None                # malformed capacity is unknown capacity, never full
        status = str(fact_value(view.request, "owner.status") or "").strip().lower()
        if status in _AVAILABLE_STATUSES:
            return 10_000
        if status in _REDUCED_STATUSES:
            return _config_bp(view, "owner_reduced_availability_bp", 4_000)
        if status in _UNAVAILABLE_STATUSES:
            return 0
        return None


class WorkloadSaturationPlugin:
    """How much of the declared capacity is already spoken for.

    Availability and load are deliberately kept apart. An owner can be fully available and still
    be the wrong person to hand a fourteenth open commitment to, and an owner on leave with an
    empty queue is a different problem entirely. Reporting them as one number would make both
    unexplainable.

    Owner load and team load are separate observations: when a team is at the wall it does not
    help that this particular person is not.
    """

    plugin_id = "workload_saturation"

    _SOURCES = (
        ("owner", "owner.load_bp", "owner.open_items", "owner_workload_declared"),
        ("team", "team.load_bp", "team.open_items", "team_workload_declared"),
    )

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        request = view.request
        capacity_items = _config_count(view, "workload_capacity_items", 10)
        observations: list[Observation] = []
        for scope, load_field, items_field, reason in self._SOURCES:
            metrics: dict[str, int] = {}
            declared = fact_value(request, load_field)
            if declared is not None:
                try:
                    metrics["load_bp"] = basis_points(declared, load_field)
                except ValueError:
                    continue               # a malformed load figure is not a load claim
            else:
                open_items = _optional_int(request, items_field)
                if open_items is None:
                    continue               # nobody counted; saying "0 load" would be a fiction
                # Load is commitments against the capability's declared serving capacity. Past
                # 100% the ratio saturates: twice over capacity and five times over capacity are
                # both simply "cannot take more", and pretending to distinguish them is noise.
                metrics["load_bp"] = _ratio_bp(open_items, capacity_items)
                metrics["open_items"] = max(open_items, 0)
                metrics["capacity_items"] = capacity_items
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind=f"resource.{scope}_workload",
                metrics=metrics,
                evidence_ids=evidence_ids(request, load_field, items_field),
                reason_codes=(reason,),
            ))
        return tuple(observations)


class HeadroomPlugin:
    """What is left of the two resources that run out on their own: money and time.

    Both are reported as the fraction of the declared allowance still unspent, so a budget and a
    deadline can be compared on one scale without either being converted into the other. The unit
    then lets the scarcer one bind, because having budget does not buy back a window that closed.

    The deadline is measured against the request's frozen evaluation time — never a clock — which
    is what lets this reading be reproduced identically in a replay months later.
    """

    plugin_id = "budget_time_headroom"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        return tuple(item for item in (self._budget(view), self._deadline(view))
                     if item is not None)

    def _budget(self, view: UnitView) -> Observation | None:
        request = view.request
        total = _optional_int(request, "budget.total_minor")
        remaining = _optional_int(request, "budget.remaining_minor")
        if total is None or remaining is None or total <= 0:
            return None                    # no allowance declared, so no headroom claim is possible
        return Observation(
            plugin_id=self.plugin_id,
            kind="resource.budget_headroom",
            metrics={"headroom_bp": _ratio_bp(remaining, total),
                     "remaining_minor": max(remaining, 0)},
            evidence_ids=evidence_ids(request, "budget.remaining_minor", "budget.total_minor"),
            reason_codes=("budget_headroom_declared",),
        )

    def _deadline(self, view: UnitView) -> Observation | None:
        field = view.config.get("deadline_field", "commitment.due_at")
        if not isinstance(field, str) or not field.strip():
            raise ValueError("deadline_field must be a non-empty field name")
        field = field.strip()
        raw = fact_value(view.request, field)
        if raw is None:
            return None
        try:
            due_at = parse_time(raw, field)
        except ValueError:
            return None                    # an unparseable deadline is not a deadline
        window = _config_count(view, "deadline_window_hours", 168)
        hours_remaining = int(
            (due_at - view.request.evaluation_time).total_seconds()) // 3600
        # A window already past has no headroom at all, and the hours are reported so a reader can
        # see how far past — a deadline missed by an hour reads very differently from one missed
        # by a week, even though both leave nothing to spend.
        return Observation(
            plugin_id=self.plugin_id,
            kind="resource.deadline_headroom",
            metrics={"headroom_bp": 0 if hours_remaining <= 0 else _ratio_bp(
                hours_remaining, window),
                "hours_remaining": hours_remaining},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=(("deadline_passed",) if hours_remaining <= 0
                          else ("deadline_headroom_declared",)),
        )


class ResourceUnit(ReasoningUnit):
    """Optimization · whether the organisation can actually resource this.

    Publishes three orthogonal readings rather than one blended feasibility number, so a downstream
    reader can tell *which* resource is short. Each is omitted entirely when nothing was observed:
    an absent metric means unknown, and a reader that defaults it chooses its own default rather
    than inheriting a fabricated one.
    """

    unit_id = "core.resource"
    version = "1.0.0"
    category = UnitCategory.OPTIMIZATION
    publishes = ("capacity_bp", "load_bp", "headroom_bp", "resource_signal_count")
    plugins = (OwnerAvailabilityPlugin(), WorkloadSaturationPlugin(), HeadroomPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """The binding constraint wins on every axis — capacity is not an average.

        Deliberately not a mean: an owner who is fully available and a budget that is exhausted do
        not average out to "half feasible". The scarcest capacity, the heaviest load and the
        tightest headroom are what the work will actually run into, so those are what get
        published.
        """
        del view
        capacities = [item.metrics["capacity_bp"] for item in observations
                      if "capacity_bp" in item.metrics]
        loads = [item.metrics["load_bp"] for item in observations if "load_bp" in item.metrics]
        headrooms = [item.metrics["headroom_bp"] for item in observations
                     if "headroom_bp" in item.metrics]
        metrics: dict[str, int] = {"resource_signal_count": len(observations)}
        if capacities:
            metrics["capacity_bp"] = min(capacities)
        if loads:
            metrics["load_bp"] = max(loads)
        if headrooms:
            metrics["headroom_bp"] = min(headrooms)
        return metrics

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means *a resource shortfall is present* — the thing this unit looks for.

        Three readings are possible and they are not the same reading:

        * **unknown** — nothing about capacity or headroom was observed. `matched` is None, because
          "we did not measure" is not "we are fine", and every play carries a precondition WARN so
          the blind spot reaches the human instead of dying inside the unit.
        * **strained** — a declared capacity, load or headroom crossed its configured threshold.
          `matched` is True and each strain is warned per play, with the reason it fired.
        * **comfortable** — signals exist and all sit inside their thresholds. `matched` is False
          and a PASS is recorded per play, so the audit trail shows capacity was checked rather
          than skipped.

        No outcome is ever ELIMINATE. Capacity is a caution this unit reports; whether a shortfall
        should stop a play is a decision, and decisions are Part 3's.
        """
        capacity_floor = _config_bp(view, "capacity_floor_bp", 3_000)
        load_ceiling = _config_bp(view, "load_ceiling_bp", 8_000)
        headroom_floor = _config_bp(view, "headroom_floor_bp", 2_000)

        known = "capacity_bp" in metrics or "headroom_bp" in metrics
        # Fixed precedence, not set iteration: the order these codes appear in is the order a
        # reader sees them on every replay of the same situation.
        strains: list[str] = []
        if metrics.get("capacity_bp", 10_000) <= capacity_floor:
            strains.append("owner_capacity_below_floor")
        if metrics.get("headroom_bp", 10_000) <= headroom_floor:
            strains.append("resource_headroom_exhausted")
        if metrics.get("load_bp", 0) >= load_ceiling:
            strains.append("workload_saturated")

        matched: bool | None
        if not known:
            # A load reading without a capacity reading still says something real, so an observed
            # saturation is warned alongside the blind spot rather than swallowed by it.
            outcome = CheckOutcome.WARN
            codes = tuple(strains) + ("resource_capacity_unknown",)
            matched = True if strains else None
        elif strains:
            outcome, codes = CheckOutcome.WARN, tuple(strains)
            matched = True
        else:
            outcome, codes = CheckOutcome.PASS, ("resource_capacity_available",)
            matched = False

        detail = dict(metrics)
        checks = tuple(
            CandidateCheck(play_id=play.play_id, stage="precondition", outcome=outcome,
                           reason_code=code, evaluator_id=self.unit_id,
                           evaluator_version=self.version, detail=detail)
            # Sorted by play id so the check order is a property of the capability's content, not
            # of the order plays happened to be authored in.
            for play in sorted(view.request.capability.plays, key=lambda item: item.play_id)
            for code in codes)

        findings = tuple(Finding(
            finding_id=item.kind,
            kind="resource",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations) if matched else ()

        reason_codes = tuple(sorted(
            set(codes) | {code for item in observations for code in item.reason_codes})) \
            if matched else codes
        return Verdict(matched=matched, metrics=dict(metrics), reason_codes=reason_codes,
                       findings=findings, checks=checks)


__all__ = ["HeadroomPlugin", "OwnerAvailabilityPlugin", "ResourceUnit", "WorkloadSaturationPlugin"]
