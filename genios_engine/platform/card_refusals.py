"""What the card contract refused, kept where it can be read (STEP-14, `yc2_w27_s14` M43.C4.L-integration.V2.U05; 0222).

Both card writers run `contracts/card_contract` before anything is written — `deliver/pipeline` and `reason/team/emit` —
and a refused card is never written, so `cards` cannot say it existed. A refusal nobody can see is a silent stop: each
is kept here, one row per rule a card broke, and `scripts/pipeline_health` says them per rule. In `platform/` because
two layers write it (`deliver` and `reason`), and neither may import the other.

NEVER RAISES PAST ITS CALLER'S CHOICE: `record` writes on the caller's connection, in its transaction; a caller that
must not fail on a measurement wraps it.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text

from genios_engine.platform.ids import new_id

#: Who refused — closed, as 0222's check is.
PIPELINE = "pipeline"
TEAM = "team"
WRITERS: tuple[str, ...] = (PIPELINE, TEAM)

#: ⛔ ONCE PER WRITER, CARD AND RULE (STEP-14 fix, the crosscheck's findings 3 and 14): a refused signal stays open and
#: is refused again on every pass — a row a pass made the health check count passes, not cards. The first refusal is
#: kept, with what it found and when; the same refusal again adds nothing.
_INSERT = text(
    "insert into card_refusals (org_id, refusal_id, writer, ref, rule, found, refused_at) "
    "select :o, :id, :w, :ref, :rule, :found, coalesce(cast(:at as timestamptz), now()) "
    " where not exists (select 1 from card_refusals where org_id = :o and writer = :w and ref = :ref "
    "                   and rule = :rule)")


def record(conn, *, org_id: str, writer: str, ref: str, refusals: Iterable, at=None) -> int:
    """Keep one row per refusal (`contracts/card_contract.Refusal`) — once per writer, card and rule; returns how
    many were new."""
    if writer not in WRITERS:
        raise ValueError(f"a refusal's writer is one of {WRITERS}, not {writer!r}")
    n = 0
    for r in refusals:
        n += conn.execute(_INSERT, {"o": org_id, "id": new_id("cref"), "w": writer, "ref": str(ref),
                                    "rule": r.rule, "found": str(r.found)[:500], "at": at}).rowcount or 0
    return n


__all__ = ["PIPELINE", "TEAM", "WRITERS", "record"]
