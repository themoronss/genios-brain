"""Wave Z3 · K1 · the three ranking components the compiled lane never measured.

**THE DEFECT THIS MODULE CLOSES.** `decision_maker._weighted_utility` ranks a candidate on six
components. Three of them — `impact`, `risk`, `success` — were IDENTICAL on every candidate the
compiled lane has ever produced, because `adapters/expertise._plays` constructed every
`PlayDefinition` without passing them and the dataclass defaults are `5_000` apiece. 2,000 of
10,000 basis points of weight on impact, 1,500 on success, 1,000 on risk: **45% of the ranking
formula was a constant**, and the units that measure those dimensions (`core.impact`, `core.risk`,
`core.opportunity`, `core.recommendation`) reached the score through authored per-play delta maps
that no compiled capability authors, so their measurements arrived as exactly zero. The formula had
two live components — urgency and effort — and was reported as having six.

`legacy_pack.py` had already met this and said so in a comment that is worth restating because it
is the same bug one lane over: *"Leaving them unset meant every one of this org's 144 candidates
carried {impact 5000, success 5000, effort 5000, risk 5000} — four of the five inputs to the
ranking formula frozen at the same placeholder, which makes any unit that adjusts them a no-op and
makes the persisted score_components read as measurements when nothing was measured."* The legacy
adapter fixed it from `Rule` attributes. The compiled lane routes ExpertisePackages, not rules, so
it needs its own derivation, and this is it.

**WHERE THE NUMBERS COME FROM: THE AUTHOR, NOT THIS MODULE.** Every term below is read off a field
a human wrote in the corpus. Nothing here estimates, samples, models or asks anything. Measured on
the shipped corpus (228 playbooks) the fields exist at these rates, which is why these and not
others were chosen:

    steps                910 across 228 playbooks    steps[].actor          897
    steps[].done_when    834                         steps[].optional         8
    when_to_use.do_not_use_when  215                 objects_used           172
    limits               144                         failure_modes          130
    variants             129                         outcomes / metrics      35
    identity.status      228 (draft 722 / stable 377 across the whole corpus)

A field this thin — `outcomes` at 35 of 228 — is still worth reading BECAUSE it is thin: the
authors who bothered to declare a measurable outcome are making a claim the others did not, and a
component that cannot tell those apart is the constant this module exists to remove.

**THE FOUR DOCTRINES, as they land here.**

* **The model describes, never scores.** No model, no prompt, and nothing that could grow one.
* **Integer basis points.** No float, no `round()`. Every division is `divide_half_up` on ints, so
  the same package gives the same basis points on every machine — which it must, because these
  numbers reach `PlayDefinition`, which reaches the manifest's content address.
* **No claim without a receipt.** Every term records the field it read and the number it produced,
  in `PlayPriors.receipt`, and a term that did NOT fire records that it did not. A reader asking
  "why is this play's effort 6,400" gets the arithmetic and the field names with no re-run.
* **No clocks in logic.** Nothing here reads a clock. `identity.status` is a stored word, not an
  age.

**AND THE SCAR TISSUE RULE, inherited from `context/importance`: the output must be
CONTENT-STABLE.** These numbers land in `PlayDefinition`, which lands in `CapabilityManifest`,
which is hashed into a version string. A term derived from anything that moves on its own — a
clock, a sweep instant, a row count that grows — would mint a new capability version on every
sweep whether or not a human changed anything. Every input here is a property of the authored
YAML and changes only when an author edits it.

**WHY PRIORS AND DELTAS ARE DIFFERENT THINGS.** This module produces the play's STANDING
properties: what it costs, what it risks, what it is worth, before anything is known about today's
situation. That is what `PlayDefinition.impact_bp` has always meant. The measured, situation-
specific half is the units' business and reaches the score through the delta maps
(`play_impact_bp`, `play_risk_reduction_bp`, `play_success_bp`, `play_effort_bp`), which
`expertise._roster_specs` now authors from the same declared evidence — see `play_deltas`. Priors
without deltas would rank plays identically on every situation; deltas without priors would tilt a
flat field. Both, or the formula still does not decide.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from genios_engine.reason.reasoners.common import clamp_bp, divide_half_up

# =================================================================================================
# The scale, and the three midpoints the corpus falls back to
# =================================================================================================

#: Basis-point ceiling, restated rather than imported so this module has no reason to import a
#: reasoner. `clamp_bp` enforces it.
BP_MAX = 10_000

#: The neutral reading, and the value every compiled play carried before this module existed. A
#: term that cannot be evidenced returns to this rather than to zero: "we did not measure it" and
#: "we measured nothing there" are different claims, and only the midpoint makes the first one.
NEUTRAL_BP = 5_000

# =================================================================================================
# EFFORT — read off the steps, because the steps ARE the work
# =================================================================================================

#: What one step costs, by who has to do it. A human step is the expensive one: it needs a person's
#: attention on a specific day. An agent step needs a person to approve it. A system step needs
#: nobody. The three are ordered by that and by nothing else; the gaps are wide because the whole
#: point is to separate a nine-step human procedure from a nine-step automated one, which the old
#: constant could not do.
_ACTOR_COST_BP: Mapping[str, int] = {
    "human": 1_200,
    "agent": 700,
    "system": 300,
}

#: A step whose `actor` the author left blank. Priced as a human step rather than as free: the
#: corpus's 897-of-910 coverage means a blank is an omission, and pricing an omission at zero would
#: make an under-specified playbook look cheap.
_UNTYPED_ACTOR_COST_BP = _ACTOR_COST_BP["human"]

#: `steps[].optional: true` — 8 in the corpus, and they are genuinely optional, so they are priced
#: at a third. Not zero: an optional step is still a step somebody reads and decides about.
_OPTIONAL_STEP_DIVISOR = 3

#: A day of declared duration, in effort basis points. `typical_duration_days` appears on 17 steps
#: and is the only place the corpus states elapsed cost at all, so where it exists it is read.
_DURATION_DAY_COST_BP = 250

#: The effort a play carries before its steps are counted. Every compiled play is read-only and
#: human-approved, so somebody has to read the card at minimum.
_EFFORT_FLOOR_BP = 500

# =================================================================================================
# RISK — read off what the author declared can go wrong
# =================================================================================================

#: Each declared failure mode, limit, and misuse condition raises the risk of acting on this play.
#: These are the author telling you, in their own words, where this goes wrong; a play with five
#: failure modes is not the same bet as one with none, and the constant said it was.
#:
#: Weighted differently because they are different claims: a FAILURE MODE is a way the play breaks
#: when used correctly, a LIMIT is a bound on what it can achieve, and a DO_NOT_USE_WHEN is a
#: misuse the author anticipated — the first is the sharpest and the last is the softest, because
#: `when_to_use` is checked before the play is offered at all.
#:
#: CALIBRATED AGAINST THE SHIPPED CORPUS, not chosen by feel. The first cut of these rates
#: (500/300/150 with a 1,500 draft penalty) put **115 of 228 playbooks on the 4,000 ceiling** — a
#: component that is constant for half the population is the defect this module exists to remove,
#: arriving one layer further in. The rates below, with the per-category caps, keep the ordinary
#: playbook inside the band and let the ceiling bite only at the genuine extreme.
_FAILURE_MODE_BP = 250
_LIMIT_BP = 150
_DO_NOT_USE_BP = 75

#: Per-category ceilings. An author who enumerated nine failure modes is being thorough, not
#: describing a play nine times as dangerous as one with a single failure mode — and without these
#: one prolific category would saturate the total on its own and flatten everything behind it.
_FAILURE_MODE_CAP_BP = 1_000
_LIMIT_CAP_BP = 750
_DO_NOT_USE_CAP_BP = 500

#: `identity.status`. A draft is knowledge nobody has signed off; a stable one has been through
#: review. The corpus is 722 draft to 377 stable, so this term genuinely separates the population.
#: `executable` (1 in the corpus) is treated as stable — it is a stronger claim, not a weaker one.
_STATUS_RISK_BP: Mapping[str, int] = {
    "draft": 800,
    "stable": 0,
    "executable": 0,
}

#: A status the corpus does not use. Priced as a draft: an unrecognised status is not a reviewed
#: one, and the failure mode of guessing the other way is shipping unreviewed advice as safe.
_UNKNOWN_STATUS_RISK_BP = _STATUS_RISK_BP["draft"]

#: The irreducible exposure every read-only, human-approved play still carries — the same argument
#: `reasoners/risk.py` makes for its own floor: work that looks perfect is still work that can be
#: lost, and a card that is wrong costs attention and credibility even when nothing is executed.
_RISK_FLOOR_BP = 1_000

#: The ceiling on risk derived here. A compiled play is READ-ONLY and gated on human approval, so
#: it cannot reach the top of the scale by construction; claiming it could would make a review
#: artifact look as dangerous as an executed action. `legacy_pack._risk_bp` caps at 3,500 for the
#: same reason and this stays deliberately close to it.
_RISK_CEILING_BP = 4_000

# =================================================================================================
# IMPACT — read off what the author declared this is worth
# =================================================================================================

#: The author declared a measurable outcome or a metric. 35 of 228 playbooks do, and that is the
#: single strongest statement of worth in the schema: it is the difference between "here is a
#: procedure" and "here is a procedure and here is what it should move".
#:
#: EVERY CEILING IN THIS SECTION IS CALIBRATED SO THE TERMS SUM TO EXACTLY `BP_MAX`. With the
#: first cut's rates the maximum reachable impact was 12,300 against a 10,000 scale, so the top
#: ~15% of the corpus clamped to an identical 10,000 — the constant returning at the top of the
#: range, which is the half of the distribution that decides what gets shown first. The sum below
#: is 5,000 base + 1,500 + 800 + 800 + 400 + 1,500 = 10,000, so the scale is reachable and nothing
#: piles up beneath a clamp.
_OUTCOMES_BP = 800
_METRICS_BP = 700

#: Breadth: each distinct business object the play touches. A play that reads one object is narrow;
#: one that spans five is doing structural work. Capped, because breadth stops meaning worth after
#: a point and a play listing twenty objects is an author being thorough, not a bigger bet.
_OBJECT_BP = 200
_OBJECT_CAP_BP = 800

#: Specificity: the play declares the CONDITIONS or SIGNALS under which it applies. An author who
#: wrote them is claiming this fires on something real rather than being generally good advice.
_CONDITION_BP = 250
_SIGNAL_BP = 250
_SPECIFICITY_CAP_BP = 800

#: SITUATION FIT — the play's `when_to_use.situations` names one of the situations that actually
#: fired. The strongest authored statement of relevance the corpus has, which is why `_plays`
#: already ranks on it; it belongs in impact too, because a play written for the thing that just
#: happened is worth more here than one that merely could apply.
#:
#: This is the ONE term that is not a standing property of the play — it depends on which
#: situation fired — and it is here rather than in the deltas because it is authored knowledge
#: matched against an authored situation id, with no measurement anywhere in it. The deltas carry
#: the MEASURED half.
_SITUATION_FIT_BP = 1_500

#: Variants: the author wrote alternative shapes of this play for different contexts. 129 of 228
#: declare them, and a play with variants has been thought about more than one that has not.
_VARIANT_BP = 150
_VARIANT_CAP_BP = 400

# =================================================================================================
# SUCCESS — how likely this play is to produce its declared result
# =================================================================================================
#
# WHY THIS TERM EXISTS AT ALL, given `_learned_play_efficacy` already sets `success_probability_bp`
# from the org's own outcomes. Because that reader returns nothing on a tenant that has not yet
# accumulated outcomes — which is EVERY tenant on day one, and every tenant for any play that has
# not yet run — and the fallback was the flat 5,000. So the component the formula weights at 1,500
# was constant precisely on the tenants where ranking matters most: the new ones. The prior gives
# the authored answer until the tenant has a measured one, and the measured one still wins the
# moment it exists (see `_plays`): evidence beats authorship, but authorship beats a placeholder.

#: Every step declares `done_when`. 834 of 910 corpus steps do, so a play missing it is in a real
#: minority — and a play whose steps do not say how you know they are done is one whose success
#: nobody can confirm, which is a weaker claim about succeeding.
_SUCCESS_OBSERVABLE_BP = 1_000

#: `identity.status`, mirroring `_STATUS_RISK_BP` and pointing the other way: a reviewed play has
#: been run by somebody other than its author, which is the corpus's own test of whether a
#: procedure works. Draft subtracts rather than merely failing to add, because 722 of the corpus is
#: draft and a term that only ever adds would leave the majority at the flat midpoint again.
_SUCCESS_STATUS_BP: Mapping[str, int] = {
    "draft": -800,
    "stable": 800,
    "executable": 800,
}
_UNKNOWN_STATUS_SUCCESS_BP = _SUCCESS_STATUS_BP["draft"]

#: The author declared what this should move. A play with a metric attached is a play somebody
#: intended to check, and an intention to check correlates with the thing working.
_SUCCESS_OUTCOME_BP = 500

#: Each step beyond this many is one more place the procedure gets abandoned halfway. The corpus
#: averages four steps per playbook, so the threshold sits just above the median and only genuinely
#: long procedures are marked down.
_SUCCESS_STEP_THRESHOLD = 5
_SUCCESS_LONG_STEP_BP = 200
_SUCCESS_LONG_CAP_BP = 1_000


# =================================================================================================
# The result
# =================================================================================================

@dataclass(frozen=True, slots=True)
class PlayPriors:
    """One play's three standing components, and the receipt for every term that produced them.

    `receipt` is not decoration. These numbers reach a ranking that reaches a card, and doc 00's
    Law 6 — every silence names itself — applies to a component exactly as it applies to a
    finding: a reader asking why this play ranked below that one must be able to get the
    arithmetic without re-running the compiler.
    """

    impact_bp: int
    effort_bp: int
    risk_bp: int
    #: The AUTHORED success probability. Overridden by the org's own measured efficacy wherever
    #: `_learned_play_efficacy` has one — see `_SUCCESS_OBSERVABLE_BP` for why both exist.
    success_bp: int
    receipt: Mapping[str, Any] = field(default_factory=dict)


def _sequence(value: Any) -> Sequence[Any]:
    """A declared list, or empty. A scalar where a list belongs is an authoring slip and counts as
    one item rather than raising: refusing to compile a whole package over a stray string would
    take a tenant's entire domain offline for a YAML typo."""
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _effort(definition: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    """What this play costs to carry out, read off its steps.

    Deliberately NOT a step count alone: nine automated steps and nine human ones are the same
    number and not the same afternoon, and the whole reason effort is in the formula is so a cheap
    play can beat an expensive one at equal impact.
    """
    steps = _sequence(definition.get("steps"))
    total = _EFFORT_FLOOR_BP
    by_actor: dict[str, int] = {}
    optional = 0
    duration_days = 0
    for step in steps:
        record = _mapping(step)
        actor = str(record.get("actor") or "").strip().lower()
        cost = _ACTOR_COST_BP.get(actor, _UNTYPED_ACTOR_COST_BP)
        key = actor if actor in _ACTOR_COST_BP else "unstated"
        if record.get("optional") is True:
            optional += 1
            cost = divide_half_up(cost, _OPTIONAL_STEP_DIVISOR)
        by_actor[key] = by_actor.get(key, 0) + 1
        total += cost
        days = record.get("typical_duration_days")
        # `bool` is an `int` in Python and `optional: true` sits one key away, so the type check is
        # explicit rather than trusting `isinstance(days, int)`.
        if isinstance(days, int) and not isinstance(days, bool) and days > 0:
            duration_days += days
            total += days * _DURATION_DAY_COST_BP
    receipt = {
        "step_count": len(steps),
        "steps_by_actor": dict(sorted(by_actor.items())),
        "optional_steps": optional,
        "declared_duration_days": duration_days,
        "floor_bp": _EFFORT_FLOOR_BP,
        # The one case where the number means "nothing was declared" rather than "this is cheap".
        # A playbook with no steps never reaches here — `_plays` skips it with its own receipt —
        # but a caller handing this function a non-playbook would otherwise get a confident 500.
        "unmeasured": not steps,
    }
    return (clamp_bp(total) if steps else NEUTRAL_BP), receipt


def _risk(definition: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    """How likely acting on this play is to be wrong, read off what the author said can go wrong.

    Capped well below the top of the scale: every compiled play is read-only and human-approved,
    so the downside is a wasted review and a dented trust, not an executed mistake. Pretending
    otherwise would make advisory output compete with the risk of real action.
    """
    identity = _mapping(definition.get("identity"))
    when = _mapping(definition.get("when_to_use"))
    failure_modes = len(_sequence(definition.get("failure_modes")))
    limits = len(_sequence(definition.get("limits")))
    do_not_use = len(_sequence(when.get("do_not_use_when")))
    status = str(identity.get("status") or "").strip().lower()
    status_bp = _STATUS_RISK_BP.get(status, _UNKNOWN_STATUS_RISK_BP)
    failure_bp = min(failure_modes * _FAILURE_MODE_BP, _FAILURE_MODE_CAP_BP)
    limit_bp = min(limits * _LIMIT_BP, _LIMIT_CAP_BP)
    misuse_bp = min(do_not_use * _DO_NOT_USE_BP, _DO_NOT_USE_CAP_BP)
    total = _RISK_FLOOR_BP + failure_bp + limit_bp + misuse_bp + status_bp
    receipt = {
        "failure_modes": failure_modes,
        "failure_mode_bp": failure_bp,
        "limits": limits,
        "limit_bp": limit_bp,
        "do_not_use_when": do_not_use,
        "do_not_use_bp": misuse_bp,
        "status": status or None,
        "status_bp": status_bp,
        "status_recognised": status in _STATUS_RISK_BP,
        "floor_bp": _RISK_FLOOR_BP,
        "ceiling_bp": _RISK_CEILING_BP,
        "capped": total > _RISK_CEILING_BP,
    }
    return min(total, _RISK_CEILING_BP), receipt


def _impact(definition: Mapping[str, Any], *, situation_fit: bool) -> tuple[int, dict[str, Any]]:
    """What acting on this play is worth if it is right.

    Every term is an authored declaration of worth or reach. `situation_fit` is the one term that
    depends on today — see `_SITUATION_FIT_BP` for why it is here and not in the deltas.
    """
    when = _mapping(definition.get("when_to_use"))
    outcomes = len(_sequence(definition.get("outcomes")))
    metrics = len(_sequence(definition.get("metrics")))
    objects = len({str(item) for item in _sequence(definition.get("objects_used"))})
    conditions = len(_sequence(when.get("conditions")))
    signals = len(_sequence(when.get("signals")))
    variants = len(_sequence(definition.get("variants")))

    outcome_bp = (_OUTCOMES_BP if outcomes else 0) + (_METRICS_BP if metrics else 0)
    object_bp = min(objects * _OBJECT_BP, _OBJECT_CAP_BP)
    specificity_bp = min(conditions * _CONDITION_BP + signals * _SIGNAL_BP, _SPECIFICITY_CAP_BP)
    variant_bp = min(variants * _VARIANT_BP, _VARIANT_CAP_BP)
    fit_bp = _SITUATION_FIT_BP if situation_fit else 0

    # The midpoint is the BASE here rather than a floor, because impact is the one component with
    # no natural zero: a play nobody described the worth of is not worthless, it is unmeasured,
    # and the neutral reading is the honest one. Terms move it up from there.
    total = NEUTRAL_BP + outcome_bp + object_bp + specificity_bp + variant_bp + fit_bp
    receipt = {
        "declares_outcomes": bool(outcomes),
        "declares_metrics": bool(metrics),
        "outcome_bp": outcome_bp,
        "objects_used": objects,
        "object_bp": object_bp,
        "conditions": conditions,
        "signals": signals,
        "specificity_bp": specificity_bp,
        "variants": variants,
        "variant_bp": variant_bp,
        "situation_fit": situation_fit,
        "situation_fit_bp": fit_bp,
        "base_bp": NEUTRAL_BP,
    }
    return clamp_bp(total), receipt


def _success(definition: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    """How likely this play is to produce its declared result, on the author's own evidence.

    Distinct from risk on purpose, and the distinction is the reason both are weighted separately
    in the formula: RISK is the cost of acting wrongly, SUCCESS is the chance of acting rightly,
    and a play can be low-risk and low-success at once — a safe procedure nobody ever finishes.
    """
    steps = _sequence(definition.get("steps"))
    identity = _mapping(definition.get("identity"))
    status = str(identity.get("status") or "").strip().lower()
    status_bp = _SUCCESS_STATUS_BP.get(status, _UNKNOWN_STATUS_SUCCESS_BP)
    observable = _observable(definition)
    declares_outcome = bool(_sequence(definition.get("outcomes"))
                            or _sequence(definition.get("metrics")))
    over = max(0, len(steps) - _SUCCESS_STEP_THRESHOLD)
    length_bp = min(over * _SUCCESS_LONG_STEP_BP, _SUCCESS_LONG_CAP_BP)
    total = (NEUTRAL_BP
             + (_SUCCESS_OBSERVABLE_BP if observable else 0)
             + status_bp
             + (_SUCCESS_OUTCOME_BP if declares_outcome else 0)
             - length_bp)
    receipt = {
        "every_step_observable": observable,
        "observable_bp": _SUCCESS_OBSERVABLE_BP if observable else 0,
        "status": status or None,
        "status_bp": status_bp,
        "status_recognised": status in _SUCCESS_STATUS_BP,
        "declares_outcome": declares_outcome,
        "outcome_bp": _SUCCESS_OUTCOME_BP if declares_outcome else 0,
        "step_count": len(steps),
        "steps_over_threshold": over,
        "length_penalty_bp": length_bp,
        "base_bp": NEUTRAL_BP,
        "unmeasured": not steps,
    }
    return (clamp_bp(total) if steps else NEUTRAL_BP), receipt


def derive_play_priors(definition: Mapping[str, Any], *, situation_fit: bool) -> PlayPriors:
    """The three standing components for one authored playbook, with the arithmetic attached.

    Pure: same definition and same `situation_fit` give the same basis points, on every machine and
    in every process. That is load-bearing rather than tidy — the output reaches
    `CapabilityManifest.version` through the manifest's content address, so a derivation that
    varied by dict ordering or platform would mint a new capability version for an unchanged
    corpus and break every immutability guard that reads it.
    """
    definition = _mapping(definition)
    impact_bp, impact_receipt = _impact(definition, situation_fit=situation_fit)
    effort_bp, effort_receipt = _effort(definition)
    risk_bp, risk_receipt = _risk(definition)
    success_bp, success_receipt = _success(definition)
    return PlayPriors(
        impact_bp=impact_bp,
        effort_bp=effort_bp,
        risk_bp=risk_bp,
        success_bp=success_bp,
        receipt={"impact": impact_receipt, "effort": effort_receipt, "risk": risk_receipt,
                 "success": success_receipt},
    )


# =================================================================================================
# THE DELTAS — how far a MEASURED signal may tilt each play
# =================================================================================================
#
# The priors above rank plays against each other before anything is known about today. The deltas
# are the other half: `reasoners/impact_unit`, `risk`, `recommendation_unit` and `cost_unit` each
# measure a dimension of the LIVE situation and then look for an authored `{play_id: delta}` map to
# find out how far that measurement may move each play. No compiled capability authored one, so
# every one of those measurements arrived at the ranking as zero — the units ran, emitted, and
# changed nothing.
#
# A delta is a CEILING, not a bonus: `impact_unit` applies `delta * impact_bp / 10_000`, so an
# authored 600 means "at a maximal measured stake, tilt this play by 600bp, and proportionally
# less below that". Authoring the same delta for every play would restore a constant one level up,
# so each play's ceiling is derived from what it declared about its own responsiveness.

#: How far a measured stake may tilt a play that declared a measurable outcome, versus one that did
#: not. A play with declared outcomes and metrics is the one whose worth actually tracks the size
#: of the thing in front of it; a procedural checklist's value does not double because the account
#: is twice as large.
_IMPACT_DELTA_RESPONSIVE_BP = 600
_IMPACT_DELTA_BASE_BP = 200

#: How far measured momentum decay and thin coverage may be REDUCED by running this play. Only a
#: reviewed play earns the larger reduction: claiming a draft procedure reliably mitigates a
#: measured exposure is exactly the unearned confidence `identity.status` exists to record.
_RISK_REDUCTION_REVIEWED_BP = 500
_RISK_REDUCTION_DRAFT_BP = 200

#: How far the org's own measured outcomes may move a play's success probability. A play whose every
#: step declares `done_when` is one whose success is observable, so a measurement of it means more.
_SUCCESS_DELTA_OBSERVABLE_BP = 500
_SUCCESS_DELTA_BASE_BP = 200

#: How far a measured cost signal may move effort. Human-heavy plays are the ones whose real cost
#: varies with the situation; an automated one costs what it costs.
_EFFORT_DELTA_HUMAN_BP = 400
_EFFORT_DELTA_BASE_BP = 150

#: Config keys, spelled once. Each is read by exactly one unit and a typo in any of them is a
#: silent no-op — the precise failure this module was written to remove — so they are constants and
#: `tests/reason/adapters/test_play_priors.py` asserts each one is read by the unit that owns it.
IMPACT_DELTA_KEY = "play_impact_bp"
RISK_REDUCTION_KEY = "play_risk_reduction_bp"
SUCCESS_DELTA_KEY = "play_success_bp"
EFFORT_DELTA_KEY = "play_effort_bp"


def _observable(definition: Mapping[str, Any]) -> bool:
    """Does every step say how you know it is done? `done_when` covers 834 of 910 corpus steps, so
    a play missing it is in a real minority and is making a weaker claim about its own success."""
    steps = _sequence(definition.get("steps"))
    if not steps:
        return False
    return all(_mapping(step).get("done_when") for step in steps)


def _human_heavy(definition: Mapping[str, Any]) -> bool:
    """Is most of this play a person's work? Ties go to human — the majority actor in the corpus,
    and the reading that does not under-price effort."""
    steps = [_mapping(step) for step in _sequence(definition.get("steps"))]
    if not steps:
        return False
    human = sum(1 for step in steps
                if str(step.get("actor") or "human").strip().lower() == "human")
    return human * 2 >= len(steps)


def play_deltas(definitions: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    """The four authored delta maps for one capability's plays, keyed by config key.

    Returns `{config_key: {play_id: bp}}` for the plays that earn a non-default ceiling, ready to
    be merged into the relevant unit's config by `expertise._roster_specs`.

    Every map is built over `sorted(definitions)` and the returned dicts are insertion-ordered by
    that sort. This is not tidiness: `reasoners/risk.py` documents that adjustment order reaches a
    result's semantic hash and that the manifest is re-sorted when it round-trips through the audit
    store, so an unsorted map would report every replayed run as non-reproducible.
    """
    impact: dict[str, int] = {}
    risk: dict[str, int] = {}
    success: dict[str, int] = {}
    effort: dict[str, int] = {}
    for play_id in sorted(definitions):
        definition = _mapping(definitions[play_id])
        identity = _mapping(definition.get("identity"))
        status = str(identity.get("status") or "").strip().lower()
        reviewed = status in ("stable", "executable")
        declares_outcome = bool(_sequence(definition.get("outcomes"))
                                or _sequence(definition.get("metrics")))
        impact[play_id] = (_IMPACT_DELTA_RESPONSIVE_BP if declares_outcome
                           else _IMPACT_DELTA_BASE_BP)
        risk[play_id] = (_RISK_REDUCTION_REVIEWED_BP if reviewed
                         else _RISK_REDUCTION_DRAFT_BP)
        success[play_id] = (_SUCCESS_DELTA_OBSERVABLE_BP if _observable(definition)
                            else _SUCCESS_DELTA_BASE_BP)
        effort[play_id] = (_EFFORT_DELTA_HUMAN_BP if _human_heavy(definition)
                           else _EFFORT_DELTA_BASE_BP)
    return {
        IMPACT_DELTA_KEY: impact,
        RISK_REDUCTION_KEY: risk,
        SUCCESS_DELTA_KEY: success,
        EFFORT_DELTA_KEY: effort,
    }


__all__ = ["BP_MAX", "EFFORT_DELTA_KEY", "IMPACT_DELTA_KEY", "NEUTRAL_BP", "PlayPriors",
           "RISK_REDUCTION_KEY", "SUCCESS_DELTA_KEY", "derive_play_priors", "play_deltas"]
