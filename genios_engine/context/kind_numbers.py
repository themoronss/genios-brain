"""Your own numbers for a kind of work — measured across your files of it, beside the playbook's priors (STEP-16).

`speedrun008/YC-II W27/` STEP-16 §3.4 and §8.4 item 4, tree `yc2_w27_s16` M47.C2.L-logic.V3.U01. A playbook's stage
durations are PRIORS — an author's numbers, not measured here. This measures yours, across the tenant's files of one
kind of work (the kind the brief gives each file, `context/workstreams`):

  * REACHED — how many of the files a review has placed at each stage the reviews named
    (`expected_vs_actual.stage`, one of the playbook's stages), a count;
  * DAYS IN A STAGE — for each file whose reviews moved it on from a stage, the days from the first review naming
    that stage to the first naming the next: a median, with its n;
  * VERIFIED — of the decisions on those files that ended, how many ended verified (`context/file_outcomes`): a
    rate, with its n.

Each a `contracts/measured.Measured`, so "a prior" and "yours" are told apart and a number is never a habit below
`NORMAL_AT` (`06` D37). Observe-only (Atlas V.3): nothing here changes a judgment — the dossier prints it beside the
prior. Org-level: the files are the org's, the reviews are of them, nothing a seat holds privately is read.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.measured import Measured, count_of, median_of, rate_of

#: Each valid review of the given files — the stage it named, when — oldest first.
_STAGES = (
    "select file_id, reviewed_at, review -> 'expected_vs_actual' ->> 'stage' as stage from expert_reviews "
    "where org_id = :o and status = 'valid' and file_id = any(:files) order by file_id, reviewed_at, fingerprint")


@dataclass(frozen=True, slots=True)
class KindNumbers:
    """Your numbers for one kind of work."""
    kind: str
    files: int
    reached: Mapping[str, Measured] = field(default_factory=dict)       # stage → a count of files
    days_in: Mapping[str, Measured] = field(default_factory=dict)       # stage → a median, with its n
    verified: Measured | None = None

    def as_dict(self) -> dict:
        def m(x: Measured | None):
            return None if x is None else {"value": x.value, "n": x.n, "says": x.says()}
        return {"kind": self.kind, "files": self.files, "reached": {s: m(v) for s, v in self.reached.items()},
                "days_in": {s: m(v) for s, v in self.days_in.items()}, "verified": m(self.verified)}


def stage_numbers(rows) -> tuple[dict[str, Measured], dict[str, Measured]]:
    """From `(file_id, reviewed_at, stage)` rows, oldest first: the files that reached each stage, and the days a file
    spent in each before a review moved it on — pure."""
    firsts: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
    for r in rows:
        if not r.stage:
            continue
        seen = firsts[r.file_id]
        if all(stage != r.stage for stage, _at in seen):
            seen.append((r.stage, r.reviewed_at))
    reached: dict[str, int] = defaultdict(int)
    dwell: dict[str, list[float]] = defaultdict(list)
    for stages in firsts.values():
        for stage, _at in stages:
            reached[stage] += 1
        for (stage, at), (_next, then) in zip(stages, stages[1:]):
            dwell[stage].append(round((then - at).total_seconds() / 86400, 2))
    return ({s: count_of(n, basis="your files of this kind", unit="files") for s, n in sorted(reached.items())},
            {s: median_of(v, basis="your files of this kind", unit="days") for s, v in sorted(dwell.items())})


def numbers_for_kind(conn, org_id: str, kind: str, *, now: datetime, files: tuple[str, ...] | None = None) -> KindNumbers:
    """Your numbers for `kind` across the tenant's files of it (or the given `files` — the caller has read them)."""
    from genios_engine.context.file_outcomes import OPEN, VERIFIED, ended_for_files
    if files is None:
        from genios_engine.context.workstreams import files_for
        files = tuple(f.file_id for f in files_for(conn, org_id, now=now).files if f.work_kind == kind)
    if not files:
        return KindNumbers(kind=kind, files=0, verified=rate_of(0, 0, basis="decisions on your files of this kind"))
    rows = conn.execute(text(_STAGES), {"o": org_id, "files": list(files)}).fetchall()
    reached, days_in = stage_numbers(rows)
    ended = [e for e in ended_for_files(conn, org_id, files) if e.ended != OPEN]
    return KindNumbers(kind=kind, files=len(files), reached=reached, days_in=days_in,
                       verified=rate_of(sum(1 for e in ended if e.ended == VERIFIED), len(ended),
                                        basis="decisions on your files of this kind"))


__all__ = ["KindNumbers", "numbers_for_kind", "stage_numbers"]
