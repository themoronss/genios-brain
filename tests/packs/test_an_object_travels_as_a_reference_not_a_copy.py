"""An object's `definition` carries what readers open, and not the whole authored document.

    pytest tests/packs/test_an_object_travels_as_a_reference_not_a_copy.py -q

⛔ WHY THIS FILE EXISTS. `expertise_packages` reached **460 MB over 1,163 rows** on production
(2026-10-02) — 388 kB average, one payload 1,338 kB of which **85% was `objects`** (1,143 kB for 13
objects). That took the database past its 0.5 GB quota into read-only, and a read-only database
crash-loops every deploy, because `platform/migrate.apply_migrations` raises when migrations are
pending and the server will not take writes. The compiler was inlining each object's full authored
YAML — `attributes`, `relationships`, `anti_patterns`, `states`, `business_rules`, `exceptions`,
`actions` — while `objects.yaml` is specified as *"the load-set — references only"* and no consumer
of `package.objects` ever opened any of it.

⛔ THE TEST THAT MATTERS IS THE EQUIVALENCE ONE. Asserting "the big keys are gone" only proves bytes
left; it cannot tell a saving from a regression. `test_the_only_consumer_sees_exactly_what_it_saw`
runs the real reader over a pruned definition and over the full one and requires the SAME answer —
so this file fails both when the pruning stops happening and when it starts removing something that
is read.
"""

from __future__ import annotations

import json

import pytest

from genios_engine.packs.compiler.expertise_builder import (OBJECT_DEFINITION_KEYS, _authored)

pytestmark = pytest.mark.unit


class _Doc:
    """The shape `_authored` consumes — id, kind, version, content."""

    def __init__(self, content: dict) -> None:
        self.id = "admin.obj.contract"
        self.kind = "object"
        self.version = "1.0.0"
        self.content = content


#: An authored object the size and shape the corpus actually ships: a small `identity`, the
#: `inference_patterns` a reader opens, and the six bulky sections nobody does.
_FULL = {
    "identity": {"id": "admin.obj.contract", "domain": "admin"},
    "inference_patterns": {
        "deterministic": [
            {"status": "executable",
             "evidence_fields": ["contract.end_date", "contract.notice_period_days"],
             "when": [{"path": "contract.auto_renew", "op": "eq", "value": True}]},
            {"status": "needs_signal", "evidence_fields": ["contract.never_emitted"]},
        ],
        "heuristic": [
            {"status": "executable", "evidence_fields": ["contract.owner"], "when": []},
        ],
    },
    "attributes": {f"attr_{i}": {"type": "string", "doc": "x" * 200} for i in range(40)},
    "relationships": [{"to": f"obj_{i}", "kind": "depends_on"} for i in range(30)],
    "anti_patterns": ["y" * 300 for _ in range(10)],
    "states": {f"s{i}": {"desc": "z" * 150} for i in range(20)},
    "business_rules": ["r" * 250 for _ in range(10)],
    "exceptions": ["e" * 250 for _ in range(10)],
}


def _record(keep=OBJECT_DEFINITION_KEYS) -> dict:
    return _authored(_Doc(dict(_FULL)), bindings={}, keep=keep)


# =================================================================================================
# 1 · the record still identifies its object
# =================================================================================================
def test_the_reference_half_is_untouched():
    """Pruning is about the BODY. A record that no longer says which object it is would be smaller
    and useless — a package a human cannot read while debugging one."""
    rec = _record()
    assert rec["id"] == "admin.obj.contract"
    assert rec["kind"] == "object"
    assert rec["version"] == "1.0.0"
    assert rec["definition"]["identity"]["id"] == "admin.obj.contract"


def test_entity_bindings_still_travel():
    assert "entity_bindings" in _record()


