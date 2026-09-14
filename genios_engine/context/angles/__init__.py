"""L2 · ANGLES — the bounded question a model is allowed to be asked.

Layer 2 is a rule engine that looks like a model. Nine of its correlators call none, its
situation assembly calls none, and of the four model sites in the layer three never execute on a
sweep. That is the design and it is the right one: the same graph re-swept tomorrow by a different
model version produces the same answers, and `support_situations` states the trade in one line —
"that costs recall, and buys replayability".

The cost is real, though, and it is not evenly spread. A deterministic reading finds exactly what
somebody wrote a rule for, and the places where nobody could write one are not random: they are
the places the deterministic layer ITSELF refused, and it says so, in a queue. Two exist —
`derived.timeline.condition_review` holds the conditions `parse_condition` declined to guess at,
and `context_residue` holds what no reading explained at all.

An ANGLE is a question asked of one of those queues, and nothing else. It is not a licence to
read the graph.
"""
from genios_engine.context.angles.contract import (Angle, AngleVerdict, CostTier,
                                                   GateSource, UnavailableAngle,
                                                   register, registered, resolve)

# REGISTRATION IS THE IMPORT, which is why this line sits below the re-exports and carries a
# `noqa` rather than a name. `registered()` is what the sweep iterates; an angle in a module
# nobody imports is a declaration that never fires and never errors — the failure
# `patterns/registry.py` refuses loudly for condition kinds. Importing the package registers its
# questions, so `evaluate_org` cannot silently have nothing to ask.
from genios_engine.context.angles import library as _library  # noqa: E402,F401

__all__ = ["Angle", "AngleVerdict", "CostTier", "GateSource", "UnavailableAngle",
           "register", "registered", "resolve"]
