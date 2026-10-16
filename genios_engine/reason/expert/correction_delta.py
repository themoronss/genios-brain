"""What your correction changed, read back from what was stored — and no model asked (STEP-16).

`speedrun008/YC-II W27/` STEP-16 §8.4 item 6, tree `yc2_w27_s16` M46.C4.L-logic.V4.U07. A correction of a file brings
it back to the expert (`reason/expert/triggers.FOUNDER_CORRECTED`); the review before it and the one after are both
stored, each with the inputs it saw (`expert_reviews.inputs`, 0198 — whose `corrections` name the corrections its
dossier showed) and the check it was decided through (0200). This reads, for each correction, on each file it
reached — its own, or every file of its kind of work —

  * BEFORE: the last valid review of the file that did not see it;
  * AFTER: the first valid review that did;

and for each: its mode once checked (`reason/expert/decide.mode_of`), its move as the check let it stand, whether it
cited your correction (a fact, an inference or a pattern of it), and the check's fate — the decision, replayed from
the store: the stored review and its stored check, never the model (a held move is a question; a suppressed one,
nothing). `changed` says whether the decision moved — its mode or its move.

Its readers: the weekly scorecard (`feedback/scorecard`, M47) and STEP-16's acceptance. Read-only; no I/O but the
caller's connection, no clock, no model.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text

from . import store
from .verify import cited_anywhere

#: Every valid review of the files a correction reached: the correction's own file, and any file a review of which saw
#: it — every review of those files, so the one before is read beside the one after.
_REVIEWS = (
    "select file_id, fingerprint, model, prompt_version, dossier_digest, status, reason, review, input_tokens, "
    "output_tokens, cost_micro_usd, reviewed_at, inputs, triggers, checked, checked_at, dossier, card_lines "
    "from expert_reviews where org_id = :o and status = 'valid' "
    "and (file_id = :f or file_id in (select s.file_id from expert_reviews s where s.org_id = :o "
    "and coalesce(s.inputs -> 'corrections', '[]'::jsonb) @> jsonb_build_array(cast(:ref as text)))) "
    "order by file_id, reviewed_at, fingerprint")


@dataclass(frozen=True, slots=True)
class Decided:
    """One stored review of the file, as it decided once checked."""
    fingerprint: str
    reviewed_at: datetime
    mode: str
    move: str | None
    cited: bool
    fate: str | None


@dataclass(frozen=True, slots=True)
class FileDelta:
    """On one file: the last review that did not see the correction, and the first that did."""
    file_id: str
    before: Decided | None
    after: Decided | None

    @property
    def changed(self) -> bool:
        """Did the decision move — its mode, or its move?"""
        if self.before is None or self.after is None:
            return False
        return (self.before.mode, self.before.move) != (self.after.mode, self.after.move)


@dataclass(frozen=True, slots=True)
class CorrectionDelta:
    correction_id: str
    scope: str
    files: tuple[FileDelta, ...]

    @property
    def reviewed(self) -> int:
        """How many files a review that saw the correction has decided."""
        return sum(1 for f in self.files if f.after is not None)

    @property
    def changed(self) -> int:
        return sum(1 for f in self.files if f.changed)

    @property
    def cited(self) -> int:
        """How many of those reviews cited it — followed it, or said why the file outweighs it."""
        return sum(1 for f in self.files if f.after is not None and f.after.cited)


def _saw(row: store.StoredReview, ref: str) -> bool:
    return ref in set((row.inputs or {}).get("corrections") or ())


def _decided(row: store.StoredReview, ref: str) -> Decided:
    from .decide import mode_of
    review, checked = row.review, row.checked
    move = (checked.words.headline if checked is not None
            else review.next_move.what if review.next_move is not None else None)
    return Decided(fingerprint=row.fingerprint, reviewed_at=row.reviewed_at,
                   mode=mode_of(review, checked) if checked is not None else review.mode,
                   move=move, cited=ref in cited_anywhere(review), fate=checked.fate if checked is not None else None)


def delta_for(conn, org_id: str, correction: Any) -> CorrectionDelta:
    """What `correction` (`context/founder_corrections.Correction`) changed, file by file."""
    ref = f"corr:{correction.correction_id}"
    rows = [store._stored(r) for r in conn.execute(text(_REVIEWS), {"o": org_id, "f": correction.file_id,
                                                                    "ref": ref})]
    by_file: dict[str, list[store.StoredReview]] = {}
    for row in rows:                    # valid reviews only (`_REVIEWS`): each one decided
        by_file.setdefault(row.file_id, []).append(row)
    files = []
    for file_id in sorted(by_file):
        reviews = by_file[file_id]
        first = next((i for i, r in enumerate(reviews) if _saw(r, ref)), None)
        earlier = reviews if first is None else reviews[:first]
        before = next((r for r in reversed(earlier) if not _saw(r, ref)), None)
        files.append(FileDelta(file_id=file_id, before=_decided(before, ref) if before is not None else None,
                               after=_decided(reviews[first], ref) if first is not None else None))
    return CorrectionDelta(correction_id=correction.correction_id, scope=correction.scope, files=tuple(files))


def deltas_for(conn, org_id: str, corrections: Iterable[Any]) -> tuple[CorrectionDelta, ...]:
    """What each of `corrections` changed, in their order."""
    return tuple(delta_for(conn, org_id, c) for c in corrections)


__all__ = ["CorrectionDelta", "Decided", "FileDelta", "delta_for", "deltas_for"]
