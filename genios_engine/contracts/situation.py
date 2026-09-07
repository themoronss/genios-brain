"""D-01 · `BusinessSituationObject` v2 and V-1..V-8 — the one object that crosses L2 -> L3.

Layer 1 hands up `QualifiedEnterpriseSignal`: one message, qualified. This is the answer to the
question no single signal can be asked — *what is going on with this account, how much does it
matter, how sure are we, and what could we not see*. Everything above reads only this object, the
same way L2 reads only C-12.

**This is a v2 of a contract that was already good, and the problem was never the contract.** The
frozen dataclass at `contracts/domain_expertise.py:55` is immutable, validated, basis-point
enforced, and it REQUIRES `importance_bp` and evidence. It asked exactly the right question. L2
had no answer, so it supplied 5000 — `context/situation_bso.py`'s `DEFAULT_IMPORTANCE_BP`, stamped
on every situation the builder ever produced, which is why 193 of 223 signals on the design
partner's org shared one importance and Layer 4's utility formula had nothing to rank on.

So the single most important property of the type below is what it will NOT let you express.

* `importance` is an `ImportanceAttribution`, not an int, and it has **no default at any level**.
  A constant cannot arrive by omission.
* An attribution whose `basis` is `UNSCORED` must carry `score_bp = 0` and no components. Zero is
  an ABSENCE — the convention `situation_bso.UNSCORED_VERSION` already relies on — and a consumer
  must read `basis` to tell it from a measured zero. What is now unconstructible is the state that
  did the damage: a neutral midpoint that nothing measured, sitting in the same column as a score,
  indistinguishable from one.
* A SCORED attribution must carry a non-empty `components` map and a `version`. "Why is this a
  7400" has to be answerable from the stored row without recomputation — which matters most
  precisely when it is hardest, after the weights were retuned and a recomputation would quietly
  rewrite history.
* `INHERITED` must satisfy `score_bp == base_bp`. If a modifier moved the number, the basis is
  `COMPOSED` and the modifiers are in `components`, where a reader can see them.

The components are deliberately NOT required to sum to the score. L1's `ImportanceComponents` is a
weighted mean under a multiplier, not a sum, and a reconciliation rule here would make the L1
score inexpressible at this seam — the contract would have prevented the cutover it exists to
enable. What the contract can honestly demand is that the terms are present, integral, and
versioned.

**Confidence is a six-axis vector, and an axis with no basis is `None`.** `context/situations.py`
already got this right and had nowhere to put it: it composes `overall` as the MINIMUM of the axes
that have a basis and deliberately leaves out the ones that do not, because "we cannot tell how
current this is" must never read as "this is stale" — and it carries `COVERAGE_UNKNOWN = -1` as a
sentinel outside the 0..100 range for exactly the same reason. A flat `Mapping[str, int]` cannot
say that: every consumer doing `.get(axis, 0)` reads an unmeasured axis as a zero. So the axes are
`int | None`, `composed_from` names the ones that actually went into `overall_bp`, and the
weakest-link ceiling is enforced over those.

**`matched_conditions` is the field to insist on.** *"This fired because of these five facts"* is
what makes a situation explainable at L3 and defensible on a card. Without it, a pattern match is
an assertion — and an assertion rendered in the same typography as a fact is how a founder learns
not to trust the product. `pattern_id` without `matched_conditions` is therefore refused.

**V-1..V-8 exist twice, on purpose, and the two are not redundant.** Every rule is enforced at
CONSTRUCTION by the type that owns the field (universal rule 5: the validator runs at the seam
that produced the object), which is stricter and earlier — a situation that cannot be built cannot
be published by accident. `validate_situation` re-checks all eight over an assembled object and
returns a typed `SituationDecision` rather than raising, because there are two documented ways
past a constructor (`model_construct`, and a row rehydrated by something that is not this class),
and because the caller's next move after a refusal is to write a ledger row, not to unwind a
stack. That is the same division `contracts/publication.py` draws at L1.6.10.

**The failure action is REJECT for all eight, and that is a real difference from L1.** At L1, V-1
PARKS (an unestablished audience is a recoverable question) and V-5 DOWNGRADES (an unverified span
degrades trust without destroying the signal). Doc 08's L2 table gives every one of these eight
the same action: reject. It is encoded as data in `LAW_ACTIONS` rather than assumed, because
getting a failure action backwards does not fail loudly — it silently changes what reaches the
layer above, and a rule that was supposed to reject but parks is a claim published with a caveat
nobody reads.

GAP FLAG — doc 08's addition list has no `correlations` field, yet V-6 and V-7 govern
`MetricCorrelation` and nothing at this seam would otherwise carry one. The field is added here
(the alternative is two laws with no object to run over), and the doc should be amended.

GAP FLAG — the v1 dataclass typed `evidence`, `entities`, `relationships`, `timeline` and
`dependencies` as tuples of free-form mappings, and `context/situation_bso.py` synthesises a
receipt (`{"reconstructed": True}`) when a correlation has no qualified signal behind it. Those
lanes are typed here, and the synthetic receipt has no spelling in `EvidenceSpan` — by design, it
was never a receipt. The information it carried is not lost: `provenance_refs` takes the event and
source-object ids as what they actually are, join keys rather than quotes. The X8 cutover must
therefore map a reconstruction onto `provenance_refs`, and a situation whose only "evidence" was
reconstructed is one this contract refuses — which is the intended consequence, not an oversight.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from genios_engine.contracts.analytic import (DIRECTIONAL, MAX_TREND_CONFIDENCE_BP,
                                              MIN_COHORT_POPULATION, MIN_CORRELATION_SAMPLES,
                                              MIN_TREND_POINTS, Anomaly, CohortPosition,
                                              MetricCorrelation, MetricPoint, Trend,
                                              require_measure)
from genios_engine.contracts.conflict import Conflict, require_no_float
from genios_engine.contracts.dependency import DependencyChain
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.quality import MissingFact
from genios_engine.contracts.validators import (require_aware, require_bool, require_bp,
                                                require_enum, require_identifier,
                                                require_non_negative, require_sorted_unique,
                                                require_text)
from genios_engine.contracts.visibility import Visibility

#: The v2 schema id. A NEW string rather than a bump of `business-situation.v1`, because the v1
#: value is baked into `expertise_packages` content addresses that already exist: reusing it would
#: make two structurally different objects hash into the same address space.
BUSINESS_SITUATION_V2_VERSION = "business-situation.v2"

#: `context/situations.py`'s four lifecycle states, verbatim (`STATUS_ACTIVE`, `STATUS_DORMANT`,
#: `STATUS_RESOLVED`, `STATUS_ARCHIVED`). Enforced as a frozenset over a `str` field rather than
#: as an enum for the reason `signal.py` gives for `SIGNAL_STATES`: `context_situations.status` is
#: a text column and the wire form, the column and the contract must stay the same literal word.
#: Spelled here rather than imported because `contracts/` may not import `context/` — the topology
#: test enforces that — and `tests/contracts/test_l2_contracts.py` pins the two together.
SITUATION_STATES: frozenset[str] = frozenset({"active", "dormant", "resolved", "archived"})

#: The six confidence axes, exactly. Doc 05's own acceptance row is "confidence vector axes on
#: every situation: all 6", and five of them already exist as functions in
#: `context/situations.py` (`evidence_score`, `freshness_score`, `consistency_score`,
#: `identity_score`, `coverage_score`); `analytic` is doc 05's one addition, reflecting the
#: quality of the comparative inputs a situation's trends and cohorts rest on.
CONFIDENCE_AXES: tuple[str, ...] = ("evidence", "freshness", "consistency", "identity",
                                    "coverage", "analytic")


def _stable(value: Any) -> Any:
    """Normalise an open-lane value into the shape it will come back as from JSON.

    The two `Any`-typed lanes on this object — `ImportanceAttribution.inputs` and
    `BusinessSituationObject.metadata` — are round-tripped through `context_situations`' jsonb,
    and a lane that accepts a `list` returns a `list` while a lane that accepted a `tuple`
    returns a `list` too. Without this, an object built from a tuple and the same object read
    back from its own row are unequal, which makes every equality check on a stored situation a
    coin flip and every "did this change" comparison wrong in the direction that re-writes the
    row. Sequences become tuples in BOTH directions, so the two forms converge.

    Deliberately narrow: it re-shapes containers and touches no scalar, so it cannot repair a
    value the way a coercing validator would. `require_no_float` still runs alongside it.
    """
    if isinstance(value, Mapping):
        return {str(key): _stable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_stable(item) for item in value)
    return value


class ImportanceBasis(str, Enum):
    """WHERE the number came from. Required, no default — see the module docstring.

    The three members are the three honest answers, and the distinction between them is the one
    `situation_bso.py`'s `importance_source` metadata key was reaching for with four string
    literals nothing validated.
    """

    #: BLG-18 ran: a base taken from the strongest constituent signal, plus the L2-only modifiers
    #: (trend, cohort, anomaly, dependency, conflict, staleness, coverage) that no single signal
    #: could know. `components` carries every term.
    COMPOSED = "composed"
    #: Layer 1's score, carried through unchanged because no L2 modifier applied. `score_bp` must
    #: equal `base_bp`; if they differ, something modified it and the basis is COMPOSED.
    INHERITED = "inherited"
    #: Nothing measured this. `score_bp` is 0 and that 0 is an ABSENCE, not a low score — a
    #: consumer that ranks on it without reading `basis` puts every unmeasured situation below
    #: every measured one, which is the opposite of what "a floor must never refuse what it could
    #: not measure" protects.
    UNSCORED = "unscored"


class ImportanceAttribution(BaseModel):
    """The score, its provenance, and the terms that explain it — one object, no defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Which of the three. See `ImportanceBasis`.
    basis: ImportanceBasis
    #: 0..10000. HOW BIG IS THIS THING, and never how urgent — priority is relative to a person's
    #: whole book and belongs to Layer 4. An $84K renewal is a big thing on any day.
    score_bp: int
    #: The strongest constituent signal's own importance (BLG-18 step 1 takes the MAX, never the
    #: mean: a situation holding one critical signal and four routine ones is a critical
    #: situation, and averaging is how it becomes a routine one). `None` only when UNSCORED.
    base_bp: int | None
    #: Which version of the formula produced this. Stored on every situation so a weight change
    #: cannot make March's importance incomparable to September's without saying so.
    version: str
    #: Every NUMERIC term, signed. A modifier that SUBTRACTS (staleness, the coverage penalty)
    #: is stored as the negative delta it applied — including the multiplicative coverage step,
    #: whose applied delta is what makes it readable at all. Non-empty for any scored basis.
    components: dict[str, int]
    #: The non-numeric context the arithmetic ran AGAINST — which baseline currency, which
    #: baseline basis, which entity standing, which flags were raised.
    #:
    #: A second lane rather than widening `components` to `Any`, and the reason is concrete:
    #: L1's `ImportanceComponents.as_record` (`capture/esqe/importance.py:618`) emits thirteen
    #: keys of which four are a string, two enum values and a list. Widening the numeric lane to
    #: hold them would give up the property that every term is an integer — the one thing that
    #: makes "why is this a 7400" arithmetic a reader can check — while dropping them would make
    #: the real L1 record inexpressible at this seam and break the cutover. `context/situations.
    #: Confidence` already draws exactly this line with its own `inputs` field.
    inputs: Mapping[str, Any] = {}

    @field_validator("basis", mode="before")
    @classmethod
    def _basis(cls, value: Any) -> ImportanceBasis:
        return require_enum(value, ImportanceBasis, "basis")

    @field_validator("score_bp", mode="before")
    @classmethod
    def _score(cls, value: Any) -> int:
        return require_bp(value, "score_bp")

    @field_validator("base_bp", mode="before")
    @classmethod
    def _base(cls, value: Any) -> int | None:
        return None if value is None else require_bp(value, "base_bp")

    @field_validator("version", mode="before")
    @classmethod
    def _version(cls, value: Any) -> str:
        return require_identifier(value, "importance version")

    @field_validator("components", mode="before")
    @classmethod
    def _components(cls, value: Any) -> dict[str, int]:
        """Signed integers, no floats, at any depth of nothing — the map is flat by contract.

        Flat because a nested component map is a component nobody renders: the whole purpose is a
        table a human reads next to the number, and `require_measure` refuses the float that a
        `0.8` coverage multiplier would otherwise leave here.
        """
        if not isinstance(value, Mapping):
            raise TypeError("importance components must be a mapping of term to basis points")
        return {require_text(name, "component name"): require_measure(term, f"component {name}")
                for name, term in value.items()}

    @field_validator("inputs", mode="before")
    @classmethod
    def _inputs(cls, value: Any) -> Mapping[str, Any]:
        """String keys, no float at any depth. A ratio smuggled in here reaches the same jsonb
        column the components do."""
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise TypeError("importance inputs must be a mapping")
        return {require_text(key, "input name"):
                _stable(require_no_float(item, f"inputs.{key}"))
                for key, item in value.items()}

    @model_validator(mode="after")
    def _explains_itself(self) -> ImportanceAttribution:
        """The rules that make the 5000 constant unconstructible. See the module docstring.

        UNSCORED is pinned to 0 with no components and no base: the state that caused the damage
        was a neutral MIDPOINT nothing measured, sitting in the same column as a real score. Zero
        is the honest spelling of "nothing scored this" and `basis` is what a consumer reads to
        tell it from a measured zero.

        A scored basis must name its terms. An unexplained score is one that cannot be defended
        the day somebody asks, and it cannot be compared across a weight change either.

        INHERITED must equal its base, or it is not inherited — it is composed, and the modifier
        that moved it belongs in `components` where a reader can see it.
        """
        if self.basis is ImportanceBasis.UNSCORED:
            if self.score_bp != 0:
                raise ValueError(
                    f"an unscored situation must carry score_bp=0, got {self.score_bp} — a "
                    "midpoint nothing measured is indistinguishable from a real score in the "
                    "same column, which is the defect this contract exists to close")
            if self.base_bp is not None or self.components:
                raise ValueError(
                    "an unscored situation has no base and no components — carrying either "
                    "claims an arithmetic that did not happen")
            if self.inputs:
                raise ValueError(
                    "an unscored situation has no inputs — there was no arithmetic for them to "
                    "be the context of")
            return self
        if self.base_bp is None:
            raise ValueError(
                f"a {self.basis.value} score must name the constituent signal it was built from")
        if not self.components:
            raise ValueError(
                f"a {self.basis.value} score must carry its components — 'why is this a "
                f"{self.score_bp}' has to be answerable from the stored row, and it has to stay "
                "answerable after the weights move")
        if self.basis is ImportanceBasis.INHERITED and self.score_bp != self.base_bp:
            raise ValueError(
                f"an inherited score must equal its base ({self.score_bp} != {self.base_bp}) — "
                "if a modifier moved it the basis is composed and the modifier belongs in "
                "components")
        return self

    @property
    def is_measured(self) -> bool:
        """Did anything actually score this? The read every ranker must make before sorting."""
        return self.basis is not ImportanceBasis.UNSCORED


