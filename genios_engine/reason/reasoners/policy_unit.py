"""Category 3 · Optimization — the Policy Unit.

Answers one question: *what does this organisation forbid or require here?*

Every other unit in Part 2 reasons about the situation. This one reasons about the rules the
business has written down around the situation — the sentences that exist in a compliance handbook
rather than in a CRM: "anything over £50,000 needs the VP's signature", "we do not email this
account, ever", "no external communication during the close period".

**Why this is not core.constraint.** `core.constraint` enforces what the *capability* declared: its
`policies` tuple (read_only, human_approval_required, evidence_required, no_unverified_recipient)
and the preconditions authored onto each play. Those are properties of the expertise pack — they
ship with it and change when it is re-versioned. Organisation policy is different in kind: it is
tenant-owned, it changes when the business changes and not when the pack does, and it is carried in
this unit's `ReasonerSpec.config` so a customer can tighten their own rules without anyone editing a
play. Two authorities, two blast radii, deliberately kept apart. Nothing in this file re-reads
`capability.policies` or play preconditions; `core.constraint` owns those and duplicating it would
mean two different answers to the same question.

Three separable rule families, one plugin each:

* **Approval thresholds** — value above which a human must sign off before the org commits.
* **Contact permission** — do-not-contact records and consent state.
* **Timing rules** — declared blackout dates and declared working hours.

The unit reports observations and a compliance reading. It never selects a play and never ranks
one. Where an organisation rule is *breached*, it fails closed: a `policy`-stage CandidateCheck with
outcome ELIMINATE against every play the rule actually reaches. Where a rule is merely *unsatisfied
on the evidence available* — consent not on file, a value it could not verify, an hour outside the
declared window — it emits WARN, because "we cannot show this is allowed" and "this is forbidden"
are different sentences and only one of them should stop work.

A rule the tenant has not configured is not a rule. This unit says nothing about it rather than
inventing a default, because a fabricated policy is indistinguishable from a real one downstream.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CheckOutcome,
    Finding,
    PlayDefinition,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import clamp_bp, evidence_ids, fact_value, integer

# The only check stage this unit is allowed to speak on. Stated once so the string that must match
# the frozen contract's vocabulary lives in exactly one place.
POLICY_STAGE = "policy"

# Severity carried by a breached rule. A hard organisation rule has no gradient — it is either
# broken or it is not — so the number is a constant rather than a knob somebody can quietly soften.
BLOCKING_SEVERITY_BP = 10_000

# Source systems export booleans as strings far more often than as booleans; a "true" in a CRM
# export is a do-not-contact flag and must not be read as an absent one.
_TRUE_TEXT = frozenset({"true", "yes", "y", "1"})


# --------------------------------------------------------------------------------------------
# Configuration readers — organisation policy arrives as Layer 3 config, and bad config is a
# deployment fault. Every reader refuses rather than coerces: silently accepting a malformed rule
# would let a capability believe it had a policy it does not actually have.
# --------------------------------------------------------------------------------------------

def _config_bp(view: UnitView, key: str, default: int) -> int:
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{key} must be integer basis points")
    return value


def _config_field(view: UnitView, key: str, default: str) -> str:
    """The fact name a rule reads. Configurable because the same rule sits over differently named
    facts in different capabilities, while the rule itself is identical."""
    value = view.config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a fact name")
    return value.strip()


def _config_flag(view: UnitView, key: str, default: bool) -> bool:
    value = view.config.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _config_amount(view: UnitView, key: str) -> int | None:
    """A money threshold in whole minor units, or None when the tenant declared no such rule.

    Not basis points: an approval threshold of 5,000,000 (fifty thousand pounds in pence) is
    ordinary, and validating it as bp would reject every realistic value.
    """
    if key not in view.config:
        return None
    value = view.config[key]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10 ** 15:
        raise ValueError(f"{key} must be a non-negative whole amount")
    return value


def _config_texts(view: UnitView, key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """A declared vocabulary — accepted statuses, blackout dates — normalised for comparison."""
    if key not in view.config:
        return tuple(sorted(default))
    value = view.config[key]
    if isinstance(value, str) or not isinstance(value, (tuple, list)):
        raise ValueError(f"{key} must be a list of strings")
    items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} must be a list of non-empty strings")
        items.append(item.strip().lower())
    return tuple(sorted(set(items)))


def _config_hour(view: UnitView, key: str) -> int | None:
    if key not in view.config:
        return None
    value = view.config[key]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 23:
        raise ValueError(f"{key} must be an hour between 0 and 23")
    return value


def _config_weekdays(view: UnitView, key: str, default: tuple[int, ...]) -> frozenset[int]:
    if key not in view.config:
        return frozenset(default)
    value = view.config[key]
    if isinstance(value, str) or not isinstance(value, (tuple, list)) or not value:
        raise ValueError(f"{key} must be a non-empty list of weekday numbers")
    days = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 6:
            raise ValueError(f"{key} must contain weekday numbers between 0 (Monday) and 6")
        days.append(item)
    return frozenset(days)


def _config_offset_minutes(view: UnitView, key: str) -> int:
    value = view.config.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or not -720 <= value <= 840:
        raise ValueError(f"{key} must be whole minutes between -720 and 840")
    return value


def _text_fact(view: UnitView, field: str) -> str:
    """A fact read as normalised text, or "" when it is absent. Comparison-only: an empty string
    here always means "we did not see one", never "we saw an empty policy value"."""
    value = fact_value(view.request, field)
    return "" if value is None else str(value).strip().lower()


def _local_time(view: UnitView) -> datetime:
    """The frozen evaluation time expressed in the organisation's own working day.

    `request.evaluation_time` is an input, not a clock read — that is what lets a decision be
    replayed in a year and reach the same answer. The offset is declared in config because a
    blackout date and a working hour are statements about the business's calendar, not about UTC.
    """
    return view.request.evaluation_time + timedelta(minutes=_config_offset_minutes(
        view, "org_utc_offset_minutes"))


# --------------------------------------------------------------------------------------------
# Rule reach — which plays a given rule actually governs
# --------------------------------------------------------------------------------------------

def _reaches_outside(play: PlayDefinition) -> bool:
    """Does running this play put something in front of the counterparty?

    A do-not-contact record and a communications blackout govern *contact*. Neither says anything
    about logging a note in the CRM, and eliminating internal record-keeping on a contact rule would
    make the org's own compliance work impossible during the exact period it matters most.

    An explicit `external_recipient_required` declaration is believed in both directions, because
    Layer 3 authored it deliberately. Where a play declares nothing, the unit falls back to
    reversibility and reads any non-read-only play as reaching outside — the fail-closed reading,
    since an undeclared side effect is exactly the case where guessing "internal" is dangerous.
    """
    declared = play.metadata.get("external_recipient_required")
    if isinstance(declared, bool):
        return declared
    return not play.read_only


def _carries_human_approval(play: PlayDefinition) -> bool:
    """Is a human already in the loop before this play takes effect?

    Read from the same two signals `core.constraint` uses for the capability-level approval policy,
    on purpose: a play should not satisfy one approval authority and fail the other because the two
    read different fields.
    """
    return (play.metadata.get("execution_boundary") == "human_approval_required"
            or "human_approval" in play.tags)


def _needs_approval_cover(play: PlayDefinition) -> bool:
    """Does an approval threshold govern this play?

    Only if it commits the organisation to something (a read-only play approves nothing) *and* the
    play does not already route through a person. A play that is gated on human sign-off already
    satisfies the rule the threshold exists to enforce; flagging it would train reviewers to ignore
    this unit's output.
    """
    return not play.read_only and not _carries_human_approval(play)


# Which plays each rule family reaches. Keyed by plugin so a new rule family has to state its reach
# explicitly rather than inherit somebody else's blast radius by accident.
_RULE_REACH = {
    "approval_threshold": _needs_approval_cover,
    "contact_permission": _reaches_outside,
    "timing_rules": _reaches_outside,
}


class ApprovalThresholdPlugin:
    """Above a declared value, the organisation requires a human signature before it commits.

    This is the most common written rule in any business and the one that is most expensive to get
    wrong in both directions: acting past it is an unauthorised commitment, and stopping short of it
    on every deal makes the system useless. So the rule fires on exactly one condition — the value
    at stake is over the declared bar and no sign-off is recorded against it.

    Where the tenant declared a threshold but the value cannot be read, the plugin reports a
    *concern* rather than a breach. "We could not verify this is within the approval limit" is the
    truthful statement; escalating it to a prohibition would block routine work every time a CRM
    field was blank, and staying silent would let an unbounded commitment through unremarked.
    """

    plugin_id = "approval_threshold"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        threshold = _config_amount(view, "approval_threshold_amount")
        if threshold is None:
            return ()                       # the tenant declared no approval rule
        value_field = _config_field(view, "approval_value_field", "deal.value")
        raw = fact_value(view.request, value_field)
        if raw is None:
            return (self._unverifiable(view, value_field, threshold, "value_absent"),)
        try:
            amount = integer(raw, value_field)
        except ValueError:
            return (self._unverifiable(view, value_field, threshold, "value_unreadable"),)
        if amount <= threshold:
            return ()                       # under the bar: the org has nothing to say here
        status_field = _config_field(view, "approval_status_field", "deal.approval_status")
        granted = _config_texts(view, "approval_granted_values",
                                ("approved", "granted", "signed_off"))
        if _text_fact(view, status_field) in granted:
            return ()                       # sign-off is on record; the rule is satisfied
        return (Observation(
            plugin_id=self.plugin_id,
            kind="policy.approval_threshold",
            metrics={"blocking_bp": BLOCKING_SEVERITY_BP,
                     "value_amount": amount,
                     "threshold_amount": threshold},
            evidence_ids=evidence_ids(view.request, value_field, status_field),
            reason_codes=("approval_threshold_exceeded",),
        ),)

    def _unverifiable(self, view: UnitView, field: str, threshold: int,
                      detail: str) -> Observation:
        return Observation(
            plugin_id=self.plugin_id,
            kind="policy.approval_unverifiable",
            metrics={"concern_bp": _config_bp(view, "approval_unverifiable_concern_bp", 2_000),
                     "threshold_amount": threshold},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=(f"approval_{detail}",),
        )


class ContactPermissionPlugin:
    """Are we allowed to talk to this counterparty at all?

    Two rules, one question. A do-not-contact record is absolute — somebody has asked us to stop,
    and no amount of deal value makes ignoring that acceptable. Consent is softer and depends on the
    org: a tenant under an opt-in regime turns the consent rule on, and a withdrawn consent then
    reads exactly like a do-not-contact, while a consent nobody has recorded reads as a concern
    because "not on file" is usually a data-quality gap rather than a refusal.

    Absence of a do-not-contact flag produces nothing at all. The overwhelming majority of accounts
    have no such record, and a "we checked and it was fine" observation on every one of them would
    bury the handful that matter.
    """

    plugin_id = "contact_permission"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        return tuple(item for item in (self._do_not_contact(view), self._consent(view))
                     if item is not None)

    def _do_not_contact(self, view: UnitView) -> Observation | None:
        field = _config_field(view, "do_not_contact_field", "contact.do_not_contact")
        raw = fact_value(view.request, field)
        if raw is None:
            return None                     # no record; not evidence of a record saying "yes"
        flagged = raw is True or (isinstance(raw, str) and raw.strip().lower() in _TRUE_TEXT)
        if not flagged:
            return None                     # an evidenced "no": the rule has nothing to add
        return Observation(
            plugin_id=self.plugin_id,
            kind="policy.do_not_contact",
            metrics={"blocking_bp": BLOCKING_SEVERITY_BP},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("do_not_contact_on_record",),
        )

    def _consent(self, view: UnitView) -> Observation | None:
        if not _config_flag(view, "require_contact_consent", False):
            return None                     # this org does not operate an opt-in rule
        field = _config_field(view, "consent_status_field", "contact.consent_status")
        status = _text_fact(view, field)
        if status and status in _config_texts(view, "consent_granted_values",
                                              ("granted", "opt_in", "subscribed")):
            return None
        revoked = _config_texts(view, "consent_revoked_values",
                                ("revoked", "opt_out", "unsubscribed", "withdrawn"))
        if status and status in revoked:
            # A withdrawn consent is a refusal on the record, which is the do-not-contact rule
            # wearing a different field name.
            return Observation(
                plugin_id=self.plugin_id,
                kind="policy.consent_revoked",
                metrics={"blocking_bp": BLOCKING_SEVERITY_BP},
                evidence_ids=evidence_ids(view.request, field),
                reason_codes=("contact_consent_revoked",),
            )
        return Observation(
            plugin_id=self.plugin_id,
            kind="policy.consent_missing",
            metrics={"concern_bp": _config_bp(view, "missing_consent_concern_bp", 3_000)},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=("contact_consent_not_on_record",),
        )


class TimingRulePlugin:
    """The organisation has declared when it does and does not communicate.

    Distinct from `core.scheduling`, which reads timing constraints out of the *situation* — their
    meeting, their out-of-office, the gap since we last wrote. These are constraints the business
    imposes on itself regardless of what the counterparty is doing: a close-period communications
    freeze, a company shutdown week, the working hours it publishes.

    A declared blackout is a breach, because somebody in the business took the trouble to write the
    date down and the whole point of doing so is that nothing goes out on it. Being outside working
    hours is a concern: a message drafted at 21:00 is not misconduct, it is a thing that should
    usually wait until morning, and turning it into a prohibition would silently make the system
    inert for two-thirds of every day.
    """

    plugin_id = "timing_rules"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        return tuple(item for item in (self._blackout(view), self._working_hours(view))
                     if item is not None)

    def _blackout(self, view: UnitView) -> Observation | None:
        declared = _config_texts(view, "blackout_dates", ())
        if not declared:
            return None
        for item in declared:
            try:
                date.fromisoformat(item)
            except ValueError as exc:
                raise ValueError("blackout_dates must be ISO-8601 calendar dates") from exc
        today = _local_time(view).date().isoformat()
        if today not in declared:
            return None
        return Observation(
            plugin_id=self.plugin_id,
            kind="policy.blackout",
            metrics={"blocking_bp": BLOCKING_SEVERITY_BP},
            reason_codes=("inside_declared_blackout",),
        )

    def _working_hours(self, view: UnitView) -> Observation | None:
        start = _config_hour(view, "working_hours_start_hour")
        end = _config_hour(view, "working_hours_end_hour")
        if start is None or end is None:
            return None                     # no published working day to be outside of
        moment = _local_time(view)
        working_days = _config_weekdays(view, "working_days", (0, 1, 2, 3, 4))
        # An overnight window (22:00–06:00, e.g. an operations desk) is a legitimate working day and
        # wraps past midnight, so the comparison flips rather than failing shut.
        inside_hours = start <= moment.hour < end if start < end else (
            moment.hour >= start or moment.hour < end)
        if inside_hours and moment.weekday() in working_days:
            return None
        return Observation(
            plugin_id=self.plugin_id,
            kind="policy.outside_working_hours",
            metrics={"concern_bp": _config_bp(view, "outside_hours_concern_bp", 3_000),
                     "local_hour": moment.hour,
                     "local_weekday": moment.weekday()},
            reason_codes=("outside_declared_working_hours",),
        )


class PolicyUnit(ReasoningUnit):
    """Optimization · what the organisation forbids or requires in this situation.

    Publishes a compliance reading and the counts behind it. It never publishes `confidence_bp`,
    `urgency_bp` or `priority_override_bp` — those belong to `core.confidence` and `core.priority`,
    and a policy unit that moved them would re-score every capability in the roster every time a
    customer edited their handbook.
    """

    unit_id = "core.policy"
    version = "1.0.0"
    category = UnitCategory.OPTIMIZATION
    publishes = ("compliance_bp", "policy_concerns", "policy_violations", "rules_triggered")
    plugins = (ApprovalThresholdPlugin(), ContactPermissionPlugin(), TimingRulePlugin())

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """Compliance is a cliff for breaches and a slope for concerns.

        A single breached rule takes `compliance_bp` to zero outright. Organisation policy is not a
        score to be traded against upside — being 70% compliant with a do-not-contact record is not
        a softer version of complying with it, so nothing else in the ledger may dilute it.

        Concerns accumulate, because three unverifiable things are a worse evidential position than
        one, but they stop at a configured floor. That floor is the line between "we cannot fully
        show this is allowed" and "this is forbidden": only a real breach is permitted to reach the
        bottom, so a stack of soft concerns can never impersonate a prohibition downstream.
        """
        breaches = [item for item in observations if "blocking_bp" in item.metrics]
        concerns = [item for item in observations if "concern_bp" in item.metrics]
        floor = _config_bp(view, "soft_compliance_floor_bp", 2_500)
        if breaches:
            compliance = 0
        else:
            penalty = sum(int(item.metrics["concern_bp"]) for item in concerns)
            compliance = max(floor, clamp_bp(10_000 - penalty))
        return {"compliance_bp": compliance,
                "policy_violations": len(breaches),
                "policy_concerns": len(concerns),
                "rules_triggered": len(observations)}

    def _checks(self, view: UnitView,
                observations: Sequence[Observation]) -> tuple[CandidateCheck, ...]:
        """Attach each triggered rule to the plays it actually governs.

        Breaches fail closed with ELIMINATE — that is the whole reason this unit exists, and it is
        the one place in Part 2 where a unit is allowed to remove an option, because "the business
        forbids this" is not a trade-off the Decision Maker gets to weigh. Concerns emit WARN and
        leave the play in contention with the reason attached.

        A play the rule does not reach gets no check at all rather than a PASS. A do-not-contact
        record is silent about logging an internal note, and recording a pass would suggest this
        unit had examined a question it never asked.

        Plays are iterated in play_id order and rules in plugin order so the emitted sequence — and
        every hash taken over it — is a property of the manifest, not of iteration order.
        """
        ordered = sorted(observations, key=lambda item: (item.plugin_id, item.kind))
        checks: list[CandidateCheck] = []
        for play in sorted(view.request.capability.plays, key=lambda item: item.play_id):
            for item in ordered:
                if not _RULE_REACH[item.plugin_id](play):
                    continue
                breach = "blocking_bp" in item.metrics
                detail = dict(item.metrics)
                detail["rule"] = item.kind
                checks.append(CandidateCheck(
                    play_id=play.play_id,
                    stage=POLICY_STAGE,
                    outcome=CheckOutcome.ELIMINATE if breach else CheckOutcome.WARN,
                    reason_code=item.reason_codes[0],
                    evaluator_id=self.unit_id,
                    evaluator_version=self.version,
                    detail=detail,
                ))
        return tuple(checks)

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """`matched` means organisation policy has something to say about this situation.

        It is not an instruction and not a verdict on the work: a matched policy unit alongside a
        matched opportunity unit is the ordinary case where a genuinely valuable action needs a
        signature first. What the reader needs is the rule, its severity, and the evidence — which
        is why every triggered rule becomes a finding whether or not the threshold was crossed.
        """
        threshold = _config_bp(view, "compliance_threshold_bp", 8_000)
        constrained = metrics["policy_violations"] > 0 or metrics["compliance_bp"] < threshold
        codes = {code for item in observations for code in item.reason_codes}
        if metrics["policy_violations"]:
            codes.add("organisation_policy_violated")
        elif metrics["policy_concerns"]:
            codes.add("organisation_policy_concern")
        else:
            # Say it out loud. A silent result is otherwise indistinguishable from a unit that was
            # never configured with any rules, and those are very different assurances.
            codes.add("organisation_policy_clear")
        findings = [Finding(
            finding_id=f"policy.{item.kind.split('.', 1)[1]}",
            kind="policy",
            matched=True,
            metrics=item.metrics,
            evidence_ids=item.evidence_ids,
            reason_codes=item.reason_codes,
        ) for item in observations]
        findings.append(Finding(
            finding_id="policy.compliance",
            kind="policy",
            matched=constrained,
            metrics=dict(metrics),
            reason_codes=tuple(sorted(codes)),
        ))
        return Verdict(
            matched=constrained,
            metrics=dict(metrics),
            findings=tuple(findings),
            checks=self._checks(view, observations),
            reason_codes=tuple(sorted(codes)),
        )


__all__ = ["ApprovalThresholdPlugin", "BLOCKING_SEVERITY_BP", "ContactPermissionPlugin",
           "POLICY_STAGE", "PolicyUnit", "TimingRulePlugin"]
