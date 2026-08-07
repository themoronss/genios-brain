"""Category 1 · Situation Understanding — the Constraint Unit.

Answers one question: *what is this situation not allowed to do?*

Every other unit in Layer 4 measures something — how late, how big, how risky.  This one measures
nothing.  It reads the policies the capability declared and the preconditions the play author wrote,
and for each declared play it emits a row saying whether that play is still on the table.  Those
rows are the fail-closed gate of the whole system: an ``ELIMINATE`` outcome removes a candidate
before ranking ever sees it, and `reason/store.py` refuses to persist a decision whose selected play
does not carry exactly one passing check per declared policy, evaluated by *this* unit at the
version the capability declared.  `reason/authority.py` re-proves the same thing in SQL on every
downstream read.

That external re-verification is why this unit's output shape is frozen far harder than a metric is.
A check row is a five-part claim — ``stage``, ``outcome``, ``reason_code``, ``evaluator_id``,
``evaluator_version`` — plus a ``detail`` mapping that an auditor reads to understand *why*.  Two
independent re-provers know those exact strings.  Changing one is not a refactor; it is a schema
migration with a replay break attached.

Three seams, matching the three questions a gate actually asks, and matching the ``stage`` values
the re-provers index on:

* **Policy** (`PolicyEnforcementPlugin`) — what the capability as a whole has forbidden: mutation
  when the capability is read-only, ungrounded action when evidence is required, and the tenant's
  own hard block list, which can retire a play by id without touching authored expertise.
* **Permission** (`PermissionVerificationPlugin`) — who is allowed to be affected: whether a play
  that acts declares a human approval boundary, and whether a play that reaches an external party
  guards that reach behind a verified-recipient precondition.
* **Precondition** (`PreconditionPlugin`) — what the play itself said must be true before it is
  eligible, evaluated against the frozen snapshot.

Two properties are load-bearing and easy to break:

**Emission order is exact.**  The checks come out grouped by play in capability declaration order,
and within a play in a fixed slot order (read-only, human approval, evidence, recipient, then
preconditions by authored index), with the tenant block list last.  The order is part of the
result's semantic hash, so it cannot be a by-product of which plugin happened to run first.  Each
plugin therefore stamps every row with an explicit ordering key and the unit sorts on it — a total
order that is a property of the *claim*, not of registration.

**The gate always runs.**  It never refuses for thin context.  A missing precondition field is not
a reason to abstain; it is precisely the finding this unit exists to report, as an ``ELIMINATE`` row
that names the absent field.  A unit that returned INSUFFICIENT_CONTEXT here would silently drop the
gate rather than close it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CheckOutcome,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
)

from ..unit import Observation, ReasoningUnit, UnitCategory, UnitView, Verdict
from .common import decimal, fact_value

#: Identity, in one place.  The plugins stamp every row with these rather than reaching for the
#: capability's declared spec: `store.py` compares `evaluator_version` against the *declared* spec
#: version, so a unit that stamped rows with whatever version the manifest happened to name would
#: make that comparison vacuous instead of a proof.
CONSTRAINT_UNIT_ID = "core.constraint"
CONSTRAINT_UNIT_VERSION = "1.0.0"

#: Ordering groups.  Per-play rows come first, then the tenant block list, exactly as authored.
_GROUP_PLAY = 0
_GROUP_TENANT = 1

#: Slot order inside one play.  Capability-wide policy is asked before play-authored preconditions,
#: because "this capability may not act at all" is a bigger statement than "this play needs a date".
_SLOT_READ_ONLY = 0
_SLOT_HUMAN_APPROVAL = 1
_SLOT_EVIDENCE = 2
_SLOT_RECIPIENT = 3
_SLOT_PRECONDITION = 4

#: Field suffixes that count as a verified-recipient guard.  Authors name the fact differently per
#: CRM; what matters is that the play refuses to run unless somebody verified the counterparty.
_RECIPIENT_GUARD_SUFFIXES = (
    ".verified_recipient",
    ".recipient_verified",
    ".stakeholder_verified",
    "_stakeholder_verified",
)

#: Equality operators.  A guard must assert the verification *is* true; ``>=`` on a boolean is not
#: a guard, it is an accident.
_EQUALITY_OPERATORS = frozenset({"=", "==", "eq"})

#: One check plus its position in the unit's total emission order.
_KeyedCheck = tuple[tuple[int, int, int, int], CandidateCheck]


def _compare(actual, operator: str, expected) -> bool:
    """Evaluate one authored precondition operator.

    Numeric comparison goes through `Decimal` rather than float so that "value >= 50000" resolves
    identically on every machine and in replay.  A value that will not parse as a number fails the
    comparison rather than raising: an unparseable fact is not a satisfied precondition.  An
    *unsupported operator* does raise, because that is an authoring fault in Layer 3 and silently
    treating it as a failure would hide a broken play behind a plausible-looking elimination.
    """
    if operator in {"=", "==", "eq"}:
        return actual == expected
    if operator in {"!=", "ne"}:
        return actual != expected
    if operator == "in":
        return actual in expected if isinstance(expected, (tuple, list, set, frozenset)) else False
    if operator in {">", ">=", "<", "<="}:
        try:
            left, right = decimal(actual, "precondition actual"), decimal(expected, "precondition expected")
        except ValueError:
            return False
        return {">": left > right, ">=": left >= right,
                "<": left < right, "<=": left <= right}[operator]
    raise ValueError(f"unsupported precondition operator: {operator}")


def _grounded_evidence_ids(view: UnitView) -> set[str]:
    """Evidence ids that a dependency actually *used*, restricted to this exact snapshot.

    Merely carrying an unrelated `EvidenceRef` is not grounding.  For the `evidence_required` policy
    to pass, some upstream unit must have cited an evidence item that exists in the frozen context
    this decision is being made from — otherwise a stale citation from another run would satisfy the
    policy without anything in *this* situation supporting the action.
    """
    request = view.request
    context_evidence_ids = {item.evidence_id for item in request.context.evidence}
    return {
        evidence_id
        for result in view.prior.values()
        for evidence_id in (
            result.evidence_ids
            + tuple(evidence_id for finding in result.findings
                    for evidence_id in finding.evidence_ids)
            + tuple(evidence_id for adjustment in result.adjustments
                    for evidence_id in adjustment.evidence_ids)
        )
        if evidence_id in context_evidence_ids
    }


def _check(play_id: str, stage: str, passed: bool, pass_code: str, fail_code: str,
           detail: Mapping[str, Any] | None = None) -> CandidateCheck:
    """Build one gate row.  Pass and fail carry *different* reason codes on purpose: a downstream
    re-prover looks for the exact passing code, so "not eliminated" can never be mistaken for
    "affirmatively allowed"."""
    return CandidateCheck(
        play_id=play_id,
        stage=stage,
        outcome=CheckOutcome.PASS if passed else CheckOutcome.ELIMINATE,
        reason_code=pass_code if passed else fail_code,
        evaluator_id=CONSTRAINT_UNIT_ID,
        evaluator_version=CONSTRAINT_UNIT_VERSION,
        detail=dict(detail or {}),
    )


class _ConstraintPlugin:
    """Shared shape for the three gate plugins.

    A gate plugin's contribution is a set of *rows*, not a number, so it implements `checks()` as
    its real work and derives the framework's `Observation` from it.  The observation carries only
    counts: this unit publishes no metrics (see `ConstraintUnit.calculate`), and an observation that
    tried to carry a check's `detail` mapping would be lying about the framework's integer-only
    metric contract.
    """

    plugin_id = ""
    kind = ""

    def checks(self, view: UnitView) -> tuple[_KeyedCheck, ...]:
        raise NotImplementedError

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        rows = self.checks(view)
        if not rows:
            return ()
        eliminated = sum(1 for _, check in rows if check.outcome == CheckOutcome.ELIMINATE)
        return (Observation(
            plugin_id=self.plugin_id,
            kind=self.kind,
            metrics={"checks_emitted": len(rows), "eliminated": eliminated},
        ),)


class PolicyEnforcementPlugin(_ConstraintPlugin):
    """What the capability — and the tenant — have forbidden outright.

    Two capability policies land here because both are statements about the capability rather than
    about any one play:

    * `read_only` — the capability was deployed in an observe-only posture, so a play that mutates
      anything is not merely risky, it is out of scope.
    * `evidence_required` — nothing may be recommended that no upstream unit could ground in this
      snapshot.  The check is capability-wide (one grounding fact serves every play), which is why
      the same verdict is stamped onto each play's row rather than recomputed per play.

    The tenant block list is the third: a hard, id-level retirement that a tenant can apply without
    editing authored expertise, emitted last so the audit trail reads "here is what the capability
    decided, and here is what the tenant then removed".  It is deliberately unconditional — a
    blocked id is eliminated whether or not the capability still declares that play.
    """

    plugin_id = "policy_enforcement"
    kind = "constraint.policy"

    def checks(self, view: UnitView) -> tuple[_KeyedCheck, ...]:
        request = view.request
        policies = set(request.capability.policies)
        read_only_declared = "read_only" in policies
        evidence_declared = "evidence_required" in policies
        rows: list[_KeyedCheck] = []

        # Computed once: grounding is a property of the run, not of the play under test.
        grounded = _grounded_evidence_ids(view) if evidence_declared else set()
        evidence_present = bool(grounded)
        evidence_detail = {"context_evidence_count": len(request.context.evidence),
                           "used_evidence_count": len(grounded)}

        for play_index, play in enumerate(request.capability.plays):
            if read_only_declared:
                rows.append((
                    (_GROUP_PLAY, play_index, _SLOT_READ_ONLY, 0),
                    _check(play.play_id, "policy", play.read_only,
                           "read_only_policy_pass", "read_only_policy",
                           {"required": True, "play_read_only": play.read_only}),
                ))
            if evidence_declared:
                rows.append((
                    (_GROUP_PLAY, play_index, _SLOT_EVIDENCE, 0),
                    _check(play.play_id, "policy", evidence_present,
                           "evidence_policy_pass", "evidence_required", evidence_detail),
                ))

        # Tenant policy inputs can hard-block a play by ID without changing authored expertise.
        # Iterated in authored sequence: this is a list in config, and a list survives the audit
        # store's JSON round-trip with its order intact.
        for block_index, play_id in enumerate(tuple(view.spec.config.get("blocked_play_ids") or ())):
            rows.append((
                (_GROUP_TENANT, block_index, 0, 0),
                CandidateCheck(str(play_id), "policy", CheckOutcome.ELIMINATE,
                               "tenant_policy_block", CONSTRAINT_UNIT_ID,
                               CONSTRAINT_UNIT_VERSION),
            ))
        return tuple(rows)


class PermissionVerificationPlugin(_ConstraintPlugin):
    """Who is allowed to be affected, and who had to say yes first.

    Both policies here are about *reach* rather than about scope, and both fail closed on an
    omission rather than an assertion — a play that simply never mentions approval or recipient
    verification is eliminated, because the absence of a declaration is exactly the state this gate
    exists to catch.

    * `human_approval_required` — the play must declare the boundary, either as the typed
      `execution_boundary` metadata or as the `human_approval` tag.  Two spellings are accepted
      because both predate the policy and both are load-bearing in shipped packs.
    * `no_unverified_recipient` — a play that reaches an external party must be guarded by a
      precondition asserting that the recipient was verified.  A play that reaches nobody external
      passes trivially.  The metadata is indexed rather than `.get()`-ed on purpose: capability
      validation already requires the typed effect declaration, so a malformed object crossing that
      boundary should fail loudly here rather than be read as "no external reach".
    """

    plugin_id = "permission_verification"
    kind = "constraint.permission"

    @staticmethod
    def _approval_declared(play: PlayDefinition) -> tuple[bool, Any]:
        boundary = play.metadata.get("execution_boundary")
        return (boundary == "human_approval_required" or "human_approval" in play.tags), boundary

    @staticmethod
    def _verification_guards(play: PlayDefinition) -> tuple[Mapping[str, Any], ...]:
        return tuple(condition for condition in play.preconditions
                     if str(condition.get("field") or "").endswith(_RECIPIENT_GUARD_SUFFIXES)
                     and condition.get("value") is True
                     and str(condition.get("op") or "") in _EQUALITY_OPERATORS)

    def checks(self, view: UnitView) -> tuple[_KeyedCheck, ...]:
        request = view.request
        policies = set(request.capability.policies)
        approval_declared_policy = "human_approval_required" in policies
        recipient_policy = "no_unverified_recipient" in policies
        rows: list[_KeyedCheck] = []

        for play_index, play in enumerate(request.capability.plays):
            if approval_declared_policy:
                approval_declared, boundary = self._approval_declared(play)
                rows.append((
                    (_GROUP_PLAY, play_index, _SLOT_HUMAN_APPROVAL, 0),
                    _check(play.play_id, "permission", approval_declared,
                           "human_approval_boundary_pass", "human_approval_boundary_missing",
                           {"execution_boundary": boundary,
                            "human_approval_tag": "human_approval" in play.tags}),
                ))
            if recipient_policy:
                recipient_required = play.metadata["external_recipient_required"]
                guards = self._verification_guards(play)
                guarded = not recipient_required or bool(guards)
                rows.append((
                    (_GROUP_PLAY, play_index, _SLOT_RECIPIENT, 0),
                    _check(play.play_id, "permission", guarded,
                           "verified_recipient_guard_pass", "verified_recipient_guard_missing",
                           {"external_recipient_required": recipient_required,
                            "guard_count": len(guards)}),
                ))
        return tuple(rows)


class PreconditionPlugin(_ConstraintPlugin):
    """What the play author said must already be true.

    Preconditions are the only part of the gate that is authored per play rather than per
    capability, and the only part that reads the snapshot.  Each condition names a field, an
    operator, and an expected value; `neighbor` selects the neighbour fact space instead of the root
    entity's.

    Absence is handled before comparison, not inside it, because "the field is missing" and "the
    field is present and smaller" are different facts and an auditor needs to tell them apart from
    the `detail` alone.  `exists`/`absent` are assertions *about* presence; every other operator
    fails closed when the field is missing, since a comparison against nothing is not a satisfied
    condition.  The row records the authored index, so a play with three conditions produces three
    independently attributable rows rather than one aggregate verdict.
    """

    plugin_id = "precondition"
    kind = "constraint.precondition"

    @staticmethod
    def evaluate_condition(request: ReasoningRequest,
                           condition: Mapping[str, Any]) -> tuple[bool, str, bool, str, Any, Any]:
        """Resolve one condition to (passed, field, neighbor, operator, expected, actual)."""
        field = str(condition.get("field") or "")
        neighbor = bool(condition.get("neighbor", False))
        exists = field in (request.context.neighbor_facts if neighbor else request.context.facts)
        operator = str(condition.get("op") or "exists")
        expected = condition.get("value")
        if operator == "exists":
            passed = exists
            actual = fact_value(request, field, neighbor=neighbor) if exists else None
        elif operator == "absent":
            passed = not exists
            actual = fact_value(request, field, neighbor=neighbor) if exists else None
        elif not exists:
            passed, actual = False, None
        else:
            actual = fact_value(request, field, neighbor=neighbor)
            passed = _compare(actual, operator, expected)
        return passed, field, neighbor, operator, expected, actual

    def checks(self, view: UnitView) -> tuple[_KeyedCheck, ...]:
        request = view.request
        rows: list[_KeyedCheck] = []
        for play_index, play in enumerate(request.capability.plays):
            for index, condition in enumerate(play.preconditions):
                passed, field, neighbor, operator, expected, actual = self.evaluate_condition(
                    request, condition)
                rows.append((
                    (_GROUP_PLAY, play_index, _SLOT_PRECONDITION, index),
                    _check(play.play_id, "precondition", passed,
                           "precondition_pass", "precondition_failed",
                           {"index": index, "field": field, "neighbor": neighbor,
                            "operator": operator, "expected": expected, "actual": actual}),
                ))
        return tuple(rows)


class ConstraintUnit(ReasoningUnit):
    """Situation Understanding · what this situation is not allowed to do."""

    unit_id = CONSTRAINT_UNIT_ID
    version = CONSTRAINT_UNIT_VERSION
    category = UnitCategory.SITUATION_UNDERSTANDING
    #: A ceiling, not a promise.  `publishes` is the set of metric names this unit is *permitted*
    #: to emit; v1.0.0 emits none of them (see `calculate`).  The names are declared anyway so they
    #: are reserved against collision — no other unit may claim them — and so that the day a gate
    #: summary is genuinely wanted, publishing it is a deliberate, reviewable, version-bumped
    #: change rather than a metric that appears in the decision record by accident.
    publishes: tuple[str, ...] = ("constraint_check_count", "constraint_elimination_count")
    plugins = (PolicyEnforcementPlugin(), PermissionVerificationPlugin(), PreconditionPlugin())

    # -- stage overrides, each because the base behaviour would change the emitted result ---------

    def validate(self, view: UnitView) -> None:
        """Never refuse.

        The base validator raises `MissingContextError` for absent `required_fields`, which the
        orchestrator turns into an INSUFFICIENT_CONTEXT result carrying no checks.  For a gate that
        would be backwards: thin context is the condition under which the gate matters most, and a
        missing precondition field is reported as an ELIMINATE row naming the field, not as an
        abstention.  Removing the gate because the room is dark is not fail-closed.
        """

    def retrieve(self, request: ReasoningRequest, spec: ReasonerSpec,
                 prior: Mapping[str, ReasonerResult]) -> UnitView:
        """The whole snapshot, and no evidence citation.

        Two departures from the base retriever, both forced:

        *No fact pre-selection.*  Precondition fields are authored per play in Layer 3 and are not
        knowable from `required_fields`, so any narrowing here would be a window that lies about
        what the unit actually reads.  The plugins read `request.context` directly.

        *No evidence ids.*  This unit cites nothing.  Its output is check rows, and `store.py` and
        `authority.py` re-verify those rows directly against the capability's declared policies —
        attaching evidence ids would add unproven provenance to a result whose entire value is that
        every part of it is independently re-provable.
        """
        return UnitView(request=request, spec=spec, prior=prior)

    # -- analysis --------------------------------------------------------------------------------

    def calculate(self, view: UnitView,
                  observations: Sequence[Observation]) -> Mapping[str, int]:
        """No metrics.

        Deliberate, not an omission.  A gate's answer is a set of per-play rows; any scalar summary
        of them ("3 eliminations") would be a number downstream units could weigh, and weighing a
        constraint is exactly how a hard block turns into a soft penalty.  The observations carry
        those counts for testing and tracing, and `publishes` reserves names for them, but the
        result deliberately carries none — an empty metrics mapping is part of this unit's frozen
        v1.0.0 output.
        """
        return {}

    def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                         observations: Sequence[Observation]) -> Verdict:
        """Assemble every plugin's rows into the unit's one total emission order.

        Plugins are asked in `plugin_id` order and their rows merged by explicit ordering key, so
        the sequence is a property of the claim (which play, which slot, which authored index)
        rather than of registration order or of how many rows a plugin happened to produce.  The key
        is unique per row, so the sort is total and the resulting hash is stable.

        `matched` stays None: this unit makes no single true/false claim about the situation.  Some
        plays may be blocked and others clear, and collapsing that into one boolean would invent a
        verdict the rows do not support.  The single reason code says only that the gate ran — what
        it *decided* is in the rows, where the re-provers look.
        """
        rows: list[_KeyedCheck] = []
        for plugin in sorted(self.plugins, key=lambda item: item.plugin_id):
            rows.extend(plugin.checks(view))
        rows.sort(key=lambda item: item[0])
        return Verdict(
            matched=None,
            metrics={},
            checks=tuple(check for _, check in rows),
            reason_codes=("constraints_evaluated",),
        )


#: The name the roster imports.  Kept as the class's public identity because
#: `reasoners/__init__.py`, the capability manifests, and the persisted traces all name it.
ConstraintReasoner = ConstraintUnit

__all__ = ["CONSTRAINT_UNIT_ID", "CONSTRAINT_UNIT_VERSION", "ConstraintReasoner", "ConstraintUnit",
           "PermissionVerificationPlugin", "PolicyEnforcementPlugin", "PreconditionPlugin"]