class ConfidenceVector(BaseModel):
    """Six axes, each of which may honestly have NO basis, plus the composed number.

    `overall_bp` is bounded by the weakest axis that went into it. Composition is otherwise a
    machine for manufacturing certainty: several weak axes agreeing is not corroboration, and a
    mean over them produces a number larger than anything it was computed from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Are the receipts real and plural? (`evidence_score`: event count x source count.)
    evidence_bp: int | None = None
    #: How old is the newest thing we know? `None` when there is nothing dated to judge — which
    #: is NOT the same as stale, and is exactly why the axes are nullable.
    freshness_bp: int | None = None
    #: Do the sources agree? (open discrepancies.)
    consistency_bp: int | None = None
    #: Are we sure these are the same people? (open merge proposals.)
    identity_bp: int | None = None
    #: Did we see enough to be talking about this? `None` is `situations.COVERAGE_UNKNOWN` — "we
    #: never declared what complete means for this domain" — and it must never read as either
    #: fully covered or fully absent.
    coverage_bp: int | None = None
    #: How good are the comparative inputs the trends and cohort positions rest on? Doc 05's one
    #: addition to the vector. `None` when the situation makes no comparative claim at all.
    analytic_bp: int | None = None
    #: The composed answer, 0..10000.
    overall_bp: int
    #: WHICH axes were composed into `overall_bp`. Non-empty, each naming an axis that has a
    #: basis. Stored rather than inferred because "we left freshness out because we could not
    #: measure it" and "freshness was fine" are different facts that an inferred rule would
    #: collapse — and because the composition rule itself may change.
    composed_from: tuple[str, ...]

    @field_validator("evidence_bp", "freshness_bp", "consistency_bp", "identity_bp",
                     "coverage_bp", "analytic_bp", mode="before")
    @classmethod
    def _axis(cls, value: Any, info: ValidationInfo) -> int | None:
        return None if value is None else require_bp(value, info.field_name or "axis")

    @field_validator("overall_bp", mode="before")
    @classmethod
    def _overall(cls, value: Any) -> int:
        return require_bp(value, "overall_bp")

    @field_validator("composed_from", mode="before")
    @classmethod
    def _composed_from(cls, value: Any) -> tuple[str, ...]:
        if value is None or isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError("composed_from must be a sequence of axis names")
        axes = require_sorted_unique(value, "confidence axis")
        unknown = sorted(set(axes) - set(CONFIDENCE_AXES))
        if unknown:
            raise ValueError(
                f"composed_from names axes that do not exist: {unknown} — the six are "
                f"{list(CONFIDENCE_AXES)}")
        return axes

    @model_validator(mode="after")
    def _weakest_link(self) -> ConfidenceVector:
        """Every composed axis has a basis, and `overall_bp` never exceeds the weakest of them.

        The first half is what stops a composition over an axis nobody measured: a `None` axis
        named in `composed_from` would be read as a zero by one consumer and skipped by another.

        The second is Rule 11 applied one layer up. `context/situations.py` composes with `min`
        today, which satisfies this with equality; the ceiling is stated rather than the formula
        so a later weighted composition is still legal, and still cannot exceed its weakest input.
        """
        if not self.composed_from:
            raise ValueError(
                "composed_from must name at least one axis — a confidence composed from nothing "
                "is a number with no inputs")
        axes = self.axes
        blind = [name for name in self.composed_from if axes[name] is None]
        if blind:
            raise ValueError(
                f"composed_from names axes with no basis: {blind} — an unmeasured axis reads as "
                "a zero to every consumer that composes it and as fine to every one that does "
                "not")
        floor = min(axes[name] for name in self.composed_from)     # type: ignore[type-var]
        if self.overall_bp > floor:
            raise ValueError(
                f"overall_bp {self.overall_bp} exceeds its weakest composed axis ({floor}) — "
                "composition may not manufacture certainty out of agreeing weak inputs")
        return self

    @property
    def axes(self) -> dict[str, int | None]:
        """The six, by name. The read a renderer makes; `None` stays `None` and is never a 0."""
        return {name: getattr(self, f"{name}_bp") for name in CONFIDENCE_AXES}

    @property
    def measured_axes(self) -> tuple[str, ...]:
        """The axes that have a basis at all, composed or not — what a "go connect a source"
        prompt is built from."""
        return tuple(name for name in CONFIDENCE_AXES if getattr(self, f"{name}_bp") is not None)


class SituationEntity(BaseModel):
    """One counterparty or subject the situation is actually about.

    Typed because the v1 lane was a free mapping and the builder put ONE element in it — the
    anchor node — so a situation anchored on a connector's address with 68 correlated events
    reported as being about one entity, the bot, rather than the dozens of real people it
    introduced. Every layer above inherited that: a rejected pitch to one introduced founder read
    as evidence about all of them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The graph node id. `require_text`, not `require_identifier`: node ids are frequently email
    #: addresses, `+` tags are legal in one, and a real customer must not be unrepresentable
    #: because their address is well-formed in a way the identifier class is not.
    id: str
    #: person | organization | external_contact | unknown — the graph's own vocabulary, kept open
    #: because it is extended by connectors rather than by this contract.
    type: str
    #: What to call it on a card.
    name: str
    #: How many correlated events this entity appears on. `None` means not counted (the anchor-
    #: only path), which is a different fact from zero and must not be spelled the same way.
    event_count: int | None = None

    @field_validator("id", "type", "name", mode="before")
    @classmethod
    def _labels(cls, value: Any, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "entity field")

    @field_validator("event_count", mode="before")
    @classmethod
    def _count(cls, value: Any) -> int | None:
        return None if value is None else require_non_negative(value, "event_count")


