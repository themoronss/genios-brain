"""D-08 · `AuthorityRule` — who may approve what, as DATA rather than as an `if` statement.

A grep of `context/` for approval thresholds returns nothing, and two Layer 4 reasoning units
cannot fire without them: the Policy unit ("which organisational rules bind") has no rules to
read, and the Constraint unit ("what cannot happen") has no thresholds to check. Globe's Founder
Bottleneck surface — the one it rates highest for "I can't unsee this" value — is an Authority
query and nothing else: *this person is the only approver for N open items*.

**Authority is HISTORICAL, which is why `valid_from` is part of the identity.** "Who could
approve this in March?" has to be answerable, because a decision made in March was correct
against March's rules and re-judging it against today's is how a review turns into an accusation.
`applies_at` takes the instant as a PARAMETER for the same reason every evaluation in this
package does: a clock read inside the object would make a replay of a March decision answer
differently in September, and this object is evidence.

**The `source` ranking is a law, not a preference, and only half of it lives here.** Doc 01 ranks
`admin_declared` over `discovered` over `inferred`, and gives each a trust weight. The WEIGHTS are
the resolver's and are deliberately absent from this contract — they are tunable, and a second
copy forks the day either moves. What is here is the half that cannot be tuned without changing
what the system is allowed to do: an INFERRED rule never enforces. Inferring an approval threshold
from observed behaviour and then enforcing it would let the system invent governance; it proposes,
and a human confirms. `enforceable` is a computed read so no caller can set it.

GAP FLAG — doc 08 lists `AuthorityRule` in its inventory and specifies not one field of it. The
shape below is taken from doc 01's `authority_rules` DDL, which is the only definition that
exists; `authority_bp` from the same doc's source ranking is deliberately NOT a field (see above),
and `org_id` is on the row rather than the object because every object in this package is carried
inside an envelope that already states the tenant. If the resolver needs the weight, it belongs
with the resolver.

GAP FLAG — doc 01 says an unmatched subject class must return `no_authority_rule`, *distinct from
"anyone may approve"*. That is the absence, not the rule, so it is a module constant here rather
than a type: the answer shape belongs to `context/authority.py`, and typing it in `contracts/`
would fix a resolver's return shape before the resolver exists. The string is spelled once, here,
so both sides use the same word.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from genios_engine.contracts.units import ISO_4217, UNKNOWN_CURRENCY
from genios_engine.contracts.validators import (require_aware, require_enum, require_identifier,
                                                require_text)

#: The answer to "who approves this?" when NO rule matches. Not an empty result and not a
#: permissive one: "we have no rule for contracts over 5 crore" and "anyone may approve a contract
#: over 5 crore" are opposite facts, and an empty return renders as the second one on every card
#: that asks. Spelled once so the resolver and its callers use the same word.
NO_AUTHORITY_RULE = "no_authority_rule"


class AuthoritySource(str, Enum):
    """Where the rule came from. The ranking is doc 01's; the ENFORCEABILITY split is the law."""

    #: A human set it in the console. Trusted, enforceable.
    ADMIN_DECLARED = "admin_declared"
    #: Extracted from an uploaded policy document (L1's `internal_kind` canon). Enforceable, and
    #: admin-confirmable — which is why `evidence_ref` is required for it: a discovered rule that
    #: cannot name the document it came from is indistinguishable from an inferred one.
    DISCOVERED = "discovered"
    #: Observed behaviour — "this person approved N of N requests in this class over 90 days".
    #: NEVER auto-applied. Surfaced as a suggestion for a human to confirm.
    INFERRED = "inferred"


#: The sources whose rules may BIND. Data rather than an inline comparison, for the reason
#: `publication.NON_BLOCKING_RULES` is: "which rules enforce" must have one answer a reader can
#: see, and adding a fourth source is then a deliberate edit here rather than a condition somebody
#: forgets to widen.
ENFORCEABLE_SOURCES: frozenset[AuthoritySource] = frozenset({AuthoritySource.ADMIN_DECLARED,
                                                             AuthoritySource.DISCOVERED})


