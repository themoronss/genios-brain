"""The architecture DAG as data — the single place a layer number lives.

Package names carry semantics, never digits: the numbers have already changed twice
across specs while the code did not, so no digit ever appears in a package name.
Import direction is enforced by tests/test_layer_topology.py: a package may import
same-or-lower layers only. That test is the mechanism that keeps domain knowledge
out of the engine and context out of expertise — a build failure, not a review nit.

Translation across the three vocabularies (docs/LAYER_MAP.md has the full table):

    package     layer   new-vision name              old dossier
    capture       1     Enterprise Sources           L1 Capture
    context       2     Context Intelligence         L2 Context graph
    packs         3     Domain Expertise             L4 Domain packs
    reason        4     Reasoning Engine             L3 Reasoning
    executive     5     Executive Engine             Atlas L5 Executive
    deliver       6     Intelligence Distribution    L5 Delivery
    feedback      7     Learning Engine              Atlas L6 Learning & Evolution

The Executive/Delivery split is live: `executive` owns the immutable commitment, owner,
communication intent and lifecycle; `deliver` owns context-aware admission, concrete adapters,
retry/failover and delivery results. `deliver` may import `executive`, never the reverse.
"""
from __future__ import annotations

LAYERS: dict[str, int] = {
    "capture": 1,      # Enterprise Sources — read + normalize, zero reasoning
    "context": 2,      # Context Intelligence — the live digital twin
    "packs": 3,        # Domain Expertise — packs are one mechanism inside it
    "reason": 4,       # Reasoning Engine — deterministic cognition
    "executive": 5,    # Executive Engine — commitment, who, communication intent, lifecycle
    "deliver": 6,      # Intelligence Distribution — admission, destination, transport, result
    "feedback": 7,     # Atlas L6 Learning & Evolution (11 governed units; no Expert writes)
}

# Cross-cutting packages: outside the layer ordering.
#   contracts — types that cross a boundary; may import nothing but platform/stdlib
#   platform  — config/db/crypto/wiring; the composition root, may import anything
#   api       — transport; the top-level composition surface, may import anything
CROSS_CUTTING: frozenset[str] = frozenset({"contracts", "platform", "api"})
