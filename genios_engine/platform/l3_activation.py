"""Per-tenant, per-DOMAIN activation for Layer 3 — the switch Law 5 is written about.

Doc 05's E-03 prints the shape and the doctrine prints the reason:

    create table if not exists l3_activation (
        org_id      text not null,
        domain      text not null,               -- 'admin' first
        enabled_at  timestamptz not null default now(),
        enabled_by  text not null,
        notes       text,
        primary key (org_id, domain)
    );

    The compiler's live pass consults this table — per tenant, per domain — INSTEAD of
    `use_domain_compiler`.

**WHY NOT THE FLAG THAT ALREADY EXISTS.** `platform/config.py` carries
`use_domain_compiler: bool = False`. It is set in no environment, has never been true anywhere, and
the codebase's own comments record the cost: 152 capabilities dark. A global boolean has two states
and both are wrong for an unlock — off means the new path is never exercised by anything real, on
means every tenant's compiled output changes on one deploy. Layer 1 answered this with
`platform/activation.py` and Layer 2 with `platform/l2_activation.py`; this module is their Layer 3
sibling and follows both of their properties exactly.

**AND WHY PER DOMAIN, not per tenant.** V1 scope is the ADMIN corpus only, per Globe's own V1
discipline, while Sales and Customer Support stay compiled, stamped and inactive. A one-row-per-
tenant table cannot express "Admin on, Sales off", and the only remaining way to express it would be
to not ship the Sales corpus — a corpus decision taken by a schema.

**THIS MODULE DOES NOT RETIRE THE GLOBAL FLAG, AND MUST NOT YET.** `use_domain_compiler` is
untouched by this wave. It becomes a read-only kill switch once the first pilot passes J5, and is
deleted only after J5 has held for fourteen days (doc 06). Deleting the kill switch in the same
change that installs the thing it kills leaves a cutover with no way back.

**WHAT ACTIVATION MUST NOT BE USED TO SKIP.** Y1 (typed consumers) comes before Y5 (this flip), and
that is the one ordering doc 06 says must not be violated. Flipping a tenant on before rules,
heuristics, mental models and frameworks have runtime readers produces the fake success
`reason/adapters/expertise.py` warns about in its own docstring — *"activation would LOOK successful
while producing generic output"*. `EFFECTS` says so where an operator reads it.

**FAIL CLOSED ON THE GATE, OPEN ON THE CONSOLE.** `is_l3_activated`, `l3_activated_orgs` and
`activated_domains` answer "not activated" for a missing database, an unreadable table or a query
that errored: the failure mode is then a tenant that keeps compiling exactly as it does today, which
is the state every tenant is in. `get_l3_activation` and `list_l3_activations` do NOT swallow — an
operator asking "what is the state of the pilot" must see the database error rather than the word
"off".

**A DEACTIVATION STAMPS, IT DOES NOT DELETE.** J5 reads a seven-day window, and a window that
silently contains a mid-week switch-off is a diff nobody can read. Deleting made the off-switch
instant and the history blank; the reads filter stamped rows out, so the compiler sees exactly what
a delete would have left it.

**Nothing here reads a request.** The writers are for an admin path behind `require_admin`, audited
there — the way `api/admin_routes.py` already drives L1's and L2's switches. This module is the
table's vocabulary, not its authorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.l3_activation")

L3_ACTIVATION_TABLE = "l3_activation"

#: V1 scope. The Admin corpus is the one the plan activates first (371 authored files, 21 unrouted
#: capabilities being routed in Y2), and it is the domain J5 measures.
DOMAIN_ADMIN = "admin"
#: Compiled and stamped, deliberately not activated in V1. Named here so a pilot for them is a
#: decision somebody takes rather than a string somebody types.
DOMAIN_SALES = "sales"
DOMAIN_CUSTOMER_SUPPORT = "customer_support"

#: THE AUTHORED CORPORA, READ FROM THE CORPUS RATHER THAN TRANSCRIBED FROM IT.
#:
#: This was a literal three-tuple, and its own comment gave the defect away: *"the three authored
#: corpora under `Domain Expertise/`, in the order that directory lists them."* The directory was
#: already the truth and a Python tuple copied it BY HAND — so authoring a fourth corpus produced
#: a folder the catalog loads, the resolver routes and `require_domain` REFUSES. A customer whose
#: business is not admin, sales or support could not be activated at all, and the refusal came
#: from a list nobody had told about their domain.
#:
#: THE GATE DOES NOT MOVE. `require_domain` still refuses everything outside this set, for exactly
#: the reason written under it — a typo must not write a row that reads as an activated tenant.
#: What changed is where the set COMES FROM: the corpus, which is the thing an author can add to,
#: instead of a literal, which is a thing only an engineer can. A rule may be a gate; it may not
#: also be the vocabulary.
#:
#: THE THREE NAMES ABOVE STAY as module constants because call sites reference them by name and a
#: constant that resolves at import is worth more than a string literal at each site. They are the
#: corpora that exist today, not the list of corpora that may exist.
def _authored_domain_ids() -> tuple[str, ...]:
    """Every domain id under `Domain Expertise/`, sorted, by cheap scan.

    NOT `ExpertBrainCatalog`, deliberately. That class parses every capability, object, situation
    and heuristic in the tree and raises on any integrity fault anywhere in it — appropriate for a
    compile, catastrophic for a module-level constant in `platform/`, where an authoring typo in
    one unrelated situation file would make the ACTIVATION TABLE unimportable and take the admin
    console down with it. This reads one key out of each `domain.yaml` and nothing else.

    FAILS SOFT, ON PURPOSE, TO THE THREE THAT SHIPPED. A corpus that cannot be read is a deployment
    problem; refusing to activate `admin` because of it would turn a missing directory into an
    outage for tenants who were already live.
    """
    shipped = (DOMAIN_ADMIN, DOMAIN_CUSTOMER_SUPPORT, DOMAIN_SALES)
    try:
        from genios_engine.packs.compiler.authoring import default_authoring_root

        root = default_authoring_root()
        if not root.is_dir():
            return shipped
        found: set[str] = set(shipped)
        for domain_root in sorted(root.iterdir()):
            if (not domain_root.is_dir() or domain_root.name.startswith("_")
                    or not (domain_root / "domain.yaml").is_file()):
                continue
            import yaml

            data = yaml.safe_load((domain_root / "domain.yaml").read_text()) or {}
            identity = data.get("identity") if isinstance(data, dict) else None
            domain_id = str((identity or {}).get("id") or "").strip()
            if domain_id:
                found.add(domain_id)
        return tuple(sorted(found))
    except Exception:      # noqa: BLE001 — see FAILS SOFT above
        return shipped


L3_DOMAINS = _authored_domain_ids()

#: What flipping one domain on ACTUALLY does, in one sentence per domain, returned beside `live`
#: wherever a console reads this table. An operator who can see a switch is on and cannot see what
#: it turned on will assume it turned on everything — and the honest answer here has a precondition
#: attached, because activation without the Y1 weld is the fake success the plan names.
EFFECTS = {
    domain: (f"the domain compiler's live pass compiles the {domain} corpus for this tenant "
             "instead of skipping it; it does NOT retire platform/config.use_domain_compiler, and "
             "it is only meaningful once the typed consumers (Y1) exist — activating before them "
             "produces generic output that looks like success")
    for domain in L3_DOMAINS
}

#: Every column the record carries, in one place, so the reads below cannot select different shapes
#: of the same row.
_COLUMNS = "org_id, domain, enabled_at, enabled_by, notes, disabled_at, disabled_by, updated_at"

#: What "activated" MEANS in SQL. One constant rather than five copies of the same `where` clause,
#: so a read cannot forget that a stamped-off row is still a row.
_LIVE = "disabled_at is null"


def require_domain(domain: str) -> str:
    """The one place a domain name is validated.

    A typo must be a refusal, not a row written under `admn` that reads as an activated tenant and
    compiles nothing. This is `l2_activation.require_switch`'s counterpart and exists for the same
    reason: the value reaches a `where` clause as a bound parameter, but it also reaches an
    operator's eyes as the answer to "is this tenant on".
    """
    if domain not in L3_DOMAINS:
        raise ValueError(f"unknown Layer 3 domain {domain!r}; expected one of {L3_DOMAINS}")
    return domain


@dataclass(frozen=True)
class L3Activation:
    """One (tenant, domain) pilot record: who turned it on, when, why, and whether it is still on."""

    org_id: str
    domain: str
    enabled_at: datetime
    enabled_by: str
    notes: str | None = None
    disabled_at: datetime | None = None
    disabled_by: str | None = None
    updated_at: datetime | None = None

    @property
    def live(self) -> bool:
        """Whether this tenant's domain is compiling RIGHT NOW. A record exists for tenants that
        were switched off too — that is the point of keeping the row — so every read asks this,
        never `record is not None`."""
        return self.disabled_at is None

    def as_record(self) -> dict:
        """The console's shape. `effect` travels beside `live` deliberately: see `EFFECTS`."""
        def _iso(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None
        return {"org_id": self.org_id, "domain": self.domain, "live": self.live,
                "enabled_at": _iso(self.enabled_at), "enabled_by": self.enabled_by,
                "disabled_at": _iso(self.disabled_at), "disabled_by": self.disabled_by,
                "notes": self.notes, "updated_at": _iso(self.updated_at),
                "effect": EFFECTS[self.domain]}


def _record(row) -> L3Activation:
    return L3Activation(org_id=row.org_id, domain=row.domain, enabled_at=row.enabled_at,
                        enabled_by=row.enabled_by, notes=row.notes,
                        disabled_at=row.disabled_at, disabled_by=row.disabled_by,
                        updated_at=row.updated_at)


# ── the compiler's reads: fail closed ────────────────────────────────────────────────────────

def is_l3_activated(engine, org_id: str, domain: str) -> bool:
    """Whether ONE tenant's ONE domain compiles on this pass. The hot-path read.

    Fail-closed on every error. The cost of a wrong `False` is a tenant that keeps compiling the way
    every tenant compiles today; the cost of a wrong `True` is an unbudgeted compile on a tenant
    nobody chose, on a path whose whole justification is that it was watched.
    """
    require_domain(domain)
    if engine is None:
        return False
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                f"select 1 from {L3_ACTIVATION_TABLE} where org_id = :o and domain = :d "
                f"and {_LIVE}"), {"o": org_id, "d": domain}).first() is not None
    except Exception as exc:      # noqa: BLE001 — an unreadable switch is an OFF switch
        _log.warning("could not read %s for org=%s domain=%s, treating as not activated: %s",
                     L3_ACTIVATION_TABLE, org_id, domain, exc)
        return False


