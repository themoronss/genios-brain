"""CLG-06 · the rule compiler — authored corpus rules become checks Layer 4 actually runs.

THE DEFECT THIS CLOSES. `Domain Expertise/` carries 49 `rules/` artifacts with a typed `when`,
a `then`, a `severity` and an `enforced_by: L4_constraint` declaration — and until this module
existed no parser for any of it. `reason/adapters/expertise.py` read `organization_rules` and
nothing else, so every one of those rules was retrieved, content-hashed into the manifest version,
and dropped. A rule marked `severity: blocking` blocked nothing, and a prescription could violate
the corpus's own doctrine while the compile reported success. That is Law 4's exact failure mode:
knowledge is not shipped until Layer 4 can consume it, TYPED.

THE FIVE STEPS (doc 03, L3.3-U1), and where each one lives:

  1. PARSE     `translate_condition` maps one authored predicate onto ONE node of the L2 cohort
               predicate grammar, and `cohort.parse_predicate` — imported, never reimplemented —
               is what actually decides whether the result is legal. There is no second grammar
               and no `eval`: an operator is a token from a closed enum, a fact is a name from a
               closed registry, and a value is normalised by the fact's own kind.
  2. BIND      `ContextAdapter.matches` — the compiler's three-state predicate evaluator, reused
               rather than copied, because a second evaluator is a second opinion about what
               UNKNOWN means.
  3. EMIT      `blocking` + TRUE  -> the plays in the rule's authored scope are eliminated, and
               the rule id travels with the elimination.
               `warning`  + TRUE  -> recorded on the decision, eliminating nothing.
  4. UNKNOWN   neither fires nor blocks, and NAMES the predicate it could not read. A rule whose
               `when` is UNKNOWN is `unevaluable`; the contract refuses an `unevaluable` record
               that cannot say what was missing, which is what stops "unevaluable" from becoming
               a polite spelling of "guessed".
  5. RECEIPT   every rule is either compiled or refused with a named, counted reason.

WHAT A BLOCKING RULE ELIMINATES, stated plainly because it is the one judgement here that is not
mechanical. An authored rule's `when` is a predicate over the SITUATION, not over a candidate —
`urgency-must-belong-to-the-buyer` fires on "open deal, proposal sent, no buyer-owned date", which
describes the deal and not any particular play. So the question "which candidate violates it?" is
answered by the rule's own declared SCOPE: `identity.scope: capability` + `owner_capability` says
which capability this doctrine governs, and the plays compiled from that capability's playbooks
are exactly the recommendations it governs. All 31 of the corpus's `L4_constraint` rules are
capability-scoped today, so this covers the enforceable corpus completely. A core-scoped
`L4_constraint` rule is REFUSED with `rule_scope_not_capability` rather than being given an
invented blast radius — eliminating every play in the package because a rule declined to say what
it governs is not enforcement, it is an outage.

ZERO LLM, ZERO CLOCK, ZERO DB. Everything here is a pure function of (package, adapter), and
`test_rule_compiler.py` reads this module's own source to prove the first of those.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, DecimalException
from typing import Any

from genios_engine.context.analytic.cohort import (
    COHORT_NODE_TYPES,
    FactDefinition,
    FactKind,
    FactRegistry,
    PredicateError,
    default_fact_registry,
    parse_predicate,
    predicate_json,
)
from genios_engine.contracts.domain_expertise import (
    PREDICATE_GRAMMAR,
    citation_statement_hash,
    require_compiled_constraint,
    require_constraint_application,
)
from genios_engine.packs.compiler.context_adapter import ContextAdapter, PredicateState

# =================================================================================================
# THE AUTHORED VOCABULARY, AND ITS TRANSLATION INTO THE ONE PREDICATE GRAMMAR
# =================================================================================================

#: The corpus's observation kinds — `Domain Expertise/_schema/vocabulary.yaml`'s
#: `substrate.obs_kinds`, which `_tools/validate.py` already refuses an authored `has_obs` outside.
#: Restated here rather than read from the corpus at runtime for two reasons: `reason/` is Layer 4
#: and must not open Layer 3's authoring tree at request time, and a registry built from whatever
#: happens to be on disk is not a closed set. `test_rule_compiler.py` asserts this tuple still
#: covers every `has_obs`/`no_obs` the shipped rules name, so drift fails a test instead of
#: silently turning a rule into `rule_fact_unregistered`.
OBSERVATION_KINDS: tuple[str, ...] = (
    "approval_blocked", "approval_granted", "approval_requested", "budget_approved",
    "budget_freeze", "buying_intent", "champion_change", "champion_engaged", "churn_risk",
    "closed_lost_mention", "competitor", "contract_requested", "deadline_stated",
    "decision_deferred", "demo_requested", "diligence_started", "discount_pressure",
    "document_sent", "followup_sent", "going_dark", "information_requested", "introduction",
    "intro_made", "intro_requested", "investor_update_sent", "invoice_sent", "legal_review",
    "meeting_cancelled", "meeting_request", "meeting_scheduled", "negative_reply",
    "next_step_agreed", "objection", "objection_authority", "objection_integration",
    "objection_price", "objection_security", "objection_timing", "pass_received",
    "payment_confirmed", "payment_overdue", "positive_reply", "price_pushback",
    "pricing_discussed", "proposal_sent", "question", "security_review_started",
    "stakeholder_added", "stakeholder_left", "timeline_slip", "verbal_yes",
)

#: How an observation kind is spelled as a registered FACT. An observation is not a graph fact, so
#: it gets its own namespace rather than colliding with one: `obs.proposal_sent` is unambiguous
#: about which space it reads, and `exists`/`missing` on a FLAG is the honest rendering of
#: `has_obs`/`no_obs` (the observation is present, or it is not).
OBSERVATION_PREFIX = "obs."
NEIGHBOR_OBSERVATION_PREFIX = "nbr_obs."

#: Fact paths the corpus's authored predicates name that the cohort registry does not carry,
#: because a cohort is a population of nodes and these describe a matter, a meeting or a period.
#: Each one is named individually — there is no pattern-matched fallback that would let a typo
#: register itself as a fact and evaluate to an empty answer.
L3_FACTS: tuple[FactDefinition, ...] = (
    FactDefinition("edge_count", FactKind.NUMBER, frozenset(COHORT_NODE_TYPES),
                   "how many counterparties are on this matter? — the authored `fn: edge_count`"),
    FactDefinition("commitment.status", FactKind.TEXT, frozenset(COHORT_NODE_TYPES),
                   "what state is the open commitment in?"),
    FactDefinition("meeting.start_at", FactKind.MOMENT, frozenset(COHORT_NODE_TYPES),
                   "when does the meeting start?"),
    FactDefinition("meeting.end_at", FactKind.MOMENT, frozenset(COHORT_NODE_TYPES),
                   "when did the meeting end?"),
    FactDefinition("meeting.attended", FactKind.FLAG, frozenset(COHORT_NODE_TYPES),
                   "did the meeting actually happen with someone in it?"),
    FactDefinition("party.role", FactKind.TEXT, frozenset(COHORT_NODE_TYPES),
                   "what role does this party hold on the matter?"),
    FactDefinition("period.events_this_window", FactKind.NUMBER, frozenset(COHORT_NODE_TYPES),
                   "how much happened in this period?"),
    FactDefinition("period.counterparties_awaiting_us", FactKind.NUMBER,
                   frozenset(COHORT_NODE_TYPES),
                   "how many counterparties are waiting on us this period?"),
)

#: Authored operator -> cohort operator. The authored spelling is doc-04's closed
#: `predicate_ops` list; the cohort spelling is `PredicateOp`. Two closed sets, one table, no
#: free text in between.
AUTHORED_OPERATORS: Mapping[str, str] = {
    "=": "eq", "!=": "ne", "IN": "in", ">": "gt", ">=": "gte", "<": "lt", "<=": "lte",
}

#: `enforced_by` values that mean "Layer 4 stops this". Anything else is enforced by another layer
#: and is refused here BY NAME rather than compiled into a check the author did not ask for.
ENFORCED_BY_L4 = "L4_constraint"

#: The two severities `core.constraint` can express. The corpus also authors `advisory`, which is
#: deliberately NOT mapped onto `warning`: an advisory rule is guidance for a human reviewer, and
#: promoting it to a recorded constraint would put a claim on the decision that its author did not
#: make. It is refused, counted, and visible in the weld report.
BLOCKING = "blocking"
WARNING = "warning"
CONSTRAINT_SEVERITIES_HERE = (BLOCKING, WARNING)

#: Basis-point scale for RATIO facts. `derived.engagement` is stored as a decimal ratio and the
#: cohort grammar normalises it to integer basis points, so an authored threshold of `1` means
#: 10,000bp and not 1bp. Converting through `Decimal` keeps the integer-only doctrine intact.
BP_SCALE = 10_000


class RuleCompileError(ValueError):
    """One authored rule this compiler will not turn into a check, with a NAMED reason.

    The reason is an identifier because it lands in the weld receipt's `refusals`, where the
    contract requires one — a refusal spelled as free prose cannot be counted, and invariant #6 is
    that every refusal is named and counted.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def l3_fact_registry() -> FactRegistry:
    """The closed set of names an authored Layer 3 predicate may reference.

    A FUNCTION, not a module constant, for the reason `cohort.default_fact_registry` gives: a
    shared mutable registry is an import-time side effect waiting to happen. The cohort core facts
    come first so `deal.status` means here exactly what it means in a cohort predicate, then the
    matter/meeting/period facts, then one FLAG per authored observation kind in each of the two
    observation spaces.
    """
    observations = tuple(
        FactDefinition(f"{prefix}{kind}", FactKind.FLAG, frozenset(COHORT_NODE_TYPES), question)
        for prefix, question_template in (
            (OBSERVATION_PREFIX, "does this entity carry a {kind} observation?"),
            (NEIGHBOR_OBSERVATION_PREFIX,
             "does a one-hop neighbour carry a {kind} observation?"),
        )
        for kind in OBSERVATION_KINDS
        for question in (question_template.format(kind=kind),)
    )
    return default_fact_registry().with_definitions(*L3_FACTS, *observations)


