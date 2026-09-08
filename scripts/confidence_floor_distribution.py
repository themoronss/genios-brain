"""Measure the confidence floor and Rule 11 on a seeded population, instead of asserting them.

A floor nothing trips and a floor everything trips are both wrong, and only the numbers say which
one was built. So this seeds a population of runs through the REAL units and the REAL
`DecisionMaker` and reports four things:

1. the distribution of `core.confidence`'s own output on the compiled lane — the number the floor
   is applied to, produced by the unit that produces it in production rather than by a constant
   this script invented;
2. what fraction of those decisions fall below the lane floor and become reason-coded DEFERs;
3. the same population under the pre-wave LAST-WRITER SCAN versus under Rule 11 composition, on
   multi-publisher runs — the shape the legacy lane has;
4. how many of those last-writer outcomes were uncited raises, i.e. how often the old scan
   published a confidence nobody could point at.

Deterministic: a fixed grid, no clock, no database, no network. Run it and read the table.

    python scripts/confidence_floor_distribution.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.contracts.reasoning import (            # noqa: E402
    CapabilityManifest,
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.decision_maker import (          # noqa: E402
    BELOW_FLOOR_REASON,
    CONFIDENCE_AUTHORITY,
    ConfidenceViolation,
    DecisionMaker,
    compose_confidence,
    resolve_confidence_floor,
)
from genios_engine.reason.reasoners.confidence import ConfidenceReasoner  # noqa: E402

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
COMPILED_LANE = "expertise_to_capability"
FIELDS = tuple(f"deal.field_{index}" for index in range(6))


def _manifest(required: tuple[str, ...]) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="expertise.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1.0.0"),),
        plays=(PlayDefinition(play_id="restore_momentum", version="1", label="Restore",
                              steps=("Prepare a grounded draft",), impact_bp=6_000,
                              success_probability_bp=6_000, effort_bp=2_000, risk_bp=1_000),),
        required_fields=required, policies=(),
        metadata={"adapter": COMPILED_LANE})


def _request(*, present: int, fact_confidence_bp: int, src_count: int, groups: int
             ) -> ReasoningRequest:
    facts = {field: {"value": "open", "confidence_bp": fact_confidence_bp,
                     "src_count": src_count}
             for field in FIELDS[:present]}
    evidence = tuple(
        EvidenceRef(evidence_id=f"ev_{index}", field=FIELDS[index % max(present, 1)],
                    value="open", confidence_bp=fact_confidence_bp,
                    independence_group=f"origin_{index}")
        for index in range(groups)) if present else ()
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="selector.v1", facts=facts, evidence=evidence,
        missing_fields=tuple(FIELDS[present:]))
    return ReasoningRequest(org_id="org_1", capability=_manifest(FIELDS), context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


def _percentiles(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)

    def at(fraction: float) -> int:
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]
    return {"min": ordered[0], "p10": at(0.10), "p50": at(0.50), "p90": at(0.90),
            "max": ordered[-1]}


def _last_writer_scan(results, request) -> int:
    """The PRE-WAVE behaviour, kept here and nowhere else: whatever the last unit to speak said.

    Reproduced verbatim so the two columns of the table below are the same population under two
    rules rather than two populations.
    """
    authority = CONFIDENCE_AUTHORITY
    value = 5_000
    for result in results:
        if result.status == ResultStatus.COMPLETED and "confidence_bp" in result.metrics:
            value = int(result.metrics["confidence_bp"])
        if result.reasoner_id == authority and result.status == ResultStatus.COMPLETED:
            break
    return value


def compiled_lane_population() -> None:
    unit = ConfidenceReasoner()
    maker = DecisionMaker()
    confidences: list[int] = []
    deferred = 0
    named_resolvers = 0
    for present in range(0, len(FIELDS) + 1):
        for fact_confidence_bp in (1_500, 3_000, 4_500, 6_000, 7_500, 9_000):
            for src_count in (1, 2, 3):
                for groups in (0, 1, 2, 4):
                    request = _request(present=present, fact_confidence_bp=fact_confidence_bp,
                                       src_count=src_count, groups=groups)
                    result = unit.evaluate(request, {})
                    synthesis = maker.decide(request, [result], terminal=None, uncertainty=(),
                                             degraded=False)
                    confidences.append(synthesis.decision.confidence_bp)
                    if synthesis.decision.outcome == DecisionOutcome.DEFER:
                        deferred += 1
                        if any(item.startswith("below_floor_")
                               for item in synthesis.decision.uncertainty):
                            named_resolvers += 1
    floor, source = resolve_confidence_floor(_request(present=3, fact_confidence_bp=5_000,
                                                      src_count=1, groups=1))
    total = len(confidences)
    print("── compiled lane · what `core.confidence` actually produces, and what the floor does")
    print(f"  runs                       {total}")
    print(f"  floor                      {floor} bp   ({source})")
    print(f"  distinct confidences       {len(set(confidences))}")
    print(f"  distribution               {_percentiles(confidences)}")
    print(f"  below floor -> DEFER       {deferred}  ({deferred * 100 // total}%)")
    print(f"  DEFERs naming a resolver   {named_resolvers}/{deferred}")
    above = total - deferred
    print(f"  above floor -> DECISION    {above}  ({above * 100 // total}%)")


def multi_publisher_population() -> None:
    """The legacy lane's shape: several units publishing the same metric, no authority reached."""
    rows: list[tuple[int, int, int, int | None]] = []
    violations = 0
    raises = 0
    lowers = 0
    for first in (2_000, 3_500, 5_000, 6_500, 8_000):
        for second in (2_000, 3_500, 5_000, 6_500, 8_000):
            for group in (None, "signed_contract"):
                evidence = (
                    EvidenceRef(evidence_id="ev_a", field=FIELDS[0], value="open",
                                confidence_bp=first, independence_group="crm"),
                    EvidenceRef(evidence_id="ev_b", field=FIELDS[0], value="open",
                                confidence_bp=second, independence_group=group),
                )
                seed = _request(present=1, fact_confidence_bp=first, src_count=1, groups=0)
                request = ReasoningRequest(
                    org_id="org_1", capability=seed.capability,
                    context=ContextSnapshot(
                        org_id="org_1", graph_version=1, root_entity_id="deal_1",
                        root_entity_type="deal", evaluation_time=NOW,
                        selector_version="selector.v1", facts=dict(seed.context.facts),
                        evidence=evidence),
                    evaluation_time=NOW, trigger_kind="email.received",
                    config_snapshot_id="cfg_1")
                results = [
                    ReasonerResult("legacy.rule", "1", ResultStatus.COMPLETED, matched=True,
                                   metrics={"confidence_bp": first}, evidence_ids=("ev_a",)),
                    ReasonerResult("legacy.score_gate", "1", ResultStatus.COMPLETED, matched=True,
                                   metrics={"confidence_bp": second}, evidence_ids=("ev_b",)),
                ]
                before = _last_writer_scan(results, request)
                try:
                    after: int | None = compose_confidence(results, request, False).confidence_bp
                except ConfidenceViolation:
                    violations += 1
                    after = None
                if after is not None:
                    raises += 1 if after > first else 0
                    lowers += 1 if after < first else 0
                rows.append((first, second, before, after))

    befores = [row[2] for row in rows]
    afters = [row[3] for row in rows if row[3] is not None]
    lifted = [(row[0], row[3]) for row in rows if row[3] is not None and row[3] > row[0]]
    print()
    print("── multi-publisher runs · the last-writer scan versus Rule 11")
    print(f"  runs                       {len(rows)}")
    print(f"  BEFORE (last-writer scan)  {_percentiles(befores)}")
    print(f"  AFTER  (Rule 11, lawful)   {_percentiles(afters)}   n={len(afters)}")
    print(f"  uncited raises REFUSED     {violations}  ({violations * 100 // len(rows)}%)")
    print(f"  lawful raises (bounded)    {raises}   lowered {lowers}   unchanged "
          f"{len(afters) - raises - lowers}")
    if lifted:
        worst = max(lifted, key=lambda item: item[1] - item[0])
        print(f"  largest lawful lift        {worst[0]} -> {worst[1]} bp "
              f"(+{worst[1] - worst[0]}); the same pair under the old scan went straight to "
              f"the published claim")
    print("  every refused run published a confidence the old scan accepted with no independent")
    print("  evidence named — that is the number those decisions used to rest on.")


if __name__ == "__main__":
    compiled_lane_population()
    multi_publisher_population()
