"""Native, capability-scoped expertise manifests.

The legacy domain packs remain the active compatibility path.  Manifests in
this package are immutable Layer 4 inputs for shadow/canary execution and do
not register or activate themselves at import time.
"""

from .deal_cooling import (
    DEAL_COOLING_CAPABILITY,
    DEAL_COOLING_V1,
    build_deal_cooling_manifest,
)
from .deal_cooling_v2 import DEAL_COOLING_FULL_V2, build_deal_cooling_full_manifest
from .deal_health import DEAL_HEALTH_V1, build_deal_health_manifest

#: Capabilities the runner sweep picks up, matched to a node by `domain` and `root_entity_type`.
#:
#: LOCK 1 (deployment runbook, Part 5): the 17-unit `DEAL_COOLING_FULL_V2` is imported and usable
#: but deliberately NOT in the sweep roster. Step 1 of activation adds it here so it runs alongside
#: v1 in shadow. Until then only the seven-unit `DEAL_COOLING_V1` baseline is swept (itself
#: shadow-only via `live_delivery_enabled=False`).
BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)

__all__ = [
    "BUILTIN_CAPABILITIES",
    "DEAL_COOLING_CAPABILITY",
    "DEAL_COOLING_FULL_V2",
    "DEAL_COOLING_V1",
    "DEAL_HEALTH_V1",
    "build_deal_cooling_full_manifest",
    "build_deal_cooling_manifest",
    "build_deal_health_manifest",
]
