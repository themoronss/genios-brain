"""The architecture DAG as data — the single place a layer number lives.

Package names carry semantics, never digits: the numbers have already changed twice
across specs while the code did not, so no digit ever appears in a package name.
Import direction is enforced by tests/test_layer_topology.py: a package may import
same-or-lower layers only. That test is the mechanism that keeps domain knowledge
out of the engine and context out of expertise — a build failure, not a review nit.

Translation across the vocabularies (docs/LAYER_MAP.md has the full table):

    package     layer   name                             old dossier      Atlas
    capture       1     Enterprise Signals               L1 Capture       1
    context       2     Situation Intelligence           L2 Context graph 2
    packs         -     Plane D · Domain Expertise       L4 Domain packs  3
    reason        -     Plane R · Reasoning              L3 Reasoning     4
    executive     5     Executive Intelligence           -                5
    deliver       6     Intelligence Distribution        L5 Delivery      5.2
    feedback      7     Learning Engine                  L6 Feedback      6

⛔ `packs` AND `reason` ARE PLANES, NOT STAGES, and the dashes above are deliberate. A digit
implies a position in a pipeline; these two are what `context` reasons WITH, consulted rather than
passed through. The `LAYERS` dict below still gives them 3 and 4 because the topology test reads
it and the IMPORT ordering it enforces is correct and unchanged — a plane may still only import
same-or-lower. The number is an import rule, not a claim about sequence.

`context` is **Situation Intelligence**, not "Context Intelligence": the old name says where the
layer sits, and this layer's output is a SITUATION — assembled, judged by eight admission laws,
and exposed only if admitted. Describing it as a graph builder is how a card came to be wired to
a signal while the situation layer was bypassed.

The `executive` split HAS happened: the package exists with 23 modules and `LAYERS`
below has carried `"executive": 5` since. Note the two collisions that make an
unqualified layer number ambiguous — Atlas 5.2 is our `deliver` (6), and Atlas 6 is
our `feedback` (7) — so always name the package, never the digit alone.
"""
from __future__ import annotations

LAYERS: dict[str, int] = {
    "capture": 1,      # Enterprise Signals — read + normalize, zero reasoning
    "context": 2,      # Situation Intelligence — assembles, judges, admits
    "packs": 3,        # Plane D · Domain Expertise — a plane, not a stage; 3 is an
                       # IMPORT rule, not a pipeline position (see the docstring)
    "reason": 4,       # Plane R · Reasoning — a plane, not a stage; deterministic
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