def _ratio_bp(value: Any) -> int:
    """An authored ratio threshold in the basis points the cohort grammar compares in.

    `derived.engagement < 1` is authored against a decimal ratio; the registered fact is a RATIO,
    which normalises stored values to basis points. Translating the threshold without scaling it
    would store a tree meaning `< 0.0001` — a predicate that reads correctly and says something
    the author did not. Through `Decimal` so no float ever exists, and refused rather than rounded
    when the scaled value is not a whole number of basis points.
    """
    try:
        scaled = Decimal(str(value)) * BP_SCALE
    except (DecimalException, TypeError, ValueError):
        raise RuleCompileError("rule_ratio_value_unreadable", repr(value)) from None
    if scaled != scaled.to_integral_value():
        raise RuleCompileError("rule_ratio_value_not_basis_points", repr(value))
    return int(scaled)


def _condition_value(registry: FactRegistry, fact: str, raw: Any) -> Any:
    """Scale a RATIO threshold; leave every other kind to `parse_predicate` to normalise."""
    definition = registry.get(fact)
    if definition is None:
        raise RuleCompileError("rule_fact_unregistered", fact)
    if definition.kind is FactKind.RATIO:
        if isinstance(raw, (list, tuple)):
            return [_ratio_bp(item) for item in raw]
        return _ratio_bp(raw)
    return raw