def l3_activated_orgs(engine, domain: str) -> frozenset[str]:
    """Every org with ONE domain live. Empty for any reason it cannot be read.

    One query for all tenants rather than one per tenant, for the same reason both sibling modules
    carry a set read: a cross-org sweep asks this for every connection it holds.
    """
    require_domain(domain)
    if engine is None:
        return frozenset()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return frozenset(row[0] for row in conn.execute(text(
                f"select org_id from {L3_ACTIVATION_TABLE} where domain = :d and {_LIVE}"),
                {"d": domain}))
    except Exception as exc:      # noqa: BLE001
        _log.warning("could not read %s for domain=%s, treating every tenant as not activated: %s",
                     L3_ACTIVATION_TABLE, domain, exc)
        return frozenset()


def activated_domains(engine, org_id: str) -> frozenset[str]:
    """Which corpora are live for ONE tenant — the read the compiler needs to bound a compile.

    Distinct from calling `is_l3_activated` three times: the compiler asks "which of this tenant's
    domains am I compiling" once per sweep, and three round trips to answer one question is three
    times the chance of a partial answer. Fail-closed, same as its siblings.
    """
    if engine is None:
        return frozenset()
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                f"select domain from {L3_ACTIVATION_TABLE} where org_id = :o and {_LIVE}"),
                {"o": org_id})
            # A row whose domain is not in `L3_DOMAINS` is filtered rather than returned: the
            # column is free text by design (see the migration), and a compiler handed a domain it
            # has no corpus for would fail at retrieval instead of here.
            return frozenset(row[0] for row in rows if row[0] in L3_DOMAINS)
    except Exception as exc:      # noqa: BLE001
        _log.warning("could not read %s for org=%s, treating every domain as not activated: %s",
                     L3_ACTIVATION_TABLE, org_id, exc)
        return frozenset()


