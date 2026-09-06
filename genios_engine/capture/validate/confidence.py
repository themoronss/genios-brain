"""ALG-13 · L1.5.7-U1 — the one place several beliefs become one number, under Rule 11.

Globe Rule 11, stated the way the doc states it: *a layer may lower confidence; it may only
raise it by adding independent evidence, and it must name that evidence.* The failure it
prevents is the hardest one in the system to see, because it "looks exactly like rigour": five
sources all repeating one weak recollection of a contract value, composed upward into an 8900
that nothing in the corpus supports. Several weak sources repeating one weak thing is not
corroboration. It is one weak thing, echoed.

That doctrine has a boundary already — W0's ``validate_publication`` runs V-6, which refuses a
signal whose ``confidence_bp`` exceeds the weakest source it names unless independent evidence
was explicitly named. A composer that violates Rule 11 therefore does not produce a wrong
number; it produces signals that V-6 silently rejects at the far end of the pipeline, and the
bug is then debugged three layers away from its cause. This module exists so the arithmetic and
the gate cannot disagree: the ceiling here is the same ``min()`` V-6 computes, and
``ComposedConfidence`` hands back exactly the two arguments V-6 takes.

**The four primitives are doc 05's, verbatim.** ``combine`` multiplies (same source: two
readings of one email are one email), ``corroborate`` adds a bounded, authority-damped share of
the remaining headroom (different sources: two documents agreeing is genuinely more than one),
``freshness_retained_bp``/``decay`` age the result, and the span penalty is *not* here — ALG-08
applies it at L1.5.1 before this unit ever sees a confidence.

**Independence is asserted, never inferred — and the assertion is REQUIRED.**
``ConfidenceSource.independence_key`` has no default: every caller must state an origin or state
``None``, and everything that states ``None`` lands in ONE group that can only ``combine``. The
grouping is the fail-closed direction on purpose — a composer that guessed independence from, say,
two different ``source_ref`` values would treat a forwarded email and its own quoted original as
two witnesses, which is precisely the echo Rule 11 is about. But a fail-closed DEFAULT is a trap
rather than a safeguard: combine-only means five agreeing sources compose to 3276 where one
composes to 8000, so a caller who never considered independence would read a number that is an
artifact of their own omission as the composer's verdict on their evidence. Required, with
``None`` still permitted, keeps the safe behaviour and removes the silence. The names of stated
origins travel out in ``ComposedConfidence.independent_evidence`` — because the carve-out the
rule allows is *naming*, not a boolean somebody set to True.

**Two seams, two behaviours, and the split is deliberate.** ``corroborate`` RAISES
``ConfidenceViolation`` when asked to lift a confidence with no name attached: that is doc 05's
literal GUARD, and at that seam an unnamed raise is a programming error in the caller — a
"warn" would let it ship. ``enforce_rule_11`` at the module's outer boundary CLAMPS instead,
and records that it did on ``ComposedConfidence.clamped``: an ingest run must not die halfway
because one composition overshot a ceiling, and a confidence that arrives lower than the
arithmetic wanted is a safe failure while a crash mid-batch is not. The clamp is not silent —
a clamp nobody can see is a ceiling that was never really there.

**What naming buys is a bounded RAISE of the ceiling, never its removal.** Doc 05: *"corroboration
from a named independent source raises but stays bounded"*. So ``enforce_rule_11`` clamps to
``corroborate(ceiling, strongest_independent)`` rather than returning the raw fold — the same
primitive, the same damping, the ceiling as its base. The alternative, which this module shipped
with, was an exemption: any one named corroborator returned the fold untouched, so a Slack aside
worth 3 bp of corroboration lifted a ceiling of 100 to 9003. An exemption with a name attached is
the failure doc 05 warns about by name, because the audit record then looks impeccable.

**Determinism.** Neither primitive is associative under integer division (``a*b//10000`` then
``*c`` differs from ``a`` then ``b*c//10000``), and ``corroborate`` is not commutative at all,
so composition order is a choice this module must make rather than inherit from whatever order a
caller happened to build a list in. The choice: **strongest authority first, then strongest
confidence, then name** — the strongest source is the base (or the prior, when there is one) and
weaker ones corroborate it, which
is both the mental model of the doc ("adding independent evidence" to a belief you already hold)
and the ordering ALG-14 already imposes for conflict resolution. The consequence worth stating:
the composed value is invariant under permutation of the input list, which the suite asserts by
shuffling.

Public surface::

    compose_confidence(sources, ...) -> ComposedConfidence   # ALG-13, the unit's entry point
    combine(a_bp, b_bp)              -> int                  # same source
    corroborate(a_bp, b_bp, ...)     -> int                  # independent source, NAMED
    freshness_retained_bp(days_old)  -> int                  # the vector's freshness axis
    decay(conf_bp, days_old=...)     -> int                  # age decay
    rule_11_ceiling(confidences)     -> int | None           # what V-6 will compute
    enforce_rule_11(value, ...)      -> int                  # the bounded clamp V-6 will check
    age_in_days(observed_at, eval_time=...) -> int           # time as a parameter, never a clock

PURE — integer basis points end to end, no clock, no model, no database, no network.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from genios_engine.capture.validate.authority import (Authority, multiplier_bp_of, rank_of)
from genios_engine.capture.validate.spans import BP_FULL
from genios_engine.contracts.signal import CONFIDENCE_COMPONENTS
from genios_engine.contracts.validators import (require_aware, require_bp, require_enum,
                                                require_non_negative, require_strings,
                                                require_text)

#: How much of a confidence a day of age costs, in basis points. 20 bp/day means a month-old
#: email keeps 94% of what it was worth, a six-month-old one keeps 64%, and anything past 500
#: days is worth nothing — which is the shape the decay has to have for the freshness axis to
#: mean "how recent is the newest supporting evidence" rather than "was this ever true".
#:
#: A parameter with a default rather than a constant burned into the arithmetic: renewal dates
#: age differently from a chat aside about headcount, and the day a domain needs its own rate
#: that must be one argument at the call site, not a fork of this module.
DEFAULT_AGE_DECAY_BP_PER_DAY = 20

#: The independence group every source that did NOT assert one falls into. Empty string, which
#: ``require_text`` guarantees no real key can be, so "unstated" cannot collide with a caller's
#: key. All unstated sources share this ONE group, and a group can only ``combine`` internally —
#: so anything the caller did not vouch for can lower a confidence and can never raise it.
_UNSTATED = ""


class ConfidenceViolation(ValueError):
    """Rule 11 was asked to be broken: a raise with no independent evidence named.

    A ``ValueError`` subclass so a caller that only catches ``ValueError`` still catches it,
    and a distinct type so a publisher can tell "this composition is illegal" apart from "this
    input was not basis points" — the first is a design error in the caller, the second is bad
    data, and they are fixed by different people.
    """


@dataclass(frozen=True, slots=True)
class ConfidenceSource:
    """One thing this signal's confidence rests on, and everything about it that changes weight.

    A typed input rather than a tuple or a dict, for the same reason ``authority.Provenance`` is
    one: a composition input gains dimensions over time (a per-source decay rate, a span grade),
    and each of those must arrive as a field with a default rather than as a key that some call
    site silently misspells and this module silently ignores.

    Frozen, because the composed value has to be reproducible on a replay and a caller that
    edits a source between two calls is how one signal acquires two confidences.
    """

    #: What this source IS, in words a human can check — a ``source_ref``, a document id, a
    #: deal id. Required and non-empty because this is the string that travels out as V-6's
    #: named independent evidence: the carve-out Rule 11 allows is naming, so an unnameable
    #: source can never take it.
    name: str
    #: What we believe this source alone, 0..10000, AFTER ALG-08's span penalty.
    confidence_bp: int
    #: The ORIGIN this source came from, stated by the caller — a thread id, a document id, a
    #: system name. ``None`` means "not asserted independent", and every such source shares one
    #: group that can only multiply. Two sources with the same key are one witness; two with
    #: different keys are two, and only then may one lift the other.
    #:
    #: REQUIRED, and deliberately without a default even though ``None`` is a legal value. The
    #: unstated group is the fail-closed direction and it can only ``combine``, which means five
    #: agreeing sources land at 3276 where one lands at 8000 — a caller who never thought about
    #: independence would silently get the one behaviour that can only LOSE confidence, and
    #: would read the result as the composer's opinion of its evidence rather than as its
    #: opinion of the caller's own omission. Making the field required does not change what
    #: ``None`` means; it changes ``None`` from an accident into an assertion.
    independence_key: str | None
    #: ALG-14's provenance class. It orders the fold (strongest source is the base) and damps
    #: how much this source may lift another — a Slack aside corroborating a signed contract
    #: moves it less than a second signed contract does. Defaults to the floor: an unstated
    #: provenance is treated as our own inference, which is the reading that cannot inflate.
    authority: Authority = Authority.INFERRED
    #: Age of this source at evaluation time, in whole days. A parameter and never a clock
    #: read — see ``age_in_days``. Zero means "as fresh as the evaluation instant".
    days_old: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_text(self.name, "source name"))
        object.__setattr__(self, "confidence_bp",
                           require_bp(self.confidence_bp, "source confidence"))
        object.__setattr__(self, "authority",
                           require_enum(self.authority, Authority, "source authority"))
        if self.independence_key is not None:
            object.__setattr__(self, "independence_key",
                               require_text(self.independence_key, "independence key"))
        object.__setattr__(self, "days_old", require_non_negative(self.days_old, "days_old"))

    @property
    def rank(self) -> int:
        """ALG-14's 0..6 ladder position for this source's provenance."""
        return rank_of(self.authority)


@dataclass(frozen=True, slots=True)
class ComposedConfidence:
    """ALG-13's answer: the scalar, the four-axis vector, and the two arguments V-6 will take.

    The vector is carried beside the scalar rather than collapsed into it because Globe's own
    open-blocker list names the collapse as a defect — *"confidence modelled as a scalar rather
    than a vector — cannot distinguish strong-evidence-no-expertise from weak-evidence"*. A
    single 6200 tells a human nothing; ``evidence 9000 / expertise 0 / freshness 6900 /
    coverage 4100`` tells them to go connect a source rather than go read a document.

    Only two of the four axes reach the scalar, and which two is not a judgement call: ALG-13's
    own pipeline is COMBINE/CORROBORATE then AGE DECAY, so the scalar is evidence aged by
    freshness — ``confidence_bp == evidence_bp * freshness_bp // 10000``, exactly, in every
    case including the clamped one. That equality is why Rule 11's ceiling is applied to
    ``evidence_bp`` and not to the aged scalar: a ceiling enforced after the decay leaves the
    axis it was supposed to bound holding the unbounded number, and the two fields then
    describe two different beliefs. ``expertise`` is 0 at Layer 1 by the doc's instruction (L3 fills it) and
    ``coverage`` answers a different question entirely — whether an ABSENCE can be trusted —
    so folding either one in would express "we have no domain pack loaded" as "this contract
    value is probably wrong".

    ``source_confidences`` and ``independent_evidence`` are shaped for ``validate_publication``
    to take directly. That is the point of returning them: V-6's ceiling and this module's
    ceiling are then the same list, rather than two lists a caller assembles twice.
    """

    #: The published belief, 0..10000 — the value that becomes ``QualifiedEnterpriseSignal
    #: .confidence_bp``. Already clamped to the Rule 11 ceiling unless independent evidence
    #: was named.
    confidence_bp: int
    #: How well the source TEXT supports this, before age — the fold's output AFTER Rule 11's
    #: ceiling. Clamped, because this axis is PUBLISHED: it is a key of ``vector`` and lands on
    #: ``QualifiedEnterpriseSignal.confidence_vector``, where V-6 (which reads only
    #: ``confidence_bp``) cannot see it. An axis handed out as the raw fold is the ceiling
    #: leaking past the one gate that checks it. What the arithmetic wanted before the clamp is
    #: kept on ``fold_bp``, so nothing about the clamp becomes invisible.
    evidence_bp: int
    #: Authored domain knowledge covering this claim. Always 0 out of Layer 1 unless a caller
    #: overrides it; doc 05 assigns this axis to L3.
    expertise_bp: int
    #: What the newest supporting source retains after age decay — the multiplier the scalar
    #: was aged by, kept visible so a stale-but-well-evidenced signal reads as stale.
    freshness_bp: int
    #: Are the sources complete enough to trust an absence? Caller-supplied; not folded.
    coverage_bp: int
    #: Every confidence this was composed FROM, in fold order, prior first when there was one.
    #: Hand this to ``validate_publication(source_confidences=...)`` — never the composed value
    #: itself, which would make V-6 trivially true.
    source_confidences: tuple[int, ...] = ()
    #: The names of the sources that actually LIFTED the value, empty when none did. Hand this
    #: to ``validate_publication(independent_evidence=...)``: non-empty is the waiver, and it
    #: is non-empty here only when a genuinely separate, named origin corroborated.
    independent_evidence: tuple[str, ...] = ()
    #: ``min(source_confidences)`` — the ceiling Rule 11 imposes, or None when nothing was
    #: composed from anything (no ceiling to respect, which is not the same as "passed").
    ceiling_bp: int | None = None
    #: True when the ceiling actually bound, i.e. the arithmetic wanted more than the weakest
    #: source allowed. Recorded rather than merely honoured: a clamp nobody can see is
    #: indistinguishable from a composer that never overshoots, and those need different fixes.
    clamped: bool = False
    #: What the fold produced BEFORE the ceiling — audit only, never published and never part
    #: of ``vector``. ``clamped`` says the ceiling bound; this says by how much, which is the
    #: difference between "the corpus was slightly weaker than the arithmetic hoped" and "the
    #: arithmetic manufactured 7405 bp the corpus never supported". Equal to ``evidence_bp``
    #: whenever nothing was clamped.
    fold_bp: int = 0
    #: The fold order that produced this, strongest first — the audit trail for "why 6400?".
    fold_order: tuple[str, ...] = field(default=())

    @property
    def vector(self) -> Mapping[str, int]:
        """The four axes keyed exactly as ``CONFIDENCE_COMPONENTS`` spells them.

        Built here rather than stored so the returned mapping cannot drift from the four typed
        fields above, and keyed off the contract's own frozenset so a renamed component fails
        at this line instead of at a ``confidence_vector`` validator one wave downstream.
        """
        vector = {"evidence": self.evidence_bp, "expertise": self.expertise_bp,
                  "freshness": self.freshness_bp, "coverage": self.coverage_bp}
        missing = CONFIDENCE_COMPONENTS - set(vector)
        if missing:                                   # pragma: no cover - contract drift guard
            raise ValueError(f"confidence vector is missing {sorted(missing)}")
        return vector


# --------------------------------------------------------------------------------------------
# ALG-13's four primitives, exactly as doc 05 prints them
# --------------------------------------------------------------------------------------------


def combine(a_bp: int, b_bp: int) -> int:
    """SAME source: ``(a * b) // 10000``. Multiplies, and therefore can only fall.

    Two readings of one email are one email. Multiplication is the arithmetic that says so:
    the product is never above either input, so no amount of re-reading a weak source turns it
    into a strong one. Doc 05's headline acceptance is this line — two 8000s give 6400, not
    8000 (which would make the second reading free) and not 9000 (which would make it
    evidence).

    Integer division truncates, so the rounding always goes against the claim. A composer that
    rounded up would hand back a basis point it had just decided was not earned.
    """
    return require_bp(a_bp, "confidence") * require_bp(b_bp, "confidence") // BP_FULL


def corroborate(base_bp: int, other_bp: int, *, evidence: str, authority: Authority,
                already_named: Sequence[str] = ()) -> int:
    """INDEPENDENT source: a bounded, authority-damped share of the remaining headroom.

    ``base + ((10000 - base) * other) // 10000 // 2``, then damped by ALG-14's multiplier for
    the corroborating source's provenance. Three properties, each load-bearing:

    * it is **bounded** — at most half the remaining headroom, so no chain of agreeing sources
      ever reaches certainty. Ten sources agreeing is very good and is still not 10000;
    * it is **proportional to the corroborator** — a 2000-confidence witness lifts almost
      nothing, because agreeing weakly is not the same as agreeing;
    * it is **authority-damped** — a Slack aside lifts a signed contract by 65% of what a
      second signed contract would. This is the term that makes the composition
      authority-weighted rather than merely authority-ordered, and it is why the fold puts the
      strongest source at the base.

    ``evidence`` is the GUARD doc 05 states literally: *a raise with no named independent
    source raises, it does not warn*. A blank name is refused here rather than defaulted,
    because "independent" that nobody can name is the echo this whole rule exists to stop.
    ``already_named`` refuses the second half of the same failure — a name that already
    corroborated cannot corroborate again, which is what a forwarded copy of an email looks
    like from the inside.
    """
    base = require_bp(base_bp, "confidence")
    other = require_bp(other_bp, "confidence")
    name = str(evidence or "").strip()
    if not name:
        raise ConfidenceViolation(
            "Rule 11: raise without named independent evidence — a layer may only raise a "
            "confidence by adding independent evidence, and it must name that evidence")
    seen = tuple(str(value or "").strip() for value in already_named)
    if name in seen:
        raise ConfidenceViolation(
            f"Rule 11: {name!r} has already corroborated this value — one source repeating "
            "itself is an echo, not a second witness")
    headroom = BP_FULL - base
    lift = headroom * other // BP_FULL // 2
    damped = lift * multiplier_bp_of(require_enum(authority, Authority, "authority")) // BP_FULL
    return base + damped


def freshness_retained_bp(days_old: int,
                          *, decay_bp_per_day: int = DEFAULT_AGE_DECAY_BP_PER_DAY) -> int:
    """The vector's freshness axis: ``max(0, 10000 - days_old * DECAY)``.

    Split out from ``decay`` because it is the number a card shows and the number the scalar is
    multiplied by, and computing it twice in two places is how a displayed freshness and an
    applied freshness end up disagreeing about the same evidence.
    """
    days = require_non_negative(days_old, "days_old")
    rate = require_non_negative(decay_bp_per_day, "decay_bp_per_day")
    retained = BP_FULL - days * rate
    return retained if retained > 0 else 0


def decay(confidence_bp: int, *, days_old: int,
          decay_bp_per_day: int = DEFAULT_AGE_DECAY_BP_PER_DAY) -> int:
    """AGE DECAY: ``conf * max(0, 10000 - days_old * DECAY) // 10000``. Monotonically down.

    Age is a parameter, never a clock read — the group law for ``capture/validate/`` (gate G1
    greps for it) and, more importantly, the only way a signal composed last March recomposes
    to the same number today. A validator that read the wall clock would silently re-age every
    replayed event to the moment the replay ran.
    """
    conf = require_bp(confidence_bp, "confidence")
    return conf * freshness_retained_bp(days_old, decay_bp_per_day=decay_bp_per_day) // BP_FULL


def age_in_days(observed_at: datetime, *, eval_time: datetime) -> int:
    """Whole days between two tz-aware instants, floored at zero. The clock's only door.

    Both arguments are required and both must be timezone-aware (``require_aware`` normalises
    to UTC), so a naive datetime cannot enter and be assumed to be in the reader's zone — an
    eight-hour offset expresses itself as a day of decay that is off by one, which is invisible
    on every card it touches.

    Evidence from the FUTURE floors at 0 rather than going negative: a clock-skewed connector
    stamping tomorrow on an email must not be able to hand this module a negative age and get
    a confidence multiplied above itself. That is Rule 11 broken by arithmetic accident.
    """
    observed = require_aware(observed_at, "observed_at")
    evaluated = require_aware(eval_time, "eval_time")
    days = (evaluated - observed).days
    return days if days > 0 else 0


# --------------------------------------------------------------------------------------------
# Rule 11's ceiling — the same arithmetic V-6 runs at the publication boundary
# --------------------------------------------------------------------------------------------


def rule_11_ceiling(source_confidences: Sequence[int]) -> int | None:
    """``min(sources)`` — the highest a composition may legally reach without naming.

    ``None`` for an empty list, and the distinction matters: it means "there is no ceiling to
    respect", which a caller must read as *V-6 did not apply here* rather than as *V-6 passed*.
    ``QualifiedEnterpriseSignal.confidence_respects_sources`` draws the same line for the same
    reason, and this function is deliberately its twin so the two seams cannot drift.
    """
    values = [require_bp(value, "source confidence") for value in source_confidences]
    return min(values) if values else None


def enforce_rule_11(value_bp: int, *, ceiling_bp: int | None,
                    independent_evidence: Sequence[str] = (), lift_bp: int = 0,
                    lift_authority: Authority = Authority.INFERRED) -> int:
    """Apply the ceiling; named independent evidence RAISES it, bounded. The outer boundary.

    Clamps rather than raising, and the asymmetry with ``corroborate`` is deliberate: this runs
    on every composition in a batch, and a ceiling that killed an ingest run would be a worse
    failure than a confidence that came out lower than the arithmetic wanted. The caller learns
    it happened from ``ComposedConfidence.clamped``.

    ``independent_evidence`` is the exception Rule 11 itself names, and it is a list of NAMES
    rather than a flag on purpose. A boolean would let a caller waive the rule by writing
    ``True``; a name is a thing a human can go and check, and it is the same value
    ``validate_publication`` records on the decision so the waiver is visible in the row rather
    than only in the arithmetic that produced it.

    **What naming buys is a bounded raise, not an exemption**, and that distinction is the
    whole unit. Doc 05 states it in four words — *"raises but stays bounded"* — and Rule 11 in
    six: *may only raise it BY ADDING independent evidence*. The size of the raise is therefore
    the size of the addition, computed with the same ``corroborate`` primitive the fold uses:
    the ceiling is the base, and the strongest independent corroborator lifts it by its bounded,
    authority-damped share of the headroom. Returning ``value`` unchanged instead — the shape
    this function had — meant one named Slack aside at 100 bp lifted a ceiling of 100 to 9003:
    3 bp of corroboration earned, 8903 bp of lift delivered. That is not a rule with an
    exception, it is a rule with an off switch, and it *"looks exactly like rigour"* (doc 05
    line 675) precisely because the name is right there in the record.

    ``lift_bp``/``lift_authority`` describe that strongest corroborator. They default to the
    floor (0 bp, ``INFERRED``) so an omission yields ``corroborate(ceiling, 0) == ceiling`` —
    the unwaived ceiling exactly. A caller that names evidence without saying what it was worth
    gets no lift, which is the fail-closed direction: the default cannot manufacture headroom.
    """
    value = require_bp(value_bp, "confidence")
    named = require_strings(independent_evidence, "independent evidence")
    if ceiling_bp is None:
        return value
    ceiling = require_bp(ceiling_bp, "ceiling")
    if not named:
        return min(value, ceiling)
    sanctioned = corroborate(ceiling, lift_bp, evidence=named[0], authority=lift_authority)
    return min(value, sanctioned)


# --------------------------------------------------------------------------------------------
# ALG-13 · the unit entry point
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Group:
    """One ORIGIN — every source the caller said came from the same place, already folded.

    Internal because it is an implementation detail of the fold, not a seam: what leaves this
    module is ``ComposedConfidence``. Grouping happens before any cross-source arithmetic so
    that "combine within, corroborate across" is a structural property of the algorithm rather
    than a branch somebody can later reorder.
    """

    key: str
    confidence_bp: int
    authority: Authority
    names: tuple[str, ...]

    @property
    def stated(self) -> bool:
        """Did the caller vouch for this origin? Only a stated origin may lift another."""
        return self.key != _UNSTATED


def _fold_group(key: str, members: Sequence[ConfidenceSource]) -> _Group:
    """COMBINE every source in one origin, strongest first."""
    ordered = sorted(members, key=lambda s: (-s.rank, -s.confidence_bp, s.name))
    value = ordered[0].confidence_bp
    for source in ordered[1:]:
        value = combine(value, source.confidence_bp)
    return _Group(key=key, confidence_bp=value, authority=ordered[0].authority,
                  names=tuple(sorted({source.name for source in ordered})))


def compose_confidence(sources: Sequence[ConfidenceSource], *, prior_bp: int | None = None,
                       expertise_bp: int = 0, coverage_bp: int = 0,
                       decay_bp_per_day: int = DEFAULT_AGE_DECAY_BP_PER_DAY,
                       ) -> ComposedConfidence:
    """ALG-13 — compose one confidence and its vector from the evidence available.

    The algorithm, in the order it runs:

    1. **Group by origin.** Sources sharing an ``independence_key`` are one witness; everything
       that stated no key shares the single unstated group. Within a group, COMBINE.
    2. **Order the groups** strongest first — authority rank, then confidence, then name. The
       strongest origin is the base a weaker one corroborates, never the reverse (see the
       module docstring on why an order had to be chosen at all).
    3. **Fold across groups.** A group with a stated key whose names have not already been
       counted CORROBORATES (bounded, authority-damped, and its names are recorded). Everything
       else COMBINES — which lowers. Unstated origins can therefore only ever cost confidence.
    4. **Age it** by the NEWEST supporting source. Doc 05 defines the freshness axis that way,
       and the alternative (the oldest, or a mean) would let one ancient source bury a claim
       that fresher evidence still supports.
    5. **Apply Rule 11's ceiling** — ``min`` over every source confidence and the prior. When
       step 3 named independent evidence the ceiling is RAISED by one bounded ``corroborate``
       step from the strongest corroborator, and the result is clamped to that. Naming buys the
       raise the arithmetic earned, never an exemption from the ceiling.

    Steps 4 and 5 run in that written order but the ceiling is applied to the EVIDENCE, so in
    the code the clamp comes first and the decay multiplies its result. The ceiling is a
    statement about what the corpus supports, which is step 3's output; age is a later and
    purely downward adjustment that cannot make a corpus stronger. Applying the ceiling to the
    aged scalar published the unclamped fold on the ``evidence`` axis, where nothing checks it.

    ``prior_bp`` is what a previous layer already believed, and it is the BASE of the fold as
    well as a ceiling. That is Rule 11 read literally: the rule governs a TRANSITION — what this
    layer may do to the incumbent belief — so the incumbent belief is the number being
    transformed. Evidence corroborates it upward (bounded) or combines it downward; it is never
    recomputed from scratch with the prior offered back only as a ceiling, because the same
    corroboration that produced the new number is entitled to raise that ceiling, and a layer
    that deliberately lowered belief to 1000 would then be overridden by a fold that never once
    looked at the 1000. Note what the prior is still NOT: a term in the evidence. It never
    corroborates, it is never named, and it cannot lift anything — only evidence raises.

    Raises ``ValueError`` on an empty source list. A confidence composed from nothing is a
    guess wearing a number, and the empty case has no defensible answer: 0 would publish a
    signal nobody believes and 10000 would publish one nothing supports.
    """
    if not sources:
        raise ValueError(
            "compose_confidence needs at least one source — a confidence composed from nothing "
            "is a guess, and V-4 refuses a claim with no receipt for the same reason")

    grouped: dict[str, list[ConfidenceSource]] = {}
    for source in sources:
        grouped.setdefault(source.independence_key or _UNSTATED, []).append(source)

    groups = sorted((_fold_group(key, members) for key, members in grouped.items()),
                    key=lambda g: (-rank_of(g.authority), -g.confidence_bp, g.names, g.key))

    # The INCUMBENT belief is the base of the fold when there is one. Rule 11 governs a
    # TRANSITION — what this layer may do to what the last layer already believed — so the
    # number being transformed has to be the previous layer's, not the strongest thing this
    # layer happens to be holding. Starting at ``groups[0]`` instead recomputed the belief from
    # scratch and then offered the prior back only as a ceiling, which the very corroboration
    # that produced the new number is entitled to waive: a layer that deliberately lowered
    # belief to 1000 was silently overridden by a fold that never once looked at the 1000.
    counted: set[str] = set()
    if prior_bp is None:
        running = groups[0].confidence_bp
        counted.update(groups[0].names)
        pending = groups[1:]
    else:
        running = require_bp(prior_bp, "prior confidence")
        pending = groups
    named: list[str] = []
    # The strongest corroborator the fold actually accepted, as (rank, confidence_bp,
    # authority) — the size of the "adding independent evidence" that Rule 11 lets the ceiling
    # be raised BY. None until something corroborates, and then the ceiling stays where it is.
    best_lift: tuple[int, int, Authority] | None = None
    for group in pending:
        if group.stated and counted.isdisjoint(group.names):
            running = corroborate(running, group.confidence_bp, evidence=group.names[0],
                                  authority=group.authority, already_named=tuple(named))
            named.extend(group.names)
            candidate = (rank_of(group.authority), group.confidence_bp, group.authority)
            if best_lift is None or candidate[:2] > best_lift[:2]:
                best_lift = candidate
        else:
            running = combine(running, group.confidence_bp)
        counted.update(group.names)

    newest_days = min(source.days_old for source in sources)
    freshness = freshness_retained_bp(newest_days, decay_bp_per_day=decay_bp_per_day)

    ordered_sources = [source.confidence_bp
                       for group in groups
                       for source in sorted(grouped[group.key],
                                            key=lambda s: (-s.rank, -s.confidence_bp, s.name))]
    if prior_bp is not None:
        ordered_sources.insert(0, require_bp(prior_bp, "prior confidence"))
    ceiling = rule_11_ceiling(ordered_sources)

    # The ceiling binds the EVIDENCE, and it therefore has to bind it BEFORE the decay. What
    # Rule 11 limits is how much belief composition may manufacture out of a corpus, and that
    # is the fold's own output — age is a separate, later, purely downward operation that has
    # nothing to say about whether the corpus supported the number in the first place.
    #
    # Clamping the aged scalar instead left the axis unclamped, and `evidence_bp` is PUBLISHED:
    # it is a key of `vector`, which becomes `QualifiedEnterpriseSignal.confidence_vector`,
    # and V-6 reads only `confidence_bp`. So 50 sources each worth 1000 bp published a scalar
    # of 1360 beside an `evidence` axis of 8765 — the module docstring's own failure, "five
    # sources all repeating one weak recollection ... composed upward into an 8900", printed on
    # the card with nothing downstream able to see it. Clamping first also restores this
    # module's stated invariant (the scalar IS evidence aged by freshness) in the one case
    # where it used to break, and it can only lower a published number, never raise one.
    evidence = enforce_rule_11(running, ceiling_bp=ceiling, independent_evidence=tuple(named),
                               lift_bp=best_lift[1] if best_lift else 0,
                               lift_authority=best_lift[2] if best_lift else Authority.INFERRED)
    composed = evidence * freshness // BP_FULL
    return ComposedConfidence(
        confidence_bp=composed,
        evidence_bp=evidence,
        expertise_bp=require_bp(expertise_bp, "expertise_bp"),
        freshness_bp=freshness,
        coverage_bp=require_bp(coverage_bp, "coverage_bp"),
        source_confidences=tuple(ordered_sources),
        independent_evidence=tuple(named),
        ceiling_bp=ceiling,
        clamped=evidence != running,
        fold_bp=running,
        fold_order=tuple(group.key for group in groups))


__all__ = [
    "DEFAULT_AGE_DECAY_BP_PER_DAY",
    "ComposedConfidence",
    "ConfidenceSource",
    "ConfidenceViolation",
    "age_in_days",
    "combine",
    "compose_confidence",
    "corroborate",
    "decay",
    "enforce_rule_11",
    "freshness_retained_bp",
    "rule_11_ceiling",
]
