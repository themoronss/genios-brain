"""The expert's reviews, kept — written once per file per fingerprint, read back without the model (STEP-12).

Tree `yc2_w27_s12` M32.C3.L-data.V1.U03, over `migrations/0197_expert_reviews.sql`. The expert reviews a
FILE once each time its fingerprint (`reason/expert/fingerprint`) moves, so its review is stored on that
key and every later read — the pass asking "was this fingerprint reviewed?", the read model showing a
file's latest review, a replay rebuilding a decision — is a read of the row, never a call of the model.

ONCE PER FINGERPRINT. A second write for a (file, fingerprint) that has a STANDING row is refused,
whatever it says: a valid review is the record, and a refusal — refused on substance, or cut at the
token ceiling — stands until the file moves (STEP-12 §8.4 item 4; a cut answer retried at the same
ceiling is cut again, `03` F140). Two rows do not stand, because neither is the expert's verdict:
`failed` (the call or its parse broke — a network blip is not a judgment) and `over_budget` (no call
was made; D7's busy day "carries the rest" to the next). Their retry may replace them.

WHAT IS READ BACK. A valid row's review is parsed back into an `ExpertReview` (`contracts/expert_review`)
— the same review that was written, field for field. A row of any other status keeps what the model
wrote, if anything, as data (`raw`); it is never parsed into a review anybody acts on.

WHAT THE FILE WAS (0198, M32.C3.L-data.V1.U10). Every row keeps its fingerprint's inputs
(`reason/expert/fingerprint.fingerprint_inputs`), and a retry replaces them with the rest. A file's
latest STANDING row is what the last judgment saw: the triggers (`reason/expert/triggers`) diff the
file against it to say what moved. And every row keeps what triggered it (0199, M32.C3.L-data.V1.U11):
each trigger's kind and what moved — the shape is checked here, the vocabulary is the triggers' own.

WHAT THE CHECK FOUND (0200, STEP-13 `yc2_w27_s13` M35.C1.L-contract.V1.U03). A valid review is decided
THROUGH its check (`reason/expert/verify`, `contracts/claim_check.CheckedReview`), and a replay reads that
check back rather than running it again over a dossier nobody stored. So a valid row keeps its check:
written with the review, or — a row checked under an older check version, or before 0200 — written onto
the standing row by `write_check`, which touches nothing else.

EVERY FILE'S CURRENT JUDGMENT, IN ONE READ (STEP-15, `yc2_w27_s15` M44.C2.L-data.V0.U01, `03` s15-F13). The morning
brief reads every file at once: `current_judgments` gives each file's newest STANDING row as of an instant — a
valid review with its check, or a refusal or a truncation with its reason — and the lane its decision was taken
on, from the change gate's record of the file (`reasoning_fingerprints`, `<file>|expert.file_review`): `shadow`
when the file's domain is not switched on, the live lane for any other word, none when nothing was decided.
`latest_valid` read per file would hand back an older valid review when the newest standing one was refused —
a judgment the expert no longer stands behind.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.claim_check import CheckedReview
from genios_engine.contracts.expert_review import ExpertReview

VALID, REFUSED, TRUNCATED, OVER_BUDGET, FAILED = "valid", "refused", "truncated", "over_budget", "failed"
STATUSES: tuple[str, ...] = (VALID, REFUSED, TRUNCATED, OVER_BUDGET, FAILED)

#: A row with one of these statuses is the fingerprint's answer until the file moves.
STANDING: tuple[str, ...] = (VALID, REFUSED, TRUNCATED)

#: A row with one of these may be replaced by its retry — `_WRITE`'s `where` names the same two.
RETRYABLE: tuple[str, ...] = (OVER_BUDGET, FAILED)

_WRITE = text(
    "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, dossier_digest, "
    "       status, reason, review, input_tokens, output_tokens, cost_micro_usd, reviewed_at, inputs, "
    "       triggers, checked) "
    "values (:o, :f, :fp, :model, :pv, :digest, :status, :reason, cast(:review as jsonb), :tin, :tout, "
    "        :cost, :at, cast(:inputs as jsonb), cast(:triggers as jsonb), cast(:checked as jsonb)) "
    "on conflict (org_id, file_id, fingerprint) do update set "
    "       model = excluded.model, prompt_version = excluded.prompt_version, "
    "       dossier_digest = excluded.dossier_digest, status = excluded.status, "
    "       reason = excluded.reason, review = excluded.review, "
    "       input_tokens = excluded.input_tokens, output_tokens = excluded.output_tokens, "
    "       cost_micro_usd = excluded.cost_micro_usd, reviewed_at = excluded.reviewed_at, "
    "       inputs = excluded.inputs, triggers = excluded.triggers, checked = excluded.checked "
    " where expert_reviews.status in ('over_budget', 'failed')")

_READ = text(
    "select file_id, fingerprint, model, prompt_version, dossier_digest, status, reason, review, "
    "       input_tokens, output_tokens, cost_micro_usd, reviewed_at, inputs, triggers, checked "
    "  from expert_reviews "
    " where org_id = :o and file_id = :f and fingerprint = :fp")

_LATEST_VALID = text(
    "select file_id, fingerprint, model, prompt_version, dossier_digest, status, reason, review, "
    "       input_tokens, output_tokens, cost_micro_usd, reviewed_at, inputs, triggers, checked "
    "  from expert_reviews "
    " where org_id = :o and file_id = :f and status = 'valid' "
    " order by reviewed_at desc, fingerprint desc "
    " limit 1")

#: What the last judgment saw: the newest row that STANDS — `STANDING`'s three statuses, named again.
_LATEST_STANDING = text(
    "select file_id, fingerprint, model, prompt_version, dossier_digest, status, reason, review, "
    "       input_tokens, output_tokens, cost_micro_usd, reviewed_at, inputs, triggers, checked "
    "  from expert_reviews "
    " where org_id = :o and file_id = :f and status in ('valid', 'refused', 'truncated') "
    " order by reviewed_at desc, fingerprint desc "
    " limit 1")


#: STEP-15 · every file's newest STANDING row as of an instant, and the change gate's record of its decision —
#: one statement for the whole tenant. `distinct on` keeps one row per file: the newest, the newest
#: fingerprint on a tie, as `_LATEST_STANDING` orders one file's.
_CURRENT = text(
    "select distinct on (r.file_id) r.file_id, r.fingerprint, r.model, r.prompt_version, r.dossier_digest, "
    "       r.status, r.reason, r.review, r.input_tokens, r.output_tokens, r.cost_micro_usd, r.reviewed_at, "
    "       r.inputs, r.triggers, r.checked, g.outcome as gate_outcome "
    "  from expert_reviews r "
    "  left join reasoning_fingerprints g on g.org_id = r.org_id "
    "       and g.subject_key = r.file_id || :decision and g.decided_at <= :now "
    " where r.org_id = :o and r.status in ('valid', 'refused', 'truncated') and r.reviewed_at <= :now "
    " order by r.file_id, r.reviewed_at desc, r.fingerprint desc")


@dataclass(frozen=True)
class StoredReview:
    """One row of `expert_reviews`. `review` is set only for a valid row; `raw` is what was stored."""
    file_id: str
    fingerprint: str
    model: str
    prompt_version: str
    dossier_digest: str
    status: str
    reason: str | None
    review: ExpertReview | None
    raw: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    cost_micro_usd: int
    reviewed_at: datetime
    inputs: dict[str, Any] | None = None         # what the file was; None only on a row before 0198
    #: What triggered it — (kind, what moved) each; None only on a row written before 0199.
    triggers: tuple[tuple[str, str], ...] | None = None
    #: What the check found (0200) — on a valid row; None before 0200, or until the pass checks it.
    checked: CheckedReview | None = None


#: A standing valid row's check, written onto it alone — a check of a newer version, or the first.
_CHECK = text(
    "update expert_reviews set checked = cast(:checked as jsonb) "
    " where org_id = :o and file_id = :f and fingerprint = :fp and status = 'valid'")


def _payload(status: str, review: ExpertReview | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if status == VALID:
        if not isinstance(review, ExpertReview):
            raise ValueError("a valid row carries its review, as an ExpertReview")
        return review.as_mapping()
    if review is None:
        return None
    return review.as_mapping() if isinstance(review, ExpertReview) else dict(review)


def _said(triggers: Iterable[Any]) -> list[dict[str, str]]:
    """Each trigger as `{kind, says}` — from a `Trigger`, anything with its kind and what moved, or a
    mapping — or ValueError: a review says what triggered it, every time, in words."""
    out = []
    for t in triggers:
        kind, says = (t.get("kind"), t.get("says")) if isinstance(t, Mapping) else (
            getattr(t, "kind", None), getattr(t, "says", None))
        if not (isinstance(kind, str) and kind.strip() and isinstance(says, str) and says.strip()):
            raise ValueError(f"a trigger names its kind and what moved, not {t!r}")
        out.append({"kind": kind, "says": says})
    return out


def write_review(conn, *, org_id: str, file_id: str, fingerprint: str, model: str, prompt_version: str,
                 dossier_digest: str, status: str, reason: str | None,
                 review: ExpertReview | Mapping[str, Any] | None, input_tokens: int, output_tokens: int,
                 cost_micro_usd: int, at: datetime, inputs: Mapping[str, Any],
                 triggers: Iterable[Any], checked: CheckedReview | None = None) -> bool:
    """Store the expert's answer for this fingerprint, with what the file was (`inputs`) and what
    triggered the review. True when it was written; False when a standing row already answers it
    (nothing changes). ValueError for a status nobody named, a non-valid row without its reason, a
    valid row without its review, inputs that are not a mapping, or a trigger without its words. A
    check rides only on a valid row: the review it checked is the row's own."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}: one of {', '.join(STATUSES)}")
    if status != VALID and not (reason or "").strip():
        raise ValueError(f"a {status} row says its reason")
    if not isinstance(inputs, Mapping):
        raise ValueError("a review keeps what the file was: its fingerprint's inputs, a mapping")
    said = _said(triggers)
    payload = _payload(status, review)
    if checked is not None and status != VALID:
        raise ValueError(f"a {status} row has no review to check")
    written = conn.execute(_WRITE, {
        "o": org_id, "f": file_id, "fp": fingerprint, "model": model, "pv": prompt_version,
        "digest": dossier_digest, "status": status, "reason": reason,
        "review": None if payload is None else json.dumps(payload, sort_keys=True),
        "tin": input_tokens, "tout": output_tokens, "cost": cost_micro_usd, "at": at,
        "inputs": json.dumps(dict(inputs), sort_keys=True), "triggers": json.dumps(said),
        "checked": None if checked is None else json.dumps(checked.as_mapping(), sort_keys=True)})
    return written.rowcount == 1


