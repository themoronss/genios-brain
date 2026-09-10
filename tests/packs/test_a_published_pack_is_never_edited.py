"""Edit a published manifest without bumping its version and production stops booting.

`PackRegistry.register` is immutable on purpose: it inserts `(pack_id, version)`, reads the row
back, and raises if the stored checksum is not the one the code just computed. `make_pack_registry`
runs at IMPORT time (`api/executive_routes.py:28`), so the raise is not a failed request — the
container exits non-zero and the deploy never binds a port.

That is exactly what shipped: the feed-inversion fix added 22 lines to `general_v1.py` and left
`"version": "1.4.0"` alone. `pack_registry` already held a general@1.4.0 with different bytes, and
every deploy after it died on

    ValueError: immutable pack version mismatch: general@1.4.0

No test could see it, because a fresh database registers whatever the code says. So this file pins
the content address of every published pack. Change a manifest and this fails — which is the
reminder to BUMP THE VERSION and re-pin, not to edit the number back.
"""
from __future__ import annotations

import pytest

from genios_engine.packs.registry import snapshot_id
from genios_engine.packs.wiring import BUILTIN_PACKS

pytestmark = pytest.mark.unit

#: pack id -> (version, content address). Update BOTH halves together, never one.
PUBLISHED = {
    "sales":            ("1.13.0", "cfg_6f98fb643fd16016"),
    "general":          ("1.5.0",  "cfg_9a238e14b6539265"),
    "admin":            ("1.0.1",  "cfg_d4cbc1cc822b78d8"),
    "customer_support": ("1.0.1",  "cfg_abb0167d5478c591"),
}


@pytest.mark.parametrize("manifest", BUILTIN_PACKS, ids=lambda m: m["id"])
def test_the_manifest_still_matches_the_version_it_claims(manifest):
    pack_id = manifest["id"]
    assert pack_id in PUBLISHED, f"new built-in pack '{pack_id}' — add it to PUBLISHED"
    version, checksum = PUBLISHED[pack_id]
    assert manifest["version"] == version, (
        f"{pack_id} moved to {manifest['version']} — update PUBLISHED to match")
    assert snapshot_id(manifest) == checksum, (
        f"{pack_id}@{manifest['version']} was EDITED after publication. Published bytes are "
        f"immutable: bump the version and re-pin here. Shipping this as-is makes "
        f"PackRegistry.register raise at import and the container exit non-zero.")


def test_every_builtin_pack_is_covered():
    assert {m["id"] for m in BUILTIN_PACKS} == set(PUBLISHED)
