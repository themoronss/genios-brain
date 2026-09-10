"""L2.1.4 · the AUTHORITY VIEW — *who can decide what, in this org, at a stated instant*.

The eighth view over the one graph, and the only one that was missing entirely. Doc 01 states
what it holds in one line — *"`Arjun approves contracts > $50K` lives here as **data**, not as an
`if` statement"* — and names the three things that cannot happen without it: Layer 4's Policy
unit has no rules to read, its Constraint unit has no thresholds to check, and the Founder
Bottleneck surface (*"this person is the only approver for N open items"*) has nothing to query.

THREE LAWS, and they are the whole module. Everything else here is plumbing.

1. **AN INFERRED RULE NEVER ENFORCES.** `contracts/authority` computes `enforceable` and this
   module obeys it: a rule read off observed behaviour lands in `AuthorityAnswer.suggestions` and
   can never be `AuthorityAnswer.rule`. `AuthorityAnswer` refuses to construct otherwise, so the
   law is not a convention a future caller can forget — inferring an approval threshold from
   behaviour and then enforcing it is the system inventing its own governance.

2. **ABSENCE IS NOT PERMISSION.** No matching rule returns `AuthorityOutcome.NO_AUTHORITY_RULE`
   with `approver_node_id is None`. "We have no rule for a contract this size" and "anyone may
   approve a contract this size" are opposite facts, and an empty list renders as the second one
   on every card that asks. Only-inferred-matches is a THIRD answer (`SUGGESTED`): there is
   something to confirm, and still nobody who may sign.

3. **AUTHORITY IS HISTORICAL.** Every read takes `evaluated_at` as a PARAMETER and never a clock.
   An authority that held last quarter is not necessarily the authority today, and a card that
   escalates to last quarter's approver is worse than one that escalates to nobody — while a
   March decision replayed in September must still be judged against March's rules.

WHAT LIVES WHERE. The contract owns the shape of a rule, its coherence checks, `applies_at` and
`covers`, and the enforceable/advisory split. This module owns the parts doc 01 marks as the
resolver's: the source WEIGHTS (tunable, and a second copy forks the day either moves), the
ranking between two rules that both match, the answer shape, the bottleneck read, and the store.

NO FLOAT ANYWHERE. Authority weights are basis points and thresholds are integer minor units.
There is no scoring here beyond an ordering, and the ordering is over integers and timestamps.

NO CURRENCY CONVERSION. A rule denominated in USD does not cover an amount in INR. Applying it
would require an exchange rate this system does not hold, and the failure would be silent and
one-directional: the wrong approver, named confidently. A cross-currency amount therefore matches
only rules that carry no threshold at all.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from genios_engine.contracts.authority import (NO_AUTHORITY_RULE, AuthorityRule, AuthoritySource)
from genios_engine.contracts.validators import require_aware, require_text

#: The table migration 0097 creates. Spelled once so the store, the erasure list and the tests
#: all name it the same way.
AUTHORITY_TABLE = "authority_rules"

#: Doc 01's source ranking, in basis points. Deliberately NOT in `contracts/authority` — the doc
#: calls these tunable, and the contract carries only the half that is not (an inferred rule
#: never binds). A weight is used for ORDERING two matching rules and for nothing else: it is
#: never multiplied into a score, so there is no arithmetic here to lose precision in.
SOURCE_AUTHORITY_BP: Mapping[AuthoritySource, int] = {
    AuthoritySource.ADMIN_DECLARED: 10000,      # a human set it in the console
    AuthoritySource.DISCOVERED: 8000,           # read out of an uploaded policy document
    AuthoritySource.INFERRED: 5000,             # observed behaviour — proposes, never binds
}

#: The sort position of a rule that applies at ANY value, when ranking against rules that carry a
#: threshold. Negative so "any value" always loses to a real threshold that also matches: given
#: *anyone may approve an expense* and *expenses over 5 lakh need the CFO*, a 6-lakh expense is
#: the CFO's. -1 rather than 0 because 0 is a legal threshold ("everything at all, explicitly").
_ANY_VALUE_RANK = -1


class AuthorityOutcome(str, Enum):
    """The three answers, and the reason there are three rather than two.

    A caller that can only tell "found" from "not found" renders an org with an unconfirmed
    suggestion identically to an org with no governance at all — and those need opposite next
    actions: one is "confirm this", the other is "write one".
    """

    #: A rule with a real source (admin_declared / discovered) is in force and covers the amount.
    ENFORCEABLE = "enforceable"
    #: Only INFERRED rules matched. Nobody may sign on this answer; a human confirms first.
    SUGGESTED = "suggested"
    #: Nothing matched. NOT permission — see law 2. Spelled from the contract's own constant.
    NO_AUTHORITY_RULE = NO_AUTHORITY_RULE


@dataclass(frozen=True, slots=True)
class AuthorityAnswer:
    """*Who approves this, at this instant, and on what evidence.*

    Frozen and self-checking: the three laws above are asserted at construction, so a resolver
    bug surfaces where the wrong answer is BUILT rather than three layers up where a card names
    the wrong person. `considered` is on the object because "no rule matched" and "no rules
    exist for this class at all" look identical to a reader otherwise, and the two mean
    different things to whoever has to fix it.
    """

    subject_type: str
    evaluated_at: datetime
    outcome: AuthorityOutcome
    #: The rule that BINDS. `None` unless `outcome is ENFORCEABLE` — never an inferred rule.
    rule: AuthorityRule | None
    #: `SOURCE_AUTHORITY_BP` of the binding rule, so a caller can say why this one won.
    authority_bp: int | None
    #: Inferred rules that matched. Present on every outcome — an enforceable answer may still
    #: have behaviour disagreeing with it, and that disagreement is worth surfacing.
    suggestions: tuple[AuthorityRule, ...]
    #: Rules in force for this class at this instant, whatever their source or threshold.
    considered: int
    amount_minor_units: int | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is AuthorityOutcome.ENFORCEABLE:
            if self.rule is None or self.authority_bp is None:
                raise ValueError("an enforceable answer must name the rule that binds")
            if not self.rule.enforceable:
                raise ValueError(
                    f"rule {self.rule.rule_id!r} is {self.rule.source.value} and may never bind — "
                    "a system that infers governance from behaviour and then enforces it has "
                    "invented the governance")
        else:
            if self.rule is not None or self.authority_bp is not None:
                raise ValueError(
                    f"outcome {self.outcome.value} carries no binding rule; found "
                    f"{self.rule!r}")
        if self.outcome is AuthorityOutcome.SUGGESTED and not self.suggestions:
            raise ValueError("a suggested answer must carry the suggestions it is made of")
        if any(s.enforceable for s in self.suggestions):
            raise ValueError("only an inferred rule is a suggestion; an enforceable one binds")

    @property
    def enforced(self) -> bool:
        """May something be blocked or escalated on this answer? Read this, never `rule is not
        None` — the two agree today because `__post_init__` makes them, and this one says why."""
        return self.outcome is AuthorityOutcome.ENFORCEABLE

    @property
    def approver_node_id(self) -> str | None:
        """Who signs, or `None`. `None` on a SUGGESTED answer too: a suggestion has a proposed
        approver and no approver, and a caller that reached past this would name them anyway."""
        return self.rule.approver_node_id if self.rule is not None else None

    @property
    def delegate_node_id(self) -> str | None:
        """Who may act in the approver's absence. `None` is the common case and is the Founder
        Bottleneck finding, not a missing value."""
        return self.rule.delegate_node_id if self.rule is not None else None

    @property
    def reason(self) -> str | None:
        """`no_authority_rule` whenever nothing binds — the one word doc 01 requires, so a card
        can say *"we hold no rule for this"* rather than rendering silence as consent."""
        return None if self.enforced else NO_AUTHORITY_RULE

    def as_record(self) -> dict[str, Any]:
        """The JSON an API surface returns. Rules are rendered by `rule_record` so the route and
        the tests cannot disagree about what a rule looks like on the wire."""
        return {
            "subject_type": self.subject_type,
            "evaluated_at": self.evaluated_at.isoformat(),
            "outcome": self.outcome.value,
            "enforced": self.enforced,
            "reason": self.reason,
            "approver_node_id": self.approver_node_id,
            "delegate_node_id": self.delegate_node_id,
            "authority_bp": self.authority_bp,
            "rule": rule_record(self.rule) if self.rule is not None else None,
            "suggestions": [rule_record(r) for r in self.suggestions],
            "considered": self.considered,
            "amount_minor_units": self.amount_minor_units,
            "currency": self.currency,
        }


@dataclass(frozen=True, slots=True)
class ApproverLoad:
    """One person's authority load — the row behind *"this person is the only approver for N"*.

    `sole_subject_types` is the finding and `subject_types` is the context: somebody who approves
    four classes and shares three of them is busy, and somebody who is the only signatory for one
    class with no delegate is a single point of failure. The two are separate fields because
    collapsing them would let the second hide inside the first.
    """

    approver_node_id: str
    #: Every class this person may approve at this instant (enforceable rules only).
    subject_types: tuple[str, ...]
    #: Classes where they are the ONLY enforceable approver.
    sole_subject_types: tuple[str, ...]
    #: Of those, the ones where no rule names a delegate — the bottleneck proper.
    undelegated_subject_types: tuple[str, ...]
    #: Enforceable rules naming this approver, in force at the instant.
    rule_count: int

    @property
    def is_bottleneck(self) -> bool:
        """Sole approver of at least one class, with nobody able to act in their absence."""
        return bool(self.undelegated_subject_types)

    def as_record(self) -> dict[str, Any]:
        return {"approver_node_id": self.approver_node_id,
                "subject_types": list(self.subject_types),
                "sole_subject_types": list(self.sole_subject_types),
                "undelegated_subject_types": list(self.undelegated_subject_types),
                "rule_count": self.rule_count,
                "is_bottleneck": self.is_bottleneck}


@dataclass(frozen=True, slots=True)
class BottleneckReport:
    """The Founder Bottleneck read, WITH its refusal.

    An org that holds no enforceable authority rules and an org whose authority is well spread
    both produce an empty list, and they are opposite findings: the first cannot be answered at
    all, the second is a clean bill of health. `refusal` is what tells them apart, and it carries
    the same word as every other absence in this module.
    """

    evaluated_at: datetime
    loads: tuple[ApproverLoad, ...]
    #: `no_authority_rule` when there was nothing enforceable to read; `None` when there was.
    refusal: str | None

    def __post_init__(self) -> None:
        if self.refusal is not None and self.loads:
            raise ValueError("a refusal carries no loads — it is the absence of anything to read")
        if self.refusal is not None and self.refusal != NO_AUTHORITY_RULE:
            raise ValueError(f"unknown refusal {self.refusal!r}")

    @property
    def answered(self) -> bool:
        return self.refusal is None

    @property
    def bottlenecks(self) -> tuple[ApproverLoad, ...]:
        """Only the people who are a single point of failure."""
        return tuple(load for load in self.loads if load.is_bottleneck)

    def as_record(self) -> dict[str, Any]:
        return {"evaluated_at": self.evaluated_at.isoformat(),
                "answered": self.answered,
                "reason": self.refusal,
                "loads": [load.as_record() for load in self.loads],
                "bottlenecks": [load.as_record() for load in self.bottlenecks]}


def rule_record(rule: AuthorityRule) -> dict[str, Any]:
    """One rule on the wire. `enforceable` is included BECAUSE it is computed: a console that
    renders a suggestion as a rule is exactly the confusion law 1 exists to prevent."""
    return {"rule_id": rule.rule_id, "subject_type": rule.subject_type,
            "threshold_minor_units": rule.threshold_minor_units,
            "threshold_basis_points": rule.threshold_basis_points,
            "currency": rule.currency,
            "approver_node_id": rule.approver_node_id,
            "delegate_node_id": rule.delegate_node_id,
            "source": rule.source.value, "evidence_ref": rule.evidence_ref,
            "enforceable": rule.enforceable,
            "authority_bp": SOURCE_AUTHORITY_BP[rule.source],
            "valid_from": rule.valid_from.isoformat(),
            "valid_until": rule.valid_until.isoformat() if rule.valid_until else None}


# =================================================================================================
# THE RESOLVER — pure functions over a set of rules
# =================================================================================================

def rules_in_force(rules: Iterable[AuthorityRule], *, evaluated_at: datetime,
                   subject_type: str | None = None) -> tuple[AuthorityRule, ...]:
    """The rules that existed at `evaluated_at`, optionally narrowed to one class.

    `applies_at` is the contract's own half-open window, so a rule superseded at noon and its
    successor effective at noon do not both match noon — "who approved this" has one answer per
    instant, or the audit trail is a pair of contradictory claims.
    """
    moment = require_aware(evaluated_at, "evaluated_at")
    wanted = None if subject_type is None else require_text(subject_type, "subject_type")
    return tuple(rule for rule in rules
                 if rule.applies_at(moment)
                 and (wanted is None or rule.subject_type == wanted))


def covers_amount(rule: AuthorityRule, amount_minor_units: int | None,
                  currency: str | None, ratio_bp: int | None = None) -> bool:
    """Does this rule bite at this amount, in this currency?

    Two refusals, both deliberate. A rule with a threshold does not cover an amountless subject
    (the contract's own `covers`), and a rule denominated in one currency does not cover an
    amount in another — see the module docstring: converting would need a rate we do not hold,
    and the failure mode is a confidently named wrong approver.
    """
    # THE RATIO ARM, SYMMETRIC WITH THE MONEY ONE. A rule bounded at 1500 basis points — "a
    # discount above 15% needs the founder" — did not cover an amountless subject either; it
    # covered EVERYTHING, because the only bound this function knew about was money and the
    # ratio one had already been dropped by the store. So a 2% goodwill discount named the
    # founder as required approver, and the Founder Bottleneck read counted them as the sole
    # approver of the whole discount class.
    #
    # A ratio rule does not cover a subject with no ratio, for exactly the reason a money rule
    # does not cover an amountless one: the bound is the whole content of the rule, and applying
    # it to something it cannot measure is a confidently named wrong approver.
    if rule.threshold_basis_points is not None:
        if ratio_bp is None:
            return False
        return int(ratio_bp) > int(rule.threshold_basis_points)
    if rule.threshold_minor_units is None:
        return True
    if amount_minor_units is None:
        return False
    if rule.currency != currency:
        return False
    return rule.covers(amount_minor_units)


def _ranked(candidates: Sequence[AuthorityRule]) -> tuple[AuthorityRule, ...]:
    """Best first, and TOTAL — two runs over the same rules give the same winner.

    The order: source authority (admin_declared beats discovered, doc 01's ranking), then the
    tightest threshold that still matches (given *any expense* and *expenses over 5 lakh*, a
    6-lakh expense is the second rule's), then the most recently effective rule, then `rule_id`
    ascending purely so a full tie is decided by something a test can name rather than by
    whatever order the database returned.

    Two passes rather than one key: a single reverse-sorted key would have to negate a datetime,
    and the only ways to do that are a float epoch or an inverted comparator. Python's sort is
    stable, so ordering by `rule_id` ascending first and by the descending key second leaves
    full ties in `rule_id` order.
    """
    by_id = sorted(candidates, key=lambda r: r.rule_id)
    return tuple(sorted(
        by_id,
        # A RATIO BOUND IS NOT AN UNBOUNDED RULE, and sharing `_ANY_VALUE_RANK` said it was —
        # so "any discount" and "a discount above 15%" tied, and the tie fell to `valid_from`.
        # Ranked in its own lane: a money rule and a ratio rule are never candidates for the
        # same subject anyway, because `covers_amount` refuses each on the other's input.
        key=lambda r: (SOURCE_AUTHORITY_BP[r.source],
                       r.threshold_minor_units if r.threshold_minor_units is not None
                       else r.threshold_basis_points if r.threshold_basis_points is not None
                       else _ANY_VALUE_RANK,
                       r.valid_from),
        reverse=True))


def resolve(rules: Iterable[AuthorityRule], *, subject_type: str, evaluated_at: datetime,
            amount_minor_units: int | None = None,
            currency: str | None = None,
            ratio_bp: int | None = None) -> AuthorityAnswer:
    """*Who approves a `subject_type` worth `amount_minor_units`, as at `evaluated_at`?*

    Pure: it takes the rules it is given and a stated instant, and reads no clock and no
    database. The store hands it a window; the answer is a function of that window.
    """
    moment = require_aware(evaluated_at, "evaluated_at")
    wanted = require_text(subject_type, "subject_type")
    if amount_minor_units is not None:
        if isinstance(amount_minor_units, bool) or not isinstance(amount_minor_units, int):
            raise TypeError("amount_minor_units must be integer minor units, never a float")
        if currency is None:
            raise ValueError(
                "an amount must name its currency — a threshold compared across unknown money "
                "decides who signs on whatever the reader's locale guesses")
    in_force = rules_in_force(rules, evaluated_at=moment, subject_type=wanted)
    matching = [rule for rule in in_force
                if covers_amount(rule, amount_minor_units, currency, ratio_bp)]
    suggestions = _ranked([rule for rule in matching if not rule.enforceable])
    binding = _ranked([rule for rule in matching if rule.enforceable])

    if binding:
        winner = binding[0]
        return AuthorityAnswer(
            subject_type=wanted, evaluated_at=moment, outcome=AuthorityOutcome.ENFORCEABLE,
            rule=winner, authority_bp=SOURCE_AUTHORITY_BP[winner.source],
            suggestions=suggestions, considered=len(in_force),
            amount_minor_units=amount_minor_units, currency=currency)
    outcome = (AuthorityOutcome.SUGGESTED if suggestions
               else AuthorityOutcome.NO_AUTHORITY_RULE)
    return AuthorityAnswer(
        subject_type=wanted, evaluated_at=moment, outcome=outcome, rule=None, authority_bp=None,
        suggestions=suggestions, considered=len(in_force),
        amount_minor_units=amount_minor_units, currency=currency)


def bottleneck(rules: Iterable[AuthorityRule], *, evaluated_at: datetime) -> BottleneckReport:
    """The Founder Bottleneck read: who is the only person who may approve a whole class.

    ENFORCEABLE RULES ONLY. An inferred rule saying somebody approves everything would otherwise
    manufacture a bottleneck out of the fact that they happen to answer their email, and the
    surface Globe rates highest for "I can't unsee this" value would be reporting an inference.
    Inferred rules are still visible — through `resolve`, as suggestions to confirm.
    """
    moment = require_aware(evaluated_at, "evaluated_at")
    in_force = [rule for rule in rules_in_force(rules, evaluated_at=moment) if rule.enforceable]
    if not in_force:
        return BottleneckReport(evaluated_at=moment, loads=(), refusal=NO_AUTHORITY_RULE)

    approvers_by_class: dict[str, set[str]] = {}
    for rule in in_force:
        approvers_by_class.setdefault(rule.subject_type, set()).add(rule.approver_node_id)

    loads: list[ApproverLoad] = []
    for approver in sorted({rule.approver_node_id for rule in in_force}):
        mine = [rule for rule in in_force if rule.approver_node_id == approver]
        classes = sorted({rule.subject_type for rule in mine})
        sole = tuple(c for c in classes if approvers_by_class[c] == {approver})
        # A delegate on ANY rule of the class is an escape hatch for that class, so the
        # undelegated set is the classes where every one of this approver's rules leaves the
        # delegate null. One delegated rule out of three still means somebody else can act.
        undelegated = tuple(
            c for c in sole
            if all(rule.delegate_node_id is None for rule in mine if rule.subject_type == c))
        loads.append(ApproverLoad(approver_node_id=approver, subject_types=tuple(classes),
                                  sole_subject_types=sole,
                                  undelegated_subject_types=undelegated, rule_count=len(mine)))
    return BottleneckReport(evaluated_at=moment, loads=tuple(loads), refusal=None)


# =================================================================================================
# THE STORE — two lanes over one shape
# =================================================================================================

class AuthorityRuleStore(Protocol):
    """What the view needs from storage. A Protocol so the in-memory lane is a real
    implementation rather than a mock: a test that passed against a mock and failed against
    Postgres would be testing the mock."""

    def put(self, org_id: str, rules: Sequence[AuthorityRule]) -> int: ...

    def rules(self, org_id: str, *, subject_type: str | None = None,
              as_of: datetime | None = None) -> tuple[AuthorityRule, ...]: ...

    def close(self, org_id: str, rule_id: str, *, valid_from: datetime,
              valid_until: datetime) -> bool: ...

    def erase(self, org_id: str) -> int: ...


def _key(rule: AuthorityRule) -> tuple[str, datetime]:
    """The primary key doc 01's DDL declares, minus the org the store already knows."""
    return (rule.rule_id, rule.valid_from)


class InMemoryAuthorityRules:
    """The hermetic lane. Same keying and same window semantics as Postgres, so a test written
    against one is true of the other."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[tuple[str, datetime], AuthorityRule]] = {}

    def put(self, org_id: str, rules: Sequence[AuthorityRule]) -> int:
        org = require_text(org_id, "org_id")
        held = self._rows.setdefault(org, {})
        changed = 0
        for rule in rules:
            key = _key(rule)
            if held.get(key) != rule:
                held[key] = rule
                changed += 1
        return changed

    def rules(self, org_id: str, *, subject_type: str | None = None,
              as_of: datetime | None = None) -> tuple[AuthorityRule, ...]:
        held = tuple(self._rows.get(org_id, {}).values())
        if as_of is not None:
            held = rules_in_force(held, evaluated_at=as_of, subject_type=subject_type)
        elif subject_type is not None:
            held = tuple(r for r in held if r.subject_type == subject_type)
        return tuple(sorted(held, key=lambda r: (r.subject_type, r.valid_from, r.rule_id)))

    def close(self, org_id: str, rule_id: str, *, valid_from: datetime,
              valid_until: datetime) -> bool:
        held = self._rows.get(org_id, {})
        key = (require_text(rule_id, "rule_id"), require_aware(valid_from, "valid_from"))
        rule = held.get(key)
        if rule is None:
            return False
        held[key] = rule.model_copy(update={"valid_until": require_aware(valid_until,
                                                                        "valid_until")})
        # Re-validate through the constructor: `model_copy` skips validators, and a window that
        # ends before it starts would otherwise be storable here and refused by Postgres.
        held[key] = AuthorityRule(**held[key].model_dump())
        return True

    def erase(self, org_id: str) -> int:
        return len(self._rows.pop(org_id, {}))


_INSERT = f"""
insert into {AUTHORITY_TABLE} (org_id, rule_id, subject_type, threshold_minor_units,
                               threshold_basis_points, currency,
                               approver_node_id, delegate_node_id, source, evidence_ref,
                               valid_from, valid_until)
values (:org_id, :rule_id, :subject_type, :threshold_minor_units, :threshold_basis_points,
        :currency,
        :approver_node_id, :delegate_node_id, :source, :evidence_ref, :valid_from, :valid_until)
on conflict (org_id, rule_id, valid_from) do update set
    subject_type = excluded.subject_type,
    threshold_minor_units = excluded.threshold_minor_units,
    threshold_basis_points = excluded.threshold_basis_points,
    currency = excluded.currency,
    approver_node_id = excluded.approver_node_id,
    delegate_node_id = excluded.delegate_node_id,
    source = excluded.source,
    evidence_ref = excluded.evidence_ref,
    valid_until = excluded.valid_until
where (authority_rules.subject_type, authority_rules.threshold_minor_units,
       authority_rules.threshold_basis_points,
       authority_rules.currency, authority_rules.approver_node_id,
       authority_rules.delegate_node_id, authority_rules.source, authority_rules.evidence_ref,
       authority_rules.valid_until)
  is distinct from
      (excluded.subject_type, excluded.threshold_minor_units, excluded.threshold_basis_points,
       excluded.currency,
       excluded.approver_node_id, excluded.delegate_node_id, excluded.source,
       excluded.evidence_ref, excluded.valid_until)
"""

_SELECT = f"""
select rule_id, subject_type, threshold_minor_units, threshold_basis_points, currency,
       approver_node_id,
       delegate_node_id, source, evidence_ref, valid_from, valid_until
from {AUTHORITY_TABLE}
where org_id = :org_id
  and (cast(:subject_type as text) is null or subject_type = :subject_type)
  and (cast(:as_of as timestamptz) is null
       or (valid_from <= :as_of and (valid_until is null or valid_until > :as_of)))
order by subject_type, valid_from, rule_id
"""


def row_to_rule(row: Any) -> AuthorityRule:
    """One database row as the contract object. Through the real constructor, so a row that
    violates a coherence law (a threshold with no currency, a discovered rule with no evidence)
    raises HERE, naming the rule, rather than reaching a card as a plausible approver."""
    return AuthorityRule(
        rule_id=row.rule_id, subject_type=row.subject_type,
        threshold_minor_units=(None if row.threshold_minor_units is None
                               else int(row.threshold_minor_units)),
        # THE RATIO ARM, dropped on both the write and the read until now. A discount policy
        # projected as `threshold_basis_points=1500` — "above 15% needs the founder" — round
        # tripped as an UNBOUNDED rule, so `covers_amount` returned True for every discount and
        # a 2% goodwill gesture named the founder as required approver. The drop failed OPEN,
        # which is the worst direction for an authority bound.
        threshold_basis_points=(None if getattr(row, "threshold_basis_points", None) is None
                                else int(row.threshold_basis_points)),
        currency=row.currency, approver_node_id=row.approver_node_id,
        delegate_node_id=row.delegate_node_id, source=row.source,
        evidence_ref=row.evidence_ref, valid_from=row.valid_from, valid_until=row.valid_until)


class PostgresAuthorityRules:
    """The real store. Constructed from a URL or from an existing Engine — the production caller
    already holds `GraphStore.engine`, and a second pool per request is a connection leak on a
    database whose measured ceiling is 60."""

    def __init__(self, target: Any) -> None:
        if isinstance(target, str):
            from genios_engine.platform.db import get_engine
            self._engine = get_engine(target)
        else:
            self._engine = target

    @property
    def engine(self):
        return self._engine

    def put(self, org_id: str, rules: Sequence[AuthorityRule]) -> int:
        """Insert or amend, keyed on `(org, rule_id, valid_from)`. Returns rows CHANGED, so
        re-declaring an identical rule counts 0 — the same answer `PostgresMetricHistory.put`
        gives, and for the same reason: an idempotent write must be visible as one."""
        from sqlalchemy import text
        if not rules:
            return 0
        org = require_text(org_id, "org_id")
        changed = 0
        with self._engine.begin() as conn:
            for rule in rules:
                changed += conn.execute(text(_INSERT), {
                    "org_id": org, "rule_id": rule.rule_id, "subject_type": rule.subject_type,
                    "threshold_minor_units": rule.threshold_minor_units,
                    "threshold_basis_points": rule.threshold_basis_points,
                    "currency": rule.currency, "approver_node_id": rule.approver_node_id,
                    "delegate_node_id": rule.delegate_node_id, "source": rule.source.value,
                    "evidence_ref": rule.evidence_ref, "valid_from": rule.valid_from,
                    "valid_until": rule.valid_until}).rowcount
        return changed

    def rules(self, org_id: str, *, subject_type: str | None = None,
              as_of: datetime | None = None) -> tuple[AuthorityRule, ...]:
        """Every rule for the org, narrowed in SQL. `as_of` filters with the SAME half-open
        window the contract's `applies_at` uses, so the database and the resolver never disagree
        about whether a rule existed at an instant."""
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text(_SELECT), {
                "org_id": require_text(org_id, "org_id"),
                "subject_type": subject_type,
                "as_of": None if as_of is None else require_aware(as_of, "as_of")}).fetchall()
        return tuple(row_to_rule(row) for row in rows)

    def close(self, org_id: str, rule_id: str, *, valid_from: datetime,
              valid_until: datetime) -> bool:
        """End a rule's window. The row is NEVER deleted and never rewritten: a superseded rule
        is what makes "who could approve this in March" answerable after the September edit."""
        from sqlalchemy import text
        with self._engine.begin() as conn:
            return bool(conn.execute(text(
                f"update {AUTHORITY_TABLE} set valid_until = :until "
                "where org_id = :org_id and rule_id = :rule_id and valid_from = :valid_from"),
                {"until": require_aware(valid_until, "valid_until"),
                 "org_id": require_text(org_id, "org_id"),
                 "rule_id": require_text(rule_id, "rule_id"),
                 "valid_from": require_aware(valid_from, "valid_from")}).rowcount)

    def erase(self, org_id: str) -> int:
        from sqlalchemy import text
        with self._engine.begin() as conn:
            return conn.execute(text(f"delete from {AUTHORITY_TABLE} where org_id = :o"),
                                {"o": require_text(org_id, "org_id")}).rowcount or 0


class AuthorityView:
    """The view itself: a store, plus the three questions doc 01 says it must answer.

    A thin object on purpose. Every decision lives in the pure functions above, so the same
    answer is reachable without a database — which is what lets Layer 4's Policy and Constraint
    units be tested against a rule set rather than against a fixture org.
    """

    def __init__(self, store: AuthorityRuleStore) -> None:
        self._store = store

    @property
    def store(self) -> AuthorityRuleStore:
        return self._store

    def declare(self, org_id: str, rules: Sequence[AuthorityRule]) -> int:
        return self._store.put(org_id, rules)

    def supersede(self, org_id: str, rule_id: str, *, valid_from: datetime,
                  valid_until: datetime) -> bool:
        return self._store.close(org_id, rule_id, valid_from=valid_from, valid_until=valid_until)

    def resolve(self, org_id: str, *, subject_type: str, evaluated_at: datetime,
                amount_minor_units: int | None = None,
                currency: str | None = None,
                ratio_bp: int | None = None) -> AuthorityAnswer:
        """*Who approves this, as at `evaluated_at`?* The store is asked for the window and the
        pure resolver decides — so the read narrows in SQL and the ranking stays testable.

        `ratio_bp` is the second kind of bound a rule can carry: "a discount above 15% needs the
        founder" is 1500 basis points, not money, and a caller asking about a 200bp discount
        must say so or every ratio rule will refuse to cover it — which is the safe direction,
        and the reason it is a parameter rather than an inference.
        """
        window = self._store.rules(org_id, subject_type=subject_type, as_of=evaluated_at)
        return resolve(window, subject_type=subject_type, evaluated_at=evaluated_at,
                       amount_minor_units=amount_minor_units, currency=currency,
                       ratio_bp=ratio_bp)

    def bottleneck(self, org_id: str, *, evaluated_at: datetime) -> BottleneckReport:
        """*Who is the only person who can sign for a whole class?*"""
        return bottleneck(self._store.rules(org_id, as_of=evaluated_at),
                          evaluated_at=evaluated_at)

    def rules(self, org_id: str, *, subject_type: str | None = None,
              as_of: datetime | None = None) -> tuple[AuthorityRule, ...]:
        return self._store.rules(org_id, subject_type=subject_type, as_of=as_of)


__all__ = ["AUTHORITY_TABLE", "SOURCE_AUTHORITY_BP", "ApproverLoad", "AuthorityAnswer",
           "AuthorityOutcome", "AuthorityRuleStore", "AuthorityView", "BottleneckReport",
           "InMemoryAuthorityRules", "PostgresAuthorityRules", "bottleneck", "covers_amount",
           "resolve", "row_to_rule", "rule_record", "rules_in_force"]
