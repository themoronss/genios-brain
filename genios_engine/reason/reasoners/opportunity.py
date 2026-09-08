"""Category 2 · Business Evaluation — the Opportunity Unit.

Answers one question: *where is there value to gain here that nobody has taken?*

An opportunity in GeniOS is never "this looks promising". It is a specific, evidenced gap between
what the situation makes possible and what has actually happened — a counterparty who wrote and
was never answered, a live piece of work that has stopped moving while it is still winnable, a
live relationship with nobody carrying it. Each of those is a separate plugin, because they are
separate claims with separate evidence, and folding them into one score would make the reasoning
unexplainable.

**Every field this unit reads is DECLARED, and none is named here (Law 5).** The unit knows the
*shapes* — a moment they wrote to us, a moment we wrote back, a state word, an assignee — and the
capability's Layer 3 manifest says which facts carry them and which state words mean "still live".
That division is the whole point: whether a status of `negotiation` counts as live is domain
knowledge that changes per industry and per customer, and a core unit that hardcoded it would be
shipping one vertical's vocabulary to every tenant and calling it reasoning. The manifest is
versioned with the expertise; this file is not.

The consequence is that an undeclared capability gets **silence with a receipt**, not a fabricated
zero: `opportunity_signals_undeclared` says the unit ran and had nothing to look at, which is a
different fact from "we looked and there is no opportunity here".

The unit never proposes an action. It reports that headroom exists and how strongly; the Decision
Maker weighs that against risk, effort, and policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from genios_engine.contracts.reasoning import Finding

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, divide_half_up, elapsed_hours, fact_value

#: The unit whose decay reading tells this one that live work has stopped moving. A default rather
#: than a hardcode: a capability may run its own decay model under another id. Enumerated as a
#: module constant so the registration check can assert it names a unit that actually exists —
#: `core.effort` was a default nobody could see, and it emptied an axis of `core.tradeoff` for the
#: whole life of that unit.
DEFAULT_MOMENTUM_SOURCE = "core.temporal"

#: Published when nothing was declared for a plugin to read. Silence that names itself.
UNDECLARED_REASON = "opportunity_signals_undeclared"

#: Named when this unit DID have inputs bound, looked at them, and found nothing above the
#: threshold — the honest negative.
#:
#: **LAW 6 — every silence names itself.** This branch used to emit `codes = ()`: the unit
#: published `opportunity_bp: 0` and said nothing whatever about it. That made three different
#: states indistinguishable in the audit row — "no inputs were declared" (which DID have a code),
#: "inputs declared, nothing found", and "the unit never ran" — and the last two are the ones a
#: reviewer most needs to tell apart, because only one of them is a reason to go and connect a
#: source. `core.opportunity` feeds `core.tradeoff` and `core.validation`, so a silent zero
#: propagates into two more units' inputs without ever naming itself.
#:
#: The verdict is UNCHANGED (`matched=False` — the unit looked and found nothing, which is a real
#: negative finding, not an absence). Only the silence became legible.
NO_SIGNAL_REASON = "opportunity_none_above_threshold"


def _config_bp(view: UnitView, key: str, default: int) -> int:
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _declared_field(view: UnitView, key: str) -> str | None:
    """The fact field the manifest bound to one of this unit's inputs, or None if it bound none.

    An absent binding is silence; a malformed one is an authoring fault and raises, because a
    capability that meant to declare a field and mistyped the key would otherwise ship a unit that
    quietly observes nothing and reports it as "no opportunity".
    """
    raw = view.config.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key} must be a non-empty fact field name")
    return raw.strip()


def _declared_values(view: UnitView, key: str) -> frozenset[str]:
    """The state words the manifest declared to mean "still live", normalised for comparison."""
    raw = view.config.get(key)
    if raw is None:
        return frozenset()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list, set, frozenset)):
        raise ValueError(f"{key} must be a list of field values")
    values = frozenset(str(item).strip().lower() for item in raw)
    if not values or "" in values:
        raise ValueError(f"{key} must not contain empty values")
    return values


def _declared_source(view: UnitView, key: str, default: str) -> str:
    """Which unit supplies a prior reading, so a capability can substitute its own authority."""
    raw = view.config.get(key, default)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key} must name a reasoning unit")
    return raw.strip()


class UnansweredInboundPlugin:
    """They reached out and nobody replied.

    The strongest opportunity signal in the system, because the counterparty already spent the
    effort — the cost of capture is one reply, and the window closes on its own.

    Reads two declared moments: when they last wrote to us, and when we last wrote back. Without
    the first there is no claim to make; without the second the unit cannot tell an unanswered
    message from an answered one, so it says nothing rather than claiming a gap it cannot see.
    """

    plugin_id = "unanswered_inbound"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        inbound_field = _declared_field(view, "inbound_field")
        outbound_field = _declared_field(view, "outbound_field")
        if inbound_field is None or outbound_field is None:
            return ()
        if fact_value(view.request, inbound_field) is None:
            return ()
        try:
            inbound_hours = elapsed_hours(view.request, inbound_field)
        except ValueError:
            return ()
        if fact_value(view.request, outbound_field) is not None:
            try:
                if elapsed_hours(view.request, outbound_field) <= inbound_hours:
                    return ()               # we already answered; no gap remains
            except ValueError:
                return ()
        # Ripe by roughly a day, decaying in value thereafter — an answer tomorrow is worth much
        # less than an answer today, and after a week the moment has mostly passed.
        strength = clamp_bp(divide_half_up(min(inbound_hours, 168) * 10_000, 24)) \
            if inbound_hours <= 24 else clamp_bp(10_000 - divide_half_up(
                (min(inbound_hours, 336) - 24) * 6_000, 312))
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.unanswered_inbound",
            metrics={"strength_bp": strength, "waiting_hours": inbound_hours},
            reason_codes=("inbound_awaiting_reply",),
        ),)


class StalledButOpenPlugin:
    """The work is still winnable and nothing is happening to win it.

    Two declared inputs: which fact carries the state of the work, and which state words mean it
    is still live. Both must be declared together — a status field with no live vocabulary is a
    question the manifest asked and did not answer, and guessing at it would mean this unit
    deciding what "open" means for a business it has never seen.
    """

    plugin_id = "stalled_but_open"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        status_field = _declared_field(view, "status_field")
        if status_field is None:
            return ()
        live = _declared_values(view, "active_statuses")
        if not live:
            raise ValueError("status_field requires active_statuses to say which values are live")
        status = str(fact_value(view.request, status_field) or "").strip().lower()
        if status not in live:
            return ()
        source = _declared_source(view, "momentum_source", DEFAULT_MOMENTUM_SOURCE)
        quiet_bp = view.prior_metric(source, "drop_bp", 0)
        if quiet_bp <= 0:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.stalled_but_open",
            metrics={"strength_bp": clamp_bp(quiet_bp)},
            reason_codes=("active_without_momentum",),
        ),)


class UnworkedRelationshipPlugin:
    """A live relationship with no one currently working it.

    The assignee field is declared, and so is the difference between *captured and empty* and
    *never captured*. Only the first is evidence: somebody looked at the record and found no owner
    on it. Treating a field nobody collected as an unowned relationship would manufacture an
    opportunity out of a gap in the data — which is how a unit ends up recommending work on every
    situation in an org that never synced its assignees.
    """

    plugin_id = "unworked_relationship"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        owner_field = _declared_field(view, "owner_field")
        if owner_field is None or owner_field not in view.request.context.facts:
            return ()
        if str(fact_value(view.request, owner_field) or "").strip():
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.unowned",
            metrics={"strength_bp": _config_bp(view, "unowned_strength_bp", 4_000)},
            reason_codes=("no_owner_assigned",),
        ),)


class OpportunityUnit(ReasoningUnit):
    """Business Evaluation · where value can be gained."""

    unit_id = "core.opportunity"
    version = "1.0.0"
    category = UnitCategory.BUSINESS_EVALUATION
    publishes = ("opportunity_bp", "opportunity_count")
    plugins = (UnansweredInboundPlugin(), StalledButOpenPlugin(), UnworkedRelationshipPlugin())

    #: The config keys a manifest binds to this unit's inputs. Enumerated so a capability author
    #: can be told what is missing, and so the unit can tell the difference between "declared and
    #: nothing found" and "never declared" without inspecting its own plugins.
    INPUT_KEYS = ("inbound_field", "outbound_field", "status_field", "owner_field")

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Strongest signal leads, others contribute diminishing support.

        Deliberately not a sum: three weak hints are not a strong opportunity, and averaging would
        let one weak plugin drag down a genuinely ripe one. The strongest claim sets the level and
        corroboration adds a bounded lift.
        """
        del view
        strengths = sorted((int(item.metrics.get("strength_bp", 0)) for item in observations),
                           reverse=True)
        if not strengths:
            return {"opportunity_bp": 0, "opportunity_count": 0}
        lift = divide_half_up(sum(strengths[1:]), 4)
        return {"opportunity_bp": clamp_bp(strengths[0] + lift),
                "opportunity_count": len(strengths)}

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """A reading, or a receipt saying why there is none.

        `matched` is False when the unit looked and found nothing worth naming, and None when it
        had nothing to look at — a capability that declared no inputs has not been told this
        situation is uninteresting, it has been told nothing at all, and the two must not collapse
        into the same verdict on the way to the Decision Maker.
        """
        declared = any(view.config.get(key) is not None for key in self.INPUT_KEYS)
        threshold = _config_bp(view, "opportunity_threshold_bp", 3_000)
        present = metrics["opportunity_bp"] >= threshold
        findings = tuple(Finding(
            finding_id=f"opportunity.{item.plugin_id}",
            kind="opportunity",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations) if present else ()
        if present:
            codes = tuple(sorted({code for item in observations for code in item.reason_codes}))
        else:
            # Both branches now carry a code: "we had nothing to look at" and "we looked and found
            # nothing" are different facts and neither of them is silence. See `NO_SIGNAL_REASON`.
            codes = (NO_SIGNAL_REASON,) if declared else (UNDECLARED_REASON,)
        return Verdict(
            matched=present if declared else None,
            metrics=dict(metrics),
            findings=findings,
            reason_codes=codes,
        )


__all__ = ["DEFAULT_MOMENTUM_SOURCE", "NO_SIGNAL_REASON", "OpportunityUnit",
           "StalledButOpenPlugin", "UNDECLARED_REASON", "UnansweredInboundPlugin",
           "UnworkedRelationshipPlugin"]
