"""A pass that failed is said in the sweep's return — it is not a pass with nothing to do.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_failed_pass_is_not_a_quiet_sweep.py -q

L3 audit, 21 Oct 2026. Every derived pass in `process_pending` is wrapped so one failure cannot skip the rest,
and every wrapper only logged: the sweep returned exactly as if the failed pass had had nothing to do — one pass
was dead for months that way. `_PassFailures` hears each traceback the sweep's own thread logs on `genios.l2`,
and the sweep returns them as `failed_passes` (the stage line counts them).
"""
from __future__ import annotations

import logging
import threading

import pytest

from genios_engine.context import runner

from .lifecycle.test_h6_fault_injection import _sweep
from .lifecycle.test_resolution import RESOLUTION_TEXT, _drop, _seed


def _boom(*_a, **_k):
    raise RuntimeError("the waiting read lost its connection")


@pytest.mark.pg
def test_a_pass_that_raises_is_named_in_the_sweep_and_the_rest_still_run(pg_store, monkeypatch):
    org = "org_a_failed_pass_is_said"
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    try:
        quiet = _sweep(pg_store, org, None)
        assert not any("waiting pass failed" in f for f in quiet["failed_passes"]), "the control"
        from genios_engine.context import waiting
        monkeypatch.setattr(waiting, "compute_waiting", _boom)
        out = _sweep(pg_store, org, None)
        assert any("waiting pass failed" in f for f in out["failed_passes"]), (
            f"the waiting pass raised and the sweep said nothing: {out['failed_passes']}")
        assert "situation_rows" in out, "the passes after it still ran"
    finally:
        _drop(pg_store, org)


def test_only_this_threads_tracebacks_are_counted():
    handler = runner._PassFailures.watch()
    log = logging.getLogger("genios.l2")
    try:
        try:
            raise ValueError("x")
        except ValueError:
            log.exception("account view pass failed for org=%s", "o")
        log.error("l2_convergence_exceeded org=o")                 # an alert, not a failed pass

        def _elsewhere():
            try:
                raise ValueError("y")
            except ValueError:
                log.exception("another tenant's pass failed")
        t = threading.Thread(target=_elsewhere)
        t.start(); t.join()
    finally:
        failed = handler.stop()
    assert failed == ["account view pass failed for org=o"]
    assert handler not in log.handlers, "the handler outlived its sweep"


def test_a_sweep_that_raised_out_leaves_nothing_behind_the_next_one_hears():
    log = logging.getLogger("genios.l2")
    first = runner._PassFailures.watch()                          # its sweep raised before `stop`
    second = runner._PassFailures.watch()
    try:
        assert first not in log.handlers and second in log.handlers
    finally:
        second.stop()
