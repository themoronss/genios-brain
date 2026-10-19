"""GeniOS-008 L2 G1 · `reasoning_results` (0243) — the judgment pass's results and receipts, written once a
sweep, in ONE transaction.

⛔ BATCHED. Today's L2 opens two transactions per situation (`reason/audit.py` + `domain_shadow._persist_live`),
the churn `DATABASE_LOAD_ANALYSIS` measured. The new path keeps its rows in memory as the sweep runs and
writes them together at the end with the watermark — one transaction per sweep. A sweep that fails before
its write writes nothing and moves no watermark, so the next sweep reads the same bundles again.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text

#: The `post_pass_watermarks` pass id this pass keeps its "bundles read up to" under.
PASS_ID = "l2_reasoning"

_WRITE = text(
    "insert into reasoning_results (org_id, subject_ref, fingerprint, request_id, trigger, status, reason, depth, "
    "  lane, lane_reason, result, receipt, dossier, model, prompt_version, input_tokens, output_tokens, "
    "  cost_micro_usd, bundle_ids, reasoned_at) "
    "values (:o, :s, :fp, :rq, :tr, :st, :rs, :d, :ln, :lr, cast(:res as jsonb), cast(:rc as jsonb), "
    "  cast(:ds as jsonb), :m, :pv, :ti, :to, :c, cast(:b as jsonb), :at) "
    # A failed or over-budget row may be replaced by its retry; a result or a refusal stands.
    "on conflict (org_id, subject_ref, fingerprint) do update set "
    "  request_id = excluded.request_id, trigger = excluded.trigger, status = excluded.status, "
    "  reason = excluded.reason, depth = excluded.depth, lane = excluded.lane, lane_reason = excluded.lane_reason, "
    "  result = excluded.result, receipt = excluded.receipt, dossier = excluded.dossier, model = excluded.model, "
    "  prompt_version = excluded.prompt_version, input_tokens = excluded.input_tokens, "
    "  output_tokens = excluded.output_tokens, cost_micro_usd = excluded.cost_micro_usd, "
    "  bundle_ids = excluded.bundle_ids, reasoned_at = excluded.reasoned_at "
    "where reasoning_results.status in ('failed', 'over_budget')")

_READ = text(
    "select subject_ref, fingerprint, status, reason, depth, lane, result, receipt, dossier, prompt_version, "
    "       reasoned_at "
    "  from reasoning_results where org_id = :o and subject_ref = :s and fingerprint = :fp")

_LATEST = text(
    "select subject_ref, fingerprint, status, reason, depth, lane, result, receipt, dossier, prompt_version, "
    "       reasoned_at "
    "  from reasoning_results where org_id = :o and subject_ref = :s "
    " order by reasoned_at desc limit 1")

_WATERMARK = text("select watermark from post_pass_watermarks where org_id = :o and pass_id = :p")
_MOVE = text(
    "insert into post_pass_watermarks (org_id, pass_id, watermark, updated_at) values (:o, :p, :w, now()) "
    "on conflict (org_id, pass_id) do update set "
    "watermark = greatest(post_pass_watermarks.watermark, excluded.watermark), updated_at = now()")

#: The statuses a row may have; a row that stands answers its fingerprint with no call.
RESULT, REFUSED, FAILED, TRUNCATED, OVER_BUDGET = "result", "refused", "failed", "truncated", "over_budget"
STANDING = (RESULT, REFUSED, TRUNCATED)


def _dumps(value: Any) -> str | None:
    return None if value is None else json.dumps(value, sort_keys=True, default=str)


def _loads(value: Any) -> Any:
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


@dataclass(frozen=True, slots=True)
class L2Row:
    org_id: str
    subject_ref: str
    fingerprint: str
    request_id: str
    trigger: str
    status: str
    depth: str
    prompt_version: str
    reasoned_at: datetime
    reason: str | None = None
    lane: str | None = None
    lane_reason: str | None = None
    result: Any = None
    receipt: Any = field(default_factory=dict)
    dossier: Any = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0
    bundle_ids: tuple[str, ...] = ()

    def params(self) -> dict[str, Any]:
        return {"o": self.org_id, "s": self.subject_ref, "fp": self.fingerprint, "rq": self.request_id,
                "tr": self.trigger, "st": self.status, "rs": self.reason, "d": self.depth, "ln": self.lane,
                "lr": self.lane_reason, "res": _dumps(self.result), "rc": _dumps(self.receipt) or "{}",
                "ds": _dumps(self.dossier), "m": self.model, "pv": self.prompt_version,
                "ti": int(self.input_tokens or 0), "to": int(self.output_tokens or 0),
                "c": int(self.cost_micro_usd or 0), "b": _dumps(list(self.bundle_ids)), "at": self.reasoned_at}


@dataclass(frozen=True, slots=True)
class StoredResult:
    subject_ref: str
    fingerprint: str
    status: str
    reason: str | None
    depth: str
    lane: str | None
    result: Any
    receipt: Any
    dossier: Any
    prompt_version: str
    reasoned_at: datetime


def _stored(row: Any) -> StoredResult:
    m = row._mapping
    return StoredResult(subject_ref=m["subject_ref"], fingerprint=m["fingerprint"], status=m["status"],
                        reason=m["reason"], depth=m["depth"], lane=m["lane"], result=_loads(m["result"]),
                        receipt=_loads(m["receipt"]) or {}, dossier=_loads(m["dossier"]),
                        prompt_version=m["prompt_version"], reasoned_at=m["reasoned_at"])


def read_result(conn, org_id: str, subject_ref: str, fingerprint: str) -> StoredResult | None:
    row = conn.execute(_READ, {"o": org_id, "s": subject_ref, "fp": fingerprint}).first()
    return _stored(row) if row is not None else None


def latest_result(conn, org_id: str, subject_ref: str) -> StoredResult | None:
    row = conn.execute(_LATEST, {"o": org_id, "s": subject_ref}).first()
    return _stored(row) if row is not None else None


def read_watermark(conn, org_id: str) -> datetime | None:
    return conn.execute(_WATERMARK, {"o": org_id, "p": PASS_ID}).scalar()


def write_sweep(conn, rows: Sequence[L2Row], *, org_id: str, watermark: datetime | None) -> int:
    """Every row of the sweep, and the watermark, on the caller's ONE transaction. Returns rows written."""
    written = 0
    for row in rows:
        written += int(conn.execute(_WRITE, row.params()).rowcount or 0)
    if watermark is not None:
        conn.execute(_MOVE, {"o": org_id, "p": PASS_ID, "w": watermark})
    return written


__all__ = ["FAILED", "L2Row", "OVER_BUDGET", "PASS_ID", "REFUSED", "RESULT", "STANDING", "StoredResult",
           "TRUNCATED", "latest_result", "read_result", "read_watermark", "write_sweep"]
