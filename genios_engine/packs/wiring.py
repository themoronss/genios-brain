from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text

from genios_engine.platform.config import get_settings

from .admin_v1 import ADMIN_V1
from .general_v1 import GENERAL_V1
from .registry import PackRegistry
from .sales_v1 import SALES_V1
from .support_v1 import SUPPORT_V1

# D0 wiring — one place that knows which packs exist and which is the tenant default. The
# runner asks here for a registry; it never imports a domain pack directly. Adding a pack =
# import it + register it here (and let an admin apply_to_tenant). Zero engine change.

BUILTIN_PACKS = [SALES_V1, GENERAL_V1, ADMIN_V1, SUPPORT_V1]
DEFAULT_PACK_ID = "sales"
DEFAULT_PACK_VERSION = SALES_V1["version"]

# Every org gets all four applied automatically (if absent). Two of them carry legacy RULES —
# sales (deal-linked signals) and general (relationship hygiene, any contact). The other two carry
# none by design: `admin` and `customer_support` exist so the COMPILED Layer 3 brain has a lane
# with authority in those domains. Without a tenant pack whose `pack_id` equals the capability's
# `domain`, `persist_complete` refuses the write and every Admin/Support capability dies at
# `domain_shadow.py` under `no_tenant_pack` — which is what had been happening to all 106 of them.
# See admin_v1.py's docstring for why they hold no rules.
DEFAULT_PACKS = [(SALES_V1["id"], SALES_V1["version"]), (GENERAL_V1["id"], GENERAL_V1["version"]),
                 (ADMIN_V1["id"], ADMIN_V1["version"]), (SUPPORT_V1["id"], SUPPORT_V1["version"])]


def _corpus_packs() -> list[dict]:
    """An AUTHORITY LANE for every authored corpus that does not have a hand-written pack.

    The comment above says *"Adding a pack = import it + register it here … Zero engine change"*,
    and the first half contradicts the second: importing and registering IS an engine change. The
    consequence is precise and silent. `persist_complete` compares the config snapshot's `pack_id`
    against the capability's `domain`, so a corpus authored as "Clinic Expertise" compiles, routes
    and reasons — and then every one of its capabilities dies at `domain_shadow.py` under
    `no_tenant_pack`. That is exactly what had been happening to all 106 Admin capabilities before
    `ADMIN_V1` was written, and `ADMIN_V1`'s own docstring says so. A fifth corpus repeats it.

    WHAT A SYNTHESISED PACK DELIBERATELY DOES NOT CARRY, each for a fault it would cause:

      rules: []          same statement `admin_v1` and `support_v1` make. A pack exists here to
                         give the COMPILED lane authority, not to smuggle in legacy rules nobody
                         authored.
      schema.fields: []  THE LOAD-BEARING ONE. `context/extract/vocab.py::field_vocabulary` unions
                         every pack's `schema.fields` into the L2 EXTRACTION PROMPT — a field named
                         here is a field the model is told to go and find. A synthesised pack has
                         no evidence that any writer exists for anything, so naming a field would
                         invite the model to invent a plausible value for a fact nobody stated.
                         Facts arrive through the pipeline and the corpus, never through here.
      scoring_defaults   COPIED FROM `ADMIN_V1`, not invented. Cards from every pack are ranked
                         against each other inside ONE shared daily budget, so a new domain with
                         its own gate or bands would win (or lose) every tie on scale rather than
                         on merit. Divergence has to be earned from a live distribution.

    A HAND-WRITTEN PACK ALWAYS WINS. If `admin_v1.py` exists, the corpus never shadows it with an
    empty lane — the builtin carries a real `schema.fields` list with real writers behind it and
    losing that would silence the extractor for the domain that works.

    FAILS SOFT for the reason `l3_activation._authored_domain_ids` records: a corpus that cannot
    be read is a deployment problem, and it must not stop the four shipped packs registering.
    """
    builtin_ids = {p["id"] for p in BUILTIN_PACKS}
    # `platform.corpus` is the ONE reader of `domain.yaml` — `capture` needs the same three
    # lines and may not import this package, so the read lives in the cross-cutting layer that
    # every side may reach. It also ends the two hand-counted `parents[]` roots that used to
    # compute this directory twice at different depths.
    from genios_engine.platform.corpus import authored_domains

    out: list[dict] = []
    for domain_id, data in authored_domains():
        try:
            if domain_id in builtin_ids:
                continue
            identity = (data.get("identity") or {})
            out.append({
                "id": domain_id,
                # The AUTHOR's version. A bump in `domain.yaml` publishes a new pack version
                # rather than mutating a used one — `registry.register` refuses changed bytes
                # under a published version, and that refusal is the property, not an obstacle.
                "version": str(identity.get("version") or "0.1.0"),
                "requires": {"engine": ">=0.1.0"},
                "scoring_defaults": ADMIN_V1["scoring_defaults"],
                "rules": [],
                "plays": {},
                "templates": {"_version": "cards.v2"},
                "schema": {"fields": []},
            })
        except Exception:      # noqa: BLE001 — one bad corpus must not cost the others a lane
            continue
    return out