def write_check(conn, *, org_id: str, file_id: str, fingerprint: str, checked: CheckedReview) -> bool:
    """Keep `checked` as the standing valid row's check — nothing else of the row moves. True when a
    valid row took it; False when there is none (a refusal has no review to check)."""
    return conn.execute(_CHECK, {"o": org_id, "f": file_id, "fp": fingerprint,
                                 "checked": json.dumps(checked.as_mapping(), sort_keys=True)}).rowcount == 1


def _stored(row) -> StoredReview:
    m = row._mapping
    raw, triggers, checked = m["review"], m["triggers"], m["checked"]
    return StoredReview(
        file_id=m["file_id"], fingerprint=m["fingerprint"], model=m["model"],
        prompt_version=m["prompt_version"], dossier_digest=m["dossier_digest"], status=m["status"],
        reason=m["reason"], review=ExpertReview.from_mapping(raw) if m["status"] == VALID else None,
        raw=raw, input_tokens=m["input_tokens"], output_tokens=m["output_tokens"],
        cost_micro_usd=m["cost_micro_usd"], reviewed_at=m["reviewed_at"], inputs=m["inputs"],
        triggers=None if triggers is None else tuple((t["kind"], t["says"]) for t in triggers),
        checked=None if checked is None else CheckedReview.from_mapping(checked))


