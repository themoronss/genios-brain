"""L1.6.7 · ALG-17 — ``importance_bp``, the number Layer 4 has never had.

**IMPORTANCE IS NOT PRIORITY, AND THAT DISTINCTION IS THIS MODULE'S LICENCE TO EXIST.**
`contracts/gated_event.py:28` refuses an importance at L1 on the grounds that it would be
"the priority/importance conflation the spec forbids". The objection is answered by keeping
two fields, not one:

===========  ==========================================  ==========================================
             ``importance_bp`` — **L1, here**            ``priority_bp`` — **L4, elsewhere**
===========  ==========================================  ==========================================
Question     *how big is this thing?*                    *what should this person do first?*
Scope        intrinsic to the event                      relative to the person's whole book
Inputs       amount, deadline, authority, criticality    importance + effort + risk + context
Moves?       no — a $84K renewal is big any day         yes — 3rd today, 1st tomorrow
===========  ==========================================  ==========================================

An $84K contract is a big thing regardless of what else is happening. Whether the founder
should look at it before the board deck is a different question, asked one layer up, and this
module deliberately cannot answer it: nothing here reads the rest of the book.

WHY THIS IS THE GATE
--------------------
The failure chain is recorded in the code it broke. `reason/decision_maker.py:243` states that
"the formula has never once decided anything"; `reason/reasoners/priority.py:165-197` is where
193 of 223 signals carried an IDENTICAL score; `context/situation_bso.py:237` still assigns
``importance_bp=DEFAULT_IMPORTANCE_BP`` — a constant. None of those three is a crash. A utility
formula fed one number for every candidate runs, returns, and ranks nothing, so
``priority_override`` replaced it outright and two tenants receive the same ordering. **Layer
4's ranking failure is a Layer 1 hole**, and the hole is exactly this function.

That is why the acceptance for this unit is a DISTRIBUTION and not an example. A
constant-returning implementation passes every example-based test anybody would write for it —
which is how the constant survived this long.

THE FIVE TERMS, AND WHY EACH IS TABLE-DRIVEN
--------------------------------------------
``monetary_exposure``, ``deadline_proximity``, ``actor_authority``, ``entity_criticality`` and
``signal_type_weight``, weighted by :data:`IMPORTANCE_WEIGHTS_V1` (which sums to 10000), then
multiplied by ALG-14's ``evidence_authority_multiplier_bp`` so a signed document outweighs a
Slack aside on identical facts. Every term is a table lookup rather than a formula, because
"why is a CFO worth more than a manager" has to be a row a founder can be shown, and because a
retunable table is a diff while a retunable expression is an argument.

Two of the five are not computed here at all. ``actor_authority_bp`` is L1.6.4's answer, read
off :class:`~genios_engine.capture.esqe.source_analyzer.SourceAttribution`, and the evidence
multiplier is ALG-14's, read off
:data:`~genios_engine.capture.validate.authority.RANK_MULTIPLIER_BP` through the same object.
A second ladder for either would be a second thing to retune, and the day one moves without the
other, importance and conflict resolution start disagreeing about which source is stronger.

PURITY — the properties the gate actually rests on
--------------------------------------------------
* **No model.** This produces a number consumed by ranking; ranking must be byte-identical
  across machines and replays. A model may DESCRIBE a score (see :func:`explain_importance`,
  which is template substitution) and may never produce one.
* **No float.** Integer basis points end to end — ``x * 9 // 10``, never ``x * 0.9``. The log
  scale is a twenty-bucket integer ladder, not ``math.log``. Float rounding is not
  reproducible across builds, and a ranking that differs in the last place is a ranking two
  machines disagree about.
* **No clock.** ``eval_time`` is a parameter. A score computed against ``now()`` re-scores last
  March's deadline as overdue today and can never be replayed to explain a card that was shown.
* **Validated facts only.** ``Money`` from L1.5.3, ``ResolvedDate`` from L1.5.2, authority from
  L1.5.8 — all reached through :class:`~genios_engine.capture.esqe.normalize.NormalizedSignal`,
  never from raw model output.

WHAT A COLD-START ORG GETS, AND WHY IT IS NOT FLAT
---------------------------------------------------
The money term is relative to the org's own p50, because $84K means different things to a
five-person company and a five-hundred-person one. A brand-new org has no p50. The failure
mode that invites is the precise bug this unit exists to fix: no baseline -> every money term
0 -> every score collapses onto the same handful of values.

So a baseline that could not be computed does not zero the term — it switches ladders.
:data:`RATIO_LADDER` (amount vs the org's p50) is replaced by :data:`ABSOLUTE_LADDER` (amount
in whole currency units), both twenty buckets wide and both spanning 500..10000 bp, and
``baseline_estimated`` is flagged on the components so the switch is visible in the audit row
rather than inferred from a suspicious number. A day-one org therefore still gets twenty
distinct money readings, and its scores still spread across the other four terms exactly as an
established org's do. The one thing it loses is CALIBRATION — a $50K deal reads "large" for
everybody until the org's own history says otherwise — and that is recoverable by the nightly
:func:`compute_org_baseline`, whereas a flat distribution is not recoverable by anything.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType

from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.validate.canonical import derive_key
from genios_engine.capture.validate.money import minor_unit_exponent
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import (UNKNOWN_CURRENCY, DateCertainty, Money,
                                           ResolvedDate)

__all__ = [
    "ABSOLUTE_LADDER",
    "DEADLINE_LADDER",
    "ENTITY_CRITICALITY_BP",
    "IMPORTANCE_VERSION",
    "IMPORTANCE_WEIGHTS_V1",
    "RATIO_LADDER",
    "SIGNAL_TYPE_WEIGHT_BP",
    "BaselineBasis",
    "BaselineObservation",
    "EntityStanding",
    "ImportanceComponents",
    "ImportanceFlag",
    "ImportanceScore",
    "ImportanceWeights",
    "OrgBaseline",
    "compute_org_baseline",
    "fold_entity_key",
    "nearest_rank",
    "explain_importance",
    "require_aware_instant",
    "score_importance",
]

#: Stamped on every score. Weights are versioned because a retune makes historical scores
#: incomparable, and a card that says 8100 has to name the arithmetic that produced 8100 —
#: otherwise "it used to be a 6000" is unanswerable after the next tuning pass.
IMPORTANCE_VERSION = "alg17-v1"

#: The full basis-point range. One name, so a clamp and a ladder cannot drift apart.
BP_MAX = 10000


@dataclass(frozen=True, slots=True)
class ImportanceWeights:
    """ALG-17's five weights. Frozen and total-checked, because the arithmetic assumes the sum.

    ``/ 10000`` in the formula is only a weighted MEAN while the weights sum to 10000; a sixth
    weight added without adjusting the others silently rescales every score in the product and
    nothing would go red. :data:`IMPORTANCE_WEIGHTS_V1` is validated at import for that reason.
    """

    money: int
    deadline: int
    authority: int
    criticality: int
    signal_type: int

    @property
    def total(self) -> int:
        return self.money + self.deadline + self.authority + self.criticality + self.signal_type


#: Doc 06 L1.6.7-U1's weights, verbatim.
#:
#: ``money`` is capped at 3000 of 10000 on purpose and the cap is half the mitigation for the
#: named L4 failure mode — "every large number is urgent; small critical things buried". The
#: other half is the log scaling below. Money is the single largest term and still cannot
#: decide a score alone: a maximal amount with nothing else contributes 3000 bp.
IMPORTANCE_WEIGHTS_V1 = ImportanceWeights(money=3000, deadline=2500, authority=1500,
                                          criticality=2000, signal_type=1000)

if IMPORTANCE_WEIGHTS_V1.total != BP_MAX:                              # pragma: no cover
    raise RuntimeError("ALG-17 weights must sum to 10000; "
                       f"got {IMPORTANCE_WEIGHTS_V1.total}")

#: Doc 06 L1.6.7-U1 term 5 — a NUDGE by type, never the dominant term (weight 1000 of 10000).
#:
#: The top three mirror ALG-16's precedence for the reason `classifier.py` gives: a conflict
#: means we may be about to tell a founder something false with a receipt that looks
#: legitimate, an escalation is time-bound by nature, an approval is blocking a human right
#: now. CONTRACT_RENEWAL — commercially the most valuable kind — sits below all three, and the
#: gap between the top (9000) and the floor (3000) is worth only 600 bp of the final score,
#: which is what keeps a type from outvoting an $84K amount three weeks overdue.
SIGNAL_TYPE_WEIGHT_BP: Mapping[SignalType, int] = MappingProxyType({
    SignalType.INFORMATION_CONFLICT: 9000,
    SignalType.ESCALATION: 9000,
    SignalType.APPROVAL_REQUESTED: 8000,
    SignalType.CONTRACT_RENEWAL: 8000,
    SignalType.COMMITMENT_DUE: 7500,
    SignalType.FINANCIAL_OBLIGATION: 7000,
    SignalType.DECISION_PENDING: 6500,
    SignalType.DEADLINE_STATED: 6000,
    SignalType.RISK_FLAGGED: 6000,
    SignalType.OPPORTUNITY_SIGNAL: 5500,
    SignalType.COMMITMENT_MADE: 5000,
    SignalType.DECISION_MADE: 4000,
    SignalType.RELATIONSHIP_CHANGE: 3500,
    SignalType.ANOMALY: 3000,
})

#: Import-time totality, on the same terms as `classifier.PRECEDENCE`. A fifteenth member with
#: no weight is not a smaller bug than a wrong weight — it is a `KeyError` inside a capture at
#: 3am, on the one code path a tenant's whole sync runs through.
_MISSING_TYPES = set(SignalType) - set(SIGNAL_TYPE_WEIGHT_BP)
if _MISSING_TYPES:                                                     # pragma: no cover
    raise RuntimeError("ALG-17 needs a weight for every SignalType; missing="
                       f"{sorted(t.value for t in _MISSING_TYPES)}")


class EntityStanding(str, Enum):
    """Doc 06 term 4's ladder, as a closed vocabulary rather than five loose booleans.

    An enum because the five rungs are mutually exclusive and ORDERED, and a caller holding
    three independent flags has to decide which wins — which is a ranking decision made at a
    call site instead of in this table.

    ``ABSENT`` is this module's own sixth rung and is not in doc 06, whose five all presume a
    named entity. "This signal names no organisation" and "this signal names an organisation we
    have never seen" are different facts, and collapsing the first onto the second would hand
    2000 bp of criticality to every newsletter — 400 bp of final score for nothing.
    """

    #: Tagged mission-critical in the Organization Brain. The org said so itself.
    MISSION_CRITICAL = "mission_critical"
    #: Top-decile counterparty by contract value over the baseline window.
    TOP_DECILE = "top_decile"
    #: An active deal or an open contract is running with this entity right now.
    ACTIVE = "active"
    #: We have seen this entity before; nothing else distinguishes it.
    KNOWN = "known"
    #: First sighting.
    FIRST_SEEN = "first_seen"
    #: The signal names no entity at all.
    ABSENT = "absent"


#: Doc 06 L1.6.7-U1 term 4, plus the ABSENT floor. The only place these six numbers appear.
ENTITY_CRITICALITY_BP: Mapping[EntityStanding, int] = MappingProxyType({
    EntityStanding.MISSION_CRITICAL: 10000,
    EntityStanding.TOP_DECILE: 8000,
    EntityStanding.ACTIVE: 6000,
    EntityStanding.KNOWN: 4000,
    EntityStanding.FIRST_SEEN: 2000,
    EntityStanding.ABSENT: 0,
})

_MISSING_STANDINGS = set(EntityStanding) - set(ENTITY_CRITICALITY_BP)
if _MISSING_STANDINGS:                                                 # pragma: no cover
    raise RuntimeError("every EntityStanding needs a criticality; missing="
                       f"{sorted(s.value for s in _MISSING_STANDINGS)}")

#: Doc 06 L1.6.7-U1 term 2 — days until the deadline -> basis points, as ``(max_days, bp)``
#: rungs read in order. The first rung whose bound the day count does not exceed wins.
#:
#: Days, not hours: a `ResolvedDate` for "October 15" is a calendar fact and an hours-based
#: ladder would make the same deadline score differently depending on what time of day the
#: sweep ran, which is a clock leaking in through the back door.
DEADLINE_LADDER: tuple[tuple[int, int], ...] = (
    (0, 10000),     # overdue, or due today
    (2, 9000),
    (7, 7500),
    (14, 6000),
    (30, 4000),
    (90, 2000),
)

#: Everything past the last rung. Not 0: a deadline eight months out is still a deadline, and
#: zeroing it would make a dated signal indistinguishable from an undated one.
DEADLINE_FLOOR_BP = 500

#: Term 1, the RELATIVE path. Doc 06: *"renewal coming up pretty soon"* must not score the same
#: as *"renewal on October 15"*. Integer halving, ``* 5 // 10``.
RELATIVE_NUMERATOR = 5
RELATIVE_DENOMINATOR = 10

#: Term 1's log scale, against the ORG's own p50. Twenty buckets as ``(max_ratio_bp, bp)``,
#: where ``ratio_bp`` is ``amount * 10000 // p50`` — so 10000 means "exactly typical for this
#: org", 20000 means "twice typical".
#:
#: WHY LOG AND NOT LINEAR: doc 06 names the failure — "without it every large number becomes
#: urgent and small critical things get buried". A linear ratio puts a 40x deal and a 4x deal
#: 36 buckets apart and a 1x and a 2x deal in the same one, which is backwards: the difference
#: between typical and twice-typical is the one a founder acts on, and the difference between
#: 40x and 80x is noise on an outlier they were always going to read.
#:
#: WHY THE LADDER DOES NOT STOP AT 1x: doc 06's formula literally reads
#: ``ratio_bp = min(10000, amount * 10000 // max(baseline, 1))``, which caps the ratio at
#: exactly the baseline and therefore scores EVERY above-average amount identically. That
#: contradicts the same section's own acceptance row — "the same event with the amount at the
#: org p50 -> strictly lower" — which is unsatisfiable under the cap, and its own worked
#: example, in which $84K at a $45K baseline scores 7200 rather than the capped maximum. The
#: cap is read here as a transcription error for the ladder's top bucket, and the ratio is
#: allowed to run to 50x before saturating.
RATIO_LADDER: tuple[tuple[int, int], ...] = (
    (100, 500),        # under 1% of typical
    (200, 1000),
    (400, 1500),
    (700, 2000),
    (1000, 2500),      # a tenth of typical
    (1500, 3000),
    (2000, 3500),
    (3000, 4000),
    (4000, 4500),
    (5000, 5000),      # half of typical
    (7000, 5500),
    (10000, 6000),     # typical
    (15000, 6500),
    (20000, 7000),     # twice typical
    (30000, 7500),
    (50000, 8000),
    (100000, 8500),    # ten times typical
    (200000, 9000),
    (500000, 9500),
)

#: The cold-start ladder — WHOLE currency units, twenty buckets, same 500..10000 range.
#:
#: Used whenever the ratio cannot be taken: no org history yet, or the signal's currency is not
#: the baseline's (there is no FX table in this build, and inventing one to compare ₹ to $ would
#: put a fabricated conversion at the top of a founder's list). "Industry-neutral" is doc 06's
#: own word for it and it is an honest description of the compromise: 84,000 of ANY currency
#: reads the same here, which is wrong in detail and right in magnitude, and the
#: ``baseline_estimated`` flag says so on the row.
ABSOLUTE_LADDER: tuple[tuple[int, int], ...] = (
    (100, 500),
    (250, 1000),
    (500, 1500),
    (1_000, 2000),
    (2_500, 2500),
    (5_000, 3000),
    (10_000, 3500),
    (25_000, 4000),
    (50_000, 4500),
    (100_000, 5000),
    (250_000, 5500),
    (500_000, 6000),
    (1_000_000, 6500),
    (2_500_000, 7000),
    (5_000_000, 7500),
    (10_000_000, 8000),
    (25_000_000, 8500),
    (50_000_000, 9000),
    (100_000_000, 9500),
)

#: The bucket above every ladder's last rung. Both ladders top out here.
LADDER_TOP_BP = 10000

#: Minor-unit exponent assumed when the currency was never identified. Two rather than zero:
#: assuming cents where there are none DIVIDES the whole-unit reading by a hundred, which
#: understates the amount. Understating an unknown-currency figure costs it some importance;
#: overstating it puts a fabricated magnitude at the top of a list.
_UNKNOWN_CURRENCY_EXPONENT = 2

#: How far back :func:`compute_org_baseline` looks. Doc 06 L1.6.7-U2: 365 days.
BASELINE_WINDOW_DAYS = 365

#: Term 4 rung 2's share: the top TENTH of counterparties by their largest contract.
#:
#: A share of the COUNTERPARTIES and not a threshold on the amounts, which is the reading doc
#: 06's own words ask for — "top-decile counterparty by contract value" ranks counterparties.
#: The threshold reading breaks on ties, and ties are the normal case: nine identical £10K
#: retainers and one £500K contract put the 90th percentile AT £10K, so every retainer clears
#: it and "top decile" names the whole book.
TOP_DECILE_DIVISOR = 10


class ImportanceFlag(str, Enum):
    """What was MISSING or substituted, recorded on the score rather than inferred from it.

    Doc 06 names two (``no_money_baseline``, ``baseline_estimated``); the rest exist because a
    zero term has several causes and they are not equivalent. A 0 monetary exposure because the
    signal named no amount is correct; a 0 because the amount's currency could not be compared
    is a gap in this module. Reading them apart from the integer alone is impossible, which is
    how a missing-data bug hides inside a plausible score for a year.
    """

    #: The signal carries no `Money` at all. Term 1 is 0 and that is the right answer.
    NO_MONEY = "no_money"
    #: The org has no usable p50 — a new tenant, or a window with no priced history.
    NO_MONEY_BASELINE = "no_money_baseline"
    #: Term 1 was taken from the absolute ladder rather than the org ratio.
    BASELINE_ESTIMATED = "baseline_estimated"
    #: The amount's currency is not the baseline's, and this build has no FX table.
    CURRENCY_MISMATCH = "currency_mismatch"
    #: ALG-10 could not identify the currency; the minor-unit exponent was assumed.
    UNKNOWN_CURRENCY = "unknown_currency"
    #: No date on the signal — term 2 is 0 because nothing is due, not because it is far off.
    NO_DEADLINE = "no_deadline"
    #: A date that could not be resolved at all. Guessing is not an option (ALG-09).
    UNRESOLVED_DEADLINE = "unresolved_deadline"
    #: A RELATIVE date; term 2 was halved because "pretty soon" is a guess.
    RELATIVE_DEADLINE = "relative_deadline"
    #: The signal names no organisation, so term 4 has nothing to rank.
    NO_ENTITY = "no_entity"


class BaselineBasis(str, Enum):
    """Where an :class:`OrgBaseline`'s p50 came from — measured, or absent."""

    #: A real p50 over the org's own priced history in the window.
    ORG_HISTORY = "org_history"
    #: No priced history. The absolute ladder is used and every score says so.
    ESTIMATED = "estimated"


