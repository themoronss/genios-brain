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


@lru_cache(maxsize=4)
def make_registry(database_url: str = "") -> PackRegistry:
    """Registry with every built-in pack content-addressed into pack_registry (idempotent)."""
    url = database_url or get_settings().database_url
    reg = PackRegistry(url)
    for pack in BUILTIN_PACKS:
        reg.register(pack)
    return reg


def ensure_default(registry: PackRegistry, org_id: str,
                   pack_id: str = DEFAULT_PACK_ID,
                   version: str = DEFAULT_PACK_VERSION) -> None:
    """Apply the default pack to an org that has NONE — only if absent, so an admin who
    disabled/overrode a pack is never silently re-enabled by a background L3 run."""
    with registry._engine.connect() as c:
        exists = c.execute(text("select 1 from tenant_packs where org_id=:o and pack_id=:p"),
                           {"o": org_id, "p": pack_id}).first()
    if exists is None:
        registry.apply_to_tenant(org_id, pack_id, version, state="active")


def ensure_defaults(registry: PackRegistry, org_id: str) -> None:
    """Apply every default pack (sales + general) to an org that doesn't have it yet — only if
    absent, same non-clobbering rule as ensure_default. Orgs already on an older pinned version
    keep it until explicitly promoted (zero-deploy lifecycle); this only backfills what's missing."""
    for pack_id, version in DEFAULT_PACKS:
        ensure_default(registry, org_id, pack_id, version)
