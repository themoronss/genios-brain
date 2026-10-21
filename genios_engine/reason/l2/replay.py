"""GeniOS-008 L2 G3 · replay — a stored run read back and checked again, with NO model call.

Spec §14: every run must be replayable from its receipt. The row keeps the result (`ReasoningResult.as_mapping`)
and the dossier it was checked against (text, ids, numbers, stages), so a replay rebuilds the result, re-runs
the STEP-13 claim check and `validate_judgment` on THAT dossier — never today's — and compares the output hash
with the one the receipt recorded. A different hash means the result was edited or the check moved; both are
things an audit must be able to say.
"""
from __future__ import annotations

from dataclasses import dataclass

from genios_engine.contracts.expert_review import DossierCatalogue
from genios_engine.contracts.reasoning_result import ReasoningResult, judgment_hold, validate_judgment
from genios_engine.reason.expert.review import NOBODY
from genios_engine.reason.expert.verify import check_review

from . import store as results


@dataclass(frozen=True, slots=True)
class Replayed:
    result: ReasoningResult
    output_hash_matches: bool
    check_fate: str
    problems: tuple[tuple[str, str], ...]


def catalogue_of(dossier: dict) -> DossierCatalogue:
    return DossierCatalogue(evidence_ids=frozenset(dossier.get("evidence_ids") or ()),
                            numbers=frozenset(dossier.get("numbers") or ()),
                            stages=tuple(dossier.get("stages") or ()))


def replay_row(row: results.StoredResult, people=None) -> Replayed | None:
    """One stored row replayed — None for a row that holds no result (refused, failed, carried)."""
    if row.status != results.RESULT or not isinstance(row.result, dict) or not isinstance(row.dossier, dict):
        return None
    result = ReasoningResult.from_mapping(row.result)
    catalogue = catalogue_of(row.dossier)
    # The lane's hold, as the live run applied it (`judge.judge`): the problems are the stored result's own.
    checked = check_review(result.review, row.dossier.get("text") or "", people or NOBODY,
                           evidence_ids=catalogue.evidence_ids, judged=judgment_hold(result.lane, result.problems))
    from dataclasses import replace
    unstamped = replace(result, receipt_ref="")
    recorded = (row.receipt or {}).get("output_hash")
    return Replayed(result=result, output_hash_matches=(recorded == unstamped.output_hash()),
                    check_fate=checked.fate,
                    problems=validate_judgment(result.review, result.judgment, catalogue))


def replay(conn, org_id: str, subject_ref: str, fingerprint: str) -> Replayed | None:
    row = results.read_result(conn, org_id, subject_ref, fingerprint)
    return replay_row(row) if row is not None else None


__all__ = ["Replayed", "catalogue_of", "replay", "replay_row"]
