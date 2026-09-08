"""Per-tenant, per-FEATURE activation for Layer 4 — five switches, no global flag.

Doc 07's G-07 prints the shape and doc 00's Law 5 prints the reason:

    create table if not exists l4_activation (
        org_id  text not null,
        feature text not null,   -- 'roster_v2'|'ranking_v2'|'bundle'|'critique'|'brief'
        enabled_at timestamptz not null default now(),
        enabled_by text not null,
        primary key (org_id, feature)
    );

**WHY FIVE SWITCHES AND NOT ONE.** The five features are five different amounts of behaviour and
they land in five different waves. `roster_v2` (Z1) replaces the six hardcoded units at
`reason/adapters/expertise.py:189` with the staged roster; `ranking_v2` (Z3) gives the utility
formula its sixth component and demotes the priority override from a verdict to a 70/30 prior;
`bundle` (Z4) generates the narrative for published decisions; `critique` and `brief` (Z6) open the
two outbound seams. A one-row-per-tenant boolean cannot express "the roster is awake here, the
narrative is not" — which is the exact state every pilot tenant passes through between Z1 and Z4 —
and it would make the gates unreadable, because K1a and K4 measure the SAME tenant in two different
states within one fortnight.

**WHY NOT A CONFIG FLAG.** `platform/config.py` still carries `use_domain_compiler: bool = False`,
set in no environment, never true anywhere, and the codebase's own comments record the cost: 152
capabilities dark. That is the standing counterexample Law 5 is written against. Layer 1 answered it
with `platform/activation.py`, Layer 2 with `platform/l2_activation.py` and Layer 3 with
`platform/l3_activation.py`; this module is their Layer 4 sibling and follows both of their
properties exactly.

**FAIL CLOSED ON THE GATE, OPEN ON THE CONSOLE.** `is_l4_activated`, `l4_activated_orgs` and
`activated_features` answer "not activated" for a missing database, an unreadable table or a query
that errored. The failure mode is then a tenant whose engine behaves exactly as it behaves today —
which is the state every tenant is in — because all five features are ADDITIVE. `get_l4_activation`
and `list_l4_activations` do NOT swallow: an operator asking "what is the state of the pilot" must
see the database error rather than the word "off".

**A DEACTIVATION STAMPS, IT DOES NOT DELETE.** K7 reads a seven-day window, and a window that
silently contains a mid-week switch-off is a diff nobody can read. Deleting made the off-switch
instant and the history blank; the reads filter stamped rows out, so the engine sees exactly what a
delete would have left it.

**WHAT ACTIVATION MUST NOT BE USED TO SKIP.** Doc 08's wave order is not advisory: `ranking_v2`
before Z1 has woken the roster gives the six-component formula five units to read, and `bundle`
before Z3 narrates a decision the formula never made. `EFFECTS` says so where an operator reads it,
and the wave each feature belongs to travels beside its name in `FEATURE_WAVES` for the same reason.

**Nothing here reads a request.** The writers are for the admin path behind `require_admin`, audited
there — the way `api/admin_routes.py` already drives L1's, L2's and L3's switches. This module is the
table's vocabulary, not its authorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.l4_activation")

L4_ACTIVATION_TABLE = "l4_activation"

#: Z1 — the staged unit roster runs through the Unit Selector instead of the six ids
#: `reason/adapters/expertise.py:189` returns literally.
FEATURE_ROSTER_V2 = "roster_v2"
#: Z3 — six-component utility including L1/L2's importance, and `priority_override_bp` demoted from
#: a verdict to a 70/30 prior with the divergence recorded.
FEATURE_RANKING_V2 = "ranking_v2"
#: Z4 — the `ReasoningBundle` narrative is generated for published decisions, gauntlet and all.
FEATURE_BUNDLE = "bundle"
#: Z6 — the critique seam scores an external agent's proposed action. Advisory, always.
FEATURE_CRITIQUE = "critique"
#: Z6 — the book-level daily re-rank that carries `rank_components` on every entry.
FEATURE_BRIEF = "brief"

#: The five features doc 07 names, in WAVE order rather than alphabetical order — the order is the
#: only safe order to switch them on in, and a list that read `bundle, brief, critique, ranking_v2,
#: roster_v2` would put the narrative first. A caller naming anything else is REFUSED by
#: `require_feature` rather than silently writing a row nothing will ever read, which is the failure
#: mode a free-text column invites and which looks exactly like an activated tenant right up until
#: nothing happens.
L4_FEATURES = (FEATURE_ROSTER_V2, FEATURE_RANKING_V2, FEATURE_BUNDLE, FEATURE_CRITIQUE,
               FEATURE_BRIEF)

#: Which wave builds each feature. Carried in code rather than in a doc because it is what makes
#: `PRECONDITIONS` checkable by eye: a feature is safe to switch on when the features its wave
#: depends on are already on for that tenant.
FEATURE_WAVES = {
    FEATURE_ROSTER_V2: "Z1",
    FEATURE_RANKING_V2: "Z3",
    FEATURE_BUNDLE: "Z4",
    FEATURE_CRITIQUE: "Z6",
    FEATURE_BRIEF: "Z6",
}

#: The features that should already be live on a tenant before this one is switched on. NOT
#: enforced — this module refuses unknown names and nothing else, because an operator debugging a
#: pilot at 2am needs to be able to turn one thing on in isolation. It is REPORTED, on every write
#: and every console read, so a wave order violated on purpose is visible and one violated by
#: accident is caught by the operator rather than by the K-gate a fortnight later.
PRECONDITIONS = {
    FEATURE_ROSTER_V2: (),
    FEATURE_RANKING_V2: (FEATURE_ROSTER_V2,),
    FEATURE_BUNDLE: (FEATURE_RANKING_V2,),
    FEATURE_CRITIQUE: (FEATURE_RANKING_V2,),
    FEATURE_BRIEF: (FEATURE_RANKING_V2,),
}

#: What flipping ONE feature on ACTUALLY does, in one sentence, returned beside `live` wherever a
#: console reads this table. An operator who can see a switch is on and cannot see what it turned on
#: will assume it turned on everything.
EFFECTS = {
    FEATURE_ROSTER_V2: (
        "the reasoning orchestrator plans the STAGED UNIT ROSTER through the Unit Selector for this "
        "tenant instead of the six units the compiled lane hardcodes; it changes which units run "
        "and therefore which findings exist, and it does not change any published metric name"),
    FEATURE_RANKING_V2: (
        "the decision maker scores candidates on SIX components including importance, and demotes "
        "priority_override_bp from a verdict to a 70/30 prior with the divergence recorded on every "
        "decision; only meaningful once roster_v2 is live, because the sixth component's inputs "
        "come from units the old lane does not run"),
    FEATURE_BUNDLE: (
        "published decisions for this tenant carry a ReasoningBundle narrative — generated AFTER "
        "the decision is fixed, numbers substituted by code, falling back to a labelled template; "
        "it can never change what was decided, and it narrates a decision the formula made only "
        "once ranking_v2 is live"),
    FEATURE_CRITIQUE: (
        "the critique seam will score an external agent's proposed action for this tenant and "
        "return an ADVISORY verdict; GeniOS scores and the agent executes — the verdict cannot be "
        "made binding, by construction"),
    FEATURE_BRIEF: (
        "this tenant's daily brief is re-ranked at book level with rank_components recorded on "
        "every entry, so 'why #1 today' is answerable from the record rather than from a re-run"),
}

#: Every column the record carries, in one place, so the reads below cannot select different shapes
#: of the same row.
_COLUMNS = "org_id, feature, enabled_at, enabled_by, notes, disabled_at, disabled_by, updated_at"

#: What "activated" MEANS in SQL. One constant rather than six copies of the same `where` clause, so
#: a read cannot forget that a stamped-off row is still a row.
_LIVE = "disabled_at is null"


def require_feature(feature: str) -> str:
    """The one place a feature name is validated.

    A typo must be a refusal, not a row written under `bundel` that reads as an activated tenant and
    narrates nothing. This is `l3_activation.require_domain`'s counterpart and exists for the same
    reason: the value reaches a `where` clause as a bound parameter, but it also reaches an
    operator's eyes as the answer to "is this tenant on".
    """
    if feature not in L4_FEATURES:
        raise ValueError(f"unknown Layer 4 feature {feature!r}; expected one of {L4_FEATURES}")
    return feature


@dataclass(frozen=True)
class L4Activation:
    """One (tenant, feature) pilot record: who turned it on, when, why, and whether it is still on."""

    org_id: str
    feature: str
    enabled_at: datetime
    enabled_by: str
    notes: str | None = None
    disabled_at: datetime | None = None
    disabled_by: str | None = None
    updated_at: datetime | None = None

    @property
    def live(self) -> bool:
        """Whether this tenant's feature is running RIGHT NOW. A record exists for tenants that were
        switched off too — that is the point of keeping the row — so every read asks this, never
        `record is not None`."""
        return self.disabled_at is None

    def as_record(self) -> dict:
        """The console's shape. `effect` and `wave` travel beside `live` deliberately: see
        `EFFECTS`."""
        def _iso(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None
        return {"org_id": self.org_id, "feature": self.feature, "live": self.live,
                "enabled_at": _iso(self.enabled_at), "enabled_by": self.enabled_by,
                "disabled_at": _iso(self.disabled_at), "disabled_by": self.disabled_by,
                "notes": self.notes, "updated_at": _iso(self.updated_at),
                "wave": FEATURE_WAVES[self.feature], "effect": EFFECTS[self.feature]}


def _record(row) -> L4Activation:
    return L4Activation(org_id=row.org_id, feature=row.feature, enabled_at=row.enabled_at,
                        enabled_by=row.enabled_by, notes=row.notes,
                        disabled_at=row.disabled_at, disabled_by=row.disabled_by,
                        updated_at=row.updated_at)


# ── the engine's reads: fail closed ──────────────────────────────────────────────────────────

def is_l4_activated(engine, org_id: str, feature: str) -> bool:
    """Whether ONE tenant's ONE feature is live on this run. The hot-path read.

    Fail-closed on every error. The cost of a wrong `False` is a tenant whose engine behaves exactly
    as every tenant's engine behaves today; the cost of a wrong `True` is a narrative, a re-rank or a
    changed roster on a tenant nobody chose, on a path whose whole justification is that it was
    watched.
    """
    require_feature(feature)
    if engine is None:
        return False
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                f"select 1 from {L4_ACTIVATION_TABLE} where org_id = :o and feature = :f "
                f"and {_LIVE}"), {"o": org_id, "f": feature}).first() is not None
    except Exception as exc:      # noqa: BLE001 — an unreadable switch is an OFF switch
        _log.warning("could not read %s for org=%s feature=%s, treating as not activated: %s",
                     L4_ACTIVATION_TABLE, org_id, feature, exc)
        return False


def l4_activated_orgs(engine, feature: str) -> frozenset[str]:
    """Every org with ONE feature live. Empty for any reason it cannot be read.

    One query for all tenants rather than one per tenant, for the same reason all three sibling
    modules carry a set read: a cross-org sweep asks this for every connection it holds.
    """
    require_feature(feature)
    if engine is None:
        return frozenset()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return frozenset(row[0] for row in conn.execute(text(
                f"select org_id from {L4_ACTIVATION_TABLE} where feature = :f and {_LIVE}"),
                {"f": feature}))
    except Exception as exc:      # noqa: BLE001
        _log.warning("could not read %s for feature=%s, treating every tenant as not activated: %s",
                     L4_ACTIVATION_TABLE, feature, exc)
        return frozenset()


def activated_features(engine, org_id: str) -> frozenset[str]:
    """Which features are live for ONE tenant — the read a run needs to bound itself.

    Distinct from calling `is_l4_activated` five times: a reasoning run asks "what is on for this
    tenant" ONCE, and five round trips to answer one question is five times the chance of a partial
    answer — a run that saw `bundle` on and `ranking_v2` off because a connection blipped between
    two of them would narrate a decision the formula did not make. Fail-closed, same as its siblings.
    """
    if engine is None:
        return frozenset()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                f"select feature from {L4_ACTIVATION_TABLE} where org_id = :o and {_LIVE}"),
                {"o": org_id})
            # A row whose feature is not in `L4_FEATURES` is filtered rather than returned: the
            # column is free text by design (see the migration), and an engine handed a feature it
            # has no code for would fail at the call site instead of here.
            return frozenset(row[0] for row in rows if row[0] in L4_FEATURES)
    except Exception as exc:      # noqa: BLE001
        _log.warning("could not read %s for org=%s, treating every feature as not activated: %s",
                     L4_ACTIVATION_TABLE, org_id, exc)
        return frozenset()


def missing_preconditions(engine, org_id: str, feature: str) -> tuple[str, ...]:
    """Which features `feature` expects to be live on this tenant and are NOT. Reported, not enforced.

    Doc 08's wave order is real — `bundle` before `ranking_v2` narrates a decision the formula never
    made — but enforcing it here would mean an operator cannot switch one thing on in isolation to
    debug it, and every enforcement of an ordering eventually meets a legitimate exception at 2am.
    So the order is REPORTED: on the write, and on every console read. A violation on purpose stays
    possible and stays visible; a violation by accident is caught by the operator rather than by the
    gate a fortnight later.
    """
    require_feature(feature)
    live = activated_features(engine, org_id)
    return tuple(item for item in PRECONDITIONS[feature] if item not in live)


# ── the console's reads: NOT fail-closed ─────────────────────────────────────────────────────

def get_l4_activation(engine, org_id: str, feature: str) -> L4Activation | None:
    """One (tenant, feature) FULL record, live or not — the read an operator and K7 need.

    Returns a record for a pair that has been switched OFF, whose `live` is False; `None` only for a
    pair that was never in the pilot at all. Deliberately not fail-closed: this feeds a console and a
    gate report, and both must see a database error rather than the word "off".
    """
    require_feature(feature)
    if engine is None:
        return None
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text(
            f"select {_COLUMNS} from {L4_ACTIVATION_TABLE} where org_id = :o and feature = :f"),
            {"o": org_id, "f": feature}).first()
    return _record(row) if row is not None else None


def list_l4_activations(engine, *, include_disabled: bool = False) -> tuple[L4Activation, ...]:
    """Every pilot record, newest enablement first. The console's list.

    `include_disabled` defaults False so the ordinary question — "who is on the Layer 4 pilot" — is
    answered without an operator filtering a mixed list by eye and mistaking a tenant switched off
    last Tuesday for a live one.
    """
    if engine is None:
        return ()
    from sqlalchemy import text
    where = "" if include_disabled else f"where {_LIVE}"
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"select {_COLUMNS} from {L4_ACTIVATION_TABLE} {where} "
            "order by enabled_at desc, org_id, feature")).all()
    return tuple(_record(r) for r in rows)


# ── the writers ──────────────────────────────────────────────────────────────────────────────

def activate(engine, org_id: str, *, feature: str, by: str, notes: str | None = None,
             at: datetime | None = None) -> L4Activation:
    """Switch ONE feature on for ONE tenant. Idempotent on a LIVE row: the ORIGINAL enabling stands.

    Keeping the first `enabled_at` rather than refreshing it is the point of storing it: "since when
    has this tenant been on the pilot" is what the seven-day K7 report is read against, and an upsert
    that refreshed it would answer with the date of the last click.

    Re-activating a pair that was switched OFF is the opposite case and takes the new values — that
    is a new pilot period with a new decision behind it, and dating it from the first would hand the
    report a window containing days the feature was not running.

    `notes` follows the same rule with one softening, copied from all three siblings: on a live row a
    new note FILLS IN a reason left blank and never overwrites one already there. Changing why a
    tenant is in the pilot is its own decision, and a double-click on a form is not it.

    Writes nothing else, and starts nothing. In particular it triggers no reasoning run and no
    backfill: the next ordinary run reads the switch. An activation that kicked off a sweep would
    make "activate twice" mean "reason over the tenant twice".
    """
    require_feature(feature)
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    table = L4_ACTIVATION_TABLE
    with engine.begin() as conn:
        conn.execute(text(
            f"insert into {table} (org_id, feature, enabled_at, enabled_by, notes, updated_at) "
            "values (:o, :f, :at, :by, :notes, :at) "
            "on conflict (org_id, feature) do update set "
            # `case` on the STORED disabled_at: a live row keeps its first enabling, a revived one
            # takes the new instant. One statement rather than read-then-write, so two operators
            # clicking at once cannot interleave into a half-updated row.
            f"  enabled_at = case when {table}.disabled_at is null "
            f"                    then {table}.enabled_at else excluded.enabled_at end, "
            f"  enabled_by = case when {table}.disabled_at is null "
            f"                    then {table}.enabled_by else excluded.enabled_by end, "
            # `coalesce(STORED, new)` on a live row, not the other way round — see the docstring.
            f"  notes = case when {table}.disabled_at is null "
            f"               then coalesce({table}.notes, excluded.notes) else excluded.notes end, "
            "   disabled_at = null, disabled_by = null, updated_at = excluded.updated_at"),
            {"o": org_id, "f": feature, "at": at, "by": by, "notes": notes})
        row = conn.execute(text(
            f"select {_COLUMNS} from {table} where org_id = :o and feature = :f"),
            {"o": org_id, "f": feature}).first()
    return _record(row)


def deactivate(engine, org_id: str, *, feature: str, by: str = "unrecorded",
               at: datetime | None = None) -> bool:
    """Switch ONE feature off. True when a LIVE row was switched off — the rollback half of the flip,
    which is not optional: an activation you cannot reverse is a deploy with extra steps.

    The row is STAMPED, not deleted, and `enabled_at` is left where it was: K7 reads a seven-day
    window and has to be able to say "the narrative was switched off on day four", which a missing
    row cannot say. Every read filters the stamped rows out, so the engine sees exactly what a delete
    would have left it.
    """
    require_feature(feature)
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    with engine.begin() as conn:
        switched_off = conn.execute(text(
            f"update {L4_ACTIVATION_TABLE} set disabled_at = :at, disabled_by = :by, "
            f"updated_at = :at where org_id = :o and feature = :f and {_LIVE}"),
            {"o": org_id, "f": feature, "at": at, "by": by}).rowcount > 0
    if switched_off:
        _log.info("Layer 4 %s DEACTIVATED for org=%s by=%s", feature, org_id, by)
    return switched_off


__all__ = ["EFFECTS", "FEATURE_BRIEF", "FEATURE_BUNDLE", "FEATURE_CRITIQUE", "FEATURE_RANKING_V2",
           "FEATURE_ROSTER_V2", "FEATURE_WAVES", "L4Activation", "L4_ACTIVATION_TABLE",
           "L4_FEATURES", "PRECONDITIONS", "activate", "activated_features", "deactivate",
           "get_l4_activation", "is_l4_activated", "l4_activated_orgs", "list_l4_activations",
           "missing_preconditions", "require_feature"]
