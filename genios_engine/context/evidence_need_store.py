"""U10 · the needs queue, written — the last hop between measuring a gap and asking about it.

`evidence_needs.py` and `hold_needs.py` turn residue and holds into `EvidenceNeed` objects. Nothing
persisted them, so the executor in `capture/acquire/evidence_need.py` read an empty table. This is
the writer.

⛔ `on conflict do nothing`, AND THAT IS THE WHOLE DESIGN OF THIS MODULE.

`need_id` is deterministic over (org, question, subject), so the same question raised on two sweeps
is one row — that part is migration 0187's primary key. What matters here is the UPDATE that must
never happen: an `on conflict do update` would reset a need that already closed `met` or
`unavailable` back to `open` on the very next sweep, because residue and holds are **re-derived
every sweep** and a re-derived need is always born `open`.

The consequences of getting that backwards, in order of how bad they are:

  1. A question answered "the document does not exist" would be asked again every sweep, forever.
  2. The executor would fetch again each time and charge the tenant again each time.
  3. ⛔ The system would learn that its questions are always eventually answered, because every
     closed need keeps reopening and closing. That is the failure `evidence_needs` excludes three of
     four residue kinds to avoid, undone by one SQL verb.

So: a need is written once and thereafter only the executor moves it. A re-derivation is not new
information; it is the same question, still on file.

NEVER RAISES. A sweep that could not file its questions has lost a cycle of visibility. A sweep that
died trying has lost the tenant's ingestion — the same trade `detect_residue` makes one call earlier.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import text

from genios_engine.contracts.evidence import EvidenceNeed
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.evidence_needs")

_INSERT = text(
    "insert into evidence_needs "
    "  (need_id, org_id, trace_id, question, why_it_matters, subject_ref, "
    "   acceptable_sources, unacceptable_sources, window_from, window_to, "
    "   max_cost_usd, expires_at, state, unavailable_reason) "
    "values (:need_id, :org_id, :trace_id, :question, :why, :subject, "
    "        cast(:acceptable as jsonb), cast(:unacceptable as jsonb), :w_from, :w_to, "
    "        :max_cost, :expires_at, :state, :reason) "
    # ⛔ NOTHING, never `do update`. See the module docstring: the alternative reopens closed
    # questions every sweep and teaches the system that it always gets answers.
    "on conflict (need_id) do nothing")

_OPEN = text(
    "select need_id, org_id, trace_id, question, why_it_matters, subject_ref, "
    "       acceptable_sources, unacceptable_sources, window_from, window_to, "
    "       max_cost_usd, expires_at, state, unavailable_reason "
    "from evidence_needs where org_id = :o and state = 'open' "
    "order by created_at limit :n")

_CLOSE = text(
    "update evidence_needs set state = :state, unavailable_reason = :reason, "
    "  closed_at = now() "
    # Only an OPEN need may be closed. A second executor pass on a need the first already settled
    # must not overwrite the first outcome, and this predicate is that guard — one statement, no
    # read-modify-write, so two concurrent passes cannot both win.
    "where need_id = :need_id and state = 'open'")


def _params(need: EvidenceNeed) -> dict:
    return {
        "need_id": need.need_id, "org_id": need.org_id, "trace_id": need.trace_id,
        "question": need.question, "why": need.why_it_matters, "subject": need.subject_ref,
        "acceptable": json.dumps(list(need.acceptable_sources)),
        "unacceptable": json.dumps(list(need.unacceptable_sources)),
        "w_from": need.window_from, "w_to": need.window_to,
        "max_cost": need.max_cost_usd, "expires_at": need.expires_at,
        "state": need.state, "reason": need.unavailable_reason,
    }


def store_needs(conn, needs: Sequence[EvidenceNeed]) -> int:
    """File these needs, skipping any already on file. Returns how many rows were NEW.

    The return value is the honest one: "how many questions we had not already asked". A count of
    needs passed in would report the same number every sweep and read as progress.
    """
    if not needs:
        return 0
    written = 0
    for need in needs:
        result = conn.execute(_INSERT, _params(need))
        written += int(result.rowcount or 0)
    return written


def read_open_needs(conn, org_id: str, *, limit: int = 100) -> list[dict]:
    """The executor's queue: this tenant's open needs, oldest first.

    Oldest first on purpose — the longest-waiting question is worked before the newest one, so a
    steady stream of new needs cannot starve one that has been waiting a week.
    """
    return [dict(r) for r in conn.execute(_OPEN, {"o": org_id, "n": limit}).mappings()]


def close_need(conn, need_id: str, *, state: str, reason: str | None = None) -> bool:
    """Record an outcome. Returns False when the need was already closed by someone else.

    ⛔ A `False` here is not an error and must not be retried as one: it means another pass settled
    this question first, and its answer stands. Overwriting it would replace a recorded outcome with
    a later one for no reason, and `unavailable` overwritten by `unavailable` would still reset
    `closed_at`, losing when the question was actually settled.
    """
    if state not in {"met", "unavailable"}:
        raise ValueError(f"a need closes as met or unavailable, not {state!r}")
    if state == "unavailable" and not (reason or "").strip():
        # The database check constraint says the same thing. Refusing here too means the caller gets
        # a name for its mistake instead of an IntegrityError from three frames down.
        raise ValueError("an unavailable need carries its reason")
    result = conn.execute(_CLOSE, {"need_id": need_id, "state": state, "reason": reason})
    return bool(result.rowcount)


def file_needs(store, needs: Sequence[EvidenceNeed]) -> int:
    """`store_needs` in its own transaction, swallowing failure. For use inside a sweep.

    Separate from `store_needs` so a caller that already holds a transaction is not forced into a
    nested one, and so the swallowing is visible at the call site that wants it.
    """
    if not needs:
        return 0
    try:
        with store.engine.begin() as conn:
            return store_needs(conn, needs)
    except Exception:      # noqa: BLE001 — filing a question must never break ingestion
        _log.exception("could not file %d evidence need(s)", len(needs))
        return 0


__all__ = ["close_need", "file_needs", "read_open_needs", "store_needs"]
