"""ONE ADMISSION SEQUENCE, THREE CALL SITES — pinned, because the copies are real.

WHY THIS FILE EXISTS. The J4/J5 closure round put three separate implementations of Layer 6's
admission sequence in the tree, and two of them were written by different agents in parallel:

    feedback/orchestrator.py::run_learning      the weekly pass
    feedback/brain_pipeline.py::admit_proposals the immediate lease, inside a founder's request
    feedback/org_rule_ingest.py::admit_discovery an uploaded policy's declarations

Each one spells out `validate_learning → preflight → govern → persist → publish` in its own body.
They agree today. Nothing makes them agree tomorrow, and the failure would be silent in the worst
possible way: a lease granted inside an HTTP request under gates the weekly pass no longer
applies, or a declaration admitted under floors the batch would have refused. "One governance,
one set of floors" is an invariant of the design and it was, until this file, a convention.

WHAT IS PINNED, AND WHAT IS DELIBERATELY NOT. The ORDER and the PRESENCE of the four gates is
pinned in all three. `admit_discovery`'s documented divergence is not flattened: it treats the
recurrence floors as advisory when governance routes the object to a HUMAN, because a written
policy statement is a declaration observed once rather than an inferred pattern and the human
confirmation is the evidence. That divergence is asserted here as a divergence — with its own
guard, `if not decision.needs_human and not floors_ok`, named — so that removing the guard is a
red test rather than a quiet widening.

It is an AST check on purpose. A behavioural test would need one tenant per call site and would
still only prove the paths agree on the case it seeded; the claim here is about the code's shape,
which is the thing that drifts.
"""

from __future__ import annotations

import ast
import inspect

from genios_engine.feedback import brain_pipeline, orchestrator, org_rule_ingest

#: The four gates, in the order Layer 6 applies them. `publish` follows `persist`; a call site
#: that publishes without persisting has written a brain entry with no object behind it.
GATES = ("validate_learning", "preflight", "govern", "persist", "publish")

CALL_SITES = {
    "orchestrator.run_learning": (orchestrator, "run_learning"),
    "brain_pipeline.admit_proposals": (brain_pipeline, "admit_proposals"),
    "org_rule_ingest.admit_discovery": (org_rule_ingest, "admit_discovery"),
}


def _called_names(module, function_name: str) -> list[str]:
    """Every call in the function's body, in source order, by the name being called."""
    tree = ast.parse(inspect.getsource(module))
    target = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == function_name)
    names: list[str] = []
    for node in ast.walk(target):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name:
                names.append((node.lineno, name))
    return [name for _, name in sorted(names)]


def test_every_admission_site_applies_all_four_gates():
    for label, (module, function_name) in CALL_SITES.items():
        called = _called_names(module, function_name)
        missing = [gate for gate in GATES if gate not in called]
        assert not missing, f"{label} does not apply {missing} — Layer 6 has two governances"


def test_every_admission_site_gates_before_it_writes():
    """A gate applied after the write is not a gate. Order, not merely presence."""
    for label, (module, function_name) in CALL_SITES.items():
        called = _called_names(module, function_name)
        first = {gate: called.index(gate) for gate in GATES}
        assert first["validate_learning"] < first["persist"], f"{label}: floors after the write"
        assert first["preflight"] < first["persist"], f"{label}: preflight after the write"
        assert first["govern"] < first["persist"], f"{label}: governance after the write"
        assert first["persist"] < first["publish"], f"{label}: published without an object"


def test_the_org_declaration_path_keeps_its_floors_where_no_human_looks():
    """`admit_discovery`'s ONE documented divergence, asserted as a divergence.

    A declaration reaches `human_review` without clearing the recurrence floors, because a policy
    sentence is observed once and the confirming human is the evidence. `organization_requires_
    review` is settable, so a tenant who turned review off must not thereby have turned the floors
    off too — that is what this guard is, and deleting it made exactly one test red before this
    one existed.
    """
    source = inspect.getsource(org_rule_ingest.admit_discovery)
    assert "if not decision.needs_human and not floors_ok:" in source, \
        "the floors no longer bite on the org path where no human will look"


def test_only_the_publisher_writes_a_brain_entry():
    """One write path. `learned_brain_entries` and the lease grant have exactly one writer each.

    Read off the source of the whole engine rather than asserted about a module, because the
    failure this catches is a NEW module quietly gaining an insert — which is the shape J4's
    "writes outside the L6 pipeline == 0" row counts after the fact, one tenant at a time.
    """
    import pathlib
    root = pathlib.Path(inspect.getfile(orchestrator)).parents[1]
    brain_writers: set[str] = set()
    lease_granters: set[str] = set()
    for path in root.rglob("*.py"):
        text = path.read_text()
        for line in text.splitlines():
            lowered = line.lower()
            if "learned_brain_entries" in lowered and ("insert into" in lowered
                                                       or "update learned_brain" in lowered):
                brain_writers.add(path.name)
            if "insert into temporary_memories" in lowered:
                lease_granters.add(path.name)
    assert brain_writers == {"publisher.py"}, brain_writers
    assert lease_granters == {"publisher.py"}, lease_granters
