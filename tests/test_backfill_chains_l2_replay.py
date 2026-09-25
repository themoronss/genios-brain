"""L3-0A · the capture drain must chain into the Layer 2 history replay.

WHAT WAS BROKEN. `POST /connections/{id}/backfill` drained a tenant's full history and then ran
`_run_l2`, whose `process_pending` walks events one at a time under
`order by triage_lane asc, occurred_at asc` — oldest-first WITHIN a lane, lane-first globally.
`context/backfill.backfill_layer2` — aliases -> deals -> correlations -> situations, the pass
written *because* "on a tenant that already has months of history [the features] would appear to do
nothing" — was reachable only from `POST /situations/backfill`. Two endpoints, no chain, and the
one an operator uses when widening a backfill window was the one that could not rebuild.
"""
from __future__ import annotations

import pytest

from genios_engine.api import routes


# =================================================================================================
# 1 · THE KEYS ARE REAL
# =================================================================================================

def test_moved_keys_are_all_produced_by_backfill_layer2():
    """Technique 3 on the defect this build actually made.

    The first draft asked for `aliases_claimed` and `correlations_written`. NEITHER EXISTS, so
    alias and correlation work would have read falsy forever and only a new deal or situation could
    ever have re-run the chain — L1 step 14's defect, a name that is never present tested against a
    value that is never there. This pins the four keys to the `return {...}` statements they come
    from, so a rename inside `context/backfill` fails here instead of silently reporting "nothing
    moved" on every backfill from then on.
    """
    import inspect

    from genios_engine.context import backfill as l2_backfill

    src = inspect.getsource(l2_backfill)
    for key in routes._MOVED_KEYS:
        assert f'"{key}"' in src, (
            f"_MOVED_KEYS names {key!r}, which context/backfill.py never returns. A key that is "
            "never present reads falsy forever and the replay silently stops re-running the chain.")

    # And the reverse direction: `events_seen` must stay OUT. Reading an event is not changing
    # anything; counting it would re-run L4 and the card builder on every drain, for ever.
    assert "events_seen" not in routes._MOVED_KEYS


# =================================================================================================
# 2 · THE CHAIN RUNS, AND IN ORDER
# =================================================================================================

class _Conn:
    org_id = "org_test"
    connection_id = "conn_test"
    source_type = "gmail"
    seat_id = None
    config: dict = {}


class _Summary:
    scanned = 12
    emitted = 5

    def __init__(self, exhausted: bool) -> None:
        self.cursor_exhausted = exhausted


def _drive(monkeypatch, *, exhausted: bool, moved: bool) -> list[str]:
    """Run the endpoint's background task with every expensive edge stubbed, recording the order."""
    calls: list[str] = []

    monkeypatch.setattr(routes, "_graph", object(), raising=False)
    monkeypatch.setattr(routes._connections, "get", lambda _cid: _Conn(), raising=False)
    monkeypatch.setattr(routes, "make_connector_for", lambda _c: object(), raising=False)
    for helper in ("make_relevance_classifier", "_sender_resolver_for", "_coverage_fn_for",
                   "_esqe_stage_for", "_structured_lane_for", "_mailbox_owner_for_connection"):
        monkeypatch.setattr(routes, helper, lambda *a, **k: None, raising=False)
    monkeypatch.setattr(routes, "_semantic_lane_for", lambda *a, **k: None, raising=False)

    def _fake_drain(*_a, **_k):
        calls.append("drain")
        return _Summary(exhausted)

    import genios_engine.capture.acquire.sync_runner as sync_runner
    monkeypatch.setattr(sync_runner, "backfill_drain", _fake_drain, raising=False)
    monkeypatch.setattr(routes, "_run_l2", lambda *a, **k: calls.append("run_l2"), raising=False)
    monkeypatch.setattr(routes, "_replay_l2_history",
                        lambda *a, **k: (calls.append("replay"), moved)[1], raising=False)

    class _BG:
        @staticmethod
        def add_task(fn, *a, **k):
            fn(*a, **k)

    routes.backfill_connection("conn_test", _BG(), org_id="org_test")   # type: ignore[arg-type]
    return calls


