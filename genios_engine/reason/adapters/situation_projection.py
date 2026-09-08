"""DLG-06 · IN-1 — Layer 2's BSO becomes snapshot facts a reasoning unit can read.

THE DEAD SEAM THIS CLOSES. Layer 2 v2 publishes, on every situation, a composed importance with a
term-by-term record, the analytic stratum (trend / cohort position / anomaly / dependency), a
six-axis confidence vector, typed absence, the M-4 lifecycle, resolved conflicts and verified
evidence spans. Every one of those reaches `expertise_capability_manifest` on the compiled lane —
and stops there. `native_context_snapshot` builds its `ContextSnapshot` from the graph
`NodeContext` alone, so a reasoning unit has never been able to see any of it. Doc 06 calls this
"the importance dead-seam repeated at scale", and it is: L2 computes an entire analytic stratum
that no decision has ever read.

WHAT THIS MODULE IS. A pure projection: `(BusinessSituationObject, SituationContextSlice) ->
namespaced snapshot facts + evidence refs + a receipt`. It decides nothing, scores nothing and
reads no clock and no database. Units then consume the result as ORDINARY DECLARED FIELDS, which
is what makes the Unit Selector (doc 01 C1) able to schedule a situation-aware unit on a situation
that carries the input and drop it, with a receipt, on one that does not.

THE NAMESPACE is doc 06's, spelled once here and nowhere else:

    situation.trend.<metric>       the declining comparison the importance leaned on
    situation.cohort.<metric>      percentile_bp · cohort_id · population · band
    situation.anomaly.<metric>     z_like_bp · direction · periods_used
    situation.conflict.<field>     what was contested, how Layer 1 resolved it, how many claims
    situation.missing.<fact>       THE ABSENCE TYPE — never the missing fact's value
    situation.confidence.<axis>    one fact per axis; the vector is never collapsed to a scalar
    situation.importance           the composed number with its source and version
    situation.dependency_count     how many items wait on this situation
    situation.lifecycle            M-4: state, who resolved it, whether the closure was partial
    situation.pattern_id           L2.6's fire, when one named the situation
    situation.matched_conditions   the per-condition receipt behind that fire
    situation.evidence_spans       how many spans were verified against their source text

THE TYPED-ABSENCE RULE, WHICH IS THE ONE TO GET RIGHT
-----------------------------------------------------
Layer 2 built a five-state absence vocabulary — PRESENT / STALE / NOT_EXPECTED / UNKNOWABLE /
GENUINELY_ABSENT — precisely so that *"we cannot see it"* stops being confused with *"it is not
there"*. A projection that flattens UNKNOWABLE into a number, a zero or a false undoes that whole
wave at the seam, so this module holds three states all the way through and there is no fourth:

  PRESENT   the reading exists  -> a fact, with an evidence ref, in `facts`
  UNKNOWN   nothing measured it -> the NAME goes into `unknown_fields` (which the snapshot carries
                                   as `missing_fields`) and the reason into the receipt. There is
                                   no value, no default, no neutral midpoint. An unassessed
                                   confidence axis arrives here, never as a 0 and never as a 5000.
  ABSENT    it was measured and there is nothing -> `situation.missing.<fact>` carries the ABSENCE
                                   TYPE as its value. That is a statement ABOUT the gap, not a
                                   value FOR the missing fact, and only `GENUINELY_ABSENT` licenses
                                   a negative inference (`contracts.quality.
                                   NEGATIVE_INFERENCE_TYPES`, re-read here, never re-decided).

The same three states are applied to the analytic stratum, using L2's own modifier reasons:
a term that reports `no_input` never ran a comparison, so its absence is UNKNOWABLE; a term that
reports `trend_not_declining` or `cohort_not_at_worst_extreme` DID compare and found nothing
qualifying, which is GENUINELY_ABSENT — a finding, not a blind spot. Reading those two as the same
thing is how "the metric is fine" and "we never looked at the metric" become one card.

WHY A FIRED TREND TERM IS A DECLINING TREND. `context.importance._qualifying_trends` admits a
trend only when `direction == "declining"` and its confidence clears `MIN_TREND_CONFIDENCE_BP`,
and `_trend_term` fires only on what that returns. So the presence of `situation.trend.<metric>`
IS the declining reading; this module does not restate the direction it did not read, it projects
the term's own receipt verbatim and records the qualification law in `metadata['reading']`.

EVIDENCE — ONE BUILDER, ONE WITNESS
-----------------------------------
Every projected fact is minted through `reason.evidence.build_evidence_ref` (DLG-11's single
seed), entity-referenced to the SAME root entity the snapshot names so that
`canonical_evidence_id_for` — the backfill's engine — reproduces the id without knowing this file
exists. `source_ref` is the situation id and `independence_group` is `l2:situation:<id>` for ALL
of them, deliberately: every projected reading has one witness, Layer 2's situation, and Rule 11
raises confidence only across independence groups. A projection that gave each fact its own group
would let one situation manufacture twelve independent corroborations of itself.

`observed_at` is deliberately None. A composed reading has no single observation instant, and
`last_seen_at` — the only candidate — moves on every sweep: it is inside the evidence seed, so
using it would re-mint every evidence id, and therefore the whole content-addressed snapshot, on
sweeps where nothing changed. That is the mechanism that put 995 MB on one tenant's database and
took the project read-only. Undated evidence is excluded from `core.context`'s freshness reading,
which is the honest outcome: this projection is not a fresh observation of anything.

PURE. No DB, no clock, no LLM, no float. `test_situation_projection.py` reads this module's own
source to prove the first three.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.quality import NEGATIVE_INFERENCE_TYPES, AbsenceType
from genios_engine.contracts.reasoning import EvidenceRef
from genios_engine.contracts.situation_evidence import (
    AXIS_UNKNOWN_BP,
    CONFIDENCE_AXES,
    SituationConfidenceVector,
)
from genios_engine.context.quality.inference import (
    ABSENT_FIELDS_KEY,
    OBSERVATION_LICENCE_KEY,
    UNKNOWABLE_FIELDS_KEY,
)
from genios_engine.reason.evidence import build_evidence_ref

# =================================================================================================
# THE NAMESPACE (doc 06, IN-1)
# =================================================================================================

#: Everything this module writes lives under one prefix, so `native_context_snapshot` can tell a
#: projected fact from a graph fact without a list to keep in sync, and so a capability that
#: declares one cannot collide with a Layer 2 fact path.
SITUATION_NAMESPACE = "situation."

TREND_PREFIX = "situation.trend."
COHORT_PREFIX = "situation.cohort."
ANOMALY_PREFIX = "situation.anomaly."
CONFLICT_PREFIX = "situation.conflict."
ABSENCE_PREFIX = "situation.missing."
CONFIDENCE_PREFIX = "situation.confidence."
IMPORTANCE_FIELD = "situation.importance"
DEPENDENCY_FIELD = "situation.dependency_count"
LIFECYCLE_FIELD = "situation.lifecycle"
PATTERN_FIELD = "situation.pattern_id"
MATCHED_CONDITIONS_FIELD = "situation.matched_conditions"
EVIDENCE_SPANS_FIELD = "situation.evidence_spans"

#: Bumped when the field mapping below changes, so a replayed snapshot is never silently
#: attributed to a different projection. It travels on every projected fact record and in the
#: receipt.
PROJECTION_VERSION = "l4-situation-projection.v1"

#: What a projected fact says about itself. Not "graph": a reader of a snapshot must be able to
#: tell a reading Layer 2 composed from a fact a connector wrote.
PROJECTION_SOURCE = "l2.situation"

#: The one witness. See the module docstring — Rule 11 groups by this, and twelve groups from one
#: situation would be twelve corroborations of a single observation.
def independence_group_for(situation_id: str) -> str:
    return f"l2:situation:{situation_id}"


#: The analytic modifier names, and the namespace each one projects into. Spelled as the strings
#: `context.importance.ModifierName` publishes rather than imported, because this module reads a
#: STORED record — `metadata['importance_components']` — and a stored record's vocabulary is not
#: an enum this process happens to hold. `test_situation_projection.py` asserts the four names
#: still match `ModifierName`, so drift fails a test instead of silently projecting nothing.
ANALYTIC_TERMS: tuple[tuple[str, str], ...] = (
    ("trend", TREND_PREFIX),
    ("cohort_position", COHORT_PREFIX),
    ("anomaly", ANOMALY_PREFIX),
)

#: The dependency modifier is a COUNT rather than a per-metric comparison, so it projects into one
#: named field instead of a namespace.
DEPENDENCY_TERM = "dependency"

#: `ModifierReason.NO_INPUT`'s stored spelling. This is the ONE reason that means nothing was
#: measured; every other non-firing reason means a comparison ran and did not qualify. Getting
#: this mapping backwards is exactly the UNKNOWABLE/GENUINELY_ABSENT confusion doc 05 names as the
#: worst output the quality group can emit.
NO_INPUT_REASON = "no_input"

#: How many entries a namespaced family may project. A situation carries a handful by
#: construction; the cap is a guard against an unbounded stored list reaching a content-addressed
#: snapshot, not an expected truncation — anything cut is counted in the receipt.
MAX_PER_FAMILY = 12

#: A projected name has to be a legal `EvidenceRef.field` (`contracts.reasoning._IDENTIFIER`) and
#: a legal mapping key. Metric names, cohort ids and conflict field names arrive from stored rows,
#: so they are CHECKED rather than trusted: an unprojectable name is counted in the receipt, never
#: coerced into something that looks like a different metric.
#:
#: ONE CHECK, ON THE ASSEMBLED NAME, and deliberately not a second one per segment. A per-segment
#: guard that is strictly narrower than this one can never let anything through that this one
#: would refuse, so it is a branch no input can reach — and an unreachable guard is a guard whose
#: removal no test can notice. Every site therefore checks only that its segment is non-empty and
#: lets `_Builder.present` / `_Builder.unknown_typed` own legality.
_FIELD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


def _no_floats(value: Any) -> Any:
    """The frozen contracts forbid floats — they are not replay-stable. Same conversion
    `context.situation_bso` applies on the way IN to the BSO, applied again here because a stored
    JSONB round trip can reintroduce one."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {str(k): _no_floats(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_no_floats(v) for v in value]
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _records(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _int(value: Any) -> int | None:
    """An integer, or None. `None` is the answer for anything that is not one — a stored column
    read as 0 is the fabricated-zero this whole module exists to refuse."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


# =================================================================================================
# THE PROJECTION
# =================================================================================================

@dataclass(frozen=True, slots=True)
class SituationProjection:
    """One situation's Layer 2 output, in the shape a `ContextSnapshot` carries.

    `facts` and `unknown_fields` are DISJOINT by construction and the constructor proves it: a
    name in both would be read as present by `reasoners.common.missing_fields` and as missing by
    `reason.guards.required_missing`, and the two answers would disagree about the same field on
    the same run.

    `unknowable_paths` and `absent_paths` are NOT snapshot fields — they are Layer 2's typed
    verdict about GRAPH fact paths, carried so a Layer 4 consumer can honour it. `expertise.py`
    uses `unknowable_paths` to keep `core.dependency` from reporting "go and find it" about a fact
    no connected source could ever have carried.
    """

    root_entity_id: str
    situation_id: str
    facts: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    evidence: tuple[EvidenceRef, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    unknowable_paths: tuple[str, ...] = ()
    absent_paths: tuple[str, ...] = ()
    receipt: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "facts", dict(sorted(self.facts.items())))
        setter(self, "evidence", tuple(sorted(self.evidence, key=lambda item: item.evidence_id)))
        setter(self, "unknown_fields", tuple(sorted(set(self.unknown_fields))))
        setter(self, "unknowable_paths", tuple(sorted(set(self.unknowable_paths))))
        setter(self, "absent_paths", tuple(sorted(set(self.absent_paths))))
        overlap = sorted(set(self.facts) & set(self.unknown_fields))
        if overlap:
            raise ValueError(
                f"projected fields {overlap} are both present and unknown — a field cannot be "
                "read as a value and as a gap on the same snapshot")
        for ref in self.evidence:
            if ref.field not in self.facts:
                raise ValueError(
                    f"projected evidence {ref.evidence_id} names {ref.field!r}, which this "
                    "projection does not carry as a fact")

    @property
    def declared_fields(self) -> tuple[str, ...]:
        """The projected facts a unit may DECLARE. Present ones only: the orchestrator refuses a
        unit when any declared field is missing, so declaring an unknown-typed name would drop the
        unit on exactly the situations this projection exists to describe."""
        return tuple(sorted(self.facts))

    @property
    def is_empty(self) -> bool:
        return not self.facts and not self.unknown_fields


def _fact(value: Any, *, kind: str, reading: str) -> dict[str, Any]:
    """One projected fact record.

    `value` is where `ContextSnapshot` looks when it re-proves an evidence ref against its fact,
    and where `reasoners.common.fact_value` looks when a unit reads one, so the payload goes there
    and the provenance goes beside it. `reading` is a sentence about what the presence of this
    fact MEANS — it is what stops a downstream reader inventing a direction this module did not
    project.
    """
    return {"value": _no_floats(value), "source": PROJECTION_SOURCE,
            "projection": PROJECTION_VERSION, "kind": kind, "reading": reading}


class _Builder:
    """Accumulates one projection. A class rather than a pile of closures because every `add`
    has to answer to the same three-state rule and the same receipt, and a helper that could be
    called without updating the receipt is a helper that eventually is."""

    def __init__(self, *, org_id: str, root_entity_id: str, situation_id: str) -> None:
        self.org_id = org_id
        self.root_entity_id = root_entity_id
        self.situation_id = situation_id
        self.facts: dict[str, dict[str, Any]] = {}
        self.evidence: list[EvidenceRef] = []
        self.unknown: dict[str, str] = {}
        self.refused: dict[str, int] = {}
        self.truncated: dict[str, int] = {}

    # ── the three states ─────────────────────────────────────────────────────────────────────
    def present(self, name: str, payload: Any, *, kind: str, reading: str,
                confidence_bp: int = 5_000) -> bool:
        """State 1: a reading exists. One fact, one evidence ref, minted by the one builder."""
        if not _FIELD_NAME.fullmatch(name):
            self.refused["unprojectable_field_name"] = (
                self.refused.get("unprojectable_field_name", 0) + 1)
            return False
        if name in self.facts or name in self.unknown:
            self.refused["duplicate_field"] = self.refused.get("duplicate_field", 0) + 1
            return False
        record = _fact(payload, kind=kind, reading=reading)
        self.facts[name] = record
        self.evidence.append(build_evidence_ref(
            org_id=self.org_id,
            entity_ref=self.root_entity_id,
            field=name,
            value=record["value"],
            source_ref=self.situation_id,
            # No clock. See the module docstring: a composed reading has no observation instant,
            # and the only candidate moves on every sweep and sits inside the evidence seed.
            observed_at=None,
            context_scope="root",
            confidence_bp=confidence_bp,
            authority_rank=2,
            independence_group=independence_group_for(self.situation_id),
        ))
        return True

    def unknown_typed(self, name: str, reason: str) -> bool:
        """State 2: nothing measured it. A NAME and a reason — never a value.

        The name reaches the snapshot as a `missing_field`, which is what makes it visible to
        `reason.guards.required_missing` (a declared field that Layer 2 published as missing stops
        reasoning rather than defaulting) and to `core.context`'s completeness denominator.
        """
        if not _FIELD_NAME.fullmatch(name):
            self.refused["unprojectable_field_name"] = (
                self.refused.get("unprojectable_field_name", 0) + 1)
            return False
        if name in self.facts:
            self.refused["unknown_after_present"] = (
                self.refused.get("unknown_after_present", 0) + 1)
            return False
        self.unknown[name] = reason
        return True

    def absence(self, path: str, absence_type: AbsenceType, *, reason: str) -> bool:
        """State 3: it was looked for and there is nothing. The ABSENCE TYPE is the value.

        The licence is read off `contracts.quality.NEGATIVE_INFERENCE_TYPES` rather than
        re-decided here: exactly one member licenses a negative inference, and a second opinion
        about which one is how `UNKNOWABLE` becomes `GENUINELY_ABSENT` on a card.
        """
        licensed = absence_type in NEGATIVE_INFERENCE_TYPES
        return self.present(
            f"{ABSENCE_PREFIX}{path}",
            {"fact": path, "absence": absence_type.value, "reason": reason,
             "licenses_negative_inference": licensed},
            kind="absence",
            reading=("a source could have carried this and none did — a finding" if licensed
                     else "no connected source could have carried this — infer nothing from it"))

    def cut(self, family: str, count: int) -> None:
        if count > 0:
            self.truncated[family] = self.truncated.get(family, 0) + count


def _project_analytic(builder: _Builder, components: Mapping[str, Any]) -> dict[str, Any]:
    """The analytic stratum, three-state, off the STORED importance composition.

    `metadata['importance_components']` carries all six modifier terms — fired or not, each with
    its reason and its receipt — strictly more than `metadata['trends' | 'cohort_positions' |
    'anomalies']` (fired only). Reading the components is therefore the only way to tell "no
    trend was ever computed" from "a trend was computed and is not declining", and those two are
    the UNKNOWABLE/GENUINELY_ABSENT pair this seam exists to keep apart.
    """
    terms = {str(term.get("name")): term for term in _records(components.get("modifiers"))}
    report: dict[str, Any] = {}
    for name, prefix in ANALYTIC_TERMS:
        term = terms.get(name)
        if term is None:
            # The composition itself is absent (a tenant whose sweep predates the composer). Not
            # "no trend" — nothing composed anything, so the honest answer is UNKNOWN.
            builder.unknown_typed(f"{prefix.rstrip('.')}", "importance_composition_absent")
            report[name] = {"state": "unknown", "reason": "importance_composition_absent"}
            continue
        reason = str(term.get("reason") or "")
        evidence = _mapping(term.get("evidence"))
        if not term.get("fired"):
            if reason == NO_INPUT_REASON:
                builder.unknown_typed(f"{prefix.rstrip('.')}", reason)
                report[name] = {"state": "unknown", "reason": reason}
            else:
                builder.absence(prefix.rstrip("."), AbsenceType.GENUINELY_ABSENT, reason=reason)
                report[name] = {"state": "absent", "reason": reason}
            continue
        metric = str(evidence.get("metric") or "").strip()
        if not metric:
            builder.refused["analytic_metric_unnamed"] = (
                builder.refused.get("analytic_metric_unnamed", 0) + 1)
            report[name] = {"state": "refused", "reason": "analytic_metric_unnamed"}
            continue
        # `present` owns name legality and counts its own refusal; the report reads its answer
        # rather than pre-judging it, so the two can never disagree about what was projected.
        if not builder.present(f"{prefix}{metric}", evidence, kind=name,
                               reading=_ANALYTIC_READING[name]):
            report[name] = {"state": "refused", "reason": "unprojectable_field_name"}
            continue
        report[name] = {"state": "present", "metric": metric, "reason": reason}
    return report


#: What the PRESENCE of each analytic fact means, stated on the fact itself. These sentences are
#: the qualification laws of `context.importance`'s modifiers, restated where a consumer reads
#: them; they are not new claims. See the module docstring on why a fired trend is a declining one.
_ANALYTIC_READING = {
    "trend": ("a DECLINING trend on this metric, above the trend-confidence floor, that the "
              "situation's importance leaned on"),
    "cohort_position": ("this subject sits at the worst extreme of a real population on this "
                        "metric"),
    "anomaly": "the detector flagged this subject against its own baseline on this metric",
}


def _project_confidence(builder: _Builder, situation: BusinessSituationObject) -> dict[str, Any]:
    """The six axes, one fact each. **Never collapsed to a scalar** — doc 09's must-not-regress
    row 3, honoured at the seam that would have collapsed it.

    An axis at `AXIS_UNKNOWN_BP` is UNKNOWN and projects as a name, not as a number. That sentinel
    means either "this sweep predates the axis" or "the axis ran and had nothing to measure"; both
    are "we do not know", and a 0 would rank an unassessed situation below every assessed one.
    """
    vector = SituationConfidenceVector.from_record(
        _mapping(situation.metadata.get("confidence_vector")))
    report: dict[str, str] = {}
    for axis in CONFIDENCE_AXES:
        value = getattr(vector, axis)
        if value == AXIS_UNKNOWN_BP:
            builder.unknown_typed(f"{CONFIDENCE_PREFIX}{axis}", "axis_not_assessed")
            report[axis] = "unknown"
            continue
        builder.present(f"{CONFIDENCE_PREFIX}{axis}", {"value_bp": int(value), "axis": axis},
                        kind="confidence_axis",
                        reading=f"Layer 2's {axis} confidence axis, in basis points",
                        confidence_bp=int(value))
        report[axis] = "present"
    return report


def _project_absences(builder: _Builder, context: SituationContextSlice | None
                      ) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    """L2.5.5's stored absences, as typed facts, from the slice that carries them.

    Both keys are read through `context.quality.inference`'s constants rather than by literal, so
    the producer (`build_context_slice`) and this consumer cannot disagree by typo — which is the
    stated reason that module names them once.
    """
    metadata = _mapping(context.metadata) if context is not None else {}
    unknowable = tuple(sorted({str(item) for item in (metadata.get(UNKNOWABLE_FIELDS_KEY) or ())}))
    absent = tuple(sorted({str(item) for item in (metadata.get(ABSENT_FIELDS_KEY) or ())}))
    both = sorted(set(unknowable) & set(absent))
    for path in unknowable[:MAX_PER_FAMILY]:
        builder.absence(path, AbsenceType.UNKNOWABLE, reason="no_connected_source")
    builder.cut("unknowable", max(0, len(unknowable) - MAX_PER_FAMILY))
    for path in absent[:MAX_PER_FAMILY]:
        # A path Layer 2 typed BOTH ways is a contradiction in the STORED ROWS, and it resolves to
        # the conservative reading: the UNKNOWABLE record written above stands, and no negative
        # inference is licensed on a path we may not be able to see at all.
        #
        # SKIPPED HERE rather than left to `present`'s duplicate guard, which would also leave the
        # right record standing. The guard exists to catch a PROJECTION BUG — two writers reaching
        # for one name — and letting a known contradiction in the input trip it would put a
        # `duplicate_field` refusal in the receipt that describes this module rather than the data.
        # The contradiction is reported where it belongs, as `typed_both_ways`.
        if path in both:
            continue
        builder.absence(path, AbsenceType.GENUINELY_ABSENT, reason="coverage_epoch_stands")
    builder.cut("genuinely_absent", max(0, len(absent) - MAX_PER_FAMILY))
    licence = metadata.get(OBSERVATION_LICENCE_KEY)
    report: dict[str, Any] = {
        "unknowable_count": len(unknowable),
        "genuinely_absent_count": len(absent),
        "typed_both_ways": both,
        # Tri-state in, tri-state out: an unassessed domain is None, not False.
        "observation_absence_licensed": (None if licence is None else bool(licence)),
    }
    return unknowable, absent, report


def _project_conflicts(builder: _Builder, situation: BusinessSituationObject) -> dict[str, Any]:
    """The disagreements Layer 1 resolved, keyed by the field that was contested.

    A situation resting on a contested claim must not reach a reasoning unit looking settled. The
    resolved VALUE is deliberately not projected — `gather_conflicts` already refuses to copy the
    losing side's prose into a content-addressed artifact, and this seam does not reopen it.
    """
    conflicts = _records(situation.metadata.get("conflicts"))
    projected = 0
    for record in conflicts[:MAX_PER_FAMILY]:
        name = str(record.get("field") or "").strip()
        if not name:
            builder.refused["conflict_field_unnamed"] = (
                builder.refused.get("conflict_field_unnamed", 0) + 1)
            continue
        if builder.present(
                f"{CONFLICT_PREFIX}{name}",
                {"field": name, "resolution": str(record.get("resolution") or "unresolved"),
                 "claim_count": _int(record.get("claim_count")) or 0,
                 "conflict_id": str(record.get("conflict_id") or "")},
                kind="conflict",
                reading="independent sources disagreed about this field; Layer 1 resolved it"):
            projected += 1
    builder.cut("conflict", max(0, len(conflicts) - MAX_PER_FAMILY))
    return {"count": len(conflicts), "projected": projected}


def _project_pattern(builder: _Builder, situation: BusinessSituationObject) -> dict[str, Any]:
    """L2.6's fire. `pattern_id` is None with no fire, and that projects as UNKNOWN rather than as
    a fact whose value is null — the same rule as everywhere else in this module."""
    metadata = situation.metadata
    pattern_id = metadata.get("pattern_id")
    if not pattern_id:
        builder.unknown_typed(PATTERN_FIELD, "no_pattern_fire")
        builder.unknown_typed(MATCHED_CONDITIONS_FIELD, "no_pattern_fire")
        return {"state": "unknown", "reason": "no_pattern_fire"}
    strength = _int(metadata.get("pattern_match_strength_bp"))
    builder.present(
        PATTERN_FIELD,
        {"pattern_id": str(pattern_id),
         "pattern_version": (str(metadata["pattern_version"])
                             if metadata.get("pattern_version") else None),
         "activated": bool(metadata.get("pattern_activated")),
         "match_strength_bp": strength},
        kind="pattern",
        reading=("a declared pattern matched this anchor; `activated` says whether the tenant let "
                 "it name the situation"),
        confidence_bp=(strength if strength is not None and 0 <= strength <= 10_000 else 5_000))
    conditions = _records(metadata.get("matched_conditions"))
    if conditions:
        builder.present(MATCHED_CONDITIONS_FIELD, [dict(item) for item in conditions],
                        kind="pattern_conditions",
                        reading="the per-condition receipt behind the pattern match")
    else:
        builder.unknown_typed(MATCHED_CONDITIONS_FIELD, "fire_carries_no_condition_receipt")
    return {"state": "present", "pattern_id": str(pattern_id),
            "activated": bool(metadata.get("pattern_activated")),
            "matched_conditions": len(conditions)}


def _project_importance(builder: _Builder, situation: BusinessSituationObject,
                        components: Mapping[str, Any]) -> dict[str, Any]:
    """The composed number, with the two things that make it readable: where the base came from,
    and whether the fallback fired. `importance_fallback=True` means this is a documented midpoint
    and not a measurement, and a consumer that cannot see that will rank a blind spot as an
    average situation."""
    fallback = bool(situation.metadata.get("importance_fallback"))
    builder.present(
        IMPORTANCE_FIELD,
        {"value_bp": int(situation.importance_bp),
         "source": str(situation.metadata.get("importance_source") or "unknown"),
         "version": (str(situation.metadata["importance_version"])
                     if situation.metadata.get("importance_version") else None),
         "fallback": fallback,
         "base_bp": _int(components.get("base_bp")),
         "modifier_total_bp": _int(components.get("modifier_total_bp")),
         "coverage_penalty_bp": _int(components.get("coverage_penalty_bp"))},
        kind="importance",
        reading=("Layer 2's composed importance for this situation; `fallback` says whether the "
                 "number is a measurement or the documented midpoint"),
        confidence_bp=int(situation.confidence_bp))
    return {"importance_bp": int(situation.importance_bp), "fallback": fallback}


def _project_dependency(builder: _Builder, components: Mapping[str, Any]) -> dict[str, Any]:
    """How many items wait on this situation, from the dependency modifier's own receipt."""
    terms = {str(term.get("name")): term for term in _records(components.get("modifiers"))}
    term = terms.get(DEPENDENCY_TERM)
    if term is None:
        builder.unknown_typed(DEPENDENCY_FIELD, "importance_composition_absent")
        return {"state": "unknown", "reason": "importance_composition_absent"}
    reason = str(term.get("reason") or "")
    if not term.get("fired"):
        if reason == NO_INPUT_REASON:
            builder.unknown_typed(DEPENDENCY_FIELD, reason)
            return {"state": "unknown", "reason": reason}
        builder.absence(DEPENDENCY_FIELD[len(SITUATION_NAMESPACE):],
                        AbsenceType.GENUINELY_ABSENT, reason=reason)
        return {"state": "absent", "reason": reason}
    evidence = _mapping(term.get("evidence"))
    count = _int(evidence.get("blocked_count"))
    if count is None:
        builder.unknown_typed(DEPENDENCY_FIELD, "blocked_count_unreadable")
        return {"state": "unknown", "reason": "blocked_count_unreadable"}
    builder.present(DEPENDENCY_FIELD, {"blocked_count": count}, kind="dependency",
                    reading="how many items Layer 2 measured as blocked on this situation")
    return {"state": "present", "blocked_count": count}


def _project_lifecycle(builder: _Builder, situation: BusinessSituationObject) -> dict[str, Any]:
    """X6/M-4: the state verbatim, who closed it, and whether the closure was total.

    A partially-resolved situation read as fully open is a nag about work that is mostly done;
    read as fully closed it is work silently dropped. Both halves travel or neither does.
    """
    resolved_by = situation.metadata.get("resolved_by")
    payload = {
        "state": str(situation.state),
        "partially_resolved": bool(situation.metadata.get("partially_resolved")),
        "resolved_by": (str(resolved_by) if resolved_by else None),
    }
    builder.present(LIFECYCLE_FIELD, payload, kind="lifecycle",
                    reading="the situation's M-4 lifecycle state and who closed it")
    return dict(payload)


def _project_spans(builder: _Builder, situation: BusinessSituationObject) -> dict[str, Any]:
    """The evidence measurement — how many spans exist, and how many were VERIFIED against their
    source text. A BSO carrying none says so rather than reading as unmeasured."""
    spans = _int(situation.metadata.get("evidence_spans"))
    verified = _int(situation.metadata.get("evidence_verified_spans"))
    if spans is None or verified is None:
        builder.unknown_typed(EVIDENCE_SPANS_FIELD, "span_counts_absent")
        return {"state": "unknown", "reason": "span_counts_absent"}
    builder.present(EVIDENCE_SPANS_FIELD, {"spans": spans, "verified_spans": verified},
                    kind="evidence_spans",
                    reading="how many of this situation's evidence spans resolve in their source")
    return {"state": "present", "spans": spans, "verified_spans": verified}


def project_situation(*, situation: BusinessSituationObject,
                      context: SituationContextSlice | None,
                      root_entity_id: str) -> SituationProjection:
    """Doc 06 IN-1 · one BSO becomes the situation half of a `ContextSnapshot`.

    `root_entity_id` is passed rather than read off the slice because the evidence seed has to
    name the SAME entity the snapshot names: `canonical_evidence_id_for` reconstructs a stored
    ref's id from the snapshot's root, and a projection that seeded from the situation id instead
    would produce ids the backfill cannot reproduce. `native_context_snapshot` refuses a
    projection whose root does not match, so the two cannot drift.

    `context` is optional and its absence is honest rather than silent: with no slice there are no
    stored absences to type, the receipt says `slice_supplied: false`, and nothing is projected as
    "no absence" — which would be a claim, not a default.
    """
    builder = _Builder(org_id=situation.org_id, root_entity_id=str(root_entity_id),
                       situation_id=situation.id)
    components = _mapping(situation.metadata.get("importance_components"))
    report = {
        "schema": PROJECTION_VERSION,
        "situation_id": situation.id,
        "situation_type": situation.type,
        "slice_supplied": context is not None,
        "importance": _project_importance(builder, situation, components),
        "analytic": _project_analytic(builder, components),
        "dependency": _project_dependency(builder, components),
        "confidence": _project_confidence(builder, situation),
        "conflicts": _project_conflicts(builder, situation),
        "pattern": _project_pattern(builder, situation),
        "lifecycle": _project_lifecycle(builder, situation),
        "evidence_spans": _project_spans(builder, situation),
    }
    unknowable, absent, absence_report = _project_absences(builder, context)
    report["typed_absence"] = absence_report
    report["projected_field_count"] = len(builder.facts)
    report["unknown_field_count"] = len(builder.unknown)
    report["unknown_fields"] = dict(sorted(builder.unknown.items()))
    report["refused"] = dict(sorted(builder.refused.items()))
    report["truncated"] = dict(sorted(builder.truncated.items()))
    report["independence_group"] = independence_group_for(situation.id)
    return SituationProjection(
        root_entity_id=str(root_entity_id),
        situation_id=situation.id,
        facts=builder.facts,
        evidence=tuple(builder.evidence),
        unknown_fields=tuple(builder.unknown),
        unknowable_paths=unknowable,
        absent_paths=absent,
        receipt=report,
    )


__all__ = [
    "ABSENCE_PREFIX",
    "ANALYTIC_TERMS",
    "ANOMALY_PREFIX",
    "COHORT_PREFIX",
    "CONFIDENCE_PREFIX",
    "CONFLICT_PREFIX",
    "DEPENDENCY_FIELD",
    "DEPENDENCY_TERM",
    "EVIDENCE_SPANS_FIELD",
    "IMPORTANCE_FIELD",
    "LIFECYCLE_FIELD",
    "MATCHED_CONDITIONS_FIELD",
    "MAX_PER_FAMILY",
    "NO_INPUT_REASON",
    "PATTERN_FIELD",
    "PROJECTION_SOURCE",
    "PROJECTION_VERSION",
    "SITUATION_NAMESPACE",
    "TREND_PREFIX",
    "SituationProjection",
    "independence_group_for",
    "project_situation",
]
