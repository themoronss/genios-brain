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
#: `DEAL_COOLING_V1` stays in the roster and stays shadow-only (`live_delivery_enabled=False`): it
#: is the seven-unit baseline whose decisions v2 is compared against, and two delivery-enabled
#: capabilities over the same subject would compete for one open signal per subject. They publish
#: under different rule ids (`deal_cooling` vs `deal_cooling_full`) so nothing collides — only one
#: of them is entitled to speak.
BUILTIN_CAPABILITIES = (DEAL_COOLING_V1, DEAL_COOLING_FULL_V2)

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
