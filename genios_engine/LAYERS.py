"""The architecture DAG as data — product identity separated from import rank.

Package names carry semantics, never digits: the numbers have already changed twice
across specs while the code did not, so no digit ever appears in a package name.
Import direction is enforced by tests/test_layer_topology.py: a package may import
same-or-lower import ranks only. That test is the mechanism that keeps domain knowledge
out of the engine and context out of expertise — a build failure, not a review nit.

Canonical product identity (docs/LAYER_MAP.md has the full table):

    package     product layer   import rank   name
    capture          1               1        Knowledge Layer
    context          2               2        Context Intelligence
    packs            3               3        Domain Expertise
    reason           4               4        Reasoning Engine
    executive        5               5        Executive Engine
    deliver          5.2             6        Delivery Engine
    feedback         6               7        Learning & Evolution

There is no product Layer 7. The integer 7 below is only the last import rank used by the topology
ratchet; package names and `PRODUCT_LAYERS` carry product identity.

The Executive/Delivery split is live: `executive` owns the immutable commitment, owner,
communication intent and lifecycle; `deliver` owns context-aware admission, concrete adapters,
retry/failover and delivery results. `deliver` may import `executive`, never the reverse.
"""
from __future__ import annotations

PRODUCT_LAYERS: dict[str, str] = {
    "capture": "1",
    "context": "2",
    "packs": "3",
    "reason": "4",
    "executive": "5",
    "deliver": "5.2",
    "feedback": "6",
}

# Integer import ranks. These are deliberately contiguous so same-or-lower comparisons stay simple;
# they are not the displayed product-layer numbers after Executive.
LAYERS: dict[str, int] = {
    "capture": 1,      # Enterprise Sources — read + normalize, zero reasoning
    "context": 2,      # Context Intelligence — the live digital twin
    "packs": 3,        # Domain Expertise — packs are one mechanism inside it
    "reason": 4,       # Reasoning Engine — deterministic cognition
    "executive": 5,    # Executive Engine — commitment, who, communication intent, lifecycle
    "deliver": 6,      # Product Layer 5.2 Delivery — admission, destination, transport, result
    "feedback": 7,     # Product Layer 6 Learning & Evolution — no Expert writes
}

# Cross-cutting packages: outside the layer ordering.
#   contracts — types that cross a boundary; may import nothing but platform/stdlib
#   platform  — config/db/crypto/wiring; the composition root, may import anything
#   api       — transport; the top-level composition surface, may import anything
CROSS_CUTTING: frozenset[str] = frozenset({"contracts", "platform", "api"})