class SituationRelationship(BaseModel):
    """A typed edge between two of the situation's entities, as the situation understands it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    target_id: str
    #: works_at | corresponded_with | reports_to | owns — the graph's edge vocabulary, open for
    #: the same reason `SituationEntity.type` is.
    kind: str
    #: How sure we are of the EDGE, which is a different question from how sure we are of the
    #: situation. `None` when the edge came from a source that states rather than infers.
    confidence_bp: int | None = None

    @field_validator("source_id", "target_id", "kind", mode="before")
    @classmethod
    def _labels(cls, value: Any, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "relationship field")

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> int | None:
        return None if value is None else require_bp(value, "confidence_bp")

    @model_validator(mode="after")
    def _two_ends(self) -> SituationRelationship:
        if self.source_id == self.target_id:
            raise ValueError(
                f"a relationship needs two ends ({self.source_id!r} to itself) — a self-edge "
                "inflates every degree count without describing anything")
        return self


class TimelinePoint(BaseModel):
    """One dated moment in the situation's life.

    The v1 lane carried a single mapping of `{first_seen_at, last_seen_at}`, which is two facts
    wearing one row and cannot be extended to a third without every reader learning a new key.
    Two points express the same thing and a renderer can sort them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: WORLD time — when the thing happened, tz-aware UTC. Never an ingest stamp: a two-month-old
    #: backfilled thread stamped at ingest looks like this morning's news.
    at: datetime
    #: first_seen | last_seen | deadline | renewal — what happened at that moment.
    label: str
    #: The event or document this moment came from, if any. A join key, not a receipt.
    ref: str | None = None

    @field_validator("at")
    @classmethod
    def _when(cls, value: datetime) -> datetime:
        return require_aware(value, "timeline at")

    @field_validator("label", mode="before")
    @classmethod
    def _label(cls, value: Any) -> str:
        return require_text(value, "timeline label")

    @field_validator("ref", mode="before")
    @classmethod
    def _ref(cls, value: Any) -> str | None:
        return None if value is None else require_text(value, "timeline ref")


