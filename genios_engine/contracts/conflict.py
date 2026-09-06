"""C-10 · Conflict and C-10a · ConflictClaim — the record that refuses to pick a winner quietly.

The worked fault this type exists for: a signed PDF says the annual commitment is $74,000, an
email in the same thread says "the $84K annual contract". v1 wrote whichever landed last into
the graph and told the founder one number with no indication the other existed. That is the
failure mode that ends trust permanently — not being wrong, but being *confidently wrong with a
receipt that looks legitimate*.

So this contract has **no ``winner`` field**, and it is not an omission to be fixed later.
Detection (ALG-12, L1.5.5) may resolve a disagreement, and when it does it records *which rule
resolved it* in ``resolution`` — but it writes both claims, both authorities and both sets of
evidence into ``signal_conflicts`` and keeps them there. The losing claim is never deleted,
because the founder routinely knows something the authority ranking does not: that the PDF is
the superseded draft, that the email quotes the amendment nobody uploaded. A resolution is a
recommendation with its reasoning attached, not a deletion.

Two boundaries are drawn deliberately, and both are the same boundary evidence.py draws:

* **Detection does not happen here.** Which values compete, whether two amounts are the same
  amount, whether two date windows overlap, and which rule fires — all ALG-12 at
  ``genios_engine/capture/validate/conflict.py``. This module owns only what a conflict must be
  true of once one exists.
* **The authority table does not live here.** ``authority_rank`` arrives from ALG-14 (L1.5.8,
  the authority weighter). A copy of that lookup table in a contract is a second table that
  forks from the first the day either is edited, so what is enforced below is the *shape* of a
  rank — an integer inside ALG-14's range — and never the class→rank mapping itself.

**V-7 lives here too.** ``value`` and ``resolved_value`` are typed ``ClaimValue``, which ends in
``Any`` and is therefore the one hole in this document's no-float rule: every other field is an
``int`` or a string, and no annotation can stop ``74000.10`` from being handed to an ``Any``.
``require_no_float`` below is the guard, and it is exported because C-12's ``versions`` field has
the same hole and should reuse it rather than grow a second copy.

GAP FLAG — the obvious guard would be ``validators.freeze``, which the spec names as the repo's
existing float refusal. It cannot be used here: ``freeze`` runs ``platform.canonical.canonicalize``,
which has no branch for a pydantic ``BaseModel`` and raises ``unsupported semantic value`` on
one. The headline fixture's value is a ``Money`` — a ``BaseModel`` — so freezing it would reject
the exact case this file was written for. ``require_no_float`` therefore mirrors canonicalize's
accept-list and adds the ``BaseModel`` branch canonicalize is missing.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import fields as dataclass_fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.units import Money, ResolvedDate
from genios_engine.contracts.validators import (require_aware, require_identifier,
                                                require_non_negative)

#: What a disputed value may be, and the ONLY reason this is not a bare ``Any``.
#:
#: Doc 08 types both value fields ``Any``, and the openness is deliberate — the field being
#: disputed is not known to the contract, so a closed union would make some future dispute
#: unrepresentable. That openness is preserved exactly: ``Any`` is the last member, so a string,
#: an int, a list of contract terms or a nested mapping all validate unchanged and re-serialise
#: byte-identically.
#:
#: What the two leading members buy is REHYDRATION, and it is a correctness property rather than
#: a convenience. A conflict is stored in ``signal_conflicts.claims`` as jsonb; under a bare
#: ``Any`` a ``Money`` written there comes back as a plain ``dict``, so the stored row no longer
#: satisfies this module's own stated contract that a claim's value is "already normalized". The
#: cost is concrete: ``Money.same_amount`` and ``ResolvedDate.overlaps`` ARE ALG-12's comparison
#: ladder, and neither exists on a dict — a re-judgement of a stored conflict would have to
#: re-implement them against raw keys, which is the second implementation this file's docstring
#: refuses everywhere else. It also breaks doc 08's own W0 acceptance line, "round-trip:
#: QualifiedEnterpriseSignal -> model_dump_json -> reparse is identical", for the exact fixture
#: the type was written for: the $74K signed PDF against the "$84K" email.
#:
#: Pydantic's smart union resolves a mapping carrying C-02's or C-03's fields to that model and
#: lets everything else fall through to ``Any`` untouched, so nothing is narrowed and nothing is
#: coerced. ``require_no_float`` still runs ``mode="before"``, ahead of any union member, which
#: is what stops ``74000.0`` being quietly accepted as an ``int`` by a lax coercion.
ClaimValue = Union[Money, ResolvedDate, Any]

#: The top of ALG-14's ranking table (L1.5.8): a signed / executed document. The bound is not
#: decoration — it is what actually enforces this type's stated invariant that `authority_rank`
#: "is a rank, not a probability". A bare `int` check would let a 7,500 bp confidence score be
#: pasted into the rank field, and 7500 vs 2 is a rank difference of 7,498, which resolves every
#: conflict it touches by authority in favour of whichever side leaked a bp value.
MAX_AUTHORITY_RANK = 6


def require_no_float(value: Any, label: str) -> Any:
    """V-7 — prove a value carries no float anywhere inside it, at any depth.

    The universal rule is "no float appears in the SERIALIZED object", not "no field is
    annotated float", because ``Any`` smuggles one past every annotation. Walking is the only
    way to honour the rule: a float nested three keys deep in a dict of contract terms reaches
    ``signal_conflicts.claims`` as jsonb and comes back out as a number nobody can trace to a
    source string.

    The accept-list mirrors ``platform.canonical.canonicalize`` exactly, plus the ``BaseModel``
    branch canonicalize lacks (see the module GAP FLAG). Anything outside it is refused rather
    than skipped: a value this function cannot walk is a value it cannot prove float-free, V-7's
    failure action is REJECT, and an object with no canonical form could not be written to the
    jsonb column anyway. ``complex`` is refused alongside ``float`` because its components are
    floats wearing a different type name.

    Returns the value unchanged — this proves a property, it does not repair one. Cyclic
    structures terminate on the identity set rather than recursing forever.
    """
    seen: set[int] = set()
    stack: list[Any] = [value]
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, str, Enum, datetime, date, UUID)):
            continue                                  # canonicalize's scalars; bool before int
        if isinstance(item, (float, complex)):
            raise TypeError(
                f"{label} must not contain a float ({item!r}) — every score is integer basis "
                "points and every amount is integer minor units")
        if isinstance(item, Decimal):
            if not item.is_finite():
                raise ValueError(f"{label} must not contain a non-finite Decimal")
            continue
        marker = id(item)
        if marker in seen:
            continue
        seen.add(marker)
        if isinstance(item, BaseModel):
            stack.extend(getattr(item, name) for name in type(item).model_fields)
            continue
        if is_dataclass(item) and not isinstance(item, type):
            stack.extend(getattr(item, f.name) for f in dataclass_fields(item))
            continue
        if isinstance(item, Mapping):
            stack.extend(item.keys())
            stack.extend(item.values())
            continue
        if isinstance(item, (list, tuple)) or (
                isinstance(item, Set) and not isinstance(item, (str, bytes, bytearray))):
            stack.extend(item)
            continue
        raise TypeError(
            f"{label} may not contain a {type(item).__name__} — a value that cannot be walked "
            "cannot be proven float-free, and cannot be stored as jsonb")
    return value


class Authority(str, Enum):
    """The provenance class of the source that made a claim — ALG-14's vocabulary.

    A ``str`` enum so the wire form is the doc's literal string and the stored jsonb reads as
    text, while the set stays closed: an unknown provenance class must be a schema decision,
    not a typo that reaches conflict resolution as a rank nobody assigned.

    The doctrine rank each member carries is noted below for the reader. It is deliberately NOT
    a lookup table in this module and is never cross-checked against ``authority_rank`` — see
    the module docstring. ALG-14 owns the mapping; contracts owning a second copy is how the two
    silently disagree.

    GAP FLAG (cross-doc): doc 08's C-10 comment lists five classes —
    ``signed_document | attachment | email_prose | chat_aside | structured_source``. Doc 05's
    ALG-14 table has seven rows: those five plus company canon at rank 5 and inferred /
    unattributed at rank 0. Enforcing only doc 08's five would make an uploaded pricing policy
    disagreeing with an email — canon vs prose, a real and material conflict — unrepresentable,
    so both extra rows are admitted here. This follows the reconciliation ``units.py`` already
    made for ``UNKNOWN_CURRENCY``, where doc 08's validator and doc 05's algorithm disagreed the
    same way and the algorithm's need won without weakening what the doc-08 rule protected.
    """

    #: rank 6 — a countersigned or executed agreement. The top of the table.
    SIGNED_DOCUMENT = "signed_document"
    #: rank 5 — company canon: the org deliberately asserting something about itself, an
    #: uploaded pricing policy or handbook. `SourceEvent.internal_kind` is what marks it.
    COMPANY_CANON = "company_canon"
    #: rank 4 — a structured source of record: a HubSpot deal field, a client DB row.
    STRUCTURED_SOURCE = "structured_source"
    #: rank 3 — a document attached to a message: the PDF quote inside an email.
    ATTACHMENT = "attachment"
    #: rank 2 — email prose. "the $84K contract" is a person's recollection, not the contract.
    EMAIL_PROSE = "email_prose"
    #: rank 1 — a chat aside. A Slack one-liner is the weakest thing a human actually wrote.
    CHAT_ASIDE = "chat_aside"
    #: rank 0 — inferred / unattributed, ALG-14's floor for a `source_ref` prefix its table does
    #: not map (an unmapped prefix logs a warning and ranks 0, it never crashes). Rare inside a
    #: ConflictClaim, since a claim here must carry evidence and rank 0 describes a claim with no
    #: evidence pointer at all — but an unmapped prefix on a real span lands exactly here.
    INFERRED = "inferred"


class ConflictResolution(str, Enum):
    """Which rule settled the disagreement — and by construction, WHY.

    There is no separate free-text reason field, on purpose. These three members *are* the
    complete reason vocabulary ALG-12 step 4 can produce, and a prose field beside them would
    drift from the enum on the first card that explained a resolution differently from the rule
    that made it. The card copy (L1.5.5-U3) renders from the member, so the explanation and the
    decision can never disagree.
    """

    #: The default and the doctrine. Both values go to the human, with no recommendation.
    #: ALG-12 lands here on equal authority AND on a rank difference of exactly 1 — one step of
    #: authority is not enough to silence the other side.
    UNRESOLVED_SURFACE_BOTH = "unresolved_surface_both"
    #: An authority gap of >= 2 ranks. The signed PDF outranks the email by four, so the card
    #: says which one to trust — and still shows both. `resolved_value` is the higher-ranked
    #: claim's value, never a third number.
    RESOLVED_BY_AUTHORITY = "resolved_by_authority"
    #: A tie-break WITHIN one authority rank: the amendment supersedes the original. Recency
    #: only ever breaks ties — a newer email never beats an older signed document, which is why
    #: this can never be the resolution for claims of differing rank.
    RESOLVED_BY_RECENCY = "resolved_by_recency"


class ConflictClaim(BaseModel):
    """One side of a disagreement: what was asserted, who asserted it, how much that source
    counts, and the receipt.

    A claim is the unit that survives resolution. Both of them are written to
    ``signal_conflicts.claims`` and neither is ever pruned, so this object has to carry enough
    on its own to be re-judged later by a human who disagrees with the ranking: the value, the
    provenance class in words, the rank that class had *at detection time*, and the verbatim
    quote it came from.
    """

    #: Frozen and extra-forbidding for the same reason `EvidenceSpan` is: a claim whose value
    #: can be edited after the fact is not a record of what a source said, and the evidence
    #: below would still point at text the claim no longer asserts. `extra="forbid"` also means
    #: a mistyped field name raises here rather than vanishing into a stored row.
    model_config = ConfigDict(frozen=True, extra="forbid")

    #: What this source asserted, already normalized — a `Money` (integer minor units + ISO
    #: code), a `ResolvedDate` (a window plus a certainty), or a plain string / int for a text
    #: field. `ClaimValue` is `Any` widened by nothing and narrowed by nothing — see that
    #: constant for why the two normalized types are named ahead of it, and why the width is
    #: still exactly why `require_no_float` runs over it below.
    #:
    #: Normalized, not raw, because ALG-12 step 2 compares AFTER normalization: "$84K" and
    #: "USD 84,000" are one amount written twice, and comparing the raw strings would report a
    #: disagreement between two sources that agree. The literal source text is not lost — it
    #: rides along in `Money.as_written` / `ResolvedDate.as_written` and in `evidence`.
    value: ClaimValue

    #: The provenance class of the source. Closed set; see `Authority`.
    authority: Authority

    #: ALG-14's rank for that class, 0..MAX_AUTHORITY_RANK. NOT a bp score and never scaled to
    #: one — ALG-12 step 4 subtracts two of these and compares the difference to 2, arithmetic
    #: that is meaningless the moment the scale changes.
    #:
    #: Stored per claim rather than derived from `authority` on read, because it is the rank
    #: that was in force when the conflict was detected. If the table is later re-tuned, a
    #: stored conflict must still explain the resolution it actually made, not the one today's
    #: table would make.
    authority_rank: int

    #: Universal rule 4. Non-empty is enforced below: a claim with no receipt is a guess, and a
    #: guess is not something to weigh against a signed document. Note the spans are not
    #: required to be `verified` here — V-5 is the one non-blocking rule, and it downgrades
    #: confidence at the qualified-signal seam rather than destroying the claim at this one.
    evidence: list[EvidenceSpan]

    @field_validator("value", mode="before")
    @classmethod
    def _no_float_value(cls, value: Any) -> Any:
        """V-7, at the seam that produced the object. `mode="before"` so a float is refused
        before it is ever bound to the field."""
        return require_no_float(value, "ConflictClaim.value")

    @field_validator("authority_rank", mode="before")
    @classmethod
    def _rank_in_table(cls, value: Any, info: ValidationInfo) -> int:
        """A whole number inside ALG-14's table. `require_non_negative` refuses a bool and a
        float (pydantic's lax mode would otherwise turn `4.0` into `4` and `True` into `1`),
        and the ceiling is what stops a bp score masquerading as a rank."""
        rank = require_non_negative(value, info.field_name or "authority_rank")
        if rank > MAX_AUTHORITY_RANK:
            raise ValueError(
                f"authority_rank must be between 0 and {MAX_AUTHORITY_RANK} (ALG-14's table); "
                f"got {rank} — a rank is not a basis-point score")
        return rank

    @model_validator(mode="after")
    def _require_evidence(self) -> ConflictClaim:
        """CV-EVID. Without this, the cheapest way to win a conflict would be to assert a value
        with nothing behind it and a high authority string."""
        if not self.evidence:
            raise ValueError(
                "a conflict claim requires evidence — a claim with no receipt is a guess, and "
                "a guess must not be weighed against a document")
        return self


class Conflict(BaseModel):
    """Two sources disagree about the same field. Both sides are kept, permanently.

    Produced by ALG-12 at L1.5.5 and stored in ``signal_conflicts``. Read the class docstring
    of ``ConflictResolution`` for what ``resolution`` can say; read the module docstring for why
    there is no ``winner``.
    """

    #: `extra="forbid"` is load-bearing here, not hygiene. The single most likely future edit to
    #: this contract is somebody adding `winner=...` at a call site because it would make a
    #: renderer simpler. With pydantic's default the kwarg is silently ignored and the caller
    #: believes it stored something; forbidding extras turns that into an error at the seam.
    #: Frozen for the same reason the claims are: a detected conflict is a record of a
    #: disagreement that happened, and a record that can be edited after the fact is not one.
    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The dotted field path the two claims disagree about — "contract.value", "renewal.date".
    #: Validated as an identifier: dots and colons are allowed, whitespace and quotes are not,
    #: because this string is written into `signal_conflicts.field`, joined on, logged, and
    #: rendered into card copy — four contexts that would otherwise each need their own escaping.
    field: str

    #: Both sides, always, in every resolution mode. Length >= 2 is enforced below: a "conflict"
    #: with one claim is a fact, and the type that exists to stop facts being silently replaced
    #: must not itself be constructible as a single fact.
    #:
    #: Whether two claims genuinely compete is NOT decided here — ALG-12 step 3 owns the
    #: tolerance ladder (money exact on minor_units+currency with no percentage tolerance, dates
    #: by window overlap, text casefold-equal after whitespace normalization). A contract cannot
    #: re-derive that without reimplementing the detector it is the output of.
    claims: list[ConflictClaim]

    #: Which rule settled it, or that nothing did. Closed set; see `ConflictResolution`.
    resolution: ConflictResolution

    #: The value the resolution points at — always one of the `claims` values, never a third
    #: number the detector computed. Required with no default, on the same grounds `ResolvedDate`
    #: refuses to default its window: passing `None` must be something somebody typed, because a
    #: resolution that defaults itself to "nothing won" is a resolution that disappears without
    #: anyone choosing to drop it.
    #:
    #: That it matches a claim is a property of ALG-12 step 4 (it selects the higher-ranked
    #: claim's value) and is deliberately not re-checked here: proving "equals one of the claims"
    #: for an arbitrary `Any` means re-implementing the normalized comparison ladder that lives
    #: in the detector, and a second implementation of it would eventually disagree with the
    #: first about whether "$84K" and "USD 84,000" are the same value.
    #:
    #: Same `ClaimValue` annotation as the claims it is copied from, and for the same reason: a
    #: resolved value that rehydrated as a bare dict while its source claim rehydrated as a
    #: `Money` would make the two incomparable on read-back — which is precisely the check a
    #: reviewer re-judging a stored resolution needs to run.
    resolved_value: ClaimValue

    #: When the disagreement was detected, tz-aware UTC. Required and never defaulted from the
    #: clock: a `datetime.now()` inside a contract makes a replay of a March event produce a
    #: different row than the original, and this row is evidence.
    detected_at: datetime

    @field_validator("field", mode="before")
    @classmethod
    def _dotted_path(cls, value: Any) -> str:
        return require_identifier(value, "field")

    @field_validator("resolved_value", mode="before")
    @classmethod
    def _no_float_resolved(cls, value: Any) -> Any:
        """V-7 again — the resolved value is copied out of a claim, and a guard on the claim
        alone would miss a caller that composed this field by hand."""
        return require_no_float(value, "Conflict.resolved_value")

    @field_validator("detected_at")
    @classmethod
    def _aware_detected_at(cls, value: datetime) -> datetime:
        """Runs AFTER pydantic's own parse, not before it — same as `ResolvedDate`'s eval-time
        validator, and for a concrete reason. `require_aware` type-checks for a `datetime`, so
        in `mode="before"` it would reject the ISO-8601 *string* a `signal_conflicts` row comes
        back as, making a stored conflict unrehydratable through `model_validate_json`. Let
        pydantic parse the string, then insist the result carries a timezone."""
        return require_aware(value, "detected_at")

    @model_validator(mode="after")
    def _coherent_conflict(self) -> Conflict:
        """CV-10 — the two rules that keep this record honest.

        The first stops a single fact from being dressed as a disagreement. The second and third
        are one rule seen from both sides: `resolution` and `resolved_value` must tell the same
        story. An `unresolved_surface_both` carrying a value has silently picked a winner while
        claiming not to have — precisely the behaviour this contract exists to prevent — and a
        `resolved_by_*` carrying `None` claims a rule fired and names nothing, so the card would
        say "the signed document has higher authority" next to a blank.

        GAP FLAG: doc 08's validator states only the first direction ("if unresolved then
        resolved_value is None"). The converse is enforced anyway because the state it admits is
        unrenderable, and V-7's ``Any`` typing means nothing else downstream would catch it.
        """
        if len(self.claims) < 2:
            raise ValueError(
                f"a conflict needs at least 2 claims, got {len(self.claims)} — one claim is a "
                "fact, not a disagreement")
        if self.resolution is ConflictResolution.UNRESOLVED_SURFACE_BOTH:
            if self.resolved_value is not None:
                raise ValueError(
                    "unresolved_surface_both must carry resolved_value=None — surfacing both "
                    "sides and naming a resolved value at once is picking a winner silently")
        elif self.resolved_value is None:
            raise ValueError(
                f"{self.resolution.value} requires a resolved_value — a resolution that names "
                "no value is not a resolution")
        return self

    @property
    def is_resolved(self) -> bool:
        """True when a rule settled it. Never read as "the other claim is gone" — it is not, in
        any resolution mode, and `claims` still holds both."""
        return self.resolution is not ConflictResolution.UNRESOLVED_SURFACE_BOTH

    @property
    def authority_gap(self) -> int:
        """The spread between the strongest and weakest claim's rank — ALG-12 step 4's input.

        Exposed because the card copy needs it in words ("the signed document has higher
        authority") and because a stored conflict whose gap is < 2 but whose resolution is
        `resolved_by_authority` is a detector bug that is otherwise invisible in the row.
        """
        ranks = [claim.authority_rank for claim in self.claims]
        return max(ranks) - min(ranks)


__all__ = ["MAX_AUTHORITY_RANK", "Authority", "ClaimValue", "Conflict", "ConflictClaim",
           "ConflictResolution",
           "require_no_float"]