@dataclass(frozen=True, slots=True)
class BaselineObservation:
    """One priced thing the org did — a closed deal, a signed contract, an invoice.

    A typed input rather than a tuple or a dict for the reason `Provenance` gives: adding a
    dimension later is a field with a default, not a silently-ignored key at some call site.
    """

    #: The value. `Money`, so the currency travels with the integer and can never be assumed.
    amount: Money
    #: WORLD time — when the deal closed or the contract was signed, never when we read it.
    occurred_at: datetime
    #: The counterparty this was with, or None when the record names none.
    counterparty: str | None = None
    #: Whether the deal/contract is still running. Feeds term 4's ``ACTIVE`` rung.
    is_open: bool = False


def fold_entity_key(name: str | None) -> str | None:
    """One entity key shape — **L1.5.4's**, not a second one invented here.

    PUBLIC because it is now also the shape a tag is STORED in.
    `org_mission_critical_entities` (migration 0091) is keyed by this function's output, so the
    row a founder writes through the route and the key `standing_of` compares against are the
    same string. Storing a bare `casefold()` there would re-create, in a new table, the exact
    fault the paragraph below records: "Northwind Ltd" tagged and ``northwind`` looked up, never
    equal, and a mission-critical vendor scoring `first_seen` with no error anywhere.

    This used to be `str.strip().casefold()`, and that single line made term 4 unable to fire on
    the production path at all. `normalize._primary_entity` puts the CANONICAL name on the
    signal (ALG-11 has already run: "Northwind Ltd" arrives as ``northwind``, the legal-form
    token dropped), while every set on this baseline was keyed on the surface form the history
    was written with — ``northwind ltd``. The two never compared equal, so a mission-critical
    vendor with an open contract and nine years of invoices scored ``first_seen`` (2000) exactly
    like a stranger, on every event, for every tenant. A casefold that is 99% right is worse
    than no folding, because the 1% is invisible.

    `derive_key` is the one place fuzziness is allowed to live (its own words), and delegating
    to it is what makes "the name on the signal" and "the name in the history" the same string.
    Its failure mode is a return value, not an exception, but the fallback is kept: a key this
    baseline could not derive must still be comparable to itself.
    """
    if name is None:
        return None
    text = str(name).strip()
    if not text:
        return None
    try:
        key = derive_key(text, entity_type="organization").key
    except Exception:      # noqa: BLE001 — an underivable name folds to itself, never raises
        key = ""
    return key or text.casefold() or None