def read_review(conn, org_id: str, file_id: str, fingerprint: str) -> StoredReview | None:
    """The row for this fingerprint, whatever its status — or None."""
    row = conn.execute(_READ, {"o": org_id, "f": file_id, "fp": fingerprint}).first()
    return None if row is None else _stored(row)


def reviewed(conn, org_id: str, file_id: str, fingerprint: str) -> bool:
    """Whether this fingerprint is answered: a standing row exists. A failed or carried one is not."""
    stored = read_review(conn, org_id, file_id, fingerprint)
    return stored is not None and stored.status in STANDING


def latest_valid(conn, org_id: str, file_id: str) -> StoredReview | None:
    """The file's newest valid review — the newest fingerprint on a tie — or None."""
    row = conn.execute(_LATEST_VALID, {"o": org_id, "f": file_id}).first()
    return None if row is None else _stored(row)


def latest_standing(conn, org_id: str, file_id: str) -> StoredReview | None:
    """What the last judgment of the file saw: its newest standing row — valid, refused or truncated,
    the newest fingerprint on a tie — or None. A failed or carried row judged nothing."""
    row = conn.execute(_LATEST_STANDING, {"o": org_id, "f": file_id}).first()
    return None if row is None else _stored(row)


#: The lanes a file's decision is taken on (`reason/domain_shadow._decide_covered_files`): the change gate records
#: `shadow` for a file whose domain the tenant has not switched on, and the live lane's own word otherwise.
LIVE_LANE = "live"
SHADOW_LANE = "shadow"


