"""D-07 · typed absence — the type that decides whether a negative inference is licensed.

"No support tickets this month" is either the best news in the report or no news at all, and
nothing in the codebase could tell those two apart before this module. With Zendesk connected it
is a genuinely healthy account; with Zendesk not connected it is a statement about our own
plumbing that reads, on a card, exactly like a statement about the customer. Conflating them is
how a false churn signal is born, and the conflation is invisible because both spellings of the
absence are the same empty list.

**The third case is the interesting one, and it is the product.** "There is a renewal, and no
owner is recorded" is not missing data — it IS the intelligence. Globe's Ownership surface is
built entirely on typed absence, and `GENUINELY_ABSENT` is the member that carries it: a source
could have held this fact, every one we can see was checked, and none did.

**`licenses_negative_inference` is COMPUTED and cannot be supplied.** It is True only for
`GENUINELY_ABSENT`. Every layer that wants to say "nobody owns this" must read it, and no layer
can talk itself past it — which is the point: the argument for making an exception is always
persuasive at the call site and always wrong, because the same exception is how `UNKNOWABLE`
becomes "genuinely absent" and a coverage gap becomes a finding about a customer.

The mechanism is a `@computed_field` plus a before-validator that strips the key on the way back
in. That pairing is what makes the round-trip work at all under `extra="forbid"`: the value is
serialized (a stored row must carry the licence, or a consumer reading the row has to re-derive
it and may re-derive it differently), and on reparse the key is dropped and recomputed rather than
trusted. A caller who supplies a value that DISAGREES with the computed one is refused rather
than silently corrected — a contract that quietly repairs its input is a contract that lets a
malformed object reach a human with the repair invisible.

GAP FLAG — doc 08 gives `MissingFact` no evidence field, and an absence genuinely has no span to
quote. `coverage_basis` is added here in its place and is REQUIRED for `GENUINELY_ABSENT`: the
receipt for "we looked and it was not there" is the list of what we looked at. Without it the
strongest claim this type can make is the only one in the whole contract package with no way to
check it, and "a claim with no receipt is a guess" does not stop being true because the claim is
about an absence.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field, field_validator, model_validator

from genios_engine.contracts.validators import (require_bool, require_enum, require_identifier,
                                                require_sorted_unique, require_text)


class AbsenceType(str, Enum):
    """BLG-15's five answers. Exactly one of them applies to any (subject, expected fact) pair.

    The order below is the order the algorithm resolves them in, and the ordering is itself a
    safety rule: `coverage_ready` is consulted BEFORE the graph is searched, so a fact we could
    never have seen can never fall through into `GENUINELY_ABSENT` on its way past.
    """

    #: The fact is there. Included so the expectation map has a total answer and a caller never
    #: has to read "no MissingFact row" as "present" — the same absence-of-a-row ambiguity this
    #: whole type exists to remove.
    PRESENT = "present"
    #: No connected source could have carried it. Licenses NOTHING. A `coverage_ready` of None
    #: lands here too, never in `GENUINELY_ABSENT`: "we did not classify this domain" is not
    #: evidence that the domain is covered.
    UNKNOWABLE = "unknowable"
    #: A source could have carried it and none did. THIS IS A FINDING — "no owner", "no
    #: amendment", "no reply" — and it is the only member that licenses a negative inference.
    GENUINELY_ABSENT = "genuinely_absent"
    #: It was there and is now too old to rely on. Distinct from absent because the remedy is
    #: different: a stale fact is re-fetched, an absent one is asked about.
    STALE = "stale"
    #: This kind of situation was never expected to carry it. Not a gap; the expectation map
    #: simply does not apply here, and scoring it as missing makes every situation in a new
    #: domain look broken the day the domain is added.
    NOT_EXPECTED = "not_expected"


#: The one member that licenses a negative inference. Kept as data rather than as an `if` at the
#: single site that needs it, so "which absences license an inference" has one answer a reader can
#: see without tracing control flow — and so widening it is a deliberate one-line edit here rather
#: than a condition somebody forgets to update.
NEGATIVE_INFERENCE_TYPES: frozenset[AbsenceType] = frozenset({AbsenceType.GENUINELY_ABSENT})


class MissingFact(BaseModel):
    """D-07 · one expected fact that is not present, and the exact KIND of not-present it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Which node the fact was expected ON. `require_text` rather than `require_identifier`:
    #: graph node ids are frequently email addresses, a `+` tag is legal in one, and a real
    #: customer must not be unrepresentable because their address is well-formed in a way the
    #: identifier character class is not. The same call `signal.py` makes for `recipients`.
    subject_node_id: str
    #: The expectation's own key — a field path, never a plain-language label. `situation_bso`
    #: learned this the hard way: the human labels have spaces, do not match anything in the
    #: graph, and cannot be consulted by `packs/compiler/context_adapter.evaluate`, so a
    #: predicate over them silently answered FALSE instead of UNKNOWN.
    expected_fact: str
    #: Which of the five. See `AbsenceType`.
    absence_type: AbsenceType
    #: Was the domain connected well enough for this fact to have been visible at all? Tri-state,
    #: and `None` is NOT False: an unhinted fact is `UNKNOWABLE`, never absent.
    coverage_ready: bool | None = None
    #: WHAT WE LOOKED AT — the connected source ids that were consulted. Required for
    #: `GENUINELY_ABSENT`; see the module GAP FLAG. Sorted and deduplicated so the same basis
    #: hashes identically across two sweeps that read the connections in a different order.
    coverage_basis: tuple[str, ...] = ()

    @field_validator("subject_node_id", mode="before")
    @classmethod
    def _subject(cls, value: Any) -> str:
        return require_text(value, "subject_node_id")

    @field_validator("expected_fact", mode="before")
    @classmethod
    def _fact(cls, value: Any) -> str:
        """A field PATH — dotted identifiers, not a sentence. `require_identifier` admits the
        dots and refuses the spaces, which is exactly the distinction that matters."""
        return require_identifier(value, "expected_fact")

    @field_validator("absence_type", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> AbsenceType:
        return require_enum(value, AbsenceType, "absence_type")

    @field_validator("coverage_ready", mode="before")
    @classmethod
    def _coverage(cls, value: Any) -> bool | None:
        """A literal bool or a literal None. Truthiness coercion is precisely how an empty string
        would grant the licence to say "nobody owns this"."""
        return None if value is None else require_bool(value, "coverage_ready")

    @field_validator("coverage_basis", mode="before")
    @classmethod
    def _basis(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError("coverage_basis must be a sequence of source ids")
        return require_sorted_unique(value, "coverage basis source")

    @model_validator(mode="before")
    @classmethod
    def _licence_is_not_an_input(cls, data: Any) -> Any:
        """`licenses_negative_inference` is computed; a caller may not set it.

        The key is accepted on the way in ONLY because `model_dump()` emits it and the round-trip
        has to work — a stored row must carry the licence rather than making every reader
        re-derive it, possibly differently. It is dropped and recomputed. A value that disagrees
        with the computed one is REFUSED rather than repaired: silently correcting it would mean
        an object that claimed a licence it does not have left no trace of having tried.
        """
        if not isinstance(data, Mapping) or "licenses_negative_inference" not in data:
            return data
        fields = dict(data)
        supplied = fields.pop("licenses_negative_inference")
        kind = fields.get("absence_type")
        try:
            resolved = kind if isinstance(kind, AbsenceType) else AbsenceType(kind)
        except ValueError:
            return fields                    # the absence_type validator owns that failure
        if bool(supplied) is not (resolved in NEGATIVE_INFERENCE_TYPES):
            raise ValueError(
                "licenses_negative_inference is computed from absence_type and cannot be set — "
                f"{resolved.value} licenses "
                f"{resolved in NEGATIVE_INFERENCE_TYPES}, caller supplied {supplied!r}")
        return fields

    @model_validator(mode="after")
    def _absence_is_grounded(self) -> MissingFact:
        """The two rules that keep `GENUINELY_ABSENT` from being said carelessly.

        Doc 05's own failure table names treating `UNKNOWABLE` as `GENUINELY_ABSENT` the worst
        output in the whole quality group — a false negative inference — and its stated mitigation
        is that `coverage_ready` is checked first, ALWAYS, with `None` treated as unknowable. That
        check is enforced here rather than only inside BLG-15, because the classifier is not the
        only thing that will ever construct one of these.

        The second rule is the receipt (module GAP FLAG): the strongest claim this type can make
        must be able to name what was searched.
        """
        if self.absence_type is AbsenceType.GENUINELY_ABSENT:
            if self.coverage_ready is not True:
                raise ValueError(
                    "genuinely_absent requires coverage_ready=True — with coverage unknown or "
                    f"False (got {self.coverage_ready!r}) the honest answer is unknowable, and "
                    "reading one as the other is a false negative inference about a customer")
            if not self.coverage_basis:
                raise ValueError(
                    "genuinely_absent requires coverage_basis — the receipt for 'we looked and "
                    "it was not there' is the list of what we looked at")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def licenses_negative_inference(self) -> bool:
        """May a layer above say "nobody owns this", "they never replied", "it was never sent"?

        True only for `GENUINELY_ABSENT`. Serialized with the row so a consumer reads the licence
        rather than re-deriving it from `absence_type` with its own idea of the rule.
        """
        return self.absence_type in NEGATIVE_INFERENCE_TYPES

    @property
    def is_finding(self) -> bool:
        """A `GENUINELY_ABSENT` fact is not a data-quality complaint, it is an OUTPUT: the
        Ownership surface is built from exactly these. Named separately from the licence because
        the two questions diverge the moment a sixth absence type is added."""
        return self.absence_type is AbsenceType.GENUINELY_ABSENT


__all__ = ["NEGATIVE_INFERENCE_TYPES", "AbsenceType", "MissingFact"]
