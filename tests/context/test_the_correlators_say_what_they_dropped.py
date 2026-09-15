"""165 claims in, 0 facts out, and no surface in the engine could say so.

`correlation_dependency` carries a `DropReason` for every claim it refuses and assembles them into
`DependencySweep.dropped`. `runner.process_pending` receives that object, reads `facts_written` and
`budget_exhausted` from it, and discards the rest. The most useful diagnostic in the layer
travelled one function call and died there.

MEASURED ON THE LIVE TENANT while this was being written: 95 dependency claims read, 0 edges
materialised, and all 95 dropped as `UNRESOLVED_BLOCKED` — the WAITING end resolving to nobody.
The raw endpoints say why in one glance: "interview slot offer for GeniOS", "Shortlisting and
showcase participation", "Meeting between Sehan and Rohit". Those are outcomes, not parties, and
the traversal requires both ends to resolve to graph nodes. A shape mismatch, not a data problem —
so it will be total on every customer until somebody sees it.

THIS FILE HOLDS THE SEEING, not a fix for it. The census records `read`, `emitted` and `dropped`
and computes nothing else: no threshold, no health opinion, no correlator named in the shape. A
tenant whose dependencies genuinely are all resolved SHOULD convert at zero, and a rule calling
that a failure would be wrong for them and right for nobody.
"""
import pytest

from genios_engine.context.conversion import census, field_for, record_conversion


def test_the_subtraction_is_the_whole_point() -> None:
    c = census(read=95, emitted=0, dropped={"unresolved_blocked": 95})
    assert (c["read"], c["emitted"]) == (95, 0)
    assert c["dropped"] == {"unresolved_blocked": 95}
    assert c["rate_bp"] == 0
    assert c["unaccounted"] == 0


def test_an_unexplained_gap_is_reported_rather_than_reconciled() -> None:
    """`read - emitted` is NOT the sum of `dropped`: a step can refuse without recording a reason,
    and several claims can collapse into one edge. Hiding the difference would make a census that
    always balances and never tells you anything."""
    c = census(read=100, emitted=10, dropped={"no_evidence": 30})
    assert c["unaccounted"] == 60


def test_nothing_here_holds_an_opinion_about_a_healthy_rate() -> None:
    """THE RULE THIS UNIT REFUSES TO WRITE. An org with no open dependencies converts at zero and
    is perfectly healthy; an org converting at 100% may be extracting noise. A threshold here
    would be tuned on one customer and wrong for the next, which is the failure the whole census
    exists to avoid."""
    import ast
    import inspect

    from genios_engine.context import conversion

    # CHECKED AS CODE, NOT AS PROSE. An earlier cut grepped the source for words like "healthy"
    # and failed on the docstring that explains why there is no such rule — the same trap
    # `test_m9_never_fires_inside_a_sweep` sets for itself by scanning comments. What must be
    # absent is a THRESHOLD: a module-level number this code could compare a rate against.
    tree = ast.parse(inspect.getsource(conversion))
    numeric_consts = [t.id for node in tree.body if isinstance(node, ast.Assign)
                      for t in node.targets if isinstance(t, ast.Name)
                      and isinstance(node.value, ast.Constant)
                      and isinstance(node.value.value, (int, float))
                      and not isinstance(node.value.value, bool)]
    assert numeric_consts == [], f"a threshold lives here: {numeric_consts}"

    # …and the record carries no verdict field for anybody to read one out of.
    keys = set(census(read=10, emitted=1))
    assert keys == {"read", "emitted", "dropped", "unaccounted", "rate_bp"}

    assert census(read=0, emitted=0)["rate_bp"] == 0          # no claims is not a failure
    assert census(read=5, emitted=5)["rate_bp"] == 10_000      # nor is converting everything


def test_zero_counts_never_reach_the_record() -> None:
    """A reason that did not happen is not evidence that it did."""
    assert census(read=3, emitted=3, dropped={"self_loop": 0})["dropped"] == {}


def test_the_reasons_are_ordered_so_the_biggest_loss_reads_first() -> None:
    c = census(read=200, emitted=0, dropped={"no_evidence": 4, "unresolved_blocked": 190,
                                             "self_loop": 6})
    assert list(c["dropped"]) == ["unresolved_blocked", "self_loop", "no_evidence"]


def test_one_field_per_correlator_so_two_cannot_overwrite_each_other() -> None:
    assert field_for("dependency") == "derived.conversion.dependency"
    assert field_for("Timeline") == "derived.conversion.timeline"
    assert field_for("dependency") != field_for("timeline")


def test_a_graph_with_no_tenant_node_records_nothing_and_does_not_raise() -> None:
    """`tenant_node_id` returns None before the first sweep mints one. Minting one here would make
    a diagnostic the reason a node exists."""
    class _Conn:
        def execute(self, *a, **k):
            class _R:
                def scalar(self): return None
            return _R()

    assert record_conversion(_Conn(), "o", correlator="dependency", read=1, emitted=0,
                             eval_time=__import__("datetime").datetime.now(
                                 __import__("datetime").timezone.utc)) is False


def test_both_correlators_publish_their_census() -> None:
    """The wiring, checked at the seam rather than by running a sweep: each correlator must call
    `record_conversion` inside the SAME transaction that writes its facts, so a census cannot
    disagree with the rows it counts."""
    import ast
    import inspect

    from genios_engine.context import correlation_dependency, correlation_timeline

    def _calls(node) -> set[str]:
        return {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                for n in ast.walk(node) if isinstance(n, ast.Call)}

    for module in (correlation_dependency, correlation_timeline):
        tree = ast.parse(inspect.getsource(module))
        # CHECKED BY NESTING, NOT BY TEXT ORDER. An earlier cut compared string indexes, so
        # moving the census below the `with` block — outside the transaction, which is the whole
        # defect — still read as "after the write" and passed. The question is whether the call
        # is INSIDE the block that writes the facts it counts.
        holders = [w for w in ast.walk(tree) if isinstance(w, ast.With)
                   and "_write_facts" in _calls(w)]
        assert holders, f"{module.__name__}: no transaction writing facts was found"
        assert any("record_conversion" in _calls(w) for w in holders), (
            f"{module.__name__}: the census is not inside the transaction that writes its facts, "
            f"so a census can disagree with the rows it counts")


def test_the_sweep_reports_it() -> None:
    """A census nothing surfaces is the defect this unit exists to end, one level up."""
    import inspect

    from genios_engine.context import runner

    src = inspect.getsource(runner)
    assert '"conversion": conversion' in src
    assert "read_conversion" in src