def _fold_all(names: Iterable[str]) -> frozenset[str]:
    return frozenset(k for k in (fold_entity_key(n) for n in names) if k is not None)


@dataclass(frozen=True, slots=True)
class OrgBaseline:
    """L1.6.7-U2's answer: what "normal" costs at this company, and who matters to it.

    Frozen and self-dated. ``computed_against`` is stored because a baseline is a statement
    about a window, and a score explained six months later has to be able to say which window
    calibrated it rather than implying today's.

    The entity sets live here rather than in a second object because they answer the same
    question from the same source — the org's own history — and a caller assembling two
    org-shaped inputs for one call is a caller that will one day pass a baseline from one
    tenant beside an entity set from another.
    """

    org_id: str
    #: The p50 of priced history in the window, in ``currency``'s minor units. 0 when
    #: ``basis`` is ESTIMATED — read the basis, never the zero.
    p50_minor_units: int
    #: The ISO code ``p50_minor_units`` is denominated in, or `UNKNOWN_CURRENCY` when there is
    #: no history to denominate.
    currency: str
    #: How many observations the p50 was taken over. 0 is a cold start; 1 is a p50 that is one
    #: deal, which is why it is visible rather than implied by the basis alone.
    sample_size: int
    basis: BaselineBasis
    #: The instant the window was measured back from. A parameter upstream, never a clock.
    computed_against: datetime
    #: Entities the Organization Brain tagged mission-critical. Casefolded.
    mission_critical: frozenset[str] = frozenset()
    #: Counterparties at or above the window's p90 contract value. Casefolded.
    top_decile: frozenset[str] = frozenset()
    #: Counterparties with an open deal or a running contract. Casefolded.
    active: frozenset[str] = frozenset()
    #: Every counterparty seen in the window, whatever its standing. Casefolded.
    known: frozenset[str] = frozenset()
    #: The window the sets and the p50 were taken over, in days.
    window_days: int = BASELINE_WINDOW_DAYS

    def __post_init__(self) -> None:
        """Fold the four entity sets HERE, so an unfolded one cannot exist.

        `compute_org_baseline` already folds what it builds, but it is not the only constructor:
        a caller assembling an `OrgBaseline` by hand — a wiring factory, a test, a future reader
        of a stored baseline — would otherwise hold sets keyed on whatever spelling its source
        used, and `standing_of` would compare a canonical name against a surface form and answer
        `first_seen` for a mission-critical vendor. That failure returns a plausible number, so
        nothing about it is visible downstream. Folding at construction makes the shape of these
        sets a property of the TYPE rather than of whoever built it.
        """
        for field_name in ("mission_critical", "top_decile", "active", "known"):
            object.__setattr__(self, field_name, _fold_all(getattr(self, field_name)))

    @classmethod
    def cold_start(cls, org_id: str, *, computed_against: datetime) -> "OrgBaseline":
        """A day-one org: no p50, no history, and scoring proceeds anyway.

        This is the object a caller with nothing gets, and the whole point of it is that
        :func:`score_importance` accepts it without special-casing. Never block scoring on a
        missing baseline — doc 06's own instruction, and the alternative is a tenant whose
        first week of signals all score alike.
        """
        return cls(org_id=org_id, p50_minor_units=0, currency=UNKNOWN_CURRENCY, sample_size=0,
                   basis=BaselineBasis.ESTIMATED, computed_against=computed_against)

    @property
    def has_p50(self) -> bool:
        """True when a real, positive p50 was measured — the only state the ratio ladder is
        defined for. A zero p50 with an ORG_HISTORY basis (every observation was zero) reads
        as no baseline here, because ``x // 0`` is not a smaller problem than a cold start."""
        return self.basis is BaselineBasis.ORG_HISTORY and self.p50_minor_units > 0

    def standing_of(self, entity: str | None) -> EntityStanding:
        """Term 4's rung for one entity. The order IS the ladder: highest standing wins.

        A mission-critical vendor that is also top-decile and also has an open contract is
        mission-critical — one rung, chosen here rather than at a call site, so two callers
        cannot disagree about which of three true facts outranks the others.
        """
        key = fold_entity_key(entity)
        if key is None:
            return EntityStanding.ABSENT
        if key in self.mission_critical:
            return EntityStanding.MISSION_CRITICAL
        if key in self.top_decile:
            return EntityStanding.TOP_DECILE
        if key in self.active:
            return EntityStanding.ACTIVE
        if key in self.known:
            return EntityStanding.KNOWN
        return EntityStanding.FIRST_SEEN