class MatchedCondition(BaseModel):
    """ONE of the facts that made the pattern fire, with the receipt behind it.

    A `MatchedCondition` is by construction satisfied — there is no `satisfied` flag, because a
    flag that is always True is a field every reader eventually stops checking. A condition that
    did NOT hold is not a match; a condition whose input was unavailable is a
    `quality.MissingFact`, which is a different type because it licenses a different inference.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The fact path the condition tested — dotted, machine-readable, joinable to the graph.
    field_path: str
    #: eq | gt | exists | contains — the pack's predicate vocabulary, open by the same argument
    #: as the other open vocabularies here.
    operator: str
    #: What the condition required and what was actually there. Scalars only: a condition whose
    #: observed value is a nested structure is one a card cannot render and a human cannot check.
    #: `bool` precedes `int` in the union so `True` does not rehydrate as `1`.
    expected: bool | int | str | None = None
    observed: bool | int | str | None = None
    #: The spans this condition was satisfied BY. Non-empty — this is the entire point of the
    #: field: without it a pattern match is an assertion, and an assertion in a fact's typography
    #: is how a founder learns not to trust the product.
    evidence: tuple[EvidenceSpan, ...]

    @field_validator("field_path", mode="before")
    @classmethod
    def _path(cls, value: Any) -> str:
        return require_identifier(value, "field_path")

    @field_validator("operator", mode="before")
    @classmethod
    def _operator(cls, value: Any) -> str:
        return require_text(value, "operator")

    @model_validator(mode="after")
    def _cites_something(self) -> MatchedCondition:
        if not self.evidence:
            raise ValueError(
                f"matched condition {self.field_path!r} must cite the evidence it matched on — "
                "'this fired because of these facts' is what makes a situation defensible")
        return self


class BusinessSituationObject(BaseModel):
    """D-01 v2 · Layer 2's complete, immutable output to Layer 3. Read the module docstring.

    **Frozen**, unlike `QualifiedEnterpriseSignal`. A signal has a life — ALG-19 moves it through
    four states — while a situation object is a SNAPSHOT that is content-addressed into
    `expertise_packages`: an in-place edit would leave a stored address pointing at content that
    no longer exists. A situation whose world changed produces a new object, and the lifecycle
    lives on the `context_situations` row rather than on the artifact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- envelope -------------------------------------------------------------------------

    #: The tenant boundary. Every query above filters on it.
    org_id: str
    #: Which sweep observed this. Deliberately NOT part of the content address — `domain_shadow`
    #: mints a fresh trace id per situation per sweep, and hashing it minted a new expertise
    #: package every time, which put 995 MB on one tenant's database and took the project
    #: read-only. See `content_key`.
    trace_id: str
    #: The audience of the ORIGINAL evidence, never widened. A situation is a DERIVED claim and
    #: its audience can only ever be as narrow as the narrowest thing it was derived from.
    visibility: Visibility
    #: Pinned to `BUSINESS_SITUATION_V2_VERSION`; a value from another schema is refused rather
    #: than tolerated, because the fields' meanings are not stable across it.
    schema_version: str = BUSINESS_SITUATION_V2_VERSION

    # --- identity -------------------------------------------------------------------------

    #: The situation's own id (`context_situations.situation_id`).
    id: str
    #: The situation TYPE, from the domain registry — renewal_at_risk, deal_stalled, and so on.
    type: str
    #: One of `SITUATION_STATES`.
    state: str
    #: Which business domains this situation belongs to. Sorted and deduplicated so two sweeps
    #: over an unchanged situation produce byte-identical content.
    domain_ids: tuple[str, ...] = ()

    # --- what it is made of ----------------------------------------------------------------

    #: The qualified signals this situation rests on, in EVERY lifecycle state. Provenance only
    #: grows; filtering it by state made a situation's own account of itself decay as it aged and
    #: re-minted its content address on every ALG-19 sweep. At least one is required: a situation
    #: is a correlation OF signals, and one with none is a claim about nothing.
    signal_ids: tuple[str, ...]
    #: The real distinct counterparties, not the anchor alone. See `SituationEntity`.
    entities: tuple[SituationEntity, ...] = ()
    relationships: tuple[SituationRelationship, ...] = ()
    timeline: tuple[TimelinePoint, ...] = ()
    #: The blocking structure, from BLG-05. What makes a deadline more than a calendar entry.
    dependencies: tuple[DependencyChain, ...] = ()

    # --- trust ------------------------------------------------------------------------------

    #: The verbatim receipts. Non-empty, always: a claim with no receipt is a guess, and this
    #: object is the input to everything a founder is eventually shown.
    evidence: tuple[EvidenceSpan, ...]
    #: Event ids and source-object ids the situation was assembled from — JOIN KEYS, not
    #: receipts, and typed as what they are so nothing has to dress one up as a quote.
    provenance_refs: tuple[str, ...] = ()
    #: Six axes plus the composed number. See `ConfidenceVector`.
    confidence: ConfidenceVector
    #: May a NEGATIVE inference be made in this situation's domain — "they never replied", "no
    #: owner is recorded"? `None` is unhinted and is NOT False. Required with no default: a
    #: defaulted licence is one nobody granted.
    coverage_ready: bool | None
    #: The disagreements this situation is built across, BOTH sides retained (C-10 keeps no
    #: winner). A situation built on a contradicted claim must not reach Layer 3 looking settled.
    conflicts: tuple[Conflict, ...] = ()
    #: POINTERS to the `signal_conflicts` rows, the same discipline `qualified_signals.
    #: conflict_ids` keeps one layer down. A separate field and not derived from `conflicts`
    #: because C-10 carries no id of its own (the id is a column, not a contract field), so a
    #: situation that references a stored disagreement without embedding both sides of it has
    #: nowhere else to say so.
    conflict_ids: tuple[str, ...] = ()
    #: Typed absence. The `GENUINELY_ABSENT` entries are findings, not data-quality complaints.
    missing_facts: tuple[MissingFact, ...] = ()

    # --- the score --------------------------------------------------------------------------

    #: The number, its provenance and its terms. No default at any level — see the module
    #: docstring on why that is the single most important property of this type.
    importance: ImportanceAttribution

    # --- analytic context (the L2.4 payoff) --------------------------------------------------

    trends: tuple[Trend, ...] = ()
    cohort_positions: tuple[CohortPosition, ...] = ()
    anomalies: tuple[Anomaly, ...] = ()
    #: See the module GAP FLAG: doc 08 lists no field for these, and V-6/V-7 govern them.
    correlations: tuple[MetricCorrelation, ...] = ()

    # --- explainability ----------------------------------------------------------------------

    #: Which authored pattern fired, or None for a situation that was correlated rather than
    #: matched.
    pattern_id: str | None = None
    #: The per-condition evidence. Required whenever `pattern_id` is set.
    matched_conditions: tuple[MatchedCondition, ...] = ()

    # --- the open lane -----------------------------------------------------------------------

    #: Everything that is genuinely tenant- or sweep-specific and has no field of its own. Walked
    #: for floats at construction, because this is the one lane wide enough to smuggle one and it
    #: reaches a jsonb column where a ratio comes back out as a number nobody can trace.
    metadata: Mapping[str, Any] = {}

    # ------------------------------------------------------------------ envelope + identity

    @field_validator("org_id", "trace_id", "id", "type", mode="before")
    @classmethod
    def _identifier(cls, value: Any, info: ValidationInfo) -> str:
        return require_identifier(value, info.field_name or "identifier")

    @field_validator("schema_version", "state", mode="before")
    @classmethod
    def _required_label(cls, value: Any, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "label")

    @field_validator("schema_version")
    @classmethod
    def _known_schema(cls, value: str) -> str:
        if value != BUSINESS_SITUATION_V2_VERSION:
            raise ValueError(
                f"unsupported business situation schema {value!r} — the field meanings are not "
                f"stable across versions; this contract is {BUSINESS_SITUATION_V2_VERSION}")
        return value

    @field_validator("state")
    @classmethod
    def _known_state(cls, value: str) -> str:
        """A state outside the four is a situation that every `status = 'active'` query neither
        includes nor excludes on purpose — it simply disappears."""
        if value not in SITUATION_STATES:
            raise ValueError(
                f"state must be one of {sorted(SITUATION_STATES)}, got {value!r}")
        return value

    @field_validator("signal_ids", "domain_ids", mode="before")
    @classmethod
    def _sorted_ids(cls, value: Any, info: ValidationInfo) -> tuple[str, ...]:
        """Sorted and deduplicated. Both fields are hashed into the content address, so a
        different iteration order over the same set would mint a new package for an unchanged
        situation — the mechanism behind the 995 MB read-only incident."""
        label = info.field_name or "id"
        if value is None or isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError(f"{label} must be a sequence of ids")
        return require_sorted_unique(value, label)

    @field_validator("provenance_refs", "conflict_ids", mode="before")
    @classmethod
    def _join_keys(cls, value: Any, info: ValidationInfo) -> tuple[str, ...]:
        label = info.field_name or "join key"
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError(f"{label} must be a sequence of join keys")
        return require_sorted_unique(value, label)

    @field_validator("coverage_ready", mode="before")
    @classmethod
    def _tri_state_coverage(cls, value: Any) -> bool | None:
        """A literal bool or a literal None. Truthiness is how an empty string would grant the
        licence to make a negative inference."""
        return None if value is None else require_bool(value, "coverage_ready")

    @field_validator("pattern_id", mode="before")
    @classmethod
    def _pattern(cls, value: Any) -> str | None:
        return None if value is None else require_identifier(value, "pattern_id")

    @field_validator("metadata", mode="before")
    @classmethod
    def _metadata(cls, value: Any) -> Mapping[str, Any]:
        """String keys, and no float at any depth. `require_no_float` is imported from
        `conflict.py` — the same one V-8 runs — rather than re-implemented, so the lane cannot
        accept at construction what the gate would refuse at publication."""
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise TypeError("metadata must be a mapping")
        return {require_text(key, "metadata key"):
                _stable(require_no_float(item, f"metadata.{key}"))
                for key, item in value.items()}

    # ------------------------------------------------------------------ whole-object rules

    @model_validator(mode="after")
    def _publishable(self) -> BusinessSituationObject:
        """What a situation must have before anything above is allowed to read it.

        Signals and evidence first: a situation is a correlation OF qualified signals, and one
        that names none is a claim about nothing; a claim with no receipt is a guess. Both were
        already enforced by the v1 dataclass and are kept verbatim — the v2 additions are
        additive, and a rule that got quietly relaxed in a rewrite is the kind of regression a
        passing test suite does not notice.

        `pattern_id` without `matched_conditions` is the new one, and it is doc 08's own
        insistence: "this fired because of these five facts" is what makes a situation
        explainable at L3 and defensible on a card. A pattern id alone is an assertion.
        """
        if not self.signal_ids:
            raise ValueError(
                "a business situation requires at least one qualified signal — a correlation of "
                "nothing is a claim about nothing")
        if not self.evidence:
            raise ValueError(
                "a business situation requires evidence — a claim with no receipt is a guess")
        if self.pattern_id is not None and not self.matched_conditions:
            raise ValueError(
                f"pattern {self.pattern_id!r} fired with no matched conditions — a pattern match "
                "that cannot name the facts behind it is an assertion, and it renders in the "
                "same typography as a fact")
        return self

    # ------------------------------------------------------------------ reads

    @property
    def importance_bp(self) -> int:
        """The v1 field name, as a read. Every existing consumer of `situation.importance_bp`
        keeps working across the X8 cutover; what changed is that it can no longer be SET to a
        constant, only read from an attribution that had to explain itself."""
        return self.importance.score_bp

    @property
    def confidence_bp(self) -> int:
        """The v1 field name, as a read — the composed axis, bounded by its weakest input."""
        return self.confidence.overall_bp

    @property
    def contested_fields(self) -> tuple[str, ...]:
        """The field paths two sources disagree about, from the EMBEDDED conflicts.

        Derived rather than stored, and deliberately NOT the same read as `conflict_ids`: C-10
        carries no id, so the ids point at stored rows while this names what is actually in
        dispute on the object in hand. A renderer asking "is this settled" wants this one.
        """
        return tuple(sorted({conflict.field for conflict in self.conflicts}))

    @property
    def findings(self) -> tuple[MissingFact, ...]:
        """The absences that are OUTPUT rather than gaps — "no owner", "no amendment", "no
        reply". The only ones that license a negative inference."""
        return tuple(fact for fact in self.missing_facts if fact.is_finding)

    def content_key(self) -> dict[str, Any]:
        """WHAT THIS SITUATION IS — the payload a content address may be computed over.

        `trace_id` is absent, and its absence is the whole point. A trace id identifies one
        OBSERVATION of a situation, not the situation: `domain_shadow` mints a fresh one per
        situation per sweep, so including it made every compile address to a brand-new id even
        when nothing had changed. The publisher's `on conflict do nothing` then never fired and
        each sweep wrote a fresh ~238 kB row per situation — 4,086 rows and 995 MB on the design
        partner's database, 67% of the whole thing, and the project crossed into read-only, which
        stops every write the product makes rather than only this one.

        `model_dump(mode="json")` rather than a hand-built dict so a field added later is in the
        address by default: the failure of forgetting to add one is two different situations
        sharing an address, which is silent and permanent.
        """
        payload = self.model_dump(mode="json")
        payload.pop("trace_id", None)
        return payload


