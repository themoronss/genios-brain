"""A user received 21 cards on a day the budget said 15.

    pytest tests/reason/test_the_compiled_lane_obeys_the_daily_budget.py -q

Three lanes check the daily cap before publishing — legacy rules, native capabilities and the
composite composer all compute `budget_per_day * active_seats - _budget_used` and suppress the
surplus with a counted reason. The compiled lane checked nothing, and `reason/runner` calls it
LAST, after the other three have already spent against that cap. So it did not merely ignore the
budget: it spent past a limit the others had respected on its behalf.

MEASURED ON THE PILOT, signals published per day against a cap of 15:

    2026-09-16   15   (exactly the cap)
    2026-09-15   21   (six over — the surplus is this lane's 8)
    2026-09-14   15   (exactly the cap)
    2026-09-13   15   (exactly the cap)

The other lanes stop dead on 15 three days running, which is what a respected cap looks like. The
one day the total is different is the day this lane had the most to say.

ONE POOL, NOT A SECOND ALLOWANCE. `_budget_used` counts every signal the tenant published today
whatever wrote it, so taking the same subtraction keeps one cap rather than creating another
behind it. `packs/general_v1` states the intent in as many words: "the daily signal budget is
shared org-wide, so matching numbers keeps the cap combined, not doubled".
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.reason import domain_shadow as DS

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
PACK = {"pack_id": "admin", "version": "1.0.0", "revision": 1,
        "snapshot_id": "cfg_1", "rule_ids": set(), "budget_per_day": 15}


def _allowance(monkeypatch, *, seats, used, pack=PACK):
    monkeypatch.setattr("genios_engine.reason.runner._active_seats", lambda store, org: seats)
    monkeypatch.setattr("genios_engine.reason.runner._budget_used",
                        lambda store, org, at: used)
    return DS._daily_allowance(object(), "org_1", NOW, pack)


def test_the_lane_takes_what_the_other_three_left(monkeypatch) -> None:
    """The 2026-09-16 shape: nine signals already published against a cap of fifteen."""
    assert _allowance(monkeypatch, seats=1, used=9) == 6


def test_a_cap_already_spent_leaves_nothing(monkeypatch) -> None:
    """The 2026-09-14 shape: the legacy lane took the whole day. This lane publishes nothing,
    which is the correct outcome — the budget exists to cap the PERSON's day, not each lane's."""
    assert _allowance(monkeypatch, seats=1, used=15) == 0


def test_an_overspent_day_never_goes_negative(monkeypatch) -> None:
    """The 2026-09-15 shape, after the fact. A negative allowance would sort oddly and could
    wrap into 'plenty left' through any later arithmetic."""
    assert _allowance(monkeypatch, seats=1, used=21) == 0


def test_the_cap_scales_with_seats(monkeypatch) -> None:
    """The spec's rule is per user, never per tenant — a five-person team is not capped at one
    person's worth of attention."""
    assert _allowance(monkeypatch, seats=5, used=0) == 75


def test_a_database_hiccup_does_not_silence_the_day(monkeypatch) -> None:
    """NEVER ZERO ON FAILURE. Refusing to publish because a COUNT failed would turn a transient
    error into a silent day with no advice — a worse failure than one card over a soft cap."""
    def _boom(*a, **k):
        raise RuntimeError("connection reset")
    monkeypatch.setattr("genios_engine.reason.runner._active_seats", _boom)
    assert DS._daily_allowance(object(), "org_1", NOW, PACK) == 15


def test_a_pack_with_no_budget_stated_falls_back(monkeypatch) -> None:
    """Seven is the figure `reason/runner` already defaults to; the two must not disagree."""
    bare = {**PACK}
    del bare["budget_per_day"]
    assert _allowance(monkeypatch, seats=1, used=0, pack=bare) == 7


def test_only_an_emitted_row_spends_the_budget() -> None:
    """`standing` left yesterday's advice alone and `nothing_to_emit` concluded no action —
    neither put a card in front of anybody, so neither may consume a person's daily attention.
    Read from the source, because the alternative is a lane that quietly starves itself."""
    import inspect

    source = inspect.getsource(DS.shadow_compile)
    assert 'if outcome == "emitted" and _remaining[0] is not None:' in source, (
        "the budget is spent on an outcome that never reached a queue")
    assert 'counts["budget_exhausted"] += 1' in source, (
        "a lane that stops publishing for a reason nobody can see is indistinguishable "
        "from one that had nothing to say")
