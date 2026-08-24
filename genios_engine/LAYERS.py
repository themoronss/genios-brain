"""The architecture DAG as data — the single place a layer number lives.

Package names carry semantics, never digits: the numbers have already changed twice
across specs while the code did not, so no digit ever appears in a package name.
Import direction is enforced by tests/test_layer_topology.py: a package may import
same-or-lower layers only. That test is the mechanism that keeps domain knowledge
out of the engine and context out of expertise — a build failure, not a review nit.

Translation across the three vocabularies (docs/LAYER_MAP.md has the full table):

    package     layer   new-vision name              old dossier      Atlas
    capture       1     Enterprise Sources           L1 Capture       1
    context       2     Context Intelligence         L2 Context graph 2
    packs         3     Domain Expertise             L4 Domain packs  3
    reason        4     Reasoning Engine             L3 Reasoning     4
    executive     5     Executive Intelligence       —                5
    deliver       6     Intelligence Distribution    L5 Delivery      5.2
    feedback      7     Learning Engine              L6 Feedback      6

The `executive` split HAS happened: the package exists with 23 modules and `LAYERS`
below has carried `"executive": 5` since. Note the two collisions that make an
unqualified layer number ambiguous — Atlas 5.2 is our `deliver` (6), and Atlas 6 is
our `feedback` (7) — so always name the package, never the digit alone.
"""
from __future__ import annotations

LAYERS: dict[str, int] = {
    "capture": 1,      # Enterprise Sources — read + normalize, zero reasoning
    "context": 2,      # Context Intelligence — the live digital twin
    "packs": 3,        # Domain Expertise — packs are one mechanism inside it
    "reason": 4,       # Reasoning Engine — deterministic cognition
    # These two labels stayed pre-split after the split (see docs/LAYER_MAP.md, the table this
    # module names as authoritative): deliver/router.py:9-12 documents that assignment moved TO
    # executive/assignment.py, and deliver/{audience,orchestrator,gate,outbox}.py all import it —
    # executive owns who/where, not "decision intelligence ONLY", and deliver executes the plan
    # executive authors rather than owning who/when/where itself.
    "executive": 5,    # Executive Engine — decisions AND who/where they reach (assignment.py,
                       # communication.py); see docs/LAYER_MAP.md
    "deliver": 6,      # Executes the plan executive authors: render, gate, send, track
    "feedback": 7,     # Learning Engine
}

# Cross-cutting packages: outside the layer ordering.
#   contracts — types that cross a boundary; may import nothing but platform/stdlib
#   platform  — config/db/crypto/wiring; the composition root, may import anything
#   api       — transport; the top-level composition surface, may import anything
CROSS_CUTTING: frozenset[str] = frozenset({"contracts", "platform", "api"})