def _threshold_literal(value: Any) -> Any:
    """Refuse the authored `{baseline: …}` threshold form.

    `ContextAdapter` resolves a baseline against the slice at BIND time, which is exactly right for
    evaluation and impossible to store: a predicate tree carrying `{baseline: reply_cadence}` is
    not a comparison, it is an instruction to compute one later, and the stored tree would mean
    different things in different weeks. No shipped rule uses the form; one that did would be
    refused by name rather than compiled into a threshold nobody can read.
    """
    if isinstance(value, Mapping):
        raise RuleCompileError("rule_baseline_threshold_unsupported", str(sorted(value)))
    return value


def translate_condition(condition: Mapping[str, Any], registry: FactRegistry) -> dict[str, Any]:
    """One authored predicate -> one node of the cohort predicate grammar.

    Every form in the corpus's closed `predicate_forms` list is handled or refused by name. The
    two mappings worth reading twice:

    * `{absent: X}` becomes `missing`, and `{exists: X}` becomes `exists`. Those are the grammar's
      own presence operators, so the stored tree says what the author said.
    * `{fn: days_since, path: X, op: "<=", value: N}` becomes `within_days`. That is an exact
      equivalence — "fewer than N days have passed since X" and "X is within N days" are the same
      claim — and it is the ONLY `fn: days_since` form with one, because `within_days` has no
      "longer ago than" counterpart. `>=` is refused rather than inverted into something the
      grammar cannot express.
    """
    keys = set(condition)
    if "exists" in keys:
        return {"fact": str(condition["exists"]), "op": "exists"}
    if "absent" in keys:
        return {"fact": str(condition["absent"]), "op": "missing"}
    if "has_obs" in keys:
        return {"fact": f"{OBSERVATION_PREFIX}{condition['has_obs']}", "op": "exists"}
    if "no_obs" in keys:
        return {"fact": f"{OBSERVATION_PREFIX}{condition['no_obs']}", "op": "missing"}
    if "neighbor_has_obs" in keys:
        return {"fact": f"{NEIGHBOR_OBSERVATION_PREFIX}{condition['neighbor_has_obs']}",
                "op": "exists"}
    if "neighbor_no_obs" in keys:
        return {"fact": f"{NEIGHBOR_OBSERVATION_PREFIX}{condition['neighbor_no_obs']}",
                "op": "missing"}
    if "neighbor_fact" in keys:
        # The neighbour FACT space has no registered names — a cohort compares nodes, not their
        # neighbourhoods — so there is nothing honest to translate this into. Named, not guessed.
        raise RuleCompileError("rule_neighbor_fact_unsupported", str(condition.get("neighbor_fact")))

    function = condition.get("fn")
    if function is None and not condition.get("path"):
        # No keyword form, no fact path, no function: this predicate matches nothing the engine
        # dispatches on, which is the FORM being wrong rather than the operator. Reported as such
        # so the authoring fix is obvious from the receipt alone.
        raise RuleCompileError("rule_predicate_form_unsupported", str(sorted(keys)))
    operator = condition.get("op")
    if operator not in AUTHORED_OPERATORS:
        raise RuleCompileError("rule_operator_unsupported", str(operator))
    if function == "edge_count":
        if "path" in keys:
            raise RuleCompileError("rule_edge_count_takes_no_path", str(condition.get("path")))
        fact = "edge_count"
    elif function in ("days_since", "hours_since"):
        path = str(condition.get("path") or "")
        if not path:
            raise RuleCompileError("rule_elapsed_predicate_needs_a_path", str(function))
        if function != "days_since" or operator != "<=":
            raise RuleCompileError("rule_elapsed_predicate_unsupported",
                                   f"{function} {operator}")
        days = _threshold_literal(condition.get("value"))
        return {"fact": path, "op": "within_days", "value": days}
    elif function is not None:
        raise RuleCompileError("rule_function_unsupported", str(function))
    else:
        fact = str(condition.get("path") or "")
        if not fact:
            raise RuleCompileError("rule_predicate_form_unsupported", str(sorted(keys)))
    value = _condition_value(registry, fact, _threshold_literal(condition.get("value")))
    return {"fact": fact, "op": AUTHORED_OPERATORS[operator], "value": value}