# ── the console's reads: NOT fail-closed ─────────────────────────────────────────────────────

def get_l3_activation(engine, org_id: str, domain: str) -> L3Activation | None:
    """One (tenant, domain) FULL record, live or not — the read an operator and J5 need.

    Returns a record for a pair that has been switched OFF, whose `live` is False; `None` only for a
    pair that was never in the pilot at all. Deliberately not fail-closed: this feeds a console and a
    gate report, and both must see a database error rather than the word "off".
    """
    require_domain(domain)
    if engine is None:
        return None
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text(
            f"select {_COLUMNS} from {L3_ACTIVATION_TABLE} where org_id = :o and domain = :d"),
            {"o": org_id, "d": domain}).first()
    return _record(row) if row is not None else None


def list_l3_activations(engine, *, include_disabled: bool = False) -> tuple[L3Activation, ...]:
    """Every pilot record, newest enablement first. The console's list.

    `include_disabled` defaults False so the ordinary question — "who is on the Layer 3 pilot" — is
    answered without an operator filtering a mixed list by eye and mistaking a tenant switched off
    last Tuesday for a live one.
    """
    if engine is None:
        return ()
    from sqlalchemy import text
    where = "" if include_disabled else f"where {_LIVE}"
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"select {_COLUMNS} from {L3_ACTIVATION_TABLE} {where} "
            "order by enabled_at desc, org_id, domain")).all()
    return tuple(_record(r) for r in rows)