@dataclass(frozen=True)
class CurrentJudgment:
    """A file's current judgment: its newest standing review, and the lane its decision was taken on — None when
    no decision was taken (a refusal decides nothing; a file with no situation has no corpus to decide in)."""
    stored: StoredReview
    lane: str | None
    outcome: str | None                          # the change gate's word for what the decision came to

    @property
    def valid(self) -> bool:
        return self.stored.status == VALID

    @property
    def checked(self) -> CheckedReview | None:
        """The check of a valid review — a refusal carries none (`write_review` refuses one on it)."""
        return self.stored.checked


def current_judgments(conn, org_id: str, *, now: datetime) -> dict[str, CurrentJudgment]:
    """Every file's current judgment as of `now` — file id → its newest standing review and its lane. One
    statement. A failed or carried row judged nothing and is passed over; a later review is not yet written."""
    from genios_engine.reason.expert.decide import CAPABILITY_ID
    out: dict[str, CurrentJudgment] = {}
    for row in conn.execute(_CURRENT, {"o": org_id, "now": now, "decision": f"|{CAPABILITY_ID}"}):
        outcome = row._mapping["gate_outcome"]
        lane = None if outcome is None else (SHADOW_LANE if outcome == SHADOW_LANE else LIVE_LANE)
        out[row.file_id] = CurrentJudgment(stored=_stored(row), lane=lane, outcome=outcome)
    return out


__all__ = ["CurrentJudgment", "FAILED", "LIVE_LANE", "OVER_BUDGET", "REFUSED", "RETRYABLE", "SHADOW_LANE", "STANDING",
           "STATUSES", "TRUNCATED", "VALID", "StoredReview", "current_judgments", "latest_standing", "latest_valid",
           "read_review", "reviewed", "write_check", "write_review"]
