"""The change gate's memory — what each subject's last decision was made on (STEP-02).

One row per (tenant, subject) in `reasoning_fingerprints` (migration 0191): the fingerprint of the
decision's inputs (`reason/fingerprint.material_fingerprint`), the run that decided on them, what
came of it, and how many sweeps skipped the subject since. `reason/change_gate.should_skip` reads
it; the lanes write it.

A RUN REPLACES THE ROW and zeroes the skips: the stored fingerprint is always the one the last
decision saw. A SKIP moves only the receipt — `last_checked_at` and `skips` — so a skipped subject
still shows the sweep looked at it, and a subject re-decided on an unchanged fingerprint is visible
(`scripts/pipeline_health.py`).

The sweep reads a tenant's rows ONCE (`load_all`), never one round trip per subject.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

#: The lanes a subject is decided in, and what its key is made of:
#:   compiled  '<situation_id>|<capability_id>'
#:   legacy    'legacy|<rule_id>|<node_id>'
#:   native    'native|<capability_id>|<node_id>'
LANES: tuple[str, ...] = ("compiled", "legacy", "native")

#: What a decision came to — the bookkeeping a skip replays (migration 0191 says what each means).
#: Closed, and held equal to the migration's check constraint by `tests/reason/test_fingerprint_store.py`.
EMITTED, STANDING, DEFERRED, INDETERMINATE, SUPPRESSED, SHADOW = (
    "emitted", "standing", "deferred", "indeterminate", "suppressed", "shadow")
OUTCOMES: tuple[str, ...] = (EMITTED, STANDING, DEFERRED, INDETERMINATE, SUPPRESSED, SHADOW)


@dataclass(frozen=True)
class StoredFingerprint:
    subject_key: str
    lane: str
    fingerprint: str
    outcome: str
    run_id: str | None
    decided_at: datetime
    last_checked_at: datetime
    skips: int


def _row(r) -> StoredFingerprint:
    return StoredFingerprint(subject_key=r.subject_key, lane=r.lane, fingerprint=r.fingerprint,
                             outcome=r.outcome, run_id=r.run_id, decided_at=r.decided_at,
                             last_checked_at=r.last_checked_at, skips=int(r.skips))


def load_all(conn, org_id: str) -> Mapping[str, StoredFingerprint]:
    """Every row of one tenant, by subject key — the sweep's one read."""
    return {r.subject_key: _row(r) for r in conn.execute(text(
        "select subject_key, lane, fingerprint, outcome, run_id, decided_at, last_checked_at, "
        "       skips from reasoning_fingerprints where org_id = :o"), {"o": org_id})}


def record_decided(conn, *, org_id: str, subject_key: str, lane: str, fingerprint: str,
                   outcome: str, run_id: str | None, decided_at: datetime) -> None:
    """A run decided this subject on `fingerprint`: replace the row and zero the skips."""
    if lane not in LANES:
        raise ValueError(f"lane {lane!r} is not one of {LANES}")
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome {outcome!r} is not one of {OUTCOMES}")
    conn.execute(text(
        "insert into reasoning_fingerprints (org_id, subject_key, lane, fingerprint, outcome, "
        "       run_id, decided_at, last_checked_at, skips) "
        "values (:o, :k, :lane, :fp, :outcome, :run, :at, :at, 0) "
        "on conflict (org_id, subject_key) do update set lane = excluded.lane, "
        "       fingerprint = excluded.fingerprint, outcome = excluded.outcome, "
        "       run_id = excluded.run_id, decided_at = excluded.decided_at, "
        "       last_checked_at = excluded.last_checked_at, skips = 0"),
        {"o": org_id, "k": subject_key, "lane": lane, "fp": fingerprint, "outcome": outcome,
         "run": run_id, "at": decided_at})


def record_skipped(conn, *, org_id: str, subject_key: str, checked_at: datetime) -> int:
    """A sweep looked at this subject and skipped it: move the receipt. Returns rows touched —
    0 for a subject with no row, which a gate never skips."""
    return conn.execute(text(
        "update reasoning_fingerprints set last_checked_at = :at, skips = skips + 1 "
        " where org_id = :o and subject_key = :k"),
        {"o": org_id, "k": subject_key, "at": checked_at}).rowcount