# =================================================================================================
# 2 · ⛔ the equivalence — the reader must not be able to tell
# =================================================================================================
def test_the_only_consumer_sees_exactly_what_it_saw():
    """`adapters/expertise` reads `definition["inference_patterns"]` and nothing else from an
    object. Run the real functions over pruned and full definitions and require the same answer."""
    from genios_engine.reason.adapters.expertise import (_executable_required_fields,
                                                         _universal_required_fields)

    class _Pkg:
        def __init__(self, objects):
            self.objects = objects

    pruned = _Pkg([_record()])
    full = _Pkg([_authored(_Doc(dict(_FULL)), bindings={}, keep=None)])

    assert _executable_required_fields(pruned) == _executable_required_fields(full)
    assert _universal_required_fields(pruned) == _universal_required_fields(full)
    # and it is not vacuously equal — the reader found something on both
    assert _executable_required_fields(pruned), "the fixture stopped exercising the reader"


def test_a_key_the_reader_opens_may_never_be_dropped():
    assert "inference_patterns" in OBJECT_DEFINITION_KEYS, (
        "adapters/expertise reads this; dropping it silently empties Layer 4's required fields")


# =================================================================================================
# 3 · the bytes actually left
# =================================================================================================
def test_the_sections_no_consumer_opens_do_not_travel():
    definition = _record()["definition"]
    for dropped in ("attributes", "relationships", "anti_patterns", "states",
                    "business_rules", "exceptions"):
        assert dropped not in definition, f"{dropped} is still being copied into every package"


def test_the_saving_is_large_enough_to_be_the_point():
    """⛔ A pruning that saves a few percent is churn with a story. Measured on the corpus the real
    split is 82.6%; this fixture is the same shape, and the floor is set well under the measurement
    so an authoring change cannot make it flap."""
    full = len(json.dumps(_authored(_Doc(dict(_FULL)), bindings={}, keep=None)["definition"]))
    pruned = len(json.dumps(_record()["definition"]))
    assert pruned < full * 0.35, f"only {100 * (full - pruned) / full:.0f}% smaller"


def test_pruning_is_opt_in_so_capabilities_and_rules_keep_their_bodies():
    """`rule_compiler` reads a rule's `definition['rule']`; capabilities are read in several
    places. The closed list is applied ONLY where the readers are known."""
    assert _authored(_Doc(dict(_FULL)))["definition"] == _FULL


# =================================================================================================
# 4 · ⛔ THE WIRING — pruning that is never asked for is not pruning
# =================================================================================================
#
# The tests above all call `_authored` with `keep=` themselves, so every one of them passes with the
# builder's own call site reverted — which is the whole defect. Deleting one keyword argument from
# `build()` restores 460 MB of churn and nothing above notices. Asserted on the AST rather than on
# the text, because this file's own source contains both names.
def _objects_call() -> "ast.Call":
    import ast
    import inspect
    import textwrap

    from genios_engine.packs.compiler import expertise_builder as mod

    tree = ast.parse(textwrap.dedent(inspect.getsource(mod.ExpertiseBuilder.build)))
    for node in ast.walk(tree):
        # the `objects = tuple(_authored(...) for item in ...)` assignment, found by its TARGET
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "objects" for t in node.targets):
            continue
        for call in ast.walk(node.value):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                    and call.func.id == "_authored":
                return call
    raise AssertionError("the builder no longer assigns `objects` from `_authored`")


def test_the_builder_actually_asks_for_the_pruning():
    """⛔ THE MUTATION THIS SECTION EXISTS TO REJECT: dropping `keep=` at the call site."""
    import ast

    call = _objects_call()
    keywords = {kw.arg for kw in call.keywords}
    assert "keep" in keywords, (
        "`build()` builds objects without `keep=` — the full authored document is being copied "
        "into every package again, which is the 460 MB that took production read-only")
    keep = next(kw.value for kw in call.keywords if kw.arg == "keep")
    assert isinstance(keep, ast.Name) and keep.id == "OBJECT_DEFINITION_KEYS", (
        "the keep-set must be the module's declared closed list, not an inline one a reader "
        "cannot find from the constant")