# ====================================================================== V-1..V-8, the gate


class L2Law(str, Enum):
    """The eight laws, by doc 08's own ids. The value is what a ledger row stores.

    Ids rather than prose because these are cited by number across the L2 documents and in every
    conversation that follows a situation nobody can explain. A row that says `V-2` joins to the
    rule table; one that says "cohort too small" is a sentence somebody will later rewrite.
    """

    #: `CohortPosition` without `cohort_id` or `population_size`. **Law 2** — every comparison
    #: names its population.
    V1 = "V-1"
    #: `CohortPosition.population_size < 5`. Law 2's floor.
    V2 = "V-2"
    #: `MetricPoint` with `known=False` carrying a value. NEVER interpolate.
    V3 = "V-3"
    #: `Trend.trend_confidence_bp > 8000`. A trend is never certain.
    V4 = "V-4"
    #: `Trend` with `point_count < 4` claiming RISING or DECLINING. No trend on noise.
    V5 = "V-5"
    #: `MetricCorrelation.n < 20`. No correlation on five points.
    V6 = "V-6"
    #: `MetricCorrelation.is_causal is True`. Correlation is never cause.
    V7 = "V-7"
    #: A float anywhere in the serialized object. Integer basis points, everywhere.
    V8 = "V-8"


class LawAction(str, Enum):
    """What a failed law DOES. One member today, and the type still earns its place.

    L1 has three actions and the difference between them is load-bearing: V-1 parks (recoverable),
    V-5 downgrades (non-blocking), the rest reject. Doc 08's L2 table gives all eight of these
    REJECT — so the set is uniform, and writing that down as data is what makes it checkable
    rather than assumed. Getting a failure action backwards does not fail loudly: it silently
    changes what reaches the layer above.
    """

    REJECT = "reject"