def compile_predicate(when: Sequence[Mapping[str, Any]],
                      registry: FactRegistry | None = None) -> dict[str, Any]:
    """An authored `when` list -> the stored predicate tree, validated by the one grammar.

    The list is a CONJUNCTION — `ContextAdapter.matches` returns FALSE on the first FALSE term —
    so it becomes an `all` group even when it holds one term. A uniform shape is what lets a
    reader (and the weld report) diff two rules without special-casing arity.
    """
    if not when:
        raise RuleCompileError("rule_when_empty")
    registry = registry or l3_fact_registry()
    terms = [translate_condition(condition, registry) for condition in when
             if isinstance(condition, Mapping)]
    if len(terms) != len(when):
        raise RuleCompileError("rule_condition_not_a_mapping")
    try:
        return predicate_json(parse_predicate({"all": terms}, registry=registry))
    except PredicateError as exc:
        raise RuleCompileError("rule_parse_failed", str(exc)) from None


# =================================================================================================
# THE COMPILED RULE, AND WHAT IT DID
# =================================================================================================

@dataclass(frozen=True, slots=True)
class RuleVerdict:
    """One compiled rule, bound against one situation.

    `outcome` is three-valued because predicate evaluation is: `fired` (the `when` is TRUE),
    `satisfied` (FALSE — the situation does not violate this doctrine) and `unevaluable` (UNKNOWN,
    with `missing` naming what could not be read). A blocking rule that is `unevaluable` blocks
    nothing and passes nothing; it is recorded, and that record is the whole of step 4.
    """

    rule_id: str
    severity: str
    outcome: str
    statement: str
    statement_hash: str
    source_ref: str
    owner_capability: str
    missing: tuple[str, ...] = ()
    blocked_play_ids: tuple[str, ...] = ()
    #: WAVE Z5 · doc 06 IN-2's second row: a fired WARNING annotates the candidates it is ABOUT
    #: and eliminates none of them. The scope is resolved exactly as a blocking rule's is — the
    #: plays compiled from the capability this doctrine governs — but it is a SEPARATE field,
    #: because `blocked_play_ids` is what `core.constraint` eliminates from and a warning that
    #: shared it would eliminate a candidate the corpus only cautioned about.
    warned_play_ids: tuple[str, ...] = ()

    @property
    def fired(self) -> bool:
        return self.outcome == "fired"

    @property
    def blocks(self) -> bool:
        return self.fired and self.severity == BLOCKING

    def as_record(self) -> dict[str, Any]:
        """The verdict as the plain mapping the manifest carries. Candidate ids are NOT here —
        they do not exist until the decision does, which is why `constraint_applications` is a
        separate, decision-time function."""
        record: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "outcome": self.outcome,
            "statement": self.statement,
            "statement_hash": self.statement_hash,
            "source_ref": self.source_ref,
            "owner_capability": self.owner_capability,
            "blocked_play_ids": list(self.blocked_play_ids),
        }
        if self.missing:
            record["missing"] = list(self.missing)
        # Written ONLY when a warning actually fired with a scope. The weld's records are hashed
        # into the manifest version, so a key present on every verdict would re-mint the
        # capability version of every welded manifest in the tree for a fact most of them do not
        # have. Conditional inclusion is the same discipline `Finding.value_bp` keeps.
        if self.warned_play_ids:
            record["warned_play_ids"] = list(self.warned_play_ids)
        return record


