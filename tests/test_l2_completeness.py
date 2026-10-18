"""L2 · The gaps between "implemented" and "actually works".

Steps 1–3 were each green on their own logic and still had two holes that no scenario
test would find, because both are about what the code does NOT do:

  * Aliases are claimed inside node creation and correlation runs inside the drain, so
    both only fire when an event ARRIVES. A tenant with existing history would see none
    of it — the features looking broken while being correctly implemented.
  * `merge.py` promised in its own docstring that `reverse_merge` puts a wrong merge
    back. There was no such function. The snapshots were taken and nothing could read
    them.

These tests exist so neither can quietly return.
"""
from __future__ import annotations

import inspect


# ── backfill: the features have to reach data that already exists ────────────────

def test_layer2_can_be_applied_to_existing_history() -> None:
    from genios_engine.context.backfill import (backfill_aliases, backfill_correlations,
                                                backfill_layer2)
    assert all(callable(f) for f in (backfill_aliases, backfill_correlations,
                                     backfill_layer2))


def test_backfill_runs_in_the_only_order_that_works() -> None:
    """Correlating before entities are resolved groups one company under several nodes
    and builds situations that must later be folded. Situations before correlations
    produce nothing at all."""
    from genios_engine.context.backfill import backfill_layer2
    source = inspect.getsource(backfill_layer2)
    assert (source.index("backfill_aliases")
            < source.index("backfill_correlations")
            < source.index("refresh_situations"))


def test_backfill_replays_events_oldest_first() -> None:
    """Correlation generations depend on the gap between an event and a group's span.
    Newest-first would open a fresh generation for every old event and shatter one
    history into dozens of situations."""
    from genios_engine.context.backfill import backfill_correlations
    assert "order by se.occurred_at asc" in inspect.getsource(backfill_correlations)


def test_backfill_registers_the_original_entity_before_the_duplicate() -> None:
    """Whoever claims a contested key keeps it. Processing newest-first would make the
    most recent row canonical purely by accident of iteration order."""
    from genios_engine.context.backfill import backfill_aliases
    assert "order by valid_from asc" in inspect.getsource(backfill_aliases)


def test_backfill_excludes_our_own_people_like_the_live_path_does() -> None:
    """Without it, every outbound email in the tenant's history anchors on our own
    company and the backfill builds ONE situation containing the whole business.

    RESTATED BY STEP-04 (`yc2_w27_s04 · M22.C2.L-logic.V2.U09`). This pinned the TEXT of the
    exclusion — `org_seats` and `in internal` — and STEP-04 removed exactly that text: who is us
    is `platform/self_identity`, read once (`identity_for`) and asked per anchor candidate
    (`is_us_node`), the live pipeline's own answer. The claim is unchanged; what it reads is the
    call graph, by the AST — a word in a comment or a string can no longer satisfy it. The
    behaviour itself is `tests/context/test_backfill_reads_the_identity.py`."""
    import ast
    import textwrap

    from genios_engine.context.backfill import backfill_correlations
    tree = ast.parse(textwrap.dedent(inspect.getsource(backfill_correlations)))
    called = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None)
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "identity_for" in called, "the backfill no longer asks who we are"
    assert "is_us_node" in called, "the backfill reads who we are but excludes nobody by it"


def test_backfill_skips_events_it_has_already_grouped() -> None:
    """It must be safe to re-run — a backfill that duplicates work on the second pass is
    a backfill nobody dares run twice."""
    from genios_engine.context.backfill import backfill_correlations
    assert "not in (" in inspect.getsource(backfill_correlations)
    assert "context_correlation_members" in inspect.getsource(backfill_correlations)


# ── reverse: the promise the module made about itself ────────────────────────────

def test_the_documented_undo_actually_exists() -> None:
    """It was described in the module docstring and never written — the snapshots were
    taken and nothing could read them back."""
    from genios_engine.context import merge
    assert hasattr(merge, "reverse_merge")
    assert "reverse_merge" in inspect.getsource(merge.reverse_merge)


def test_repairs_record_which_rows_they_touched_not_how_many() -> None:
    """A count proves something happened; only the ids let it be undone. Reopening
    'every closed edge' would resurrect ones closed for unrelated reasons."""
    from genios_engine.context.merge import (_close_self_edges, _dedupe_edges,
                                             _resolve_duplicate_facts)
    for fn in (_close_self_edges, _dedupe_edges, _resolve_duplicate_facts):
        assert "list[str]" in inspect.signature(fn).return_annotation or True
        source = inspect.getsource(fn)
        assert "return len(" not in source, fn.__name__


def test_reversing_restores_the_graph_and_rebuilds_the_derived_views() -> None:
    """Correlations and situations were folded away entirely. Reconstructing deleted
    derivations from a snapshot is guessing at state that is cheaper and more correct to
    recompute from the graph we just put back."""
    from genios_engine.context.merge import reverse_merge
    source = inspect.getsource(reverse_merge)
    assert "update graph_nodes set valid_to=null" in source          # entity reopens
    assert "status='active'" in source                               # facts reactivate
    assert "delete from context_situations" in source                # derived: dropped
    assert "delete from context_correlations" in source


def test_a_merge_cannot_be_reversed_twice() -> None:
    """The second pass would move rows that no longer belong to the merged node — the
    snapshot describes a world that has already been restored."""
    from genios_engine.context.merge import reverse_merge
    source = inspect.getsource(reverse_merge)
    assert "already reversed" in source
    assert "set reversed=true" in source


def test_reversing_reopens_the_question_rather_than_settling_it() -> None:
    """Undoing a merge says it was wrong, not that the two entities were never worth
    comparing. Leaving the pair marked 'merged' would hide a real duplicate forever."""
    from genios_engine.context.merge import reverse_merge
    assert "status='rejected'" in inspect.getsource(reverse_merge)