#: Every law's action, explicitly. Uniform today (see `LawAction`); a law that later downgrades or
#: parks is a one-line change here plus a branch in `validate_situation`, rather than a condition
#: somebody has to notice.
LAW_ACTIONS: Mapping[L2Law, LawAction] = {law: LawAction.REJECT for law in L2Law}


class SituationOutcome(str, Enum):
    """What the gate decided. Two outcomes, because all eight laws reject."""

    #: Every law held. `situation` on the decision is the object to hand upward.
    ADMIT = "admit"
    #: At least one law failed. `situation` is NOT carried, so a caller cannot publish a rejected
    #: object by reaching through the result — it already holds the input and writes that, with
    #: `failures`, into the rejection ledger.
    REJECT = "reject"


class LawFailure(BaseModel):
    """One law that did not hold, with the sentence a reviewer needs and the object it was on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Which law. See `L2Law`.
    law: L2Law
    #: WHICH sub-object tripped it — "cohort_positions[1]", "trends[0].evidence_points[3]". A
    #: situation carries many analytic objects and "V-3 failed" is unactionable without knowing
    #: which point interpolated.
    subject: str
    #: WHY, in one line, naming the offending value. By the time anyone reads this the situation
    #: is a row in another table and the stack that produced it is gone.
    detail: str

    @property
    def action(self) -> LawAction:
        """What this failure does. Read from `LAW_ACTIONS` rather than assumed, so a future
        non-rejecting law changes behaviour by changing the table."""
        return LAW_ACTIONS[self.law]


class SituationDecision(BaseModel):
    """The gate's answer: what to do, which laws failed, and on what.

    Deliberately not a bool and deliberately not an exception. A bool cannot name the law a
    rejection ledger has to record; an exception cannot be written to a row without the caller
    re-deriving, from a message string, what it already knew.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: admit | reject.
    outcome: SituationOutcome
    #: Every law that did not hold, in V-order — all of them, not only the first. A situation
    #: that fails V-2 and V-6 has two different upstream bugs, and fixing one would otherwise
    #: reveal the other a day later.
    failures: tuple[LawFailure, ...] = ()
    #: The object to hand upward. `None` on reject — see `SituationOutcome.REJECT`.
    situation: BusinessSituationObject | None = None

    @property
    def admitted(self) -> bool:
        return self.outcome is SituationOutcome.ADMIT


