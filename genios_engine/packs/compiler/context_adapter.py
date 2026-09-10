"""Deterministic situation predicates and generic-object bindings.

Layer 3 does not fetch the graph. It can only inspect the BusinessSituationObject and relevant
context slice already frozen by Layer 2. Unknown predicate inputs remain unknown; they are never
coerced to a match just to keep a route alive.

L3.1-U1 · THE ANALYTIC PREDICATES. Layer 2.4 computes trends, cohort positions and anomalies and
files each one as a `derived.*` graph fact; Layer 1 publishes the disagreements between claims;
`context/quality` types every absence. Until this file could read them, none of that was
expressible in an authored `matches.when` block — a capability could ask what a fact IS and never
ask whether it is FALLING, whether it sits at the bad end of its peer group, whether it broke
against its own baseline, or whether the field it rests on is contested.

Five kinds, all spelled `{kind: ...}`, all evaluated under the same three-state rule as the rest
of this module:

    {kind: trend,    metric: engagement, direction: DECLINING, min_confidence_bp: 5000}
    {kind: cohort,   metric: spend_growth, band: D1, min_population: 5}
    {kind: anomaly,  metric: support_tickets}
    {kind: absence,  fact: decision.scheduled, type: GENUINELY_ABSENT}
    {kind: conflict, field: contract.value}

**A REFUSAL UPSTREAM IS UNKNOWN HERE, NEVER FALSE.** This is the whole reason the analytic
stratum returns refusals as first-class values instead of weak answers. `INSUFFICIENT_HISTORY`
means *we cannot see enough of this to say*, and answering FALSE to "is engagement declining?"
over it is a claim that engagement is NOT declining, drawn from the fact that we have not looked
long enough. The same holds for a cohort that refused for `insufficient_population` and for an
anomaly verdict that refused for `no_current_reading`.

**`UNKNOWABLE` NEVER SATISFIES AN ABSENCE.** `{kind: absence, type: GENUINELY_ABSENT}` is TRUE
only where `context/quality` typed the absence as GENUINELY_ABSENT under a coverage epoch that
still stands — a source that could have carried the fact was connected, everything visible was
checked, and none of it held the fact. Where the absence is UNKNOWABLE the verdict is UNKNOWN,
exactly as the older `{absent: ...}` operator already answers, because "we cannot see it" and "it
is not there" are opposite claims and a dark connector is what turns the second into the first.

**THE CORPUS VALIDATOR HAS TO ADMIT THESE FORMS BEFORE A HUMAN CAN AUTHOR ONE.**
`Domain Expertise/_tools/validate.py` carries a `FORM_KEYS` whitelist — "predicate {keys} matches
no form the engine dispatches on" — and it does not yet list the five below, so a situation file
carrying one is rejected by the corpus validator even though this adapter evaluates it. That file
belongs to the corpus wave and is deliberately not edited from here; the forms it needs are:

    {kind, metric} + optional {direction, min_confidence_bp}      trend
    {kind, metric} + optional {band, min_population}              cohort
    {kind, metric} + optional {direction, min_z_like_bp}          anomaly
    {kind, fact, type}                                            absence
    {kind, field} + optional {resolution}                         conflict

`tests/packs/compiler/test_analytic_predicates.py::test_every_form_the_corpus_validator_admits_
is_one_this_adapter_dispatches` is the seam in the other direction: it goes red if the validator
ever admits a form this module cannot answer.

**ONE SOURCE PER ANSWER.** The trend / cohort / anomaly kinds read the `derived.*` graph fact and
nothing else. The BusinessSituationObject also carries `metadata['trends']`,
`['cohort_positions']` and `['anomalies']`, and they are deliberately NOT consulted: those lists
hold the receipt of the importance MODIFIER that fired, so they exist only for a declining trend
above the composer's confidence floor, only for a cohort position at the worst extreme, only for
a flagged anomaly. Reading them would make `direction: DECLINING` answerable and
`direction: RISING` unanswerable on the same situation, and would silently import the composer's
thresholds into a predicate whose thresholds the author declared.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from enum import Enum
from typing import Any

from genios_engine.context.quality.inference import (ABSENT_FIELDS_KEY,
                                                      OBSERVATION_LICENCE_KEY,
                                                      UNKNOWABLE_FIELDS_KEY,
                                                      may_infer_absent, read_licence,
                                                      read_string_set)
from genios_engine.contracts.analytic import CohortBand
from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.quality import AbsenceType
from genios_engine.contracts.visibility import SCOPES, Visibility
from genios_engine.platform.canonical import semantic_hash

from .errors import SituationContextConflict
from .models import SourceDocument, entity_fields


class PredicateState(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PredicateVerdict:
    state: PredicateState
    missing: tuple[str, ...] = ()


_TRUE = PredicateVerdict(PredicateState.TRUE)
_FALSE = PredicateVerdict(PredicateState.FALSE)


def _unknown(*receipts: str) -> PredicateVerdict:
    """UNKNOWN, with the reason NAMED. Every one of these reaches
    `RoutePlan.unresolved_predicates` and from there the package's
    `metadata['unresolved_route_predicates']`, so "why did this capability not decide?" is
    answerable from the artifact rather than from a re-run."""
    return PredicateVerdict(PredicateState.UNKNOWN, receipts)


#: The `graph_facts.field` prefixes the three analytic families write under.
#:
#: SPELLED HERE, NOT IMPORTED, for the reason `context/importance.py` gives for spelling the same
#: four strings: this module must not drag `context/analytic/` — six modules, a SQLAlchemy
#: dependency and the whole sampler — into the compiler's import graph to learn three prefixes.
#: `tests/packs/compiler/test_analytic_predicates.py` pins each one against the module that owns
#: it (`analytic.trend`, `analytic.comparator`, `analytic.anomaly`), so the copy cannot drift
#: without a red test.
TREND_FACT_PREFIX = "derived.trend."
COHORT_POSITION_FACT_PREFIX = "derived.cohort_position."
ANOMALY_FACT_PREFIX = "derived.anomaly."

#: `signal_conflicts.resolution` for a disagreement Layer 1 could not settle — the only one a
#: `{kind: conflict}` predicate treats as material by default, on `importance._conflict_term`'s
#: argument: the other two verdicts HAVE an answer, and firing on a disagreement we already
#: resolved would charge the reader for our own resolution logic. Pinned against
#: `context.importance.UNRESOLVED_RESOLUTION` by the same test as the prefixes above.
UNRESOLVED_CONFLICT = "unresolved_surface_both"

#: `TrendDirection`'s two REFUSALS, as they appear in the fact body. A trend over either is
#: UNKNOWN — see the module docstring. Spelled beside the three answers so a body carrying a
#: sixth, unrecognised word is UNKNOWN too rather than falling through as an answer.
TREND_REFUSALS = frozenset({"insufficient_history", "insufficient_coverage"})
TREND_ANSWERS = frozenset({"rising", "declining", "flat"})

#: The absence types a context slice can actually answer. `build_context_slice` carries exactly
#: two of `AbsenceType`'s five — the UNKNOWABLE paths and the GENUINELY_ABSENT ones — because
#: those are the two that decide whether a negative inference is licensed. PRESENT, STALE and
#: NOT_EXPECTED are not carried, so a predicate naming one of them is refused by name rather than
#: answered from a set that does not describe it.
ABSENCE_PREDICATE_TYPES = frozenset({AbsenceType.GENUINELY_ABSENT.value,
                                     AbsenceType.UNKNOWABLE.value})

#: The five analytic predicate kinds, as a closed set. A `kind:` outside it is UNKNOWN and named,
#: never evaluated as one of the older key-based predicates: a typo that fell through to the
#: `path:` tail would be answered by a completely different question.
PREDICATE_KINDS = frozenset({"trend", "cohort", "anomaly", "absence", "conflict"})


def _normal(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").split())


def _whole(value: Any) -> int | None:
    """An integer, or nothing. `True` is refused — bool is an int in Python, and a `flagged`
    read as a 1 would become a confidence of one basis point nobody measured. A `Decimal` is
    refused for the same reason a float is: every number in this stratum is an integer basis
    point or an integer count, and a fractional one arriving here is a producer defect that must
    be named, not silently compared."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class ContextAdapter:
    """The only compiler component allowed to look inside the situation context slice."""

    def __init__(self, situation: BusinessSituationObject,
                 context: SituationContextSlice | None = None) -> None:
        self.situation = situation
        self.context = context
        if context is not None:
            if context.org_id != situation.org_id:
                raise SituationContextConflict(
                    f"context org {context.org_id!r} does not match situation org "
                    f"{situation.org_id!r}")
            source = Visibility.model_validate(dict(context.visibility))
            target = Visibility.model_validate(dict(situation.visibility))
            if SCOPES.index(source.scope) > SCOPES.index(target.scope) or (
                    source.scope in {"participants", "private"}
                    and not set(target.principals) <= set(source.principals)):
                raise SituationContextConflict(
                    "context visibility is narrower than the BusinessSituationObject visibility")

        self.facts = self._combine(
            context.facts if context is not None else {},
            situation.metadata.get("facts") or {},
            "fact",
        )
        self.neighbor_facts = self._combine(
            context.neighbor_facts if context is not None else {},
            situation.metadata.get("neighbor_facts") or {},
            "neighbor fact",
        )
        context_baselines = context.metadata.get("baselines") if context is not None else {}
        self.baselines = self._combine(
            context_baselines or {}, situation.metadata.get("baselines") or {}, "baseline")
        observations: set[str] = set()
        raw_observations = (
            *(context.observations if context is not None else ()),
            *(situation.metadata.get("observations") or ()),
        )
        for value in raw_observations:
            if isinstance(value, Mapping):
                value = value.get("kind") or value.get("type")
            if value:
                observations.add(str(value))
        self.observations = frozenset(observations)
        self.neighbor_observations = frozenset({
            *(context.neighbor_observations if context is not None else ()),
            *(str(value) for value in situation.metadata.get("neighbor_observations") or ()),
        })
        self.missing_fields = frozenset({
            *(context.missing_fields if context is not None else ()),
            *(str(value) for value in situation.metadata.get("missing_fields") or ()),
        })
        # L2.5.5 · TYPED ABSENCE, as this layer sees it. `missing_fields` says a field is not
        # held; these two say which KIND of not-held it is, and the difference decides whether
        # `{absent: ...}` is a finding or a fabrication. Read through `context.quality.inference`
        # so the keys have one spelling shared with the producer, and ABSENT keys mean unchanged
        # behaviour — a slice with no absence data evaluates exactly as it did before this landed.
        sources = (context.metadata if context is not None else None, situation.metadata)
        self.unknowable_fields = read_string_set(*sources, key=UNKNOWABLE_FIELDS_KEY)
        self.absent_fields = read_string_set(*sources, key=ABSENT_FIELDS_KEY)
        self.observation_absence_licensed = read_licence(*sources, key=OBSERVATION_LICENCE_KEY)

    @staticmethod
    def _combine(primary: Any, inline: Any, label: str) -> Mapping[str, Any]:
        if not isinstance(primary, Mapping) or not isinstance(inline, Mapping):
            raise SituationContextConflict(f"{label} collections must be mappings")
        combined = dict(primary)
        for key, value in inline.items():
            if key in combined and semantic_hash(combined[key]) != semantic_hash(value):
                raise SituationContextConflict(
                    f"conflicting {label} {key!r} in context slice and situation metadata")
            combined[key] = value
        return combined

    def _fact(self, path: str, *, neighbor: bool = False) -> tuple[bool, Any]:
        """One fact, with the 1-hop borrow the rest of this class already performs.

        THE TWO HALVES OF ONE RULE DISAGREED. `_typed_absence` and `_derived` both consult the
        neighbourhood; this did not, so `exists`, `absent` and `path` saw the anchor's own facts
        alone. On a COMPANY anchor that is almost nothing — `domain_shadow` measured 15 of 18
        companies on the design partner's org holding zero facts of their own, because everything
        a capability asks for (`thread.ball_in_court`, `deal.status`, `commitment.due_at`) is
        extracted onto the PEOPLE and THREADS that constitute the relationship.
        #
        And `situation_bso._missing_paths` counts a neighbour-held field as HELD, so such a path
        never entered `missing_fields` either — which is what made the answer a confident FALSE
        rather than an honest UNKNOWN. Two halves of one rule, disagreeing about what the slice
        contains.

        ROOT FIRST, ALWAYS. A fact on the anchor itself is the anchor's own answer and outranks a
        borrowed one; the borrow only fills a gap. `neighbor_fact` still reads the neighbourhood
        EXCLUSIVELY, because an author writing that form is asking about the neighbourhood
        specifically and a root value would answer a different question.
        """
        facts = self.neighbor_facts if neighbor else self.facts
        if path not in facts and not neighbor and path in self.neighbor_facts:
            facts = self.neighbor_facts
        if path not in facts:
            return False, None
        value = facts[path]
        if isinstance(value, Mapping) and "value" in value:
            value = value["value"]
        return True, value

    def _evaluation_time(self) -> datetime | None:
        if self.context is not None:
            return self.context.evaluation_time.astimezone(timezone.utc)
        raw = self.situation.metadata.get("evaluation_time")
        if isinstance(raw, datetime):
            value = raw
        elif isinstance(raw, str):
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        if op == "=":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == "IN":
            return isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)) \
                and actual in expected
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
        raise ValueError(f"unsupported authored predicate operator {op!r}")

    def _threshold(self, value: Any) -> tuple[bool, Any]:
        """What the left-hand side is compared AGAINST — a literal, a baseline, or another fact.

        `{other_path: ...}` IS THE FORM THAT LETS A RULE STOP BEING A NUMBER.
        Before it, everything an author could write was `path OP <literal>`, so every threshold in
        the corpus was somebody's guess at a number that suits every customer. `outbound-awaiting-
        reply.yaml` is the confession: it gates on `days_waiting >= 3` while its own description
        four lines up says the opposite — *"a fund that answers in three weeks is not slow at day
        ten."* The author knew the right rule and had no way to write it, so the file states it in
        prose and hopes the model applies it.

        The right rule compares two facts the graph already holds:

            - path: outreach.days_waiting
              op: ">"
              value: {other_path: party.reply_cadence_days, mult: 1.5, floor: 3}

        "Chase when we have waited half again as long as THIS counterparty's own normal, and never
        before day three." That is one rule that behaves differently for a fund who replies in a
        day and a fund who replies in a month — which is what a rule has to do when the customers
        are not the same customer.

        `mult` and `floor` mean exactly what they already mean for `baseline`, deliberately: the
        two forms are the same shape with a different left-hand source, so an author who has
        learnt one has learnt both.

        THE THREE-STATE RULE IS NOT BENT. An `other_path` the slice does not hold returns
        NOT-KNOWN, so the condition is UNKNOWN and `matches()` abstains. It must never fall back
        to a default number: silently substituting one would make the comparison answer a question
        nobody asked, and for a doctrine rule a wrong FALSE reads as *satisfied*.

        RESOLVED THROUGH `_fact`, so it obeys the same precedence as the left-hand side — the
        anchor's own value first, the 1-hop neighbourhood second, and `missing_fields` /
        `unknowable_fields` outranking both. A company anchor holds almost no facts of its own, so
        a form that read only the root would be unknown on nearly every situation.
        """
        if isinstance(value, Mapping) and "other_path" in value:
            other = str(value["other_path"])
            present, held = self._fact(other, neighbor=False)
            if not present or held is None:
                return False, f"other_path:{other}"
            multiplier = value.get("mult", 1)
            floor = value.get("floor")
            try:
                threshold = Decimal(str(held)) * Decimal(str(multiplier))
                if floor is not None:
                    threshold = max(threshold, Decimal(str(floor)))
            except (DecimalException, TypeError, ValueError):
                # A non-numeric fact on the right-hand side is not a comparison. UNKNOWN rather
                # than an exception: an author naming a text field here has made a mistake, and
                # the honest answer is that this rule could not be decided, not that it failed.
                return False, f"other_path:{other}"
            return True, threshold
        if not isinstance(value, Mapping) or "baseline" not in value:
            return True, value
        name = str(value["baseline"])
        if name not in self.baselines:
            return False, name
        baseline = self.baselines[name]
        if isinstance(baseline, Mapping) and "value" in baseline:
            baseline = baseline["value"]
        multiplier = value.get("mult", 1)
        floor = value.get("floor")
        try:
            threshold = Decimal(str(baseline)) * Decimal(str(multiplier))
            if floor is not None:
                threshold = max(threshold, Decimal(str(floor)))
        except (DecimalException, TypeError, ValueError):
            return False, name
        return True, threshold

    # =============================================================================================
    # L3.1-U1 · THE ANALYTIC PREDICATES
    # =============================================================================================

    def _derived(self, prefix: str, metric: Any) -> tuple[str, Mapping[str, Any] | None]:
        """The `derived.<family>.<metric>` fact body, or None.

        THE SUBJECT FIRST, THEN THE NEIGHBOURHOOD, in that fixed order — never a set, never
        iteration order, because this function's answer feeds a content-addressed package.

        The neighbourhood is consulted at all because of where these facts LAND. A derived fact is
        filed against the `subject_node_id` it was measured on, and a situation anchored on a
        company holds almost none of its own (15 of 18 held literally zero on the design partner's
        org): engagement is measured on the people, spend on the deals. `reason/runner._neighborhood`
        already merges the 1-hop facts deterministically — newest `occurred_at` wins, ties broken
        on node id — and `domain_shadow` hands that merge to the slice. Reading the anchor alone
        here would make every analytic predicate a rule that is always right and never fires.
        """
        path = f"{prefix}{metric}"
        for neighbor in (False, True):
            present, value = self._fact(path, neighbor=neighbor)
            if present and isinstance(value, Mapping):
                return path, value
        return path, None

    def _trend(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        """`{kind: trend, metric: ..., direction: DECLINING, min_confidence_bp: 5000}`."""
        metric = condition.get("metric")
        if not metric:
            return _unknown("trend:no_metric")
        path, body = self._derived(TREND_FACT_PREFIX, metric)
        if body is None:
            # No trend has been computed for this (node, metric). "We have not measured it" is
            # not "it is not declining", so this is the same UNKNOWN a refusal produces.
            return _unknown(path)
        direction = _normal(body.get("direction"))
        if direction in TREND_REFUSALS:
            # THE REFUSAL, CARRIED. `insufficient_history` / `insufficient_coverage` are
            # `TrendDirection` members and first-class return values, and the receipt names which
            # one so a reader can tell "too few points" from "too many gaps".
            return _unknown(f"{path}:{direction}")
        if direction not in TREND_ANSWERS:
            return _unknown(f"{path}:direction")
        wanted = condition.get("direction")
        if wanted is not None and _normal(wanted) != direction:
            return _FALSE
        floor = condition.get("min_confidence_bp")
        if floor is not None:
            confidence = _whole(body.get("trend_confidence_bp"))
            if confidence is None:
                return _unknown(f"{path}:trend_confidence_bp")
            authored_floor = _whole(floor)
            if authored_floor is None:
                return _unknown("trend:min_confidence_bp")
            # A KNOWN number under the author's own bar is FALSE, not UNKNOWN. The direction was
            # answered and the strength was measured; the author said how strong it had to be.
            if confidence < authored_floor:
                return _FALSE
        return _TRUE

    def _cohort(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        """`{kind: cohort, metric: ..., band: D1, min_population: 5}`."""
        metric = condition.get("metric")
        if not metric:
            return _unknown("cohort:no_metric")
        path, body = self._derived(COHORT_POSITION_FACT_PREFIX, metric)
        if body is None:
            return _unknown(path)
        refused = body.get("refused")
        if refused:
            # `CohortRefusalReason` — insufficient_population, degenerate_distribution,
            # subject_not_a_member and the rest. A cohort that could not position the subject has
            # not placed it OUTSIDE the band; it has not placed it at all.
            return _unknown(f"{path}:{_normal(refused)}")
        population = _whole(body.get("population_size"))
        if population is None:
            return _unknown(f"{path}:population_size")
        floor = condition.get("min_population")
        if floor is not None:
            authored_floor = _whole(floor)
            if authored_floor is None:
                return _unknown("cohort:min_population")
            if population < authored_floor:
                return _FALSE
        band_name = condition.get("band")
        if band_name is None:
            return _TRUE
        try:
            wanted = CohortBand(str(band_name).strip().upper())
        except ValueError:
            # The vocabulary is the contract's fourteen labels and there is no second one. A
            # symbolic alias like `top_decile` would be a parallel grammar for the same fact, and
            # the day the two disagree the card prints the loser.
            return _unknown(f"cohort_band:{band_name}")
        percentile = _whole(body.get("percentile_bp"))
        if percentile is None or not 0 <= percentile <= 10_000:
            return _unknown(f"{path}:percentile_bp")
        try:
            # RECOMPUTED from the percentile and the population, never read off the body — the
            # same rule `importance._expressible_band` keeps and for the same reason: a `D1`
            # written by an older, un-narrowed writer is a decile claim a cohort of six could
            # never have produced. `CohortBand.for_percentile` owns the narrowing.
            actual = CohortBand.for_percentile(percentile, divisions=wanted.divisions,
                                               population_size=population)
        except (TypeError, ValueError):
            # A population too small to express ANY scheme. It has not answered "no"; it cannot
            # answer at all, and a FALSE here would read as "this account is not at the bottom".
            return _unknown(f"{path}:population_too_small")
        return _TRUE if actual is wanted else _FALSE

    def _anomaly(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        """`{kind: anomaly, metric: ..., direction: above, min_z_like_bp: 30000}`."""
        metric = condition.get("metric")
        if not metric:
            return _unknown("anomaly:no_metric")
        path, body = self._derived(ANOMALY_FACT_PREFIX, metric)
        if body is None:
            return _unknown(path)
        refusal = body.get("refusal")
        if refusal:
            # `AnomalyRefusal.INSUFFICIENT_HISTORY` — no normal to be abnormal against — or
            # `NO_CURRENT_READING`, a series ending on a period we have no reading for. Neither
            # is evidence that the metric behaved.
            return _unknown(f"{path}:{_normal(refusal)}")
        flagged = body.get("flagged")
        if not isinstance(flagged, bool):
            return _unknown(f"{path}:flagged")
        if not flagged:
            # MEASURED AND NOT FLAGGED is a real FALSE: the detector had a baseline, computed the
            # deviation, and both of its conjuncts failed. That is the one case here that is an
            # answer rather than an abstention.
            return _FALSE
        wanted = condition.get("direction")
        if wanted is not None:
            direction = _normal(body.get("direction"))
            if not direction:
                return _unknown(f"{path}:direction")
            if _normal(wanted) != direction:
                return _FALSE
        floor = condition.get("min_z_like_bp")
        if floor is not None:
            z_like = _whole(body.get("z_like_bp"))
            if z_like is None:
                return _unknown(f"{path}:z_like_bp")
            authored_floor = _whole(floor)
            if authored_floor is None:
                return _unknown("anomaly:min_z_like_bp")
            if z_like < authored_floor:
                return _FALSE
        return _TRUE

    def _typed_absence(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        """`{kind: absence, fact: decision.scheduled, type: GENUINELY_ABSENT}`.

        THE DIFFERENCE FROM `{absent: ...}`. The older operator asks whether the fact is held and
        whether an inference over its absence is licensed; it answers TRUE for an untyped gap
        under a licence that was never withdrawn. This one asks the classifier's own question —
        *which KIND of not-held is this?* — and it will not answer from silence: a slice that
        carried no absence typing for the path says UNKNOWN, because an untyped gap is exactly
        what `context/quality` exists to stop being read as a finding.
        """
        path = str(condition.get("fact") or condition.get("path") or "")
        if not path:
            return _unknown("absence:no_fact")
        wanted = _normal(condition.get("type"))
        if wanted not in ABSENCE_PREDICATE_TYPES:
            # Includes the untyped case. `{kind: absence, fact: x}` with no `type:` is not
            # defaulted to GENUINELY_ABSENT: defaulting silently to the one member that licenses
            # a negative inference is how the licence gets granted by omission.
            return _unknown(f"absence_type:{_normal(condition.get('type')) or 'untyped'}")
        # HELD ANYWHERE IS NOT ABSENT. The neighbourhood counts as held for the same reason
        # `situation_bso._missing_paths` counts it: `reason/adapters/native` borrows a root field
        # from the 1-hop neighbours, so a fact present there is one the reasoner can read, and
        # calling it absent would be a finding over evidence we have.
        if self._fact(path)[0] or self._fact(path, neighbor=True)[0]:
            return _FALSE
        if path in self.unknowable_fields:
            # THE LAW, at its call site. An UNKNOWABLE path satisfies `GENUINELY_ABSENT` never —
            # not FALSE either, because "no connected source could have carried it" is not
            # evidence about the world, only about us.
            return _TRUE if wanted == AbsenceType.UNKNOWABLE.value else _unknown(path)
        if path in self.absent_fields:
            # Typed GENUINELY_ABSENT under a coverage epoch that still stands. Definitely not
            # UNKNOWABLE, so the other question has a real negative answer here.
            return (_TRUE if wanted == AbsenceType.GENUINELY_ABSENT.value else _FALSE)
        return _unknown(f"absence:{path}")

    def _conflict(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        """`{kind: conflict, field: contract.value}` — is this field CONTESTED?

        Layer 1 publishes each disagreement between claims and how it settled it, and
        `situation_bso.gather_conflicts` carries the records (not just the ids) onto the BSO
        precisely so Layer 3 does not have to read past Layer 2 to find out. A situation resting
        on a contested claim must not reach a capability looking settled.
        """
        field = str(condition.get("field") or "")
        if not field:
            return _unknown("conflict:no_field")
        records = self.situation.metadata.get("conflicts")
        if records is None:
            # The key is written on every BSO this codebase builds. Absent means the object came
            # from a producer that does not carry conflicts, and silence is not "nothing is
            # contested".
            return _unknown(f"conflict:{field}")
        wanted = str(condition.get("resolution") or UNRESOLVED_CONFLICT)
        carried = tuple(record for record in records if isinstance(record, Mapping))
        for record in carried:
            if str(record.get("field") or "") == field and \
                    str(record.get("resolution") or "") == wanted:
                return _TRUE
        pointers = self.situation.metadata.get("conflict_ids") or ()
        if len(tuple(pointers)) > len(carried):
            # `_attach_conflicts` caps the records at MAX_CONFLICTS while `conflict_ids` keeps
            # pointing at all of them. More pointers than records means a disagreement about this
            # field may be one of the ones that did not travel — countable, so say so.
            return _unknown(f"conflict:{field}:truncated")
        return _FALSE

    def evaluate(self, condition: Mapping[str, Any]) -> PredicateVerdict:
        kind = condition.get("kind")
        if kind is not None:
            # DISPATCHED FIRST, and on a closed set. An unrecognised kind must not fall through
            # into the `path:` tail below, where it would be answered by a different question
            # entirely; it is refused by name and counted.
            normalized = _normal(kind)
            if normalized not in PREDICATE_KINDS:
                return _unknown(f"unsupported_predicate_kind:{normalized or 'blank'}")
            return {
                "trend": self._trend,
                "cohort": self._cohort,
                "anomaly": self._anomaly,
                "absence": self._typed_absence,
                "conflict": self._conflict,
            }[normalized](condition)
        if "exists" in condition:
            path = str(condition["exists"])
            # An UNKNOWABLE field is not held and is not evidence that it does not exist, so
            # `exists:` over one is UNKNOWN exactly as over a declared gap. Checked before
            # `missing_fields` because a fact nobody DECLARED can still be unknowable — the
            # expectation map and the coverage map are different declarations.
            if path in self.unknowable_fields or path in self.missing_fields:
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))
            # THREE ANSWERS TO ONE QUESTION, and only one of them is a defect.
            #
            # An audit read this branch's FALSE (a path not in the slice), `absent:`'s TRUE for
            # the same path, and `path:`'s UNKNOWN, and called them three answers. Two of the
            # three agree: `exists`→FALSE and `absent`→TRUE both say "the fact is not there", and
            # `path:`→UNKNOWN is right on its own terms, because a value you do not have cannot
            # be compared to a threshold.
            #
            # THE REAL GAP IS UPSTREAM AND IS NOT FIXED HERE. `may_infer_absent` is
            # `path not in unknowable`, and `unknowable_fields` holds only what somebody
            # DECLARED unknowable — so a path nobody classified falls through to "licensed", and
            # this branch concludes absence from silence. `AbsenceType`'s own docstring forbids
            # exactly that: "a `coverage_ready` of None lands in UNKNOWABLE, never in
            # GENUINELY_ABSENT — 'we did not classify this domain' is not evidence that the
            # domain is covered." Closing it means making the coverage map TOTAL, which is a
            # different piece of work from this evaluator and would turn most `absent:` answers
            # into abstentions until it is done.
            #
            # A first cut of this comment shipped a `may_infer_absent` call here as if it fixed
            # that. It could not: the `unknowable_fields` test three lines above has already
            # returned, so the call can only ever answer True. Recorded rather than deleted,
            # because a no-op wearing a fix's comment is worse than the gap it claims to close.
            return PredicateVerdict(PredicateState.TRUE if self._fact(path)[0]
                                    else PredicateState.FALSE)
        if "absent" in condition:
            path = str(condition["absent"])
            # THE NEGATIVE INFERENCE. `{absent: thread.last_inbound}` says "they never replied";
            # `{absent: contract.amendment}` says "there is no amendment". Both were TRUE here
            # whenever the fact was simply not in the slice, with no reference of any kind to
            # whether a source that could have carried it was connected — so an org with no
            # mailbox satisfied "they never replied" on every situation it had.
            # ASKED, not re-derived. `quality/inference.may_infer_absent` is documented as
            # "one function rather than an `in` at each of the call sites, so 'which absences
            # license an inference' has one answer a reader can see" — and this was the call site
            # that spelled the `in` out again, leaving the licence with a definition nobody
            # consulted and a copy that decided. Two copies of one rule is how the next consumer
            # gets a third.
            if not may_infer_absent(path, unknowable=self.unknowable_fields):
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))
            # Typed GENUINELY_ABSENT under a coverage epoch that still stands: a source could
            # have carried it, everything we can see was checked, and none did. THIS is the
            # finding, and it is the one case where the answer is TRUE rather than an abstention
            # — the whole point of typing an absence is that some absences are the intelligence.
            if path in self.absent_fields and not self._fact(path)[0]:
                return PredicateVerdict(PredicateState.TRUE)
            if path in self.missing_fields:
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))
            return PredicateVerdict(PredicateState.FALSE if self._fact(path)[0]
                                    else PredicateState.TRUE)
        if "has_obs" in condition:
            return PredicateVerdict(PredicateState.TRUE if str(condition["has_obs"])
                                    in self.observations else PredicateState.FALSE)
        if "no_obs" in condition:
            kind = str(condition["no_obs"])
            if kind in self.observations:
                return PredicateVerdict(PredicateState.FALSE)
            # An observation that never arrived is only a finding when a source that would have
            # carried it was connected and flowing. This is the licence
            # `capture.coverage.model._READINESS` has computed as `can_evaluate_no_reply` since
            # the day it was written and which nothing has ever read.
            return PredicateVerdict(PredicateState.TRUE) if self.observation_absence_licensed \
                else PredicateVerdict(PredicateState.UNKNOWN, (f"no_obs:{kind}",))
        if "neighbor_has_obs" in condition:
            return PredicateVerdict(
                PredicateState.TRUE if str(condition["neighbor_has_obs"])
                in self.neighbor_observations else PredicateState.FALSE)
        if "neighbor_no_obs" in condition:
            kind = str(condition["neighbor_no_obs"])
            if kind in self.neighbor_observations:
                return PredicateVerdict(PredicateState.FALSE)
            return PredicateVerdict(PredicateState.TRUE) if self.observation_absence_licensed \
                else PredicateVerdict(PredicateState.UNKNOWN, (f"neighbor_no_obs:{kind}",))
        if condition.get("fn") == "edge_count":
            actual = self.context.edge_count if self.context is not None \
                else self.situation.metadata.get("edge_count")
            if actual is None:
                return PredicateVerdict(PredicateState.UNKNOWN, ("edge_count",))
            known, expected = self._threshold(condition.get("value"))
            if not known:
                return PredicateVerdict(PredicateState.UNKNOWN, (f"baseline:{expected}",))
            try:
                matched = self._compare(actual, str(condition.get("op") or "="), expected)
            except (TypeError, ValueError):
                return PredicateVerdict(PredicateState.UNKNOWN, ("edge_count",))
            return PredicateVerdict(
                PredicateState.TRUE if matched else PredicateState.FALSE)

        path = condition.get("path") or condition.get("neighbor_fact")
        if not path:
            return PredicateVerdict(PredicateState.UNKNOWN, ("unsupported_predicate",))
        path = str(path)
        present, actual = self._fact(path, neighbor="neighbor_fact" in condition)
        if not present:
            return PredicateVerdict(PredicateState.UNKNOWN, (path,))

        if condition.get("fn") in {"days_since", "hours_since"}:
            evaluation_time = self._evaluation_time()
            if evaluation_time is None:
                return PredicateVerdict(PredicateState.UNKNOWN, ("evaluation_time",))
            try:
                observed = actual if isinstance(actual, datetime) else datetime.fromisoformat(
                    str(actual).replace("Z", "+00:00"))
                if observed.tzinfo is None or observed.utcoffset() is None:
                    raise ValueError("naive")
                seconds = (evaluation_time - observed.astimezone(timezone.utc)).total_seconds()
                actual = Decimal(str(seconds)) / Decimal(
                    86_400 if condition["fn"] == "days_since" else 3_600)
            except (TypeError, ValueError):
                return PredicateVerdict(PredicateState.UNKNOWN, (path,))

        known, expected = self._threshold(condition.get("value"))
        if not known:
            return PredicateVerdict(PredicateState.UNKNOWN, (f"baseline:{expected}",))
        try:
            matched = self._compare(actual, str(condition.get("op") or "="), expected)
        except (TypeError, ValueError):
            return PredicateVerdict(PredicateState.UNKNOWN, (path,))
        return PredicateVerdict(PredicateState.TRUE if matched else PredicateState.FALSE)

    def matches(self, conditions: Sequence[Mapping[str, Any]]) -> PredicateVerdict:
        missing: set[str] = set()
        for condition in conditions:
            verdict = self.evaluate(condition)
            if verdict.state is PredicateState.FALSE:
                return verdict
            if verdict.state is PredicateState.UNKNOWN:
                missing.update(verdict.missing)
        if missing:
            return PredicateVerdict(PredicateState.UNKNOWN, tuple(sorted(missing)))
        return PredicateVerdict(PredicateState.TRUE)

    def bind_objects(self, objects: Sequence[SourceDocument]) -> dict[str, tuple[str, ...]]:
        entities: list[tuple[str, set[str]]] = []
        for index, entity in enumerate(self.situation.entities):
            fields = entity_fields(entity)
            entity_id = str(fields.get("id") or fields.get("entity_id") or f"entity:{index}")
            names = {
                _normal(fields.get("type")),
                _normal(fields.get("object_type")),
                _normal(fields.get("kind")),
                _normal(fields.get("name")),
            }
            entities.append((entity_id, {value for value in names if value}))

        bindings: dict[str, tuple[str, ...]] = {}
        for document in objects:
            identity = document.content.get("identity") or {}
            aliases = identity.get("aliases") or ()
            object_names = {
                _normal(document.id.rsplit(".", 1)[-1]),
                _normal(identity.get("name")),
                *(_normal(alias) for alias in aliases),
            }
            matched = sorted(entity_id for entity_id, names in entities if object_names & names)
            if matched:
                bindings[document.id] = tuple(matched)
        return bindings


__all__ = [
    "ABSENCE_PREDICATE_TYPES",
    "ANOMALY_FACT_PREFIX",
    "COHORT_POSITION_FACT_PREFIX",
    "ContextAdapter",
    "PREDICATE_KINDS",
    "PredicateState",
    "PredicateVerdict",
    "TREND_ANSWERS",
    "TREND_FACT_PREFIX",
    "TREND_REFUSALS",
    "UNRESOLVED_CONFLICT",
]
