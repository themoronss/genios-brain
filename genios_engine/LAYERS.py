"""The architecture DAG as data — the single place a layer number lives.

Package names carry semantics, never digits: the numbers have already changed twice
across specs while the code did not, so no digit ever appears in a package name.
Import direction is enforced by tests/test_layer_topology.py: a package may import
same-or-lower layers only. That test is the mechanism that keeps domain knowledge
out of the engine and context out of expertise — a build failure, not a review nit.

Translation across the vocabularies (docs/LAYER_MAP.md has the full table):

    package     layer   name                             old dossier      Atlas   PRODUCT
    capture       1     Enterprise Signals               L1 Capture       1       L1
    context       2     Situation Intelligence           L2 Context graph 2       L2 + L3
    packs         -     Plane D · Domain Expertise       L4 Domain packs  3       into L2
    reason        -     Plane R · Reasoning              L3 Reasoning     4       L2 + L4
    executive     5     Executive Intelligence           -                5       L4
    deliver       6     Intelligence Distribution        L5 Delivery      5.2     L5
    feedback      7     Learning Engine                  L6 Feedback      6       L6

⛔ THE `PRODUCT` COLUMN IS THE FOURTH VOCABULARY AND IT COLLIDES WITH THIS FILE'S OWN DIGITS.
It is how the product is described to a founder — L1 Enterprise Signals · L2 Signals Qualification
(signals + domain expertise = reasoning) · L3 Context Graph · L4 Executive · L5 Delivery ·
L6 Learning — and against it "Layer 3" means the Context Graph, while 115 files in this repo say
"Layer 3" meaning Domain Expertise. The tail is off by one throughout: `executive`/`deliver`/
`feedback` are 5/6/7 here and 4/5/6 there.

Two entries are deliberately not one-to-one, because the packages predate the vocabulary:
`context` spans product L2 and L3 (it assembles situations AND holds the graph they are derived
from), and `reason` spans product L2 and L4 (`domain_shadow` is expertise reasoning, `runner`/
`composer`/`store` choose an action). Recorded so nobody later reads a package boundary as a layer
boundary. This does not change a single import rule.

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
#   mcp       — transport, exactly like `api`: an MCP server surface, imported only by main.py
#
# ⛔ `mcp` WAS IN NEITHER SET AND THAT WAS A HOLE, NOT A CHOICE (L3-00). `test_import_direction`
# iterates `LAYERS.items()`, so an unmapped package is never checked as a SOURCE; and its
# `if imported in CROSS_CUTTING or imported not in LAYERS: continue` skips it as a TARGET too.
# An unmapped package therefore escapes the rule in BOTH directions — `capture` (1) could import
# `mcp`, which imports `feedback` (7), and the topology test would stay green on an upward path
# laundered through a package nobody declared. `mcp` behaves as transport today (2 files, imports
# platform/reason/deliver/api/executive/contracts/context, imported only by `main.py`), so it is
# declared as transport rather than left to behave that way by accident.
CROSS_CUTTING: frozenset[str] = frozenset({"contracts", "platform", "api", "mcp"})

#: ⛔ Every package under `genios_engine/` must appear in `LAYERS` or `CROSS_CUTTING`.
#: `test_every_package_is_mapped` enforces it in the direction this module was missing: the old
#: `test_every_layer_package_exists` proved every declared name is a real package, and nothing
#: proved every real package is declared. A totality guard that runs one way is half a guard, and
#: this is the file whose entire job is to be the single place a layer number lives.
ALL_DECLARED: frozenset[str] = frozenset(LAYERS) | CROSS_CUTTING
