"""Per-tenant activation for the Layer 1 semantic lane — the strangler fig's switch.

Doc 04's W4 reverse prompt is explicit about the shape of this and about why:

    Activation is PER TENANT via a table `l1_semantic_activation(org_id, enabled_at, enabled_by)`.
    NOT a global boolean in config.py. Reason: config.py:110 already carries
    `use_domain_compiler=False` which is set in NO environment and has left 152 capabilities dark.
    Do not repeat that pattern.

A global flag has two states and both are wrong for a migration: off means the new path is never
exercised by anything real, and on means every tenant's bill changes on one deploy. A per-tenant
row means the first org can be switched on, watched, and switched off again by a person who knows
which org they are talking about.

**Fail closed, always.** No database, an unreadable table, a query that errors — every one of them
answers "not activated". The failure mode of this lookup is a tenant who does not get the new
extraction, which is the state they are in today; the opposite default is an unbudgeted model call
on every message of every sweep, discovered on an invoice.

**W10 / G10 — the pilot.** The build order's "activation rule" prints this table with a fourth
column, `notes`, and the definition of done that goes with it: *"the unit is done when its
acceptance command passes against a real tenant with activation enabled. Built but not enabled is
not done."* Two things follow, and migration 0090 carries both. `notes` is stored, because a
pilot is a decision about one customer's bill and one customer's extraction quality and "who" and
"when" without "why" leaves the next operator guessing. And a deactivation now STAMPS the row
(`disabled_at`) instead of deleting it: G10 compares seven days of two extraction paths, and a
window that silently contains a mid-week switch-off is a diff nobody can read.

**Nothing here reads a request.** The writers are called by `api/admin_routes.py` behind
`require_admin` (owner JWT, superadmin email) and audited there. This module is the table's
vocabulary, not its authorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.activation")

L1_SEMANTIC_TABLE = "l1_semantic_activation"

#: Every column the record carries, in one place, so the three reads below cannot select
#: different shapes of the same row.
_COLUMNS = "org_id, enabled_at, enabled_by, notes, disabled_at, disabled_by"

#: What "activated" MEANS in SQL. A deactivation keeps the row and stamps `disabled_at`
#: (migration 0090) rather than deleting it, because G10 is a seven-day comparison and a window
#: that silently contains a mid-week switch-off is a diff nobody can read. Every read that
#: answers "is this tenant on the new lane" therefore filters on this predicate, and it is a
#: constant rather than four copies of the same `where` clause.
_LIVE = "disabled_at is null"


@dataclass(frozen=True)
class SemanticActivation:
    """One tenant's activation record: who turned it on, when, why, and whether it is still on.

    `enabled_by` is not decoration. A tenant whose bill changed needs an answer to "who decided
    this and when", and an activation table that stored only the org id can produce neither.
    `notes` is the plan's printed fourth column and answers the third question — "why this
    tenant" — which is the one that distinguishes a deliberate design partner from a leftover
    from a debugging session.
    """

    org_id: str
    enabled_at: datetime
    enabled_by: str
    notes: str | None = None
    disabled_at: datetime | None = None
    disabled_by: str | None = None

    @property
    def live(self) -> bool:
        """Whether this tenant is on the semantic lane RIGHT NOW. A record exists for tenants
        that were switched off too — that is the point of keeping the row — so the set reads and
        the wiring gate ask this, never `record is not None`."""
        return self.disabled_at is None


def _record(row) -> SemanticActivation:
    return SemanticActivation(org_id=row.org_id, enabled_at=row.enabled_at,
                              enabled_by=row.enabled_by, notes=row.notes,
                              disabled_at=row.disabled_at, disabled_by=row.disabled_by)


def semantic_activated_orgs(engine) -> frozenset[str]:
    """Every org with the L1 semantic lane switched on. Empty for any reason it cannot be read.

    Read once per sweep rather than once per org: a cross-org tick asks this for every connection
    it holds, and one query answering for all of them beats one query per tenant.
    """
    if engine is None:
        return frozenset()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return frozenset(row[0] for row in conn.execute(text(
                f"select org_id from {L1_SEMANTIC_TABLE} where {_LIVE}")))
    except Exception as exc:      # noqa: BLE001 — an unreadable switch is an OFF switch
        _log.warning("could not read %s, treating every tenant as not activated: %s",
                     L1_SEMANTIC_TABLE, exc)
        return frozenset()


def is_semantic_activated(engine, org_id: str) -> bool:
    """Whether ONE tenant is activated. Same fail-closed contract as the set read."""
    if engine is None:
        return False
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                f"select 1 from {L1_SEMANTIC_TABLE} where org_id=:o and {_LIVE}"),
                {"o": org_id}).first() is not None
    except Exception as exc:      # noqa: BLE001
        _log.warning("could not read %s for org=%s: %s", L1_SEMANTIC_TABLE, org_id, exc)
        return False


def get_semantic_activation(engine, org_id: str) -> SemanticActivation | None:
    """One tenant's FULL record, live or not — the read an operator console needs.

    Distinct from `is_semantic_activated` on purpose: that one answers the pipeline's yes/no on
    the hot path, this one answers a human's "who switched this on, when, why, and is it still
    on". Returns a record for a tenant that has been switched OFF, whose `live` is False; None
    only for a tenant that was never in the pilot at all.

    NOT fail-closed, and deliberately so: this feeds a console, not the lane. An operator asking
    "what is the state of the pilot" must see the database error rather than the word "off".
    """
    if engine is None:
        return None
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text(
            f"select {_COLUMNS} from {L1_SEMANTIC_TABLE} where org_id=:o"), {"o": org_id}).first()
    return _record(row) if row is not None else None


def list_semantic_activations(engine, *, include_disabled: bool = False
                              ) -> tuple[SemanticActivation, ...]:
    """Every pilot record, newest enablement first. The console's list.

    `include_disabled` defaults False so the ordinary question — "who is on the new lane" —
    is answered without an operator having to filter a mixed list by eye and mistake a tenant
    switched off last Tuesday for a live one.
    """
    if engine is None:
        return ()
    from sqlalchemy import text
    where = "" if include_disabled else f"where {_LIVE}"
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"select {_COLUMNS} from {L1_SEMANTIC_TABLE} {where} order by enabled_at desc, org_id"
        )).all()
    return tuple(_record(r) for r in rows)


def activate_semantic(engine, org_id: str, *, by: str, notes: str | None = None,
                      at: datetime | None = None) -> SemanticActivation:
    """Switch one tenant on. Idempotent on a LIVE row: re-activating keeps the ORIGINAL record.

    Keeping the first row rather than overwriting it is the point of storing `enabled_at` at all —
    "since when has this tenant been on the new lane" is the question a diff between the two
    extraction paths is read against, and an upsert that refreshed the timestamp would answer it
    with the date of the last click instead.

    Re-activating a tenant that was switched OFF is the opposite case and takes the new values:
    that is a new pilot period with a new decision behind it, and dating it from the first period
    would hand the shadow diff a window containing days the lane did not run.

    `notes` follows the same rule with one softening: on a live row a new note FILLS IN a reason
    that was left blank but never overwrites one that is already there. Changing why a tenant is
    in the pilot is its own decision, and a double-click on a form is not it.
    """
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text(
            f"insert into {L1_SEMANTIC_TABLE} (org_id, enabled_at, enabled_by, notes) "
            "values (:o, :at, :by, :notes) on conflict (org_id) do update set "
            # `case` on the STORED disabled_at: live rows keep their first enabling, revived
            # rows take the new one. Written as one statement rather than a read-then-write so
            # two operators clicking at once cannot interleave into a half-updated row.
            f"  enabled_at = case when {L1_SEMANTIC_TABLE}.disabled_at is null "
            f"                    then {L1_SEMANTIC_TABLE}.enabled_at else excluded.enabled_at end,"
            f"  enabled_by = case when {L1_SEMANTIC_TABLE}.disabled_at is null "
            f"                    then {L1_SEMANTIC_TABLE}.enabled_by else excluded.enabled_by end,"
            # `coalesce(STORED, new)` on a live row, not the other way round: an activation
            # call may FILL IN a reason that was left blank, and must never silently rewrite one
            # that is already there. Changing why a tenant is in the pilot is its own act.
            f"  notes      = case when {L1_SEMANTIC_TABLE}.disabled_at is null "
            f"                    then coalesce({L1_SEMANTIC_TABLE}.notes, excluded.notes) "
            "                     else excluded.notes end,"
            "  disabled_at = null, disabled_by = null"),
            {"o": org_id, "at": at, "by": by, "notes": notes})
        row = conn.execute(text(
            f"select {_COLUMNS} from {L1_SEMANTIC_TABLE} where org_id=:o"), {"o": org_id}).first()
    return _record(row)


def deactivate_semantic(engine, org_id: str, *, by: str = "unrecorded",
                        at: datetime | None = None) -> bool:
    """Switch one tenant off. True when a LIVE row was switched off — the rollback half of a
    strangler fig, which is not optional: a migration you cannot reverse is a cutover with extra
    steps.

    The row is STAMPED, not deleted. Deleting made the off-switch instant and the history blank;
    G10 reads a seven-day window and has to be able to say "this tenant was switched off on day
    four", which a missing row cannot say. `semantic_activated_orgs` filters the stamped rows out,
    so the lane sees exactly what a delete would have left it.
    """
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    with engine.begin() as conn:
        return conn.execute(text(
            f"update {L1_SEMANTIC_TABLE} set disabled_at=:at, disabled_by=:by "
            f"where org_id=:o and {_LIVE}"),
            {"o": org_id, "at": at, "by": by}).rowcount > 0


__all__ = ["L1_SEMANTIC_TABLE", "SemanticActivation", "activate_semantic", "deactivate_semantic",
           "get_semantic_activation", "is_semantic_activated", "list_semantic_activations",
           "semantic_activated_orgs"]
