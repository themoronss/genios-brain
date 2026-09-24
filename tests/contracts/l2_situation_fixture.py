"""A minimal admitted v2 situation, for the law tests. One builder, so a contract change that
breaks construction breaks in ONE place rather than in every test that happens to build one."""
from __future__ import annotations

from typing import Any

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.situation import BusinessSituationObject


def _receipt() -> EvidenceSpan:
    """⛔ Non-optional. `SituationDecision` refuses to carry a situation with no evidence —
    *"a claim with no receipt is a guess"* — which is the very doctrine V-9 extends inward."""
    quote = "the renewal is on 31 March"
    return EvidenceSpan(source_ref="prepared_content:evt_l2_2", quote=quote,
                        start_offset=0, end_offset=len(quote), verified=True)


def minimal_situation(**over: Any) -> BusinessSituationObject:
    """`model_construct` on purpose — these tests drive `validate_situation`, which exists
    *"for the objects that did not go through a constructor"*."""
    base: dict[str, Any] = {
        "org_id": "org_test", "trace_id": "trace_test", "visibility": None,
        "id": "sit_test", "type": "support_case", "state": "active",
        "domain_ids": ("support",), "signal_ids": ("sig-1",), "entities": (),
        "relationships": (), "timeline": (), "dependencies": (), "evidence": (_receipt(),),
        "provenance_refs": (), "confidence": None, "coverage_ready": True,
        "conflicts": (), "conflict_ids": (), "missing_facts": (), "importance": None,
        "trends": (), "cohort_positions": (), "anomalies": (), "correlations": (),
        "pattern_id": None, "matched_conditions": (), "metadata": {},
        "schema_version": "",
    }
    base.update(over)
    return BusinessSituationObject.model_construct(**base)