@dataclass(frozen=True, slots=True)
class ImportanceComponents:
    """Doc 06's ``importance_components``, typed. **Storing these is mandatory.**

    *"Why is this an 8100?"* must be answerable from the stored row without re-running
    anything — which matters most precisely when it is hardest: after the weights were
    retuned, when a recomputation would return a different number and quietly rewrite history.

    A dataclass rather than the doc's dict because a dict crossing this boundary is a
    key-spelling contract nobody checks; :meth:`as_record` produces the doc's shape for
    storage, once, here.
    """

    monetary_exposure_bp: int
    deadline_proximity_bp: int
    actor_authority_bp: int
    entity_criticality_bp: int
    signal_type_weight_bp: int
    evidence_authority_multiplier_bp: int
    #: The weighted mean of the five terms, BEFORE the evidence multiplier. Stored because it
    #: is the only way to see the multiplier's effect: 7600 -> 4940 says "we discounted this
    #: because it was a Slack aside", and the final number alone says nothing.
    weighted_bp: int
    #: The p50 the money term was taken against, in minor units. 0 for a cold start.
    baseline_used: int
    #: Which currency ``baseline_used`` is in.
    baseline_currency: str
    baseline_basis: BaselineBasis
    #: The entity rung term 4 came from.
    entity_standing: EntityStanding
    #: The instant term 2 was judged against. The replay key.
    eval_time: datetime
    #: What was missing or substituted. Order is the enum's, deduplicated — a set would
    #: serialise differently on two runs and break the byte-identical property.
    flags: tuple[ImportanceFlag, ...] = ()

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "ImportanceComponents":
        """The exact inverse of :meth:`as_record` — a STORED map back into the typed object.

        The reason this exists rather than a reader picking keys out of the dict at the call
        site: `qualification_drops.components` is jsonb written months before it is read, and
        the only consumer that can afford to guess a missing key is one that does not have to
        be right. Every field is required, and a record that does not carry all of them raises
        rather than defaulting — a rendered explanation whose ``entity_standing`` silently
        became ``absent`` is worse than no explanation, because it reads as a fact.

        Raises ``ValueError`` for a record written under a shape this class no longer knows,
        which is the honest answer for a row whose arithmetic cannot be reconstructed. It never
        re-scores to fill a gap: the components were stored precisely so that a later weight
        change could not re-explain an old decision.
        """
        try:
            return cls(
                monetary_exposure_bp=int(record["monetary_exposure_bp"]),      # type: ignore[arg-type]
                deadline_proximity_bp=int(record["deadline_proximity_bp"]),    # type: ignore[arg-type]
                actor_authority_bp=int(record["actor_authority_bp"]),          # type: ignore[arg-type]
                entity_criticality_bp=int(record["entity_criticality_bp"]),    # type: ignore[arg-type]
                signal_type_weight_bp=int(record["signal_type_weight_bp"]),    # type: ignore[arg-type]
                evidence_authority_multiplier_bp=int(
                    record["evidence_authority_multiplier_bp"]),               # type: ignore[arg-type]
                weighted_bp=int(record["weighted_bp"]),                        # type: ignore[arg-type]
                baseline_used=int(record["baseline_used"]),                    # type: ignore[arg-type]
                baseline_currency=str(record["baseline_currency"]),
                baseline_basis=BaselineBasis(record["baseline_basis"]),
                entity_standing=EntityStanding(record["entity_standing"]),
                eval_time=datetime.fromisoformat(str(record["eval_time"])),
                flags=tuple(ImportanceFlag(f) for f in record.get("flags", ()) or ()))
        except (KeyError, TypeError) as exc:
            raise ValueError(f"importance_components record is not the stored shape: {exc}") from exc

    def as_record(self) -> dict[str, object]:
        """Doc 06's dict shape, for the QES column and the audit row.

        Serialisation, not a boundary: every consumer inside this build takes the typed object.
        ``eval_time`` is ISO-8601 and the enums are their own ``str`` values, so the row round
        trips through JSON without a custom encoder.
        """
        return {
            "monetary_exposure_bp": self.monetary_exposure_bp,
            "deadline_proximity_bp": self.deadline_proximity_bp,
            "actor_authority_bp": self.actor_authority_bp,
            "entity_criticality_bp": self.entity_criticality_bp,
            "signal_type_weight_bp": self.signal_type_weight_bp,
            "evidence_authority_multiplier_bp": self.evidence_authority_multiplier_bp,
            "weighted_bp": self.weighted_bp,
            "baseline_used": self.baseline_used,
            "baseline_currency": self.baseline_currency,
            "baseline_basis": self.baseline_basis.value,
            "entity_standing": self.entity_standing.value,
            "eval_time": self.eval_time.isoformat(),
            "flags": [flag.value for flag in self.flags],
        }


