"""H1 · the gate command's entry point — the L2.4.1 store's WIRING, in the file doc 09 names.

Doc 09 invokes gate H1 as:

    pytest tests/context/analytic/test_history.py tests/context/analytic/test_sampler.py -q

so this path has to keep collecting something real. The store's behaviour — the primary key, the
dense gap-aware reader, point-in-time reads, both retention mechanisms, erasure and the drain
call — is proven next door in `test_metric_history.py`, which is where X1 was asked to put it;
splitting them leaves this file with the two facts that are not about behaviour at all and that
nothing else would catch:

* the table is named in `_ORG_SCOPED_TABLES`. That loop runs with NO try/except, so a name
  missing from it does not fail — it leaks a deleted tenant's engagement history, silently.
* the prune is CALLED from `context/runner.process_pending`. A retention policy that nothing
  invokes is a comment, and this table is the one store in L2 that only ever appends.

Both are read off the source rather than mocked, because both failures are failures of ABSENCE:
a test that constructed the store itself and called `prune` would pass in a build where no
production path ever reaches either.
"""

from __future__ import annotations

from pathlib import Path

from genios_engine.context.analytic.history import (HISTORY_TABLE, MAX_RETAINED_PERIODS,
                                                    RETENTION_MONTHS)

_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"


def test_the_history_table_is_named_in_the_tenant_erasure_list():
    from genios_engine.api import account_routes
    assert HISTORY_TABLE in account_routes._ORG_SCOPED_TABLES, (
        f"{HISTORY_TABLE} would survive a tenant erasure — the loop has no try/except, so the "
        "omission is silent")


def test_the_drain_calls_the_retention_prune():
    """`process_pending` is what every sync route calls (`api/routes.py`, `api/upload_routes.py`).
    Retention lives there because the Celery broker is a quota-limited Upstash instance and this
    layer's rule is to prefer in-process work on a sweep that already runs."""
    runner = (_ENGINE / "context" / "runner.py").read_text()
    assert "prune_history_for_drain" in runner
    assert "history_points_pruned" in runner


def test_the_retention_window_is_bounded_at_both_ends():
    """The two numbers the whole bounding argument rests on, pinned so a later edit that relaxes
    either has to come through this file. 104 weeks and 24 months are the same window."""
    assert RETENTION_MONTHS == 24
    assert MAX_RETAINED_PERIODS == 104