class AuthorityRule(BaseModel):
    """One approval rule, valid over one window of time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The rule's own id. Part of the primary key with `valid_from`.
    rule_id: str
    #: What class of thing it governs — contract | expense | hiring | legal | discount. Typed
    #: `str` and not an enum on purpose: the classes are a tenant-extensible vocabulary declared
    #: by the domain packs, and a closed enum here would make adding one a contract release.
    subject_type: str
    #: The value at or above which the rule bites, in the currency's minor units. `None` means it
    #: applies at ANY value — a distinct, common and legitimate case (a hiring approval has no
    #: amount), which is why it is nullable rather than defaulted to zero.
    threshold_minor_units: int | None = None
    #: ISO 4217, or `UNKNOWN_CURRENCY`. REQUIRED whenever a MONEY threshold is set, refused
    #: otherwise. A ratio threshold has no currency and must not be given one.
    currency: str | None = None
    #: The percentage at or above which the rule bites, in basis points — 15% is 1500.
    #:
    #: THE DIMENSION THIS TABLE COULD NOT HOLD. *"A discount greater than 15% requires approval
    #: from the founder"* was refused in WHOLE by CLG-09, not merely stripped of its threshold,
    #: because `threshold_as_written` was validated by a money parser alone. Discount authority is
    #: the most common approval rule a sales-led startup writes down.
    #:
    #: Mutually exclusive with `threshold_minor_units` (see `_coherent_rule`): a rule has at most
    #: one bound, and 1500 minor units and 1500 basis points are the same integer meaning nothing
    #: alike. Kept as its own field for exactly that reason rather than sharing the money column.
    threshold_basis_points: int | None = None
    #: Who approves. A graph node id, so the Founder Bottleneck query is a group-by on this
    #: column rather than a string match on a name.
    approver_node_id: str
    #: Who may act in the approver's absence. The whole point of the Bottleneck surface is that
    #: this is usually null, so it is nullable and never defaulted to the approver.
    delegate_node_id: str | None = None
    #: Which of the three. See `AuthoritySource`.
    source: AuthoritySource
    #: The document or setting the rule came from. Required for `DISCOVERED`; see the class
    #: docstring on why a discovered rule must be able to name its source.
    evidence_ref: str | None = None
    #: When the rule took effect, tz-aware UTC. Part of the identity — authority is historical.
    valid_from: datetime
    #: When it stopped, or `None` for still in force. Strictly after `valid_from`.
    valid_until: datetime | None = None

    @field_validator("rule_id", mode="before")
    @classmethod
    def _rule_id(cls, value: Any) -> str:
        """System-minted, so the narrow identifier class applies: it reaches SQL, log lines and
        the primary key."""
        return require_identifier(value, "rule_id")

    @field_validator("approver_node_id", mode="before")
    @classmethod
    def _approver(cls, value: Any) -> str:
        """A graph node id, which is frequently an email address — `require_text` for the reason
        `signal.py` uses it for `recipients`: a `+` tag is legal in an address and the identifier
        character class would make a real approver unrepresentable."""
        return require_text(value, "approver_node_id")

    @field_validator("delegate_node_id", "evidence_ref", mode="before")
    @classmethod
    def _optional_refs(cls, value: Any, info: ValidationInfo) -> str | None:
        """Present or absent, never blank. A blank delegate reads as "there is a delegate" to
        every `is not None` check and as "there is none" to every human."""
        label = info.field_name or "ref"
        return None if value is None else require_text(value, label)

    @field_validator("subject_type", mode="before")
    @classmethod
    def _subject(cls, value: Any) -> str:
        return require_text(value, "subject_type")

    @field_validator("threshold_minor_units", mode="before")
    @classmethod
    def _threshold(cls, value: Any) -> int | None:
        """Integer minor units, exactly as `contracts/units.Money` stores an amount. A float here
        is the `$84K` / `$8.4K` fault with a threshold attached: it rounds, and the rounding
        decides who has to approve."""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("threshold_minor_units must be integer minor units, never a float")
        if value < 0:
            raise ValueError("threshold_minor_units must not be negative")
        return value

    @field_validator("threshold_basis_points", mode="before")
    @classmethod
    def _basis_points(cls, value: Any) -> int | None:
        """0..10000, integer. A float here is the rounding that decides who signs, one dimension
        over from the `$84K` / `$8.4K` fault `threshold_minor_units` is integer for. Above 10000 is
        a parse that went wrong and is refused rather than clamped — clamping would turn a bug into
        a rule that always fires."""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("threshold_basis_points must be integer basis points, never a float")
        if not 0 <= value <= 10_000:
            raise ValueError(f"threshold_basis_points must be 0..10000, got {value}")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value: Any) -> str | None:
        if value is None:
            return None
        code = require_text(value, "currency")
        if code != UNKNOWN_CURRENCY and not ISO_4217.fullmatch(code):
            raise ValueError(
                f"currency must be an uppercase ISO 4217 code or {UNKNOWN_CURRENCY!r}, "
                f"got {code!r}")
        return code

    @field_validator("source", mode="before")
    @classmethod
    def _source(cls, value: Any) -> AuthoritySource:
        return require_enum(value, AuthoritySource, "source")

    @field_validator("valid_from")
    @classmethod
    def _from(cls, value: datetime) -> datetime:
        return require_aware(value, "valid_from")

    @field_validator("valid_until")
    @classmethod
    def _until(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware(value, "valid_until")

    @model_validator(mode="after")
    def _coherent_rule(self) -> AuthorityRule:
        """The three states that would be unreadable rather than merely wrong.

        A threshold with no currency is "approval required above 500000" of unknown money — the
        exact fault `contracts/units.Money` exists to prevent, with the added property that here
        it decides who signs. A currency with no threshold is a denomination for an amount that
        does not exist.

        A `DISCOVERED` rule with no `evidence_ref` cannot be confirmed by the admin the doc says
        must be able to confirm it, and is then indistinguishable in the table from an inferred
        rule that must never enforce.

        A window that ends before it starts matches nothing at any instant, so the rule silently
        stops existing while still being listed.
        """
        if self.threshold_minor_units is not None and self.currency is None:
            raise ValueError(
                "an authority threshold must name its currency — a threshold in unknown money "
                "decides who signs on whatever the reader's locale guesses")
        if self.threshold_minor_units is None and self.currency is not None:
            raise ValueError(
                "currency without a threshold denominates an amount that does not exist")
        if self.threshold_basis_points is not None and self.threshold_minor_units is not None:
            raise ValueError(
                "a rule has at most one threshold dimension — money OR a ratio. Both set is not a "
                "stricter rule, it is an unreadable one: nothing downstream could say which bound "
                "bit")
        if self.source is AuthoritySource.DISCOVERED and self.evidence_ref is None:
            raise ValueError(
                "a discovered rule must name the document it was read from — without it an "
                "admin cannot confirm it and it is indistinguishable from an inferred rule")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError(
                f"valid_until ({self.valid_until.isoformat()}) must be after valid_from "
                f"({self.valid_from.isoformat()}) — a window that ends before it starts matches "
                "no instant and the rule silently stops existing")
        return self

    @property
    def enforceable(self) -> bool:
        """May this rule BIND, or may it only be suggested?

        False for `INFERRED`, always. Computed rather than stored so no caller can set it, and
        read as a property rather than checked inline at each site so the answer is the same
        everywhere — a system that infers governance from behaviour and then enforces it has
        invented the governance.
        """
        return self.source in ENFORCEABLE_SOURCES

    def applies_at(self, evaluated_at: datetime) -> bool:
        """Was this rule in force at `evaluated_at`? The instant is a PARAMETER, never a clock.

        Half-open on purpose: `[valid_from, valid_until)`. A rule superseded at noon and its
        successor effective at noon must not both match noon, or "who approved this" has two
        answers for one instant.
        """
        moment = require_aware(evaluated_at, "evaluated_at")
        if moment < self.valid_from:
            return False
        return self.valid_until is None or moment < self.valid_until

    def covers(self, amount_minor_units: int | None) -> bool:
        """Does this rule bite at this amount?

        `threshold_minor_units is None` means it applies at any value, including no value at all
        (a hiring approval). A rule WITH a threshold does not cover an amountless subject: the
        answer to "does the 50-lakh contract rule apply to this thing with no amount" is not yes.
        """
        if self.threshold_minor_units is None:
            return True
        if amount_minor_units is None:
            return False
        if isinstance(amount_minor_units, bool) or not isinstance(amount_minor_units, int):
            raise TypeError("amount_minor_units must be integer minor units")
        return amount_minor_units >= self.threshold_minor_units


__all__ = ["ENFORCEABLE_SOURCES", "NO_AUTHORITY_RULE", "AuthorityRule", "AuthoritySource"]
