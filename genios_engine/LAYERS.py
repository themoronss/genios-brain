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
    deliver       6     Intelligence Distribution    L5 Delivery
    feedback      7     Learning Engine              L6 Feedback

`deliver` currently also hosts what the target calls Executive Intelligence (5);
an `executive` package will be extracted additively when that split happens —
today's numbering places deliver at 6 so nothing may flow backwards out of it.
"""
from __future__ import annotations

LAYERS: dict[str, int] = {
    "capture": 1,      # Enterprise Sources — read + normalize, zero reasoning
    "context": 2,      # Context Intelligence — the live digital twin
    "packs": 3,        # Domain Expertise — packs are one mechanism inside it
    "reason": 4,       # Reasoning Engine — deterministic cognition
    "executive": 5,    # Executive Intelligence — decision intelligence ONLY
    "deliver": 6,      # Intelligence Distribution (who/when/where — never what/why)
    "feedback": 7,     # Learning Engine
}

# Cross-cutting packages: outside the layer ordering.
#   contracts — types that cross a boundary; may import nothing but platform/stdlib
#   platform  — config/db/crypto/wiring; the composition root, may import anything
#   api       — transport; the top-level composition surface, may import anything
CROSS_CUTTING: frozenset[str] = frozenset({"contracts", "platform", "api"})
