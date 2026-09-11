"""What a tenant must have before Layer 3 can say anything about it — and nobody was doing it.

MEASURED ON PRODUCTION, 10 September 2026, read-only. A tenant registered at 14:46, connected
Gmail at 14:47 and Google Calendar at 14:48. Ninety minutes later its whole footprint was:

    tenant_packs 0 · l3_activation 0 · source_coverage 0 · config_snapshots 0
    source_events 0 · prepared_content 0 · graph_nodes 0

Zero on the last three is a capture problem and lives in `api/routes._adopt_completed_oauth`. The
first four are this module's, and they are worse than they look: they mean that even after the
mail arrives, the ONLY intelligence that tenant can ever receive is the legacy pack lane. The
authored corpora — 152 capabilities, three domains, every situation a founder actually reads —
are skipped for them by `packs.compiler.capability_resolver`, because that resolver filters on
`l3_activation` and the tenant has no rows.

THE PILOT TENANT LOOKED BETTER FOR ONE REASON: A HUMAN RAN AN INSERT. `l3_activation` holds
exactly one row on production — `(org_e97e…, admin)`, `enabled_by: 'harsh'`, `notes: 'pilot run
2'`, 8 September. Nothing in the product would ever have written it. So "the new account gets
worse intelligence than the old one" was not a regression; it was the only behaviour the product
had, and the old account was the exception.

WHAT THIS MODULE IS NOT ALLOWED TO DO
-------------------------------------
* It may not decide WHICH domains are ready. The corpus does, in its own `domain.yaml`
  (`activation.default_on`), read through `platform.corpus.default_on_domains`. A corpus that
  says nothing stays off, so dropping a half-written domain into the tree cannot start it
  talking to customers.
* It may not overrule an operator. Any domain the tenant already holds a row for is skipped —
  live OR stamped off. Somebody switched that pair off on purpose and a background provisioning
  pass is not a new decision to switch it back on. `l3_activation.activate`'s own docstring says
  re-activating a disabled pair "is a new pilot period with a new decision behind it"; this is
  not one.
* It may not fail a caller. Signing up, connecting a mailbox and syncing must all succeed on a
  day this cannot reach the database. Every arm returns what it managed and names what it did
  not, and the next sync tries again — which is why `provision_intelligence` is called from the
  sync path as well as from signup, and why it is idempotent.

WHY IT RUNS ON SYNC AND NOT ONLY ON SIGNUP. Every tenant that already exists signed up before
this module did. A signup-only hook would fix the next customer and leave every current one on
the legacy lane forever, waiting for somebody to remember a script. The sync path is where a
tenant proves it has data worth reasoning about, it already runs per org, and it is idempotent —
so it backfills the whole installed base without a migration or a maintenance window.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from genios_engine.platform.logging import get_logger

logger = get_logger(__name__)

#: Stamped on every row this module writes, so an operator reading `l3_activation.enabled_by`
#: can tell a default apart from a decision. `harsh` on the pilot row is a person who chose;
#: this is the product doing what it does for everyone.
PROVISIONED_BY = "system:onboarding"


@dataclass(frozen=True, slots=True)
class Provisioned:
    """What actually happened, so a caller can log it and a test can assert on it."""

    #: The pack pass RAN and did not raise. Not "a pack was written" — `ensure_defaults` is
    #: non-clobbering and does not report, and an org that already has every pack takes the
    #: skip below without opening a registry at all.
    packs: bool = False
    #: Domains switched on by THIS call. A second call returns none of them — that is the
    #: idempotence, not a failure.
    activated: tuple[str, ...] = ()
    #: Declared default-on but left alone because the tenant already holds a row for them.
    already_decided: tuple[str, ...] = ()
    #: What went wrong, one readable line each. Never raised.
    errors: tuple[str, ...] = field(default=())

    @property
    def changed(self) -> bool:
        """Did this call actually SWITCH SOMETHING ON. The pack pass is deliberately not part
        of the answer: it is idempotent and silent about whether it wrote, so folding it in
        would report a change on every tick of the sweep forever."""
        return bool(self.activated)


def provision_intelligence(engine, org_id: str, *, by: str = PROVISIONED_BY) -> Provisioned:
    """Bind the default packs and switch on every corpus that declared itself ready.

    Idempotent and non-clobbering in both halves: `ensure_defaults` applies a pack only to a
    tenant that has none of that pack (an admin who pinned an older version keeps it), and the
    activation half skips any (tenant, domain) that already has a row.
    """
    if engine is None or not org_id:
        return Provisioned(errors=("no engine or no org",))

    errors: list[str] = []
    packs = False
    try:
        # ASK BEFORE BUILDING. `_run_l2` calls this on every sweep tick for every org, and
        # `make_registry` content-addresses every builtin and every authored corpus pack on
        # construction. One cheap SELECT turns the steady state from "re-register seven packs
        # per org per tick" into "one row lookup", and the registry is only built for a tenant
        # that genuinely has none.
        from sqlalchemy import text
        with engine.connect() as c:
            has_packs = c.execute(text(
                "select 1 from tenant_packs where org_id = :o limit 1"), {"o": org_id}).first()
        if has_packs is None:
            from genios_engine.packs.wiring import ensure_defaults, make_registry
            ensure_defaults(make_registry(), org_id)
        packs = True
    except Exception as exc:      # noqa: BLE001 — see the module docstring: never fatal
        logger.exception("pack provisioning failed for org=%s", org_id)
        errors.append(f"packs: {type(exc).__name__}: {str(exc)[:160]}")

    activated: list[str] = []
    decided: list[str] = []
    try:
        from genios_engine.platform.corpus import default_on_domains
        from genios_engine.platform.l3_activation import (
            L3_DOMAINS,
            activate,
            get_l3_activation,
        )
        for domain in default_on_domains():
            if domain not in L3_DOMAINS:
                # A corpus that declares itself default-on but that the engine does not know as
                # a domain. `activate` would raise `require_domain`; naming it is more use than
                # a traceback, and the tenant keeps everything else this call did.
                errors.append(f"activation: {domain!r} is not an engine domain")
                continue
            try:
                if get_l3_activation(engine, org_id, domain) is not None:
                    decided.append(domain)
                    continue
                activate(engine, org_id, domain=domain, by=by,
                         notes="switched on at onboarding because the corpus declares "
                               "activation.default_on; see Domain Expertise/*/domain.yaml")
                activated.append(domain)
            except Exception as exc:      # noqa: BLE001 — one domain, not the tenant
                logger.exception("l3 activation failed org=%s domain=%s", org_id, domain)
                errors.append(f"activation {domain}: {type(exc).__name__}: {str(exc)[:120]}")
    except Exception as exc:      # noqa: BLE001
        logger.exception("l3 activation pass failed for org=%s", org_id)
        errors.append(f"activation: {type(exc).__name__}: {str(exc)[:160]}")

    result = Provisioned(packs=packs, activated=tuple(sorted(activated)),
                         already_decided=tuple(sorted(decided)), errors=tuple(errors))
    if result.changed:
        logger.info("provisioned intelligence org=%s packs=%s activated=%s",
                    org_id, result.packs, result.activated)
    return result


__all__ = ["PROVISIONED_BY", "Provisioned", "provision_intelligence"]