def test_replay_runs_after_extraction_and_the_chain_reruns_when_work_moved(monkeypatch):
    """drain -> extract -> REBUILD -> L4/cards.

    The replay must come AFTER `process_pending`: it resolves and correlates data ALREADY IN THE
    GRAPH, so the graph has to be written first. And the second `_run_l2` exists so L4 and the card
    builder actually see situations the rebuild created — without it the drain leaves a correct
    graph and no cards, which is the same "looks broken while perfectly implemented" failure one
    seam later.
    """
    calls = _drive(monkeypatch, exhausted=True, moved=True)
    assert calls == ["drain", "run_l2", "replay", "run_l2"]


def test_no_second_chain_when_nothing_moved(monkeypatch):
    """A replay over an already-correlated tenant legitimately writes nothing. Paying for a second
    full L4 + card pass to discover that is exactly what the `moved` flag exists to avoid."""
    calls = _drive(monkeypatch, exhausted=True, moved=False)
    assert calls == ["drain", "run_l2", "replay"]


def test_replay_still_runs_when_the_drain_was_truncated(monkeypatch):
    """⛔ 0A-U2. A capped drain STILL LANDED EVENTS.

    Leaving those uncorrelated is precisely the failure `context/backfill` opens with — history
    sitting in the graph that no situation was ever derived from — and a tenant large enough to
    truncate is the tenant most likely to hit it.
    """
    calls = _drive(monkeypatch, exhausted=False, moved=True)
    assert "replay" in calls, "TRUNCATED drains skip the rebuild — the big-mailbox case is the one that needs it"


# =================================================================================================
# 3 · THE CHAIN CANNOT KILL THE DRAIN
# =================================================================================================

def test_a_failing_replay_never_propagates(monkeypatch):
    """L2-7, at the same seam: "a receipt that can abort the thing it is a receipt for turns an
    accounting failure into a product failure." A replay that raises must not lose the history the
    drain already landed."""
    monkeypatch.setattr(routes, "_graph", object(), raising=False)

    import genios_engine.context.backfill as l2_backfill

    def _boom(*_a, **_k):
        raise RuntimeError("replay exploded")

    monkeypatch.setattr(l2_backfill, "backfill_layer2", _boom, raising=False)
    assert routes._replay_l2_history("org_test") is False


def test_replay_is_a_noop_without_a_graph(monkeypatch):
    monkeypatch.setattr(routes, "_graph", None, raising=False)
    assert routes._replay_l2_history("org_test") is False


# =================================================================================================
# 4 · SENSITIVITY — neutralise the chain, the probe goes red
# =================================================================================================

def test_the_endpoint_source_actually_calls_the_replay():
    """Technique 3. The order assertions above drive stubs; this one reads the real call site, so
    deleting the chain from `backfill_connection` cannot pass by leaving a stub in place."""
    import inspect

    src = inspect.getsource(routes.backfill_connection)
    assert "_replay_l2_history" in src, "the backfill endpoint no longer chains the L2 rebuild"


@pytest.mark.parametrize("key", ["situations_written", "events_correlated", "nodes_registered"])
def test_each_moved_key_alone_is_enough_to_rerun_the_chain(monkeypatch, key):
    """Any one phase doing work is enough. An earlier draft required a situation or a deal, so a
    drain that only claimed aliases or only correlated events reported "nothing moved"."""
    monkeypatch.setattr(routes, "_graph", object(), raising=False)

    import genios_engine.context.backfill as l2_backfill
    monkeypatch.setattr(l2_backfill, "backfill_layer2", lambda *a, **k: {key: 1}, raising=False)
    assert routes._replay_l2_history("org_test") is True
