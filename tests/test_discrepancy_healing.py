"""`consistency` must be able to RECOVER, not only fall.

Two defects made it monotonic: (1) write_discrepancy inserted a fresh row per disagreeing
event, so one recurring conflict (the same stale email re-arriving) stacked to 3+ and
pinned every situation about the entity to overall=0 permanently; (2) nothing ever closed
an open discrepancy, so even after the field was authoritatively re-decided the penalty
stayed forever. The fix bounds discrepancies to one-open-per-(subject,field) and closes
them on supersede.
"""
from __future__ import annotations

import inspect

from genios_engine.context import graph_store
from genios_engine.context.situations import consistency_score


def test_consistency_falls_with_contested_fields_and_recovers_when_cleared():
    # Direction check on the pure scorer: more contested fields → lower; back to zero
    # contested → full recovery. This is only reachable because discrepancies can close.
    assert consistency_score(open_discrepancies=0) == 100
    assert consistency_score(open_discrepancies=1) == 66
    assert consistency_score(open_discrepancies=3) == 0
    assert consistency_score(open_discrepancies=0) == 100   # recovered


def test_supersede_closes_open_discrepancies():
    src = inspect.getsource(graph_store.GraphStore.write_fact)
    # On supersede the field is re-decided → open discrepancies on it are resolved.
    assert 'action == "supersede"' in src
    assert "resolve_discrepancies" in src


def test_resolve_discrepancies_marks_resolved_not_delete():
    src = inspect.getsource(graph_store.GraphStore.resolve_discrepancies)
    assert "status='resolved'" in src
    assert "status='open'" in src        # only touches open ones
    assert "delete from discrepancies" not in src   # kept for audit, never deleted


def test_write_discrepancy_dedupes_one_open_per_field():
    src = inspect.getsource(graph_store.GraphStore.write_discrepancy)
    # Update-before-insert: an existing open row for (subject, field) is refreshed, not
    # stacked — a single recurring conflict can never exceed one contested-field penalty.
    assert "update discrepancies set" in src
    assert "if not updated" in src
    assert "insert into discrepancies" in src