@dataclass(frozen=True, slots=True)
class CompiledRules:
    """Everything CLG-06 produced for one package, including everything it refused."""

    constraints: tuple[Mapping[str, Any], ...] = ()
    verdicts: tuple[RuleVerdict, ...] = ()
    skipped: Mapping[str, str] = field(default_factory=dict)
    #: Refusal reason -> how many rules it refused. The receipt's `refusals` block, pre-aggregated
    #: here so the reason vocabulary has one owner.
    refusals: Mapping[str, int] = field(default_factory=dict)

    @property
    def fired(self) -> tuple[RuleVerdict, ...]:
        return tuple(v for v in self.verdicts if v.fired)

    @property
    def unevaluable(self) -> tuple[RuleVerdict, ...]:
        return tuple(v for v in self.verdicts if v.outcome == "unevaluable")

    @property
    def blocked_play_ids(self) -> tuple[str, ...]:
        return tuple(sorted({play_id for verdict in self.verdicts if verdict.blocks
                             for play_id in verdict.blocked_play_ids}))


def _identity(record: Mapping[str, Any]) -> Mapping[str, Any]:
    definition = record.get("definition")
    identity = (definition or {}).get("identity") if isinstance(definition, Mapping) else None
    return identity if isinstance(identity, Mapping) else {}


def artifact_class(record: Mapping[str, Any]) -> str:
    """Which of the corpus's five knowledge classes this package entry is.

    Read from `definition.identity.kind`, never from the package entry's own `kind` — the compiler
    stamps every knowledge artifact as `"artifact"` and every business-model overlay as
    `"variant"`, so the package-level field cannot tell a rule from a playbook.
    """
    return str(_identity(record).get("kind") or "")


def play_id_for(artifact_id: str) -> str:
    """The play id `expertise._plays` mints from a playbook id. One spelling, two readers."""
    return str(artifact_id).replace(" ", "_")[:120]