def _word(value: Any) -> str:
    """The wire word for an enum-or-raw field, WITHOUT assuming it is an enum.

    Every helper below reads a bypassed object — that is the whole reason the gate exists beside
    the constructors — and a row rehydrated from `context_situations` jsonb carries `direction`
    as the plain string `"declining"`, not a `TrendDirection`. `direction.value` on that string
    raises `AttributeError` out of a function whose contract is to RETURN a decision, so the
    caller's rejection-ledger row is never written and the failure looks like a crash in the
    layer above rather than a situation that broke a law.
    """
    return str(getattr(value, "value", value))


def _claims(value: Any) -> bool:
    """Is this flag asserting something? Truthiness, deliberately, and not `is True`.

    The constructors run `require_bool`, so inside a constructed object the flag is a literal
    bool and the two readings agree. This function is only ever reached by an object that did
    NOT go through one, and there the flag arrives as whatever the row held: psycopg hands back
    `1` for a jsonb `1`, and `x is True` reads that as *no claim* — which admitted a causal
    correlation and an interpolated metric point past V-7 and V-3 respectively, the two laws
    whose entire purpose is that no downstream layer can receive those claims.

    Truthiness refuses more than it must (a stray `"false"` string is truthy and is refused).
    That direction is the correct one for a REJECT law: an unreadable flag on an object that
    bypassed its own constructor is not something to hand to Layer 3.
    """
    return bool(value)


def _cohort_failures(position: Any, subject: str) -> list[LawFailure]:
    """V-1 and V-2 over one cohort position, tolerating a bypassed object.

    Read defensively with `getattr` because the whole reason this runs after construction is that
    the object may not have been through one: `model_construct` and a hand-rehydrated row both
    reach here with fields the constructor would have refused.
    """
    failures: list[LawFailure] = []
    cohort_id = getattr(position, "cohort_id", None)
    population = getattr(position, "population_size", None)
    if not cohort_id or not isinstance(cohort_id, str) or not cohort_id.strip():
        failures.append(LawFailure(
            law=L2Law.V1, subject=subject,
            detail="cohort_id is missing — a percentile whose population is unnamed cannot be "
                   "checked, disagreed with or reproduced (Law 2)"))
    if population is None or isinstance(population, bool) or not isinstance(population, int):
        failures.append(LawFailure(
            law=L2Law.V1, subject=subject,
            detail=f"population_size is missing or not an integer ({population!r}) — a "
                   "percentile without its population is a number nobody can check (Law 2)"))
    elif population < MIN_COHORT_POPULATION:
        failures.append(LawFailure(
            law=L2Law.V2, subject=subject,
            detail=f"population_size {population} is below {MIN_COHORT_POPULATION} — below that "
                   "a percentile ranks individuals and calls it a distribution"))
    return failures


