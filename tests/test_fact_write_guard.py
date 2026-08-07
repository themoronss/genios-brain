"""fact_write_action — the guard between replays/backfills and current graph state.

These are the invariants every future backfill depends on. If one of these flips,
history can overwrite the present and the correct value is already stamped
'superseded' with no recovery tool. Treat this file as frozen behaviour."""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.context.graph_store import fact_write_action

T_OLD = datetime(2024, 3, 1, tzinfo=timezone.utc)
T_NEW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def act(**kw):
    base = dict(held_value_json='"them"', held_rank=2, held_occurred_at=T_NEW,
                new_value_json='"us"', new_rank=2, new_occurred_at=T_OLD, replay=False)
    base.update(kw)
    return fact_write_action(**base)


def test_no_held_row_inserts():
    assert act(held_value_json=None) == "insert"
    assert act(held_value_json=None, replay=True) == "insert"   # filling a gap is fine in replay


def test_same_value_is_noop():
    assert act(new_value_json='"them"') == "noop"
    assert act(new_value_json='"them"', replay=True) == "noop"


def test_older_occurred_at_never_overwrites():
    """THE replay-corruption guard: 2024 ball_in_court=us must not beat today's =them."""
    assert act(new_occurred_at=T_OLD, held_occurred_at=T_NEW) == "historical"


def test_stale_beats_authority_check():
    """Old high-rank data is still old — record history, don't supersede and don't flag."""
    assert act(new_rank=4, new_occurred_at=T_OLD, held_occurred_at=T_NEW) == "historical"
    # and old LOW-rank data doesn't spray discrepancies against current state either
    assert act(new_rank=1, new_occurred_at=T_OLD, held_occurred_at=T_NEW) == "historical"


def test_newer_same_rank_supersedes():
    assert act(new_occurred_at=T_NEW, held_occurred_at=T_OLD) == "supersede"


def test_newer_lower_rank_opens_discrepancy():
    assert act(new_rank=1, held_rank=3,
               new_occurred_at=T_NEW, held_occurred_at=T_OLD) == "discrepancy"


def test_replay_never_supersedes_even_when_newer():
    assert act(new_occurred_at=T_NEW, held_occurred_at=T_OLD, replay=True) == "historical"


def test_missing_timestamps_keep_live_semantics():
    # no timestamps on either side → order unknowable → live path (supersede/discrepancy)
    assert act(held_occurred_at=None, new_occurred_at=None) == "supersede"
    assert act(held_occurred_at=None, new_occurred_at=None, new_rank=1,
               held_rank=3) == "discrepancy"
    # but replay still refuses to touch state without proof of order
    assert act(held_occurred_at=None, new_occurred_at=None, replay=True) == "historical"


def test_naive_and_string_timestamps_normalize():
    naive_old = datetime(2024, 3, 1)                       # naive → assumed UTC
    assert act(new_occurred_at=naive_old, held_occurred_at=T_NEW) == "historical"
    assert act(new_occurred_at="2024-03-01T00:00:00Z", held_occurred_at=T_NEW) == "historical"