@lru_cache(maxsize=4)
def make_registry(database_url: str = "") -> PackRegistry:
    """Registry with every built-in pack content-addressed into pack_registry (idempotent)."""
    url = database_url or get_settings().database_url
    reg = PackRegistry(url)
    for pack in BUILTIN_PACKS:
        reg.register(pack)
    # AND EVERY AUTHORED CORPUS THAT HAS NO HAND-WRITTEN PACK. Registering is content-addressed
    # and idempotent, so this is a no-op on every run after the first for a given version.
    for pack in _corpus_packs():
        reg.register(pack)
    return reg


def _semver(version) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in str(version).split("."))
    except ValueError:
        return None


def should_promote(current_version, state, pins, target_version) -> bool:
    """Whether a tenant on `current_version` moves up to `target_version` on its own.

    Only upward, and never over a decision someone made: a `disabled` pack stays disabled, and a
    tenant whose `pins` contain "version" keeps the version it has. An unparseable version is left
    alone rather than guessed at.
    """
    if state == "disabled":
        return False
    if isinstance(pins, str):
        import json
        pins = json.loads(pins or "[]")
    if "version" in (pins or []):
        return False
    current, target = _semver(current_version), _semver(target_version)
    return current is not None and target is not None and target > current


def ensure_default(registry: PackRegistry, org_id: str,
                   pack_id: str = DEFAULT_PACK_ID,
                   version: str = DEFAULT_PACK_VERSION) -> None:
    """Apply the pack to an org that has NONE, and move an org on an OLDER version up to this one.

    Promotion used to be a manual script (`scripts/promote_packs.py`), so every existing tenant ran
    the old rule set until someone remembered: general 1.5.0 shipped on 10 Sep and the design
    partner was still on 1.4.0 a day later. `should_promote` keeps it to upgrades only and respects
    a disabled pack or a "version" pin. `apply_to_tenant` bumps the pack revision, which makes
    existing signals non-authoritative; every caller (run_all, the L2 pass, card building) reasons
    after this in the same pass, which re-authorises them. Admin overrides (lvl2) survive the move;
    calibration offsets (lvl3) reset on a version change, as `apply_to_tenant` has always done."""
    with registry._engine.connect() as c:
        row = c.execute(text("select version, state, pins from tenant_packs "
                             "where org_id=:o and pack_id=:p"),
                        {"o": org_id, "p": pack_id}).first()
    if row is None:
        registry.apply_to_tenant(org_id, pack_id, version, state="active")
        return
    if should_promote(row.version, row.state, row.pins, version):
        registry.apply_to_tenant(org_id, pack_id, version, state=row.state)
        import logging
        logging.getLogger(__name__).info("pack promoted org=%s pack=%s %s -> %s",
                                         org_id, pack_id, row.version, version)


def ensure_defaults(registry: PackRegistry, org_id: str) -> None:
    """Apply every default pack to an org that doesn't have it, and move an org on an older version
    of one up to the current version — the rules of `ensure_default` (upgrade only; a disabled pack
    or a "version" pin is left alone)."""
    for pack_id, version in DEFAULT_PACKS:
        ensure_default(registry, org_id, pack_id, version)
    # AND THE AUTHORED CORPORA, on the same non-clobbering terms. An empty lane is inert for a
    # tenant that has not activated that domain at Layer 3 — it carries no rules, no templates
    # and no schema fields, so it changes no card and no extraction prompt. What it does is stop
    # `persist_complete` refusing the write on the day somebody DOES activate, which is the
    # silent `no_tenant_pack` death the four builtins were written to end.
    for pack in _corpus_packs():
        ensure_default(registry, org_id, pack["id"], pack["version"])
