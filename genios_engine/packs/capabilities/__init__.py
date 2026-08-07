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
from .deal_health import DEAL_HEALTH_V1, build_deal_health_manifest

BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)

__all__ = [
    "BUILTIN_CAPABILITIES",
    "DEAL_COOLING_CAPABILITY",
    "DEAL_COOLING_V1",
    "DEAL_HEALTH_V1",
    "build_deal_cooling_manifest",
    "build_deal_health_manifest",
]
