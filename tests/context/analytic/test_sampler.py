"""H1 · the gate command's entry point — the L2.4.2 sampler's WIRING, in the file doc 09 names.

Doc 09 invokes gate H1 as:

    pytest tests/context/analytic/test_history.py tests/context/analytic/test_sampler.py -q

so this path has to keep collecting something real. The sampler's behaviour — every row of
BLG-07's decision table, the honest gap, determinism, the point budget and the backfill — is
proven next door in `test_metric_sampler.py`, which is where this wave was asked to put it. What
stays here is the half of the unit that is not about behaviour at all, and that nothing in that
file would catch:

* the sampler is CALLED from `context/runner.process_pending`. Layer 1 shipped six units that
  were built, green, and reached by no request path, and each was found only by adversarial
  review. A sampler nothing sweeps writes no history, and every trend, percentile and anomaly
  above it then reports "insufficient history" for ever — which looks like a quiet product, not
  like a bug.
* the sweep hands it ONE instant. `process_pending` reads the clock once and passes `sweep_at`
  to the prune and to the sampler, so a sweep cannot delete against one clock and write against
  another — at a month boundary that is a point pruned and immediately rewritten.
* the sampling pass is UNCONDITIONAL. The two refresh blocks above it are gated on
  `done or affected`; this one must not be, because every trended metric is measured against a
  clock rather than against an event. An org with a quiet inbox is exactly the org whose decline
  is worth surfacing, and gating the pass on "did we ingest anything" freezes its series at the
  last sweep that happened to have mail.
* the failure is contained. A missed reading costs one period of a series; it must never stop an
  event from landing.

All four are read off the source, because all four are failures of ABSENCE: a test that
constructed the sampler itself and called it would pass in a build where no production path ever
reaches it. `test_metric_sampler.test_the_sweep_writes_history` proves the same wiring from the
other side, by driving the real entry point against a real database.
"""

from __future__ import annotations

import inspect
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"


def _sweep_source() -> str:
    from genios_engine.context.runner import process_pending
    return inspect.getsource(process_pending)


def _sampler_call_at(source: str) -> int:
    """Where the sampler is CALLED, which is not where its name first appears.

    `sample_org` is imported inside the try-block, so `source.index("sample_org")` lands on the
    import and every offset measured from it drifts the moment another name joins that import —
    which is exactly how these guards went red without the guard ever moving. Anchoring on the
    open paren pins them to the call itself.
    """
    at = source.find("sample_org(")
    assert at != -1, "no call to `sample_org` in the sweep — the sampler is imported and unused"
    return at


def test_the_drain_calls_the_metric_sampler():
    """`process_pending` is what every sync route calls (`api/routes.py`, `api/upload_routes.py`),
    and it is the only place a context sweep begins."""
    source = _sweep_source()
    assert "sample_org" in source, (
        "no sweep reaches the metric sampler — `metric_history` would stay empty and every "
        "comparison in L2.4 would report insufficient history for ever")
    assert "metric_points" in (_ENGINE / "context" / "runner.py").read_text()


def test_the_sweep_gives_the_sampler_its_own_instant():
    """`eval_time` is a parameter all the way down; the clock is read once, at the boundary."""
    source = _sweep_source()
    assert "sweep_at" in source
    assert "eval_time=sweep_at" in source, (
        "the sampler must be handed the sweep's instant — a second `now()` below this seam makes "
        "two passes of one sweep describe two different periods")


def test_the_sampling_pass_is_not_gated_on_having_ingested_anything():
    """The pass sits AFTER the last `if done or affected:` block and takes no such guard itself."""
    source = _sweep_source()
    sampler_at = _sampler_call_at(source)
    guard_at = source.rindex("if done or affected:")
    assert guard_at < sampler_at, "the sampler moved above the gated refresh blocks"
    between = source[guard_at:sampler_at]
    assert between.count("if done or affected") == 1, (
        "a second ingestion guard now sits between the refresh blocks and the sampler — an org "
        "with a quiet inbox would stop being measured")


def test_a_failed_sampling_pass_never_blocks_ingestion():
    """Same contract as the derived and situation refreshes: a derived view failing costs a cycle
    of freshness, never an event."""
    source = _sweep_source()
    sampler_at = _sampler_call_at(source)
    assert "except Exception" in source[sampler_at:sampler_at + 400]