def compile_package_rules(package, adapter: ContextAdapter | None = None, *,
                          declared_play_ids: frozenset[str] | None = None) -> CompiledRules:
    """CLG-06 over one ExpertisePackage. Pure: no clock, no database, no model.

    `adapter` is the compiler's own three-state evaluator over the situation this package was
    compiled for. It is OPTIONAL, and its absence is reported rather than assumed away: with no
    situation to bind against, every rule is `unevaluable` naming `situation_slice_not_supplied`.
    That is the same answer the three-state discipline gives for any input it cannot read, and it
    keeps a package compiled outside the live path from silently claiming that no rule applied.

    `declared_play_ids` is the manifest's own play list. A blocking rule may only eliminate a
    candidate that EXISTS: naming a play the cap cut, or one no playbook produced, would write an
    elimination receipt pointing at nothing and would put a `core.constraint` check row on the
    decision that no candidate can carry — which `reason/store.py` rejects as "candidate checks
    differ from immutable reasoner result effects". Scope is intersected, not asserted.
    """
    registry = l3_fact_registry()
    constraints: list[Mapping[str, Any]] = []
    verdicts: list[RuleVerdict] = []
    skipped: dict[str, str] = {}
    refusals: dict[str, int] = {}
    plays_by_capability = _plays_by_capability(package, declared_play_ids)

    def refuse(rule_id: str, reason: str) -> None:
        skipped[rule_id] = reason
        refusals[reason] = refusals.get(reason, 0) + 1

    for position, record in enumerate(package.expert_rules):
        if not isinstance(record, Mapping) or artifact_class(record) != "rule":
            continue
        identity = _identity(record)
        rule_id = str(record.get("id") or identity.get("id") or f"rule_{position}")
        definition = record.get("definition") or {}
        rule = definition.get("rule") if isinstance(definition, Mapping) else None
        if not isinstance(rule, Mapping):
            refuse(rule_id, "rule_block_missing")
            continue
        enforced_by = str(rule.get("enforced_by") or "")
        if enforced_by != ENFORCED_BY_L4:
            # Not a defect. `L5_validation` and `L5_2_gate` rules are enforced by layers that own
            # their own gates; compiling them here would enforce them twice, in the wrong place.
            refuse(rule_id, f"rule_enforced_by_{enforced_by.lower() or 'unstated'}")
            continue
        severity = str(rule.get("severity") or "")
        if severity not in CONSTRAINT_SEVERITIES_HERE:
            refuse(rule_id, f"rule_severity_{severity.lower() or 'unstated'}_not_a_constraint")
            continue
        owner_capability = str(identity.get("owner_capability") or "")
        if str(identity.get("scope") or "") != "capability" or not owner_capability:
            refuse(rule_id, "rule_scope_not_capability")
            continue
        statement = rule.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            refuse(rule_id, "rule_statement_missing")
            continue
        when = rule.get("when") or ()
        try:
            predicate_tree = compile_predicate(when, registry)
        except RuleCompileError as exc:
            refuse(rule_id, exc.reason)
            continue

        source_ref = f"expert:{record.get('kind') or 'artifact'}:{rule_id}"
        try:
            constraint = require_compiled_constraint({
                "rule_id": rule_id,
                "severity": severity,
                "predicate_tree": predicate_tree,
                "source_ref": source_ref,
                "predicate_grammar": PREDICATE_GRAMMAR,
                "statement": statement,
                "statement_hash": citation_statement_hash(statement),
            }, f"compiled constraint {rule_id}")
        except (TypeError, ValueError):
            # The contract refused the shape. Counted like any other refusal rather than raised:
            # one malformed authored rule must not take the whole compile down.
            refuse(rule_id, "rule_contract_refused")
            continue

        outcome, missing = _bind(adapter, when)
        blocked = ()
        warned = ()
        if outcome == "fired" and severity == BLOCKING:
            blocked = plays_by_capability.get(owner_capability, ())
        elif outcome == "fired" and severity == WARNING:
            # THE SAME SCOPE, A DIFFERENT CONSEQUENCE. A warning's `when` is a predicate over the
            # SITUATION exactly as a blocking rule's is, so "which recommendation is this caution
            # about?" has the same answer: the plays compiled from the capability the doctrine
            # governs. Until this field existed the answer was nowhere, and a fired warning
            # reached the decision as a rule id with nothing to attach it to.
            warned = plays_by_capability.get(owner_capability, ())
        constraints.append(constraint)
        verdicts.append(RuleVerdict(
            rule_id=rule_id, severity=severity, outcome=outcome, statement=statement,
            statement_hash=constraint["statement_hash"], source_ref=source_ref,
            owner_capability=owner_capability, missing=missing, blocked_play_ids=blocked,
            warned_play_ids=warned))

    return CompiledRules(
        constraints=tuple(constraints),
        verdicts=tuple(sorted(verdicts, key=lambda item: item.rule_id)),
        skipped=dict(sorted(skipped.items())),
        refusals=dict(sorted(refusals.items())),
    )


