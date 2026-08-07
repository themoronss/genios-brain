"""Category 1 · Situation Understanding — the Dependency Unit.

Answers one question: *what is blocked by what?*

Every other unit in Layer 4 reasons about whether something is worth doing. None of them ask
whether it *can be started*. Without that question, GeniOS confidently recommends work that hits a
wall on contact — chase the buyer whose contract is sitting in an unfinished legal review, prepare
the renewal whose owner left the company three weeks ago. The recommendation is not wrong about the
value; it is wrong about the world, and a human who follows it burns trust discovering that.

So this unit reads the situation for *dependencies*: things that must happen before this work can
happen, that have not happened. It reports three families of them, one per plugin, because they are
three different claims resolved three different ways:

  * an **approval or gate** that has been asked for and not answered (chase the approver),
  * a **prerequisite fact** the capability declared it needs and does not have (go find it),
  * an **upstream owner** who is absent or unavailable (nothing moves until a person does).

Two numbers describe the shape of the blockage rather than its weight:

  ``blocked_count``   how many distinct things are in the way.
  ``blocking_depth``  how long the chain is — 1 when this workflow can act on the blocker itself,
                      2 when the blocker is held by a party outside this workflow, so somebody else
                      has to move before we even get to move. Depth is what separates "chase it"
                      from "you are not the one who can chase it", and collapsing it into a single
                      severity score would destroy exactly that distinction.

And one summarises freedom to proceed: ``unblocked_bp``, 10,000 when nothing demonstrably stands in
the way. That number is only as good as what was inspected, which is why ``inspected_count`` is
published alongside it: 10,000 unblocked with 0 inspected means "we saw no blockage because we
looked at nothing", and a consumer that cannot tell those apart will eventually act on silence.

The unit reports the graph of blockage. It never says which blocker to clear first, never ranks a
play, and never eliminates one — chasing legal versus reassigning an owner is a judgement about
cost and authority that belongs to the Decision Maker in Part 3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import Finding

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, evidence_ids, fact_value

# Reason codes carry the blocking field itself so a trace names the wall, not just its species.
# Colons are legal in the contract's identifier grammar, so this survives Finding validation.
BLOCKER_PREFIX = "blocker:"

# A blocker this workflow can act on directly (chase the approver, fetch the missing fact).
DIRECT_DEPTH = 1
# A blocker held by a party outside this workflow: two links in the chain, and the first is not
# ours to pull. Reported separately because "waiting" and "able to act" are different situations.
UPSTREAM_DEPTH = 2

# Gates GeniOS has seen in the wild across CRM, contracting, and procurement sources. A capability
# that names different ones overrides this wholesale via `gate_fields` — the defaults exist so a
# capability that never thought about gates still gets the common ones checked.
DEFAULT_GATE_FIELDS: tuple[str, ...] = (
    "approval.status",
    "finance.approval_status",
    "legal.review_status",
    "procurement.status",
    "security.review_status",
)

# Vocabulary is matched, never inferred. A status word outside all three sets produces no
# observation at all: an unrecognised gate value means we do not know the gate's state, and
# guessing "probably fine" is precisely the failure this unit exists to prevent.
GATE_PENDING = frozenset({
    "awaiting", "awaiting_approval", "blocked", "in_review", "not_started", "on_hold",
    "pending", "pending_approval", "requested", "submitted", "under_review", "waiting",
})
GATE_CLEARED = frozenset({
    "approved", "cleared", "complete", "completed", "done", "granted", "not_required",
    "passed", "signed", "waived",
})
# A refusal is not a queue. Waiting will never clear it, so it is reported as a hard blocker at
# full severity: the work does not resume until someone changes the decision itself.
GATE_REJECTED = frozenset({"declined", "denied", "failed", "rejected", "revoked"})

OWNER_UNAVAILABLE = frozenset({
    "away", "inactive", "offboarded", "on_leave", "out_of_office", "terminated", "unavailable",
})
OWNER_AVAILABLE = frozenset({"active", "available", "online", "working"})


def _config_bp(view: UnitView, key: str, default: int) -> int:
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_fields(view: UnitView, key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a configured list of fact field names, sorted so iteration order can never reach output."""
    value = view.config.get(key, default)
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{key} must be a list of fact field names")
    names = {str(item).strip() for item in value}
    return tuple(sorted(name for name in names if name))