@dataclass(frozen=True, slots=True)
class ImportanceScore:
    """What ALG-17 concluded about one signal: the number, its arithmetic, and its version."""

    #: 0..10000, integer. The field `contracts/signal.QualifiedEnterpriseSignal.importance_bp`
    #: takes, whose own validator enforces the range a second time at the seam.
    importance_bp: int
    components: ImportanceComponents
    #: :data:`IMPORTANCE_VERSION` at the time of scoring. Doc 06's mitigation for score drift:
    #: two scores from two weight versions are not comparable and must not be silently sorted
    #: against each other.
    importance_version: str = IMPORTANCE_VERSION


# ------------------------------------------------------------------------------------------
# The instant this module is allowed to reason about
# ------------------------------------------------------------------------------------------

def require_aware_instant(value: datetime, *, name: str = "eval_time") -> datetime:
    """The instant a score is judged against must carry an offset. A naive one RAISES.

    Assuming UTC for a naive datetime is the silent version of this failure and it is the worse
    one. Term 2 is ``(earliest - eval_time).days`` and `ResolvedDate.earliest` is aware, so a
    naive ``eval_time`` does not merely shift the answer — the subtraction raises `TypeError`
    from inside a sweep, or, where a caller normalised one side and not the other, moves a
    renewal across a ladder rung depending on which machine ran the sweep. Both outcomes are
    invisible in a green suite whose fixtures are all UTC.

    A `ValueError` at the door instead: the caller passed the wrong kind of thing, that is a
    programming error, and the cheapest place to learn it is the call that made it.
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(
            f"{name} must be timezone-aware; got the naive {value.isoformat()!r}. "
            "Assuming UTC here would put a deadline on a different rung of ALG-17's ladder "
            "depending on where the process runs, and a score that cannot be replayed cannot "
            "explain the card it produced.")
    return value


# ------------------------------------------------------------------------------------------
# The terms. Each is a lookup; none reads a clock, a model or a database.
# ------------------------------------------------------------------------------------------

def _ladder_bp(ladder: Sequence[tuple[int, int]], value: int) -> int:
    """First rung whose bound ``value`` does not exceed, else the top bucket.

    Shared by both money ladders so the twenty-bucket shape is written once. Linear because
    twenty is small and a bisect would need a second parallel sequence of bounds, which is one
    more thing to keep in step with the table a reader is actually shown.
    """
    for bound, bp in ladder:
        if value < bound:
            return bp
    return LADDER_TOP_BP


def _whole_units(amount: Money) -> tuple[int, bool]:
    """Minor units -> whole currency units, and whether the exponent had to be assumed.

    Integer division: 8_400_050 USD minor units is 84_000 whole dollars, and the 50 cents a
    float would preserve cannot move a twenty-bucket ladder.
    """
    try:
        exponent = minor_unit_exponent(amount.currency)
    except ValueError:
        return abs(amount.minor_units) // (10 ** _UNKNOWN_CURRENCY_EXPONENT), True
    return abs(amount.minor_units) // (10 ** exponent), False


def _monetary_exposure(amount: Money | None,
                       baseline: OrgBaseline) -> tuple[int, list[ImportanceFlag]]:
    """Term 1 — how big is this amount FOR THIS COMPANY, log-scaled, 0..10000.

    Three paths, and the flags say which was taken: the org ratio (calibrated), the absolute
    ladder (honest but uncalibrated), and 0 (there is no amount, which is not a gap).
    """
    if amount is None:
        return 0, [ImportanceFlag.NO_MONEY]

    flags: list[ImportanceFlag] = []
    if not baseline.has_p50:
        flags.append(ImportanceFlag.NO_MONEY_BASELINE)
    elif amount.currency != baseline.currency:
        flags.append(ImportanceFlag.CURRENCY_MISMATCH)
    elif amount.currency_known:
        ratio_bp = abs(amount.minor_units) * BP_MAX // baseline.p50_minor_units
        return _ladder_bp(RATIO_LADDER, ratio_bp), flags

    whole, assumed = _whole_units(amount)
    if assumed:
        flags.append(ImportanceFlag.UNKNOWN_CURRENCY)
    flags.append(ImportanceFlag.BASELINE_ESTIMATED)
    return _ladder_bp(ABSOLUTE_LADDER, whole), flags


def _deadline_proximity(date: ResolvedDate | None, *,
                        eval_time: datetime) -> tuple[int, list[ImportanceFlag]]:
    """Term 2 — how close is it, from the CONSERVATIVE edge of the window, 0..10000.

    ``earliest`` and not ``latest``: a window that opens on Friday is a Friday problem even if
    it closes a fortnight later, and taking the far edge is how a deadline gets discovered
    after it passed.
    """
    if date is None:
        return 0, [ImportanceFlag.NO_DEADLINE]
    if date.certainty is DateCertainty.UNRESOLVED or date.earliest is None:
        return 0, [ImportanceFlag.UNRESOLVED_DEADLINE]

    days = (date.earliest - eval_time).days
    proximity = DEADLINE_FLOOR_BP
    for bound, bp in DEADLINE_LADDER:
        if days <= bound:
            proximity = bp
            break

    if date.certainty is DateCertainty.RELATIVE:
        halved = proximity * RELATIVE_NUMERATOR // RELATIVE_DENOMINATOR
        return halved, [ImportanceFlag.RELATIVE_DEADLINE]
    return proximity, []


def _entity_criticality(entity: str | None,
                        baseline: OrgBaseline) -> tuple[int, EntityStanding,
                                                        list[ImportanceFlag]]:
    """Term 4 — is the named entity mission-critical to THIS org, 0..10000."""
    standing = baseline.standing_of(entity)
    flags = [ImportanceFlag.NO_ENTITY] if standing is EntityStanding.ABSENT else []
    return ENTITY_CRITICALITY_BP[standing], standing, flags


# ------------------------------------------------------------------------------------------
# L1.6.7-U1 · the formula
# ------------------------------------------------------------------------------------------

def score_importance(signal: NormalizedSignal, baseline: OrgBaseline, *,
                     eval_time: datetime,
                     weights: ImportanceWeights = IMPORTANCE_WEIGHTS_V1) -> ImportanceScore:
    """ALG-17 · how big is this thing, intrinsically. 0..10000 basis points, integer, replayable.

    Total over its DATA: no signal, no baseline and no missing term makes this raise, and that
    is deliberate — the caller is a capture pipeline running unattended over a tenant's mail,
    and an exception here costs a whole sync while a flagged, degraded term costs one signal
    some calibration.

    The ONE refusal is a naive ``eval_time``, which is not data: it is the caller handing over
    an instant with no offset, and :func:`require_aware_instant` says why silently assuming UTC
    is worse than stopping.

    The arithmetic, in doc 06's own order::

        weighted_bp   = (W_money*money + W_deadline*deadline + W_authority*authority
                         + W_critical*criticality + W_type*type) // 10000
        importance_bp = clamp(0, 10000, weighted_bp * evidence_multiplier_bp // 10000)

    Two divisions rather than one fused ``// 100_000_000``, because ``weighted_bp`` is stored
    on the components and the stored number has to reproduce the score exactly. A single fused
    division is off by up to 1 bp from the product of the numbers a founder is shown, and an
    explanation that does not add up is worse than a slightly coarser one.

    ``signal`` is the whole :class:`NormalizedSignal` and not the extraction the reverse prompt
    names, because L1.6.2 has already done the reading: its ``primary_amount`` is the amount
    this signal is ABOUT under `AMOUNT_POLICY`, its ``primary_date`` is refused rather than
    borrowed from a neighbouring claim, and its ``attribution`` is the one L1.6.4 computed for
    this event with the caller's own ``executed`` and ``actor_role``. Re-reading the raw
    extraction here would re-derive all three, differently, on a shape whose whole purpose is
    that nobody has to.
    """
    eval_time = require_aware_instant(eval_time)
    money_bp, money_flags = _monetary_exposure(signal.primary_amount, baseline)
    deadline_bp, date_flags = _deadline_proximity(signal.primary_date, eval_time=eval_time)
    criticality_bp, standing, entity_flags = _entity_criticality(signal.primary_entity, baseline)
    # Terms 3 and 6 are read, never recomputed — L1.6.4 and ALG-14 own those ladders.
    authority_bp = signal.attribution.actor_authority_bp
    multiplier_bp = signal.attribution.evidence_authority_multiplier_bp
    type_bp = SIGNAL_TYPE_WEIGHT_BP[signal.signal_type]

    weighted_bp = (weights.money * money_bp
                   + weights.deadline * deadline_bp
                   + weights.authority * authority_bp
                   + weights.criticality * criticality_bp
                   + weights.signal_type * type_bp) // BP_MAX
    importance_bp = min(BP_MAX, max(0, weighted_bp * multiplier_bp // BP_MAX))

    return ImportanceScore(
        importance_bp=importance_bp,
        components=ImportanceComponents(
            monetary_exposure_bp=money_bp,
            deadline_proximity_bp=deadline_bp,
            actor_authority_bp=authority_bp,
            entity_criticality_bp=criticality_bp,
            signal_type_weight_bp=type_bp,
            evidence_authority_multiplier_bp=multiplier_bp,
            weighted_bp=weighted_bp,
            baseline_used=baseline.p50_minor_units,
            baseline_currency=baseline.currency,
            baseline_basis=baseline.basis,
            entity_standing=standing,
            eval_time=eval_time,
            flags=tuple(money_flags + date_flags + entity_flags)))


# ------------------------------------------------------------------------------------------
# L1.6.7-U2 · org baseline computation
# ------------------------------------------------------------------------------------------

def nearest_rank(ordered: Sequence[int], quantile_bp: int) -> int:
    """The value at ``quantile_bp`` of a SORTED sequence, by nearest rank, in integers.

    PUBLIC because it is the percentile the whole of L1.6.7 is stated in and there must be
    exactly one of it. `compute_org_baseline` takes the org's p50 with it; G7's acceptance
    report (`scripts/importance_distribution.py`) takes the p50 and p90 of the resulting
    distribution with it. A second nearest-rank written in the report would let the gate and
    the formula disagree about the median by one row on an even-sized book — which is a
    difference nobody would find, because both answers look right.

    NOT `context/support_situations.percentile_bp`, and the difference is the function's
    direction rather than a preference: that one answers "where in this population does this
    value sit" (a value -> a rank) and U2 needs "which value sits at the median" (a rank -> a
    value). It also divides in floats (``ties / 2.0``, ``round``), which cannot appear anywhere
    on this call path. The two are inverses of each other and neither can be written in terms
    of the other without a second implementation of exactly this.

    Nearest rank rather than interpolation for the same reason: interpolating between two
    integer amounts produces a fractional one.
    """
    if not ordered:
        return 0
    index = (quantile_bp * (len(ordered) - 1) + BP_MAX // 2) // BP_MAX
    return ordered[min(len(ordered) - 1, max(0, index))]


def _modal_currency(amounts: Sequence[Money]) -> str | None:
    """The currency most of the org's history is denominated in, or None.

    A single answer is required because the p50 is one integer and an integer in mixed
    currencies is a fiction. Ties break on the ISO code, alphabetically — arbitrary, but
    ARBITRARY AND FIXED, which is what a replay needs; a tie broken by dict order would give
    two runs over the same history two different baselines.
    """
    counts: dict[str, int] = {}
    for amount in amounts:
        if amount.currency_known:
            counts[amount.currency] = counts.get(amount.currency, 0) + 1
    if not counts:
        return None
    return min(counts, key=lambda code: (-counts[code], code))


def _top_decile(in_window: Sequence[BaselineObservation], currency: str | None) -> frozenset[str]:
    """The top tenth of counterparties, ranked by their LARGEST contract in the window.

    Largest rather than total, because term 4 asks how big a thing this counterparty can be, and
    a reseller with two hundred £200 orders is not the relationship a £500K contract is.

    ``max(1, n // 10)`` — a tenth, floored at one. An org with six counterparties still has a
    biggest one, and returning an empty set below ten would leave every young tenant's term 4
    with one fewer rung for no reason a founder could name. Ties break on the counterparty key
    so two runs over one history cannot return two different decks.
    """
    largest: dict[str, int] = {}
    for observation in in_window:
        key = fold_entity_key(observation.counterparty)
        if key is None or currency is None or observation.amount.currency != currency:
            continue
        largest[key] = max(largest.get(key, 0), abs(observation.amount.minor_units))
    if not largest:
        return frozenset()
    ranked = sorted(largest, key=lambda name: (-largest[name], name))
    return frozenset(ranked[:max(1, len(ranked) // TOP_DECILE_DIVISOR)])


def compute_org_baseline(observations: Iterable[BaselineObservation], *, org_id: str,
                         eval_time: datetime,
                         window_days: int = BASELINE_WINDOW_DAYS,
                         mission_critical: Iterable[str] = (),
                         active_counterparties: Iterable[str] = ()) -> OrgBaseline:
    """L1.6.7-U2 · what a typical contract costs at this company, over the last ``window_days``.

    Runs nightly, not per event: the p50 of a year moves by less than a rounding step when one
    deal lands, and recomputing it inside a sweep would put a table scan on the path of every
    message. ``eval_time`` is a parameter here too, so last night's baseline can be rebuilt
    exactly when a score is questioned.

    **A missing baseline never blocks scoring.** An org with no priced history in the window
    gets ``basis=ESTIMATED`` and a zero p50, and :func:`score_importance` reads the BASIS —
    switching to the absolute ladder — rather than dividing by the zero. The entity sets are
    still populated in that case: a tenant can know perfectly well which vendors are
    mission-critical on the day it connects its first mailbox, and discarding that because no
    deal has closed yet would flatten term 4 for the whole trial.
    """
    eval_time = require_aware_instant(eval_time)
    horizon = eval_time - timedelta(days=window_days)
    in_window = [o for o in observations if horizon <= o.occurred_at <= eval_time]

    currency = _modal_currency([o.amount for o in in_window])
    priced = sorted(abs(o.amount.minor_units) for o in in_window
                    if currency is not None and o.amount.currency == currency
                    and o.amount.minor_units != 0)

    known = _fold_all(o.counterparty for o in in_window if o.counterparty)
    active = _fold_all(active_counterparties) | _fold_all(
        o.counterparty for o in in_window if o.is_open and o.counterparty)

    if not priced:
        return OrgBaseline(org_id=org_id, p50_minor_units=0, sample_size=0,
                           currency=UNKNOWN_CURRENCY, computed_against=eval_time,
                           basis=BaselineBasis.ESTIMATED,
                           mission_critical=_fold_all(mission_critical), top_decile=frozenset(),
                           active=active, known=known | active, window_days=window_days)

    top_decile = _top_decile(in_window, currency)

    return OrgBaseline(
        org_id=org_id,
        p50_minor_units=nearest_rank(priced, BP_MAX // 2),
        currency=currency or UNKNOWN_CURRENCY,
        sample_size=len(priced),
        basis=BaselineBasis.ORG_HISTORY,
        computed_against=eval_time,
        mission_critical=_fold_all(mission_critical),
        top_decile=top_decile,
        active=active,
        known=known | active,
        window_days=window_days)


# ------------------------------------------------------------------------------------------
# L1.6.7-U3 · explanation renderer
# ------------------------------------------------------------------------------------------

#: Term 1's clause, by which ladder answered and how far up it the amount sat. The ratio bands
#: are read off the SCORE, not recomputed from the amount, so the sentence can never disagree
#: with the number it is explaining.
_MONEY_PHRASES: tuple[tuple[int, str], ...] = (
    (4000, "the amount is well below your typical contract"),
    (5500, "the amount is under your typical contract"),
    (6500, "the amount is about your typical contract"),
    (8000, "the amount is several times your typical contract"),
)
_MONEY_TOP = "the amount dwarfs your typical contract"

_ABSOLUTE_PHRASES: tuple[tuple[int, str], ...] = (
    (4000, "the amount is small"),
    (6500, "the amount is mid-sized"),
    (8000, "the amount is large"),
)
_ABSOLUTE_TOP = "the amount is very large"

_DEADLINE_PHRASES: tuple[tuple[int, str], ...] = (
    (2000, "the date is months out"),
    (4000, "the date is a month or two out"),
    (6000, "the date is inside a month"),
    (7500, "the date is inside a fortnight"),
    (9000, "the date is inside a week"),
    (10000, "the date is within 48 hours"),
)
_DEADLINE_TOP = "it is due or overdue"

_AUTHORITY_PHRASES: tuple[tuple[int, str], ...] = (
    (3000, "it came from an automated sender"),
    (5000, "the sender is unranked"),
    (8000, "the sender is a known contact"),
    (9500, "the sender is a senior contact"),
)
_AUTHORITY_TOP = "the sender is at the top of your org"

_STANDING_PHRASES: Mapping[EntityStanding, str] = MappingProxyType({
    EntityStanding.MISSION_CRITICAL: "it names a mission-critical counterparty",
    EntityStanding.TOP_DECILE: "it names one of your largest counterparties",
    EntityStanding.ACTIVE: "it names a counterparty you have an open deal with",
    EntityStanding.KNOWN: "it names a counterparty you know",
    EntityStanding.FIRST_SEEN: "it names a counterparty you have not seen before",
    EntityStanding.ABSENT: "it names no counterparty",
})

_MULTIPLIER_PHRASES: tuple[tuple[int, str], ...] = (
    (6500, "the claim is unattributed"),
    (8000, "the claim is a chat aside"),
    (9000, "the claim is written prose"),
    (10000, "the claim is a typed record"),
)
_MULTIPLIER_TOP = "the claim is on a signed document"


def _phrase(bands: Sequence[tuple[int, str]], top: str, value: int) -> str:
    for bound, text in bands:
        if value < bound:
            return text
    return top


def explain_importance(score: ImportanceScore) -> str:
    """L1.6.7-U3 · one human sentence for one score. Template substitution, never a model.

    *"Scored 7825: the amount is several times your typical contract (7000), the date is
    inside a fortnight (6000), it names a mission-critical counterparty (10000), and the claim
    is on a signed document (x10000)."*

    A model is refused here for a reason beyond cost. The numbers are already computed and the
    sentence's whole job is to be TRUE about them; a generated sentence is a second opinion
    about a score, and the first time it says "urgent" about a 2100 the founder stops believing
    both. Every clause below is derived from a stored component, so an explanation cannot
    outlive the arithmetic it describes.
    """
    parts = score.components
    money_bands, money_top = ((_ABSOLUTE_PHRASES, _ABSOLUTE_TOP)
                              if parts.baseline_basis is BaselineBasis.ESTIMATED
                              else (_MONEY_PHRASES, _MONEY_TOP))

    clauses: list[str] = []
    if ImportanceFlag.NO_MONEY not in parts.flags:
        clauses.append(f"{_phrase(money_bands, money_top, parts.monetary_exposure_bp)} "
                       f"({parts.monetary_exposure_bp})")
    if parts.deadline_proximity_bp > 0:
        hedge = (" — as a vague date, halved"
                 if ImportanceFlag.RELATIVE_DEADLINE in parts.flags else "")
        clauses.append(f"{_phrase(_DEADLINE_PHRASES, _DEADLINE_TOP, parts.deadline_proximity_bp)}"
                       f"{hedge} ({parts.deadline_proximity_bp})")
    clauses.append(f"{_phrase(_AUTHORITY_PHRASES, _AUTHORITY_TOP, parts.actor_authority_bp)} "
                   f"({parts.actor_authority_bp})")
    if parts.entity_standing is not EntityStanding.ABSENT:
        clauses.append(f"{_STANDING_PHRASES[parts.entity_standing]} "
                       f"({parts.entity_criticality_bp})")
    multiplier = parts.evidence_authority_multiplier_bp
    clauses.append(f"{_phrase(_MULTIPLIER_PHRASES, _MULTIPLIER_TOP, multiplier)} "
                   f"(x{multiplier})")

    if len(clauses) > 1:
        body = ", ".join(clauses[:-1]) + ", and " + clauses[-1]
    else:
        body = clauses[0]
    caveat = (" Scored without an org baseline, so the amount is judged on an absolute scale."
              if ImportanceFlag.BASELINE_ESTIMATED in parts.flags else "")
    return f"Scored {score.importance_bp}: {body}.{caveat}"