def _bind(adapter: ContextAdapter | None,
          when: Sequence[Mapping[str, Any]]) -> tuple[str, tuple[str, ...]]:
    """Step 2 and step 4, in three lines, because the three-state evaluator already exists.

    `ContextAdapter.matches` is sound three-valued AND: it returns FALSE as soon as one term is
    FALSE (a conjunction with a false term is false whatever the unknown terms hold), and UNKNOWN
    only when nothing is false and something is unreadable — carrying every unreadable path with
    it, which is what the `unevaluable` record is required to name.
    """
    if adapter is None:
        return "unevaluable", ("situation_slice_not_supplied",)
    verdict = adapter.matches(list(when))
    if verdict.state is PredicateState.TRUE:
        return "fired", ()
    if verdict.state is PredicateState.FALSE:
        return "satisfied", ()
    return "unevaluable", tuple(sorted(verdict.missing)) or ("unnamed_predicate",)


def _plays_by_capability(package,
                         declared: frozenset[str] | None = None) -> dict[str, tuple[str, ...]]:
    """capability id -> the play ids compiled from ITS playbooks.

    This is the map that turns "which capability does this rule govern" into "which candidates
    does it eliminate". Only step-bearing playbooks appear, because only those become plays —
    naming a play id no manifest declares would produce an elimination receipt pointing at nothing.
    """
    out: dict[str, set[str]] = {}
    for record in package.expert_rules:
        if not isinstance(record, Mapping) or artifact_class(record) != "playbook":
            continue
        definition = record.get("definition") or {}
        if not definition.get("steps"):
            continue
        owner = str(_identity(record).get("owner_capability") or "")
        if not owner:
            continue
        play_id = play_id_for(record.get("id") or "")
        if declared is not None and play_id not in declared:
            continue
        out.setdefault(owner, set()).add(play_id)
    return {capability: tuple(sorted(plays)) for capability, plays in out.items()}


# =================================================================================================
# THE DECISION-TIME HALF — what each compiled rule DID to this decision's candidates
# =================================================================================================

#: The reason code `core.constraint` stamps on the elimination it performs from its
#: `blocked_play_ids` config — the seam the compiled corpus's blocking doctrine travels through.
#: RESTATED here rather than imported, on the same argument `expertise._GATE_FIELDS` is restated:
#: `reason/adapters` must not import a unit's internals, and importing it would make this adapter
#: fail to load the day a unit renames a constant. `test_seams_in.py` drives the real unit and
#: asserts the two still agree, so drift fails a test instead of silently un-attributing every
#: elimination the corpus performs.
POLICY_BLOCK_REASON = "tenant_policy_block"

#: The check outcome that removes a candidate. `contracts.reasoning.CheckOutcome.ELIMINATE`'s
#: value, compared as a string because a check read back off the audit store is a mapping.
ELIMINATE_OUTCOME = "eliminate"


def _policy_eliminated(candidate: Any) -> bool:
    """Was this candidate removed BY THE CONSTRAINT POLICY SEAM, rather than by something else?

    THE DEFECT THIS CLOSES. Attribution used to be a join on `play_id` alone: any candidate the
    decision eliminated, for any reason, was claimed by every fired blocking rule whose scope
    covered it. A play removed by `read_only_policy`, by `human_approval_required` or by
    `no_unverified_recipient` therefore arrived in `alternatives_rejected` quoting an authored
    corpus rule that had not touched it — a receipt that reads correctly and is false, which is
    precisely what `require_constraint_application` exists to refuse and could not see.

    The rule id travels on the CHECK, so the check is what is asked. `core.constraint` stamps
    `tenant_policy_block` on exactly the eliminations it performs from `blocked_play_ids`, and
    that config is where the corpus's blocking doctrine arrives (`expertise._roster_specs`).
    """
    for check in getattr(candidate, "checks", ()) or ():
        outcome = getattr(check, "outcome", None)
        reason = getattr(check, "reason_code", None)
        if check is None:
            continue
        if str(getattr(outcome, "value", outcome)) == ELIMINATE_OUTCOME and \
                str(reason) == POLICY_BLOCK_REASON:
            return True
    return False