def _metric_point_failures(point: Any, subject: str) -> list[LawFailure]:
    """V-3 over one metric point. A point that is not KNOWN may carry no value.

    Read through `_claims` rather than `known is False`: a rehydrated row carries `0`, and `0 is
    False` is `False` in Python, so the identity test admitted exactly the fabricated observation
    this law exists to refuse. `None` — the shape a bypassed object with no `known` at all
    presents — is a gap too: a value whose measured-ness nobody stated is not a measurement.
    """
    known = getattr(point, "known", None)
    value = getattr(point, "value_bp", None)
    if value is not None and not _claims(known):
        return [LawFailure(
            law=L2Law.V3, subject=subject,
            detail=f"known={known!r} carries value_bp={value!r} — an interpolated value is a "
                   "fabricated observation and it inflates the coverage ratio that exists to "
                   "reveal the gap")]
    return []


def _trend_failures(trend: Any, subject: str) -> list[LawFailure]:
    """V-4 and V-5 over one trend, plus V-3 over every point it carries."""
    failures: list[LawFailure] = []
    confidence = getattr(trend, "trend_confidence_bp", None)
    if isinstance(confidence, int) and not isinstance(confidence, bool) \
            and confidence > MAX_TREND_CONFIDENCE_BP:
        failures.append(LawFailure(
            law=L2Law.V4, subject=subject,
            detail=f"trend_confidence_bp {confidence} exceeds {MAX_TREND_CONFIDENCE_BP} — a "
                   "trend is never certain"))
    direction = getattr(trend, "direction", None)
    points = getattr(trend, "point_count", None)
    if direction in DIRECTIONAL and isinstance(points, int) and not isinstance(points, bool) \
            and points < MIN_TREND_POINTS:
        failures.append(LawFailure(
            law=L2Law.V5, subject=subject,
            detail=f"a {_word(direction)} trend rests on {points} points, below "
                   f"{MIN_TREND_POINTS} — two readings and a line between them is noise with an "
                   "opinion"))
    for index, point in enumerate(getattr(trend, "evidence_points", ()) or ()):
        failures.extend(_metric_point_failures(point, f"{subject}.evidence_points[{index}]"))
    return failures


def _correlation_failures(correlation: Any, subject: str) -> list[LawFailure]:
    """V-6 and V-7 over one correlation. See `_claims` on why V-7 is truthiness, not `is True`."""
    failures: list[LawFailure] = []
    n = getattr(correlation, "n", None)
    if n is None or isinstance(n, bool) or not isinstance(n, int) \
            or n < MIN_CORRELATION_SAMPLES:
        failures.append(LawFailure(
            law=L2Law.V6, subject=subject,
            detail=f"n={n!r} is below {MIN_CORRELATION_SAMPLES} — five points correlate at 0.9 "
                   "by chance, and a spurious pairing is worse than silence because somebody "
                   "acts on it"))
    causal = getattr(correlation, "is_causal", False)
    if _claims(causal):
        failures.append(LawFailure(
            law=L2Law.V7, subject=subject,
            detail=f"is_causal is {causal!r} — L2 measures co-movement and never cause, and no "
                   "downstream layer may receive a causal claim from it no matter what it asks "
                   "for"))
    return failures


def validate_situation(situation: BusinessSituationObject) -> SituationDecision:
    """THE L2 GATE · run all eight laws over an assembled situation and return a typed decision.

    Every rule here is also enforced at construction by the type that owns the field, and the
    duplication is deliberate — see the module docstring. This function exists for the objects
    that did not go through a constructor (`model_construct`, a row rehydrated by hand, a builder
    that assembled a sub-object before a later edit tightened its rules) and for the caller whose
    next move is a ledger row rather than a stack unwind.

    Failures are returned in V-order and ALL of them are returned, because a situation that fails
    V-2 and V-6 has two different upstream defects and fixing one would otherwise reveal the other
    a day later. `situation` is carried on the decision only when it is admitted, so publishing a
    rejected object cannot be done by reaching through the result.
    """
    failures: list[LawFailure] = []
    for index, position in enumerate(situation.cohort_positions or ()):
        failures.extend(_cohort_failures(position, f"cohort_positions[{index}]"))
    for index, trend in enumerate(situation.trends or ()):
        failures.extend(_trend_failures(trend, f"trends[{index}]"))
    for index, correlation in enumerate(situation.correlations or ()):
        failures.extend(_correlation_failures(correlation, f"correlations[{index}]"))
    try:
        require_no_float(situation, "situation")
    except (TypeError, ValueError) as exc:
        failures.append(LawFailure(
            law=L2Law.V8, subject="situation",
            detail=f"{exc} — every score is integer basis points and a ratio stored as jsonb "
                   "comes back out as a number nobody can trace to a source"))
    order = {law: rank for rank, law in enumerate(L2Law)}
    ranked = tuple(sorted(failures, key=lambda failure: (order[failure.law], failure.subject)))
    if ranked:
        return SituationDecision(outcome=SituationOutcome.REJECT, failures=ranked)
    return SituationDecision(outcome=SituationOutcome.ADMIT, situation=situation)


__all__ = ["BUSINESS_SITUATION_V2_VERSION", "CONFIDENCE_AXES", "LAW_ACTIONS", "SITUATION_STATES",
           "BusinessSituationObject", "ConfidenceVector", "ImportanceAttribution",
           "ImportanceBasis", "L2Law", "LawAction", "LawFailure", "MatchedCondition",
           "SituationDecision", "SituationEntity", "SituationOutcome", "SituationRelationship",
           "TimelinePoint", "validate_situation"]