def _config_field(view: UnitView, key: str, default: str) -> str:
    value = view.config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a fact field name")
    return value.strip()


def _normalize(value: Any) -> str:
    """Fold a status string to a single comparable token. Non-strings fold to '' and stay silent."""
    if isinstance(value, bool) or not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _gate_state(value: Any) -> str | None:
    token = _normalize(value)
    if token in GATE_CLEARED:
        return "cleared"
    if token in GATE_REJECTED:
        return "rejected"
    if token in GATE_PENDING:
        return "pending"
    return None


def _pending_gate_fields(view: UnitView) -> tuple[str, ...]:
    """Which gates are currently waiting — shared so the owner plugin can see the chain it sits in."""
    return tuple(field for field in _config_fields(view, "gate_fields", DEFAULT_GATE_FIELDS)
                 if _gate_state(fact_value(view.request, field)) == "pending")


def _is_absent(value: Any) -> bool:
    """A fact written as null or blank is not a fact. L2 records placeholders; treat them as absent."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (tuple, list, Mapping)) and not isinstance(value, str):
        return len(value) == 0
    return False


def _blocker_key(observation: Observation) -> str:
    """Recover the blocking field from an observation so its finding keeps a stable identity.

    Finding ids must survive across runs: if one of three blockers clears, the remaining two should
    still be recognisable as the same findings rather than shifting position in a numbered list.
    """
    for code in observation.reason_codes:
        if code.startswith(BLOCKER_PREFIX):
            return code[len(BLOCKER_PREFIX):]
    return observation.plugin_id


class ApprovalGatePlugin:
    """Something was submitted for a decision and the decision has not come back.

    This is the most common blocker in commercial work and the most invisible one, because a
    pending gate looks identical to a healthy deal in every metric that measures activity. The
    plugin reports each waiting gate separately: legal and procurement are chased by different
    people, so folding them into one "blocked" flag would lose the only detail that makes the
    observation actionable downstream.

    A cleared gate is reported too — as a zero-blockage inspection rather than silence — because
    "we checked five gates and all five are clear" and "we checked nothing" must never produce the
    same result.
    """

    plugin_id = "approval_gate"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        pending_severity = _config_bp(view, "gate_pending_severity_bp", 6_000)
        observations: list[Observation] = []
        cleared = 0
        for field in _config_fields(view, "gate_fields", DEFAULT_GATE_FIELDS):
            state = _gate_state(fact_value(view.request, field))
            if state is None:
                continue                      # absent or unrecognised: no claim to make
            if state == "cleared":
                cleared += 1
                continue
            rejected = state == "rejected"
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.gate_rejected" if rejected else "dependency.gate_pending",
                metrics={
                    "blocked": 1,
                    "inspected": 1,
                    "depth": UPSTREAM_DEPTH if rejected else DIRECT_DEPTH,
                    # A refusal cannot be waited out and is not ours to overturn, so it is both
                    # maximal and hard; a pending gate is tunable because how long a capability
                    # tolerates a queue is a business judgement, not a fact.
                    "severity_bp": 10_000 if rejected else pending_severity,
                    "hard": 1 if rejected else 0,
                },
                evidence_ids=evidence_ids(view.request, field),
                reason_codes=(
                    "gate_decision_refused" if rejected else "gate_awaiting_decision",
                    f"{BLOCKER_PREFIX}{field}",
                ),
            ))
        if cleared:
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.gates_cleared",
                metrics={"blocked": 0, "inspected": cleared},
                reason_codes=("gates_cleared",),
            ))
        return tuple(observations)


class PrerequisiteAbsencePlugin:
    """The capability declared it needs a fact to do this work, and the fact is not there.

    A missing prerequisite is a dependency on *retrieval*, not on a person: nobody has refused
    anything, the information simply is not in hand yet. It is reported at direct depth because
    this workflow can go and get it, which is what makes it a materially different blocker from an
    approver who has gone quiet.

    Prerequisites come from Layer 3 — either named explicitly for this unit or, failing that, the
    capability's own declared `required_fields`. If neither exists the plugin says nothing: a
    capability that never stated what it needs has not given us grounds to call anything missing.
    """

    plugin_id = "prerequisite_absent"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        declared = _config_fields(view, "prerequisite_fields",
                                  tuple(view.request.capability.required_fields))
        if not declared:
            return ()
        severity = _config_bp(view, "prerequisite_severity_bp", 5_000)
        facts = view.request.context.facts
        observations: list[Observation] = []
        satisfied = 0
        for field in declared:
            if field in facts and not _is_absent(fact_value(view.request, field)):
                satisfied += 1
                continue
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.prerequisite_absent",
                metrics={"blocked": 1, "inspected": 1, "depth": DIRECT_DEPTH,
                         "severity_bp": severity, "hard": 0},
                reason_codes=("prerequisite_not_available", f"{BLOCKER_PREFIX}{field}"),
            ))
        if satisfied:
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.prerequisites_met",
                metrics={"blocked": 0, "inspected": satisfied},
                reason_codes=("prerequisites_met",),
            ))
        return tuple(observations)


class UpstreamOwnerPlugin:
    """Work that waits on a person who is not there to move it.

    Three separate situations, deliberately not merged. Nobody is assigned, so the work has no
    hands at all. The assigned owner is out of office or gone, so the work has hands that cannot
    move — and if a gate is also pending, that unavailability is *why* the gate is not clearing,
    which is a two-link chain and the single most useful thing this unit ever reports. Or the
    situation names an external party it is waiting on, which is upstream by construction.

    Everything here is reported, never resolved: reassigning an owner is an action, and this unit
    does not propose actions.
    """

    plugin_id = "upstream_owner"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        owner_field = _config_field(view, "owner_field", "deal.owner")
        status_field = _config_field(view, "owner_status_field", "owner.availability")
        upstream_field = _config_field(view, "blocked_by_field", "deal.blocked_by")
        facts = view.request.context.facts
        observations: list[Observation] = []
        inspected_clear = 0

        owner = fact_value(view.request, owner_field)
        owner_known = owner_field in facts and not _is_absent(owner)
        if owner_field in facts and not owner_known:
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.owner_unassigned",
                metrics={"blocked": 1, "inspected": 1, "depth": DIRECT_DEPTH,
                         "severity_bp": _config_bp(view, "unassigned_severity_bp", 4_000),
                         "hard": 0},
                evidence_ids=evidence_ids(view.request, owner_field),
                reason_codes=("owner_unassigned", f"{BLOCKER_PREFIX}{owner_field}"),
            ))
        elif owner_known:
            inspected_clear += 1

        status = _normalize(fact_value(view.request, status_field))
        if status in OWNER_UNAVAILABLE:
            # The chain deepens only when a gate is actually waiting on this person. Otherwise an
            # absent owner is a direct problem we can route around; claiming a two-link chain
            # without a second link would be inventing structure that is not in the facts.
            gated = bool(_pending_gate_fields(view))
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.owner_unavailable",
                metrics={"blocked": 1, "inspected": 1,
                         "depth": UPSTREAM_DEPTH if gated else DIRECT_DEPTH,
                         "severity_bp": _config_bp(view, "unavailable_severity_bp", 7_000),
                         "hard": 1},
                evidence_ids=evidence_ids(view.request, status_field),
                reason_codes=("owner_unavailable", f"{BLOCKER_PREFIX}{status_field}")
                + (("blocked_gate_has_no_decider",) if gated else ()),
            ))
        elif status in OWNER_AVAILABLE:
            inspected_clear += 1

        upstream = fact_value(view.request, upstream_field)
        if upstream_field in facts and not _is_absent(upstream):
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.upstream_party",
                metrics={"blocked": 1, "inspected": 1, "depth": UPSTREAM_DEPTH,
                         "severity_bp": _config_bp(view, "upstream_severity_bp", 6_500),
                         "hard": 1},
                evidence_ids=evidence_ids(view.request, upstream_field),
                reason_codes=("waiting_on_upstream_party", f"{BLOCKER_PREFIX}{upstream_field}"),
            ))
        elif upstream_field in facts:
            inspected_clear += 1

        if inspected_clear:
            observations.append(Observation(
                plugin_id=self.plugin_id,
                kind="dependency.ownership_clear",
                metrics={"blocked": 0, "inspected": inspected_clear},
                reason_codes=("ownership_clear",),
            ))
        return tuple(observations)


class DependencyUnit(ReasoningUnit):
    """Situation Understanding · what is blocked by what.

    Publishes the shape of the blockage — how many blockers, how deep the chain, how many are held
    outside this workflow, and how free the work is to proceed. It publishes none of the reserved
    shared metrics: dependency changes how *achievable* work is, and letting a second unit move
    confidence or urgency would silently re-score every decision in the system.
    """

    unit_id = "core.dependency"
    version = "1.0.0"
    category = UnitCategory.SITUATION_UNDERSTANDING
    publishes = ("blocked_count", "blocking_depth", "unblocked_bp", "hard_blocked_count",
                 "blocker_severity_bp", "inspected_count")
    plugins = (ApprovalGatePlugin(), PrerequisiteAbsencePlugin(), UpstreamOwnerPlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Worst blocker sets the level; the rest add bounded drag; depth costs a flat penalty.

        Deliberately not a sum of severities. Five soft blockers do not make work five times more
        impossible than one — you are blocked or you are not, and the hardest wall governs how
        blocked you are. Additional blockers still matter, because each is another thing that must
        be cleared before anything moves, so they contribute a quarter of their weight. Depth is
        charged separately and flatly: a chain that runs through someone outside this workflow is
        worse than the same severity held in-house, regardless of what the severity is.
        """
        blockers = [item for item in observations if int(item.metrics.get("blocked", 0)) == 1]
        inspected = sum(int(item.metrics.get("inspected", 0)) for item in observations)
        if not blockers:
            # Nothing demonstrably blocks. `inspected_count` is what tells a consumer whether that
            # is a clean bill of health or an empty room — this unit will not editorialise by
            # lowering a number it has no evidence to lower.
            return {"blocked_count": 0, "blocking_depth": 0, "hard_blocked_count": 0,
                    "blocker_severity_bp": 0, "inspected_count": inspected,
                    "unblocked_bp": 10_000}
        severities = sorted((clamp_bp(int(item.metrics.get("severity_bp", 0)))
                             for item in blockers), reverse=True)
        depth = max(int(item.metrics.get("depth", DIRECT_DEPTH)) for item in blockers)
        penalty = (depth - 1) * _config_bp(view, "depth_penalty_bp", 1_500)
        free = 10_000 - severities[0] - divide_half_up(sum(severities[1:]), 4) - penalty
        return {
            "blocked_count": len(blockers),
            "blocking_depth": depth,
            "hard_blocked_count": sum(int(item.metrics.get("hard", 0)) for item in blockers),
            "blocker_severity_bp": severities[0],
            "inspected_count": inspected,
            "unblocked_bp": clamp_bp(free),
        }

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means "something stands in the way", and nothing stronger.

        It is not "do not act" — a blocked deal may still be worth a call to the person blocking
        it. Turning blockage into a veto is a decision, and this unit does not make decisions; it
        hands Part 3 the graph and lets Part 3 weigh it.
        """
        blocked = metrics["blocked_count"] > 0
        findings = tuple(Finding(
            finding_id=f"dependency.{item.plugin_id}.{_blocker_key(item)}",
            kind="dependency",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations if int(item.metrics.get("blocked", 0)) == 1)
        if not blocked:
            # Distinguishing "clear" from "unobservable" is the whole reason inspected_count is
            # published; the reason codes must make the same distinction or downstream readers of
            # the trace will collapse them again.
            return Verdict(
                matched=False,
                metrics=dict(metrics),
                reason_codes=("no_blocking_dependency_observed",) if metrics["inspected_count"]
                else ("dependency_not_observable",),
            )
        # Per-blocker `blocker:<field>` codes stay on their findings; the unit-level vocabulary is
        # kept categorical so consumers can match on it without parsing field names.
        codes = tuple(sorted({code for item in observations for code in item.reason_codes
                              if not code.startswith(BLOCKER_PREFIX)
                              and int(item.metrics.get("blocked", 0)) == 1}))
        return Verdict(matched=True, metrics=dict(metrics), findings=findings, reason_codes=codes)


__all__ = ["ApprovalGatePlugin", "DependencyUnit", "PrerequisiteAbsencePlugin",
           "UpstreamOwnerPlugin"]