def constraint_applications(verdicts: Sequence[Mapping[str, Any]],
                            candidates: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    """Turn the manifest's rule verdicts into `ReasoningDecision.constraints_applied`.

    This has to happen at decision time and nowhere else: a candidate id is minted from the
    candidate's own content, so a rule can only name what it eliminated once the field exists. The
    contract then re-checks the claim — an `eliminated_candidate_ids` entry that is not an
    ELIMINATED candidate on this decision is refused, because a receipt that reads correctly and
    is false is worse than no receipt at all.

    Only candidates the constraint policy seam actually eliminated are named (see
    `_policy_eliminated`). A blocking rule whose scope covers a play that survived, or that was
    removed by a different check entirely, records the rule as fired and names the plays it
    covered in `blocked_plays_not_eliminated` — the honest middle state between "this rule removed
    that option" and silence.

    WARNING severity ANNOTATES (doc 06 IN-2's second row). A fired warning eliminates nothing and
    never has; what was missing was any link from the warning to the candidates it is ABOUT, so a
    bundle could not say which recommendation the caution applied to. `warned_play_ids` and
    `warned_candidate_ids` carry that link. Both keys, and `blocked_plays_not_eliminated`, are
    written only when non-empty: a decision where none of them applies hashes to exactly what it
    hashed to before this wave.
    """
    eliminated_by_play: dict[str, str] = {}
    by_play: dict[str, str] = {}
    for candidate in candidates:
        disposition = getattr(candidate, "disposition", None)
        by_play[str(candidate.play_id)] = str(candidate.candidate_id)
        if getattr(disposition, "value", disposition) == "eliminated" \
                and _policy_eliminated(candidate):
            eliminated_by_play[str(candidate.play_id)] = str(candidate.candidate_id)

    applications: list[Mapping[str, Any]] = []
    for verdict in verdicts:
        if not isinstance(verdict, Mapping):
            continue
        record: dict[str, Any] = {
            "rule_id": verdict["rule_id"],
            "severity": verdict["severity"],
            "outcome": verdict["outcome"],
            "statement": verdict["statement"],
            "statement_hash": verdict["statement_hash"],
        }
        scope = tuple(str(play_id) for play_id in verdict.get("blocked_play_ids") or ())
        if verdict["outcome"] == "unevaluable":
            record["missing"] = list(verdict.get("missing") or ("unnamed_predicate",))
        if verdict["outcome"] == "fired" and verdict["severity"] == BLOCKING:
            eliminated = sorted({eliminated_by_play[play_id] for play_id in scope
                                 if play_id in eliminated_by_play})
            if eliminated:
                record["eliminated_candidate_ids"] = eliminated
            unclaimed = sorted({play_id for play_id in scope
                                if play_id not in eliminated_by_play})
            if unclaimed:
                record["blocked_plays_not_eliminated"] = unclaimed
        if verdict["outcome"] == "fired" and verdict["severity"] == WARNING:
            warned_plays = sorted({str(play_id)
                                   for play_id in verdict.get("warned_play_ids") or ()
                                   if str(play_id) in by_play})
            if warned_plays:
                record["warned_play_ids"] = warned_plays
                record["warned_candidate_ids"] = sorted({by_play[p] for p in warned_plays})
        applications.append(require_constraint_application(
            record, f"constraint applied {verdict['rule_id']}"))
    return tuple(applications)


__all__ = [
    "AUTHORED_OPERATORS",
    "BLOCKING",
    "ELIMINATE_OUTCOME",
    "POLICY_BLOCK_REASON",
    "BP_SCALE",
    "CompiledRules",
    "ENFORCED_BY_L4",
    "L3_FACTS",
    "NEIGHBOR_OBSERVATION_PREFIX",
    "OBSERVATION_KINDS",
    "OBSERVATION_PREFIX",
    "RuleCompileError",
    "RuleVerdict",
    "WARNING",
    "artifact_class",
    "compile_package_rules",
    "compile_predicate",
    "constraint_applications",
    "l3_fact_registry",
    "play_id_for",
    "translate_condition",
]
