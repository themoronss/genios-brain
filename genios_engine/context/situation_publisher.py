"""The single Layer 2 publication door: legacy assembly -> strict BSO -> admission receipt.

The graph has several situation producers, but Layer 3 must have one entrance.  Every candidate
reaching this module receives one of three explicit outcomes:

* ADMIT carries the strict ``business-situation.v2`` object;
* HOLD preserves RECOVERABLE incompleteness (no verified span, unresolved identity, an open
  conflict, insufficient coverage, a receipt-less activated pattern, or a missing Layer 1 score on
  a tenant whose Layer 1 IS scoring) and may be retried after the next graph/coverage sweep.
  "Recoverable" is load-bearing: an absence no future sweep can repair is not held — see
  ``decide_publication`` and its ``l1_scoring_active`` argument;
* REJECT preserves a malformed/unsafe candidate and never exposes an object to the caller.

The caller cannot publish by reaching through a non-admitted result because ``situation`` is None
for HOLD and REJECT.  Storage is append-only by decision id and the latest candidate decision is
also queryable by ``(org_id, situation_id, candidate_hash)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from sqlalchemy import text

from genios_engine.contracts.domain_expertise import BusinessSituationObject as LegacySituation
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.quality import MissingFact
from genios_engine.contracts.situation import (
    BusinessSituationObject,
    ConfidenceVector,
    ImportanceAttribution,
    ImportanceBasis,
    SituationEntity,
    SituationRelationship,
    TimelinePoint,
    validate_situation,
)
from genios_engine.contracts.visibility import Visibility
from genios_engine.platform.canonical import canonical_dumps, semantic_hash, stable_id


class PublicationOutcome(str, Enum):
    ADMIT = "admit"
    HOLD = "hold"
    REJECT = "reject"


class HoldReason(str, Enum):
    QES_REQUIRED = "qes_required"
    VERIFIED_EVIDENCE_REQUIRED = "verified_evidence_required"
    IDENTITY_REVIEW_REQUIRED = "identity_review_required"
    PATTERN_EVIDENCE_REQUIRED = "pattern_evidence_required"
    SOURCE_COVERAGE_INSUFFICIENT = "source_coverage_insufficient"
    CONFLICT_OPEN = "conflict_open"
    #: TWO DOMAINS CLAIMING OPPOSITE THINGS ABOUT ONE SUBJECT. `CONFLICT_OPEN` above is the same
    #: shape one layer down — Layer 1 preserving two incompatible FACTS — and its comment already
    #: states the principle this extends: publishing a candidate as settled while the disagreement
    #: stands would erase it by omission. Measured on the pilot: three counterparties carried
    #: `admin:awaiting_response` (they owe us a reply) and `support:first_response_overdue` (we
    #: never answered them) at the same time. Both cards would have gone out.
    CROSS_DOMAIN_CONTRADICTION = "cross_domain_contradiction"


@dataclass(frozen=True, slots=True)
class PublicationResult:
    outcome: PublicationOutcome
    decision_id: str
    situation_id: str
    reasons: tuple[str, ...] = ()
    situation: BusinessSituationObject | None = None

    @property
    def admitted(self) -> bool:
        return self.outcome is PublicationOutcome.ADMIT


def _receipt(item: Mapping[str, Any]) -> EvidenceSpan | None:
    if not item.get("quote"):
        return None
    try:
        return EvidenceSpan.model_validate(dict(item))
    except (TypeError, ValueError):
        return None


def _receipts(old: LegacySituation) -> tuple[EvidenceSpan, ...]:
    unique: dict[EvidenceSpan, None] = {}
    for item in old.evidence:
        receipt = _receipt(item)
        if receipt is not None:
            unique.setdefault(receipt, None)
    return tuple(unique)


def _provenance(old: LegacySituation) -> tuple[str, ...]:
    refs: set[str] = set()
    for item in old.evidence:
        for key in ("event_id", "source_object_id", "signal_id", "source_ref"):
            if item.get(key):
                refs.add(str(item[key]))
    return tuple(sorted(refs))


def _importance(old: LegacySituation) -> ImportanceAttribution:
    meta = dict(old.metadata)
    record = dict(meta.get("importance_components") or {})
    numbers = {str(key): value for key, value in record.items()
               if isinstance(value, int) and not isinstance(value, bool)}
    inputs = {str(key): value for key, value in record.items() if key not in numbers}
    source = str(meta.get("importance_source") or "default")
    if source != "l1_qualified_signals":
        return ImportanceAttribution(basis=ImportanceBasis.UNSCORED, score_bp=0, base_bp=None,
                                     version="unscored", components={}, inputs={})
    version = str(meta.get("importance_version") or "unscored")
    base = numbers.get("base_bp", old.importance_bp)
    composed = version.startswith("blg18") or old.importance_bp != base
    if not numbers:
        numbers = {"inherited_bp": old.importance_bp}
    return ImportanceAttribution(
        basis=ImportanceBasis.COMPOSED if composed else ImportanceBasis.INHERITED,
        score_bp=old.importance_bp, base_bp=base, version=version,
        components=numbers, inputs=inputs)


def _confidence(old: LegacySituation) -> ConfidenceVector:
    raw = dict(old.metadata.get("confidence_vector") or {})

    def axis(name: str) -> int | None:
        value = raw.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    axes = {name: axis(name) for name in (
        "evidence", "freshness", "consistency", "identity", "coverage", "analytic")}
    measured = tuple(sorted(name for name, value in axes.items() if value is not None))
    if not measured:
        axes["evidence"] = old.confidence_bp
        measured = ("evidence",)
    overall = min(old.confidence_bp, *(axes[name] for name in measured if axes[name] is not None))
    return ConfidenceVector(
        evidence_bp=axes["evidence"], freshness_bp=axes["freshness"],
        consistency_bp=axes["consistency"], identity_bp=axes["identity"],
        coverage_bp=axes["coverage"], analytic_bp=axes["analytic"],
        overall_bp=overall, composed_from=measured)


def _timeline(old: LegacySituation) -> tuple[TimelinePoint, ...]:
    points: list[TimelinePoint] = []
    for record in old.timeline:
        for key, label in (("first_seen_at", "first_seen"), ("last_seen_at", "last_seen")):
            value = record.get(key)
            if value:
                moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
                points.append(TimelinePoint(at=moment, label=label))
    return tuple(sorted(points, key=lambda point: (point.at, point.label)))


def upgrade_situation(
    old: LegacySituation,
    *,
    missing_facts: tuple[MissingFact, ...] = (),
) -> BusinessSituationObject:
    """Losslessly move the live v1 assembly onto typed v2 homes.

    Analytic summaries remain in metadata until their full series receipts are available at this
    seam; promoting a four-field summary into a ``Trend`` that requires its evidence series would
    fabricate the missing points.  The admission gate is stricter than the old object where it
    matters: QES ids and real EvidenceSpan receipts are mandatory before this function is called.
    """
    meta = dict(old.metadata)
    coverage = meta.get("coverage_ready")
    if coverage is not None:
        coverage = bool(coverage)
    return BusinessSituationObject(
        org_id=old.org_id, trace_id=old.trace_id,
        visibility=(old.visibility if isinstance(old.visibility, Visibility)
                    else Visibility.model_validate(dict(old.visibility))),
        id=old.id, type=old.type, state=old.state,
        domain_ids=tuple(meta.get("domain_ids") or ()), signal_ids=old.signal_ids,
        entities=tuple(SituationEntity.model_validate(dict(value)) for value in old.entities),
        relationships=tuple(SituationRelationship.model_validate(dict(value))
                            for value in old.relationships),
        timeline=_timeline(old), dependencies=(), evidence=_receipts(old),
        provenance_refs=_provenance(old), confidence=_confidence(old),
        coverage_ready=coverage, conflict_ids=tuple(meta.get("conflict_ids") or ()),
        missing_facts=missing_facts,
        importance=_importance(old),
        # Keep the current metadata projection during the consumer migration.  These are
        # compatibility views of typed fields, not authority for constructing them.
        metadata=meta)


def _candidate_payload(
    old: LegacySituation,
    missing_facts: tuple[MissingFact, ...] = (),
) -> dict[str, Any]:
    payload = dict(old.to_semantic_dict())
    payload["missing_facts"] = [fact.model_dump(mode="json") for fact in missing_facts]
    # NOT canonicalized here. The only caller hands this straight to `semantic_hash`, which
    # canonicalizes — so canonicalizing first ran the encoder TWICE, and the second pass refuses
    # its own output: a `Decimal` (every Postgres `numeric` column reads back as one) became
    # `{"$decimal": …}` on the first pass and raised
    # `CanonicalizationError: semantic mapping key '$decimal' is reserved` on the second. That
    # aborted `publish_situation`, which `reason/domain_shadow.shadow_compile` catches per
    # situation — so a tenant whose situation carried one numeric fact silently published nothing
    # and the compiled lane reasoned about nothing. It surfaced as an ORDER-DEPENDENT suite:
    # four full runs on virgin databases returned 0, 26, 32 and 40 failures, because whether a
    # Decimal reached a payload depended on which rows an earlier test had left behind.
    #
    # No stored hash moves. `canonicalize` is idempotent on every payload that did not raise, so
    # `semantic_hash(canonicalize(x))` and `semantic_hash(x)` agree on exactly the inputs that
    # used to get this far.
    return payload


def _decision_id(old: LegacySituation, candidate_hash: str) -> str:
    return stable_id("l2adm", {"org_id": old.org_id, "situation_id": old.id,
                               "candidate_hash": candidate_hash})


def _preflight(old: LegacySituation, *, l1_scoring_active: bool) -> tuple[str, ...]:
    """The hold reasons this candidate earns.  ``l1_scoring_active`` conditions exactly one.

    See ``decide_publication`` for the whole argument.  In one line: a scored Layer 1 that skipped
    THIS situation is a retryable gap and holds; a tenant whose Layer 1 has never scored anything
    is a structural absence that no retry repairs, and holding it is a silent outage.
    """
    meta = old.metadata
    reasons: list[str] = []
    if l1_scoring_active and str(meta.get("importance_source") or "") != "l1_qualified_signals":
        reasons.append(HoldReason.QES_REQUIRED.value)
    if int(meta.get("evidence_verified_spans") or 0) < 1 or not _receipts(old):
        reasons.append(HoldReason.VERIFIED_EVIDENCE_REQUIRED.value)
    if bool(meta.get("split_required")):
        reasons.append(HoldReason.IDENTITY_REVIEW_REQUIRED.value)
    if bool(meta.get("requires_complete_coverage")) and meta.get("coverage_ready") is not True:
        reasons.append(HoldReason.SOURCE_COVERAGE_INSUFFICIENT.value)
    if meta.get("contradicted_by"):
        # THE LOSING SIDE OF A DECLARED IMPOSSIBILITY, or either side of one nothing settles.
        # `context/correlation_domain.py` finds these and refuses to delete anything; the decision
        # of what to do belongs here, and it is the same decision `CONFLICT_OPEN` makes: hold, so
        # the claim does not travel while a contradiction about it stands.
        #
        # HOLD AND NOT REJECT, deliberately. This is recoverable in the ordinary way — the arbiter
        # fact moves, or the losing situation resolves itself on the next sweep, and the retry
        # `reevaluate_after` promises is one a sweep genuinely keeps. That is the test the
        # docstring below sets for the difference between the two outcomes.
        reasons.append(HoldReason.CROSS_DOMAIN_CONTRADICTION.value)
    if meta.get("conflict_ids"):
        # A pointer means Layer 1 deliberately preserved two incompatible claims.  Until this
        # seam can attach both typed Conflict sides, publishing the candidate as settled would
        # erase the disagreement by omission.
        reasons.append(HoldReason.CONFLICT_OPEN.value)
    if bool(meta.get("pattern_activated")) and meta.get("pattern_id"):
        # Current pattern receipts are graph fact pointers, not EvidenceSpan quotes.  Do not
        # claim the strict pattern field until the matcher carries the real spans.
        reasons.append(HoldReason.PATTERN_EVIDENCE_REQUIRED.value)
    return tuple(sorted(set(reasons)))


def decide_publication(
    old: LegacySituation,
    *,
    missing_facts: tuple[MissingFact, ...] = (),
    l1_scoring_active: bool = True,
) -> PublicationResult:
    """Decide this candidate.  ``l1_scoring_active`` is the ONE conditional half of the gate.

    THE DESIGN QUESTION, ANSWERED.  L2.5.8 shipped this gate fail-closed and UNCONDITIONAL, so a
    tenant whose Layer 1 has never published a scored signal had every situation held and
    therefore lost its entire L3 and L4 lane.  That is wrong, and not because it made tests red.
    Four reasons, each one a fact about this repository rather than a preference:

    1. IT CONTRADICTS THIS MODULE'S OWN DEFINITION OF HOLD.  The docstring at the top says HOLD
       "preserves recoverable incompleteness ... and may be retried after the next graph/coverage
       sweep", and migration 0122 enforces that by requiring ``reevaluate_after`` on every held
       row.  For a tenant whose scorer is not live, no sweep will ever produce a qualified signal:
       the retry is a promise nothing keeps.  A permanent hold is a REJECT wearing HOLD's name,
       and it is applied tenant-wide rather than to a candidate.

    2. THE SPEC FOR THIS UNIT DOES NOT ASK FOR IT.  L2.5.8 ("Context Validation") specifies "a
       deterministic floor check against the CONFIDENCE VECTOR ... below the floor the situation is
       held".  The confidence floor is a statement about how well this situation is known.  A
       missing L1 SCORE is not a confidence axis; it is an activation state, and it arrived here
       as an extra.

    3. LAYER 4 IS ALREADY SPECIFIED, AND ALREADY BUILT, TO HANDLE IT.  Doc 04's honesty guard:
       "if L2 has not activated importance for this org, the component is ABSENT, NOT DEFAULTED
       ... reweigh the remaining five to 10000, record reason code L2_IMPORTANCE_NOT_ACTIVE."
       ``reason/decision_maker.IMPORTANCE_ABSENT_REASON`` is that code and it exists.  An
       unconditional gate here makes the specified behaviour unreachable in production, and turns
       a guard that was written to be exercised into code no tenant can ever reach.

    4. LAYER 2 ALREADY DECIDED THIS QUESTION THE OTHER WAY, ONE MODULE OVER.
       ``context/importance.assess_l1_supply``: "An EMPTY supply is unknown, not flat.  A tenant
       with no scored signals at all has published no evidence that the scorer is broken, and
       suppressing the modifiers there would leave a pre-L1-v2 tenant with no ranking whatsoever
       while the L2 facts that could rank it are sitting in the graph."  The same tenant, the same
       absence, the same layer — the two gates may not answer it differently.

    So the gate is right in KIND and was wrong in SCOPE.  What it must never do is let a claim
    travel without a receipt, and that half is UNCONDITIONAL and untouched: no verified evidence
    span, an open conflict, an unresolved identity, insufficient coverage and a receipt-less
    activated pattern all still hold, on every tenant, whatever Layer 1 did.  Nothing here lowers a
    floor; the unscored candidate is admitted CARRYING ITS ABSENCE — ``_importance`` types it
    ``ImportanceBasis.UNSCORED`` with ``score_bp=0``, ``base_bp=None`` and no components, which the
    contract pins and which every consumer must read as absent rather than as zero.

    ``l1_scoring_active`` DEFAULTS TO TRUE, i.e. to the strict behaviour, so a caller that has not
    measured its tenant's Layer 1 supply keeps the fail-closed gate.  The only caller that passes
    False is one that read the whole tenant's supply for the sweep and found no scored signal in
    it — the same predicate ``situation_bso.refresh_situation_importance`` feeds to
    ``assess_l1_supply``.
    """
    payload = _candidate_payload(old, missing_facts)
    candidate_hash = semantic_hash(payload)
    decision_id = _decision_id(old, candidate_hash)
    holds = _preflight(old, l1_scoring_active=l1_scoring_active)
    if holds:
        return PublicationResult(PublicationOutcome.HOLD, decision_id, old.id, holds)
    try:
        upgraded = upgrade_situation(old, missing_facts=missing_facts)
        decision = validate_situation(upgraded)
    except (TypeError, ValueError) as exc:
        return PublicationResult(PublicationOutcome.REJECT, decision_id, old.id,
                                 (f"contract_invalid:{str(exc)[:240]}",))
    if not decision.admitted:
        reasons = tuple(f"{failure.law.value}:{failure.subject}" for failure in decision.failures)
        return PublicationResult(PublicationOutcome.REJECT, decision_id, old.id, reasons)
    return PublicationResult(PublicationOutcome.ADMIT, decision_id, old.id,
                             situation=upgraded)


def _record(
    engine,
    old: LegacySituation,
    result: PublicationResult,
    *,
    missing_facts: tuple[MissingFact, ...],
    decided_at: datetime,
) -> None:
    if decided_at.tzinfo is None or decided_at.utcoffset() is None:
        raise ValueError("decided_at must be timezone-aware")
    payload = _candidate_payload(old, missing_facts)
    candidate_hash = semantic_hash(payload)
    with engine.begin() as conn:
        conn.execute(text(
            "insert into situation_admission_decisions "
            "(decision_id, org_id, situation_id, candidate_hash, outcome, reasons, "
            " candidate, schema_version, decided_at, reevaluate_after) "
            "values (:id,:o,:sid,:hash,:outcome,cast(:reasons as jsonb),cast(:candidate as jsonb),"
            "        :schema,:at,:retry) "
            "on conflict (decision_id) do update set outcome=excluded.outcome, "
            "reasons=excluded.reasons, decided_at=excluded.decided_at, "
            "reevaluate_after=excluded.reevaluate_after"), {
                "id": result.decision_id, "o": old.org_id, "sid": old.id,
                "hash": candidate_hash, "outcome": result.outcome.value,
                "reasons": json.dumps(list(result.reasons), sort_keys=True),
                # `canonical_dumps`, NOT `json.dumps` — the column must hold the exact
                # representation `candidate_hash` was taken over, and it is the only encoder that
                # can serialise this payload at all. `semantic_hash` one line up canonicalizes
                # internally; the raw payload it was handed still carries whatever the situation
                # carried — a `mappingproxy` (every frozen contract view reads back as one), a
                # `Decimal` (every Postgres `numeric`), a `datetime`. `json.dumps` refuses all
                # three with a TypeError, which aborted `publish_situation`, which
                # `reason/domain_shadow.shadow_compile` catches PER SITUATION — so the tenant
                # published nothing, the compiled lane reasoned about nothing, and the sweep
                # reported a clean `situations: 1` with `reasoned: 0`. Nothing silent about it
                # now: the stored candidate and its hash are the same bytes, so the receipt can
                # be verified against the row rather than trusted.
                "candidate": canonical_dumps(payload),
                "schema": (result.situation.schema_version if result.situation else
                           "business-situation.v2"), "at": decided_at,
                "retry": decided_at if result.outcome is PublicationOutcome.HOLD else None,
            })


def publish_situation(
    engine,
    old: LegacySituation,
    *,
    decided_at: datetime,
    missing_facts: tuple[MissingFact, ...] = (),
    record: bool = True,
    l1_scoring_active: bool = True,
) -> PublicationResult:
    """Decide, optionally persist the receipt, and expose only an admitted strict object."""
    result = decide_publication(old, missing_facts=missing_facts,
                                l1_scoring_active=l1_scoring_active)
    if record:
        _record(engine, old, result, missing_facts=missing_facts, decided_at=decided_at)
    return result


__all__ = ["HoldReason", "PublicationOutcome", "PublicationResult", "decide_publication",
           "publish_situation", "upgrade_situation"]