# ── the writers ──────────────────────────────────────────────────────────────────────────────

def activate(engine, org_id: str, *, domain: str, by: str, notes: str | None = None,
             at: datetime | None = None) -> L3Activation:
    """Switch ONE domain on for ONE tenant. Idempotent on a LIVE row: the ORIGINAL enabling stands.

    Keeping the first `enabled_at` rather than refreshing it is the point of storing it: "since when
    has this tenant been on the pilot" is what the seven-day J5 report is read against, and an upsert
    that refreshed it would answer with the date of the last click.

    Re-activating a pair that was switched OFF is the opposite case and takes the new values — that
    is a new pilot period with a new decision behind it, and dating it from the first would hand the
    report a window containing days the compiler did not run.

    `notes` follows the same rule with one softening, copied from both siblings: on a live row a new
    note FILLS IN a reason left blank and never overwrites one already there. Changing why a tenant
    is in the pilot is its own decision, and a double-click on a form is not it.

    Writes nothing else, and starts nothing. In particular it triggers no compile: the next ordinary
    sweep reads the switch. An activation that kicked off a backfill would make "activate twice" mean
    "compile the corpus twice".
    """
    require_domain(domain)
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    table = L3_ACTIVATION_TABLE
    with engine.begin() as conn:
        conn.execute(text(
            f"insert into {table} (org_id, domain, enabled_at, enabled_by, notes, updated_at) "
            "values (:o, :d, :at, :by, :notes, :at) "
            "on conflict (org_id, domain) do update set "
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
            {"o": org_id, "d": domain, "at": at, "by": by, "notes": notes})
        row = conn.execute(text(
            f"select {_COLUMNS} from {table} where org_id = :o and domain = :d"),
            {"o": org_id, "d": domain}).first()
    return _record(row)


def deactivate(engine, org_id: str, *, domain: str, by: str = "unrecorded",
               at: datetime | None = None) -> bool:
    """Switch ONE domain off. True when a LIVE row was switched off — the rollback half of the flip,
    which is not optional: an activation you cannot reverse is a deploy with extra steps.

    The row is STAMPED, not deleted, and `enabled_at` is left where it was: J5 reads a seven-day
    window and has to be able to say "the admin corpus was switched off on day four", which a missing
    row cannot say. Every read filters the stamped rows out, so the compiler sees exactly what a
    delete would have left it.
    """
    require_domain(domain)
    from sqlalchemy import text
    at = at or datetime.now(timezone.utc)
    with engine.begin() as conn:
        switched_off = conn.execute(text(
            f"update {L3_ACTIVATION_TABLE} set disabled_at = :at, disabled_by = :by, "
            f"updated_at = :at where org_id = :o and domain = :d and {_LIVE}"),
            {"o": org_id, "d": domain, "at": at, "by": by}).rowcount > 0
    if switched_off:
        _log.info("Layer 3 %s corpus DEACTIVATED for org=%s by=%s", domain, org_id, by)
    return switched_off


__all__ = ["DOMAIN_ADMIN", "DOMAIN_CUSTOMER_SUPPORT", "DOMAIN_SALES", "EFFECTS", "L3Activation",
           "L3_ACTIVATION_TABLE", "L3_DOMAINS", "activate", "activated_domains", "deactivate",
           "get_l3_activation", "is_l3_activated", "l3_activated_orgs", "list_l3_activations",
           "require_domain"]
