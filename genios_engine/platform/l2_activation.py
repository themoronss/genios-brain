"""Per-tenant activation for Layer 2 v2 — two switches, in a table, and one of them is honest
about turning nothing on.

Doc 09's "Activation" section prints the shape and the reason:

    create table if not exists l2_v2_activation (
        org_id text primary key,
        analytic_enabled_at timestamptz,
        patterns_enabled_at timestamptz,
        enabled_by text not null
    );

    Two independent switches — the analytic stratum can run and be validated on a tenant long
    before pattern matching replaces anchor-based detection for them.
    **No global boolean in `platform/config.py`.** `use_domain_compiler=False` has been set in
    no environment since it was written and has left 152 capabilities dark. Do not build a
    second one.

WHAT EACH SWITCH ACTUALLY DOES IN THIS REPO, because they are not symmetric and pretending they
were is how a switch that gates nothing gets believed:

  * :data:`SWITCH_PATTERNS` is a REAL GATE. ``context/patterns`` is a finished package that
    nothing on the drain calls — ``evaluate_org`` is reachable only from
    ``POST /api/org/{id}/patterns/evaluate``. `is_patterns_activated` is what makes
    `context/runner.process_pending` run the L2.6 registry in SHADOW every sweep, which is the
    only way ``pattern_fires`` accumulates the seven days of fire evidence H8 compares against
    anchor-based detection. Off, that pass does not run.

  * :data:`SWITCH_ANALYTIC` is a DECLARATION. Every analytic pass already runs unconditionally
    for every tenant (waves X1-X5), and the runner says why: a metric measured against a clock
    has to keep sampling on a quiet inbox. Gating it on this table would switch the stratum OFF
    for every tenant already on it — a founder-visible regression introduced by an activation
    table, against a gate whose last row is "founder-visible regressions: 0". So this switch
    records WHEN a tenant was declared to be in the pilot and WHO declared it, and
    `scripts/l2_shadow_diff.py` reads it to bound and interpret its window. `EFFECTS` below
    states that in one sentence, and the admin route returns it, so an operator reading the
    console is told what activation did rather than inferring it.

**It starts no work.** `sampler.backfill_history_for_drain` already runs the once-per-tenant
18-month history reconstruction, guarded on history EXISTENCE rather than on a marker. Activation
deliberately does not trigger one: a second backfill path would double the only expensive read in
the layer, and "activate twice" would mean "reconstruct eighteen months twice". Idempotency here
is therefore not only a property of the upsert — it is that this module launches nothing.

**Fail closed on the gate, open on the console.** `is_patterns_activated` and
`patterns_activated_orgs` answer "not activated" for a missing table, an unreadable one or a query
that errored: the failure mode of the lookup is then a tenant that does not get the shadow pass,
which is the state every tenant is in today. `get_l2_activation` and `list_l2_activations` do NOT
swallow — an operator asking "what is the state of the pilot" must see the database error rather
than the word "off".

**Nothing here reads a request.** The writers are called by `api/admin_routes.py` behind
`require_admin` and audited there. This module is the table's vocabulary, not its authorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.l2_activation")

L2_ACTIVATION_TABLE = "l2_v2_activation"

#: The analytic stratum switch. A DECLARATION — see the module docstring and `EFFECTS`.
SWITCH_ANALYTIC = "analytic"
#: The pattern registry switch. A REAL GATE on `context/runner.process_pending`'s shadow pass.
SWITCH_PATTERNS = "patterns"

#: Both, in the order the plan prints them. A caller naming anything else is refused by
#: `require_switch` rather than silently updating no column.
SWITCHES = (SWITCH_ANALYTIC, SWITCH_PATTERNS)

#: What each switch TURNS ON, in one sentence, returned by the admin console's read. An operator
#: who can see that a switch is live and cannot see what it did will assume it did everything.
EFFECTS = {
    SWITCH_ANALYTIC: ("declaration only — the analytic stratum (sampler, trend, cohort, peer "
                      "baseline, comparator, anomaly, gap-reason, importance composition) already "
                      "runs for every tenant; this records the pilot window that "
                      "scripts/l2_shadow_diff.py reads"),
    SWITCH_PATTERNS: ("gates the L2.6 pattern registry shadow pass in "
                      "context/runner.process_pending — pattern_fires accumulates only while "
                      "this is live; no pattern reaches a card (that is pattern_activation, "
                      "per pattern, migration 0100)"),
}

#: Every column the record carries, in one place, so the four reads below cannot select different
#: shapes of the same row.
_COLUMNS = ("org_id, analytic_enabled_at, analytic_disabled_at, patterns_enabled_at, "
            "patterns_disabled_at, enabled_by, notes, updated_at")


def require_switch(switch: str) -> str:
    """The one place a switch name is validated. A typo must be a refusal, not an update of zero
    columns reported as success — which is what a caller-supplied column name interpolated into
    SQL would produce, and is also how an interpolated column name becomes an injection."""
    if switch not in SWITCHES:
        raise ValueError(f"unknown L2 v2 switch {switch!r}; expected one of {SWITCHES}")
    return switch


@dataclass(frozen=True)
class L2Activation:
    """One tenant's pilot record: which switches are on, since when, who turned them on, and why.

    Both switches live on one row rather than one row per switch, so "is this tenant in the
    pilot" is a single read and a tenant can never be half-present in the table.
    """

    org_id: str
    enabled_by: str
    analytic_enabled_at: datetime | None = None
    analytic_disabled_at: datetime | None = None
    patterns_enabled_at: datetime | None = None
    patterns_disabled_at: datetime | None = None
    notes: str | None = None
    updated_at: datetime | None = None

    def live(self, switch: str) -> bool:
        """Whether one switch is on RIGHT NOW. A record exists for tenants switched off too —
        that is the point of keeping the row — so every read asks this, never `record is not
        None`."""
        require_switch(switch)
        return (self.enabled_at(switch) is not None
                and self.disabled_at(switch) is None)

    def enabled_at(self, switch: str) -> datetime | None:
        return (self.analytic_enabled_at if require_switch(switch) == SWITCH_ANALYTIC
                else self.patterns_enabled_at)

    def disabled_at(self, switch: str) -> datetime | None:
        return (self.analytic_disabled_at if require_switch(switch) == SWITCH_ANALYTIC
                else self.patterns_disabled_at)

    @property
    def analytic_live(self) -> bool:
        return self.live(SWITCH_ANALYTIC)

    @property
    def patterns_live(self) -> bool:
        return self.live(SWITCH_PATTERNS)

    def as_record(self) -> dict:
        """The console's shape. `effect` travels beside `live` deliberately: a switch an operator
        can see is on, without being told what it turned on, will be assumed to have turned on
        everything — and one of these two switches turns on nothing at all."""
        def _iso(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None
        return {
            "org_id": self.org_id, "enabled_by": self.enabled_by, "notes": self.notes,
            "updated_at": _iso(self.updated_at),
            "switches": {
                switch: {"live": self.live(switch),
                         "enabled_at": _iso(self.enabled_at(switch)),
                         "disabled_at": _iso(self.disabled_at(switch)),
                         "effect": EFFECTS[switch]}
                for switch in SWITCHES},
        }


def _record(row) -> L2Activation:
    return L2Activation(
        org_id=row.org_id, enabled_by=row.enabled_by, notes=row.notes,
        analytic_enabled_at=row.analytic_enabled_at,
        analytic_disabled_at=row.analytic_disabled_at,
        patterns_enabled_at=row.patterns_enabled_at,
        patterns_disabled_at=row.patterns_disabled_at,
        updated_at=row.updated_at)


def _live_predicate(switch: str) -> str:
    """`where` fragment for one switch, built from a VALIDATED name. Never from caller text."""
    column = require_switch(switch)
    return f"{column}_enabled_at is not null and {column}_disabled_at is null"


# ── the drain's read: fail closed ────────────────────────────────────────────────────────────

def is_patterns_activated(engine, org_id: str) -> bool:
    """Whether the L2.6 shadow pass runs for ONE tenant on this drain.

    Fail-closed on every error, and this is the read on the hot path: the cost of a wrong `False`
    is a sweep that does not accumulate fire evidence, which is where every tenant is today; the
    cost of a wrong `True` is an unbudgeted graph read on a tenant nobody chose.
    """
    if engine is None:
        return False
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                f"select 1 from {L2_ACTIVATION_TABLE} where org_id = :o "
                f"and {_live_predicate(SWITCH_PATTERNS)}"), {"o": org_id}).first() is not None
    except Exception as exc:      # noqa: BLE001 — an unreadable switch is an OFF switch
        _log.warning("could not read %s for org=%s, treating patterns as off: %s",
                     L2_ACTIVATION_TABLE, org_id, exc)
        return False


def activated_orgs(engine, switch: str) -> frozenset[str]:
    """Every org with ONE switch live. Empty for any reason it cannot be read.

    One query for all tenants rather than one per tenant, for the same reason L1's set read
    exists: a cross-org tick asks this for every connection it holds.
    """
    predicate = _live_predicate(switch)
    if engine is None:
        return frozenset()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return frozenset(row[0] for row in conn.execute(text(
                f"select org_id from {L2_ACTIVATION_TABLE} where {predicate}")))
    except Exception as exc:      # noqa: BLE001
        _log.warning("could not read %s, treating every tenant as not activated: %s",
                     L2_ACTIVATION_TABLE, exc)
        return frozenset()


# ── the console's reads: NOT fail-closed ─────────────────────────────────────────────────────

def get_l2_activation(engine, org_id: str) -> L2Activation | None:
    """One tenant's FULL record, live or not — the read an operator and the H8 report need.

    Returns a record for a tenant whose switches have been turned OFF, whose `live()` is False;
    `None` only for a tenant that was never in the pilot at all. Deliberately not fail-closed:
    this feeds a console and a gate report, and both must see a database error rather than the
    word "off".
    """
    if engine is None:
        return None
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text(
            f"select {_COLUMNS} from {L2_ACTIVATION_TABLE} where org_id = :o"),
            {"o": org_id}).first()
    return _record(row) if row is not None else None


def list_l2_activations(engine, *, include_disabled: bool = False) -> tuple[L2Activation, ...]:
    """Every pilot record, newest declaration first.

    `include_disabled` defaults False so the ordinary question — "who is on the L2 v2 pilot" — is
    answered without an operator filtering a mixed list by eye. A row counts as live when EITHER
    switch is live: a tenant whose patterns were switched off last Tuesday but whose declaration
    stands is still in the pilot, and dropping them from the list would hide the window the H8
    report is read against.
    """
    if engine is None:
        return ()
    from sqlalchemy import text
    where = "" if include_disabled else (
        f"where ({_live_predicate(SWITCH_ANALYTIC)}) or ({_live_predicate(SWITCH_PATTERNS)})")
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"select {_COLUMNS} from {L2_ACTIVATION_TABLE} {where} "
            "order by updated_at desc, org_id")).all()
    return tuple(_record(r) for r in rows)


# ── the writers ──────────────────────────────────────────────────────────────────────────────

def activate(engine, org_id: str, *, switch: str, by: str, notes: str | None = None,
             at: datetime | None = None) -> L2Activation:
    """Switch ONE switch on for ONE tenant. Idempotent on a LIVE switch: the ORIGINAL enabling
    timestamp is kept.

    Keeping the first timestamp rather than refreshing it is the whole point of storing it: "since
    when has this tenant been in the pilot" is the question a seven-day diff is read against, and
    an upsert that refreshed it would answer with the date of the last click. Re-activating a
    switch that was turned OFF is the opposite case and takes the new instant — that is a new
    pilot period, and dating it from the first would hand the report a window containing days the
    switch was down.

    `notes` follows the same rule with one softening, copied from L1's activation: a new note
    FILLS IN a reason that was left blank and never overwrites one already there. Changing why a
    tenant is in the pilot is its own decision, and a double-click on a form is not it.

    Writes nothing else. In particular it starts no backfill — see the module docstring.
    """
    column = require_switch(switch)
    other = SWITCH_PATTERNS if column == SWITCH_ANALYTIC else SWITCH_ANALYTIC
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    table = L2_ACTIVATION_TABLE
    with engine.begin() as conn:
        conn.execute(text(
            f"insert into {table} (org_id, {column}_enabled_at, {column}_disabled_at, "
            f"  {other}_enabled_at, {other}_disabled_at, enabled_by, notes, updated_at) "
            "values (:o, :at, null, null, null, :by, :notes, :at) "
            "on conflict (org_id) do update set "
            # `case` on the STORED state: a live switch keeps its first enabling, a switched-off
            # one takes the new instant. One statement rather than read-then-write so two
            # operators clicking at once cannot interleave into a half-updated row.
            f"  {column}_enabled_at = case "
            f"      when {table}.{column}_enabled_at is not null "
            f"       and {table}.{column}_disabled_at is null "
            f"      then {table}.{column}_enabled_at else excluded.{column}_enabled_at end, "
            f"  {column}_disabled_at = null, "
            # `coalesce(STORED, new)`, not the other way round: an activation may FILL IN a blank
            # reason and must never silently rewrite one that is already there.
            f"  enabled_by = coalesce({table}.enabled_by, excluded.enabled_by), "
            f"  notes = coalesce({table}.notes, excluded.notes), "
            "   updated_at = excluded.updated_at"),
            {"o": org_id, "at": at, "by": by, "notes": notes})
        row = conn.execute(text(f"select {_COLUMNS} from {table} where org_id = :o"),
                           {"o": org_id}).first()
    return _record(row)


def deactivate(engine, org_id: str, *, switch: str, by: str = "unrecorded",
               at: datetime | None = None) -> bool:
    """Switch ONE switch off. True when a LIVE switch was switched off.

    The row is STAMPED, not deleted, and `enabled_at` is left where it was: H8 reads a seven-day
    window and has to be able to say "the pattern pass was switched off on day four", which a
    missing row cannot say.

    `enabled_by` is NOT touched, and `by` is logged rather than stored. The column is not-null and
    already holds the person who put this tenant in the pilot, which is the attribution that
    matters; overwriting it on the way out would lose that in exchange for recording a click.
    """
    column = require_switch(switch)
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    with engine.begin() as conn:
        switched_off = conn.execute(text(
            f"update {L2_ACTIVATION_TABLE} set {column}_disabled_at = :at, updated_at = :at "
            f"where org_id = :o and {_live_predicate(column)}"),
            {"o": org_id, "at": at}).rowcount > 0
    if switched_off:
        _log.info("L2 v2 %s switch DEACTIVATED for org=%s by=%s", column, org_id, by)
    return switched_off


__all__ = ["EFFECTS", "L2Activation", "L2_ACTIVATION_TABLE", "SWITCHES", "SWITCH_ANALYTIC",
           "SWITCH_PATTERNS", "activate", "activated_orgs", "deactivate", "get_l2_activation",
           "is_patterns_activated", "list_l2_activations", "require_switch"]
