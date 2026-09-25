"""L3-06 · the heartbeat that notices what did NOT happen, and the one asymmetry guarding it.

⛔ THE PLAN WAS WRONG ABOUT THIS, LOUDLY AND ACROSS FIVE DOCUMENTS. It said "nothing evaluates when
nothing arrives — due_evaluation 0 files, next_evaluation 0 files" and called it the biggest
functional gap in Layer 3. Elapsed time is evaluated at FOUR levels, all of them live:

    platform/scheduler   a heavy tick every `sync_interval_hours` (6.0) runs L1 -> L2/L3/L5 for
                         EVERY org, whether or not a single message arrived
    reason/runner        per-rule cooldowns, so repeated ticks over unchanged data do not
                         re-card the same subject
    executions           `next_check_at` IS a registered due instant, with a real due query:
                         `and (next_check_at is null or next_check_at <= :n)`
    situations           `age_uncorrelated_situations` moves a quiet situation to `dormant` on
                         time alone

And `test_the_heavy_sweep_still_reasons_for_every_org` in this directory already pins the first.

WHAT IS ACTUALLY MISSING IS ONE ASYMMETRY. `test_the_light_tick_is_marked_and_asks_for_chain_on_
new_data_only` pins that the LIGHT tick asks for the optimisation. NOTHING PINS THAT THE HEAVY TICK
DOES NOT — and the cost argument pushes the wrong way: the chain "costs ~11k statements at zero
events", so skipping quiet orgs on the heavy tick reads as a free win. It is not. It is the entire
ability to notice that nobody replied.
"""
from __future__ import annotations

import inspect

from genios_engine.platform import scheduler as S


def test_the_heavy_tick_does_not_ask_for_the_new_data_shortcut():
    """⛔ THE ONE LINE THAT WOULD SILENTLY END TIME-BASED INTELLIGENCE.

    `_tick` -> `run_maintenance_sweep()` -> `run_sync_sweep(mode=..., limit=...)`, and
    `chain_only_on_new_data` defaults to False. Adding it anywhere on that path would stop a quiet
    org from being reasoned about at all, and EVERY EXISTING TEST WOULD STILL PASS: the sweep tests
    call `run_sync_sweep` directly, and the light-tick tests assert the optimisation is present.
    A reader looking for prior art would find only encouragement.
    """
    src = inspect.getsource(S._tick)
    assert "chain_only_on_new_data" not in src, (
        "the HEAVY tick asks to skip orgs with no new events. That is not an optimisation — it is "
        "the removal of the only pass that notices a promise nobody answered. The light tick "
        "exists for exactly this saving and already takes it.")


def test_the_two_ticks_still_differ_in_exactly_this_one_way():
    """The saving must survive. If the light tick ever stops asking for it, every 15-minute tick
    pays for a full chain per quiet org — which is the cost the split was created to avoid, and a
    guard that only pushed one way would invite it."""
    assert "chain_only_on_new_data=True" in inspect.getsource(S._light_tick)


def test_the_heavy_tick_runs_the_maintenance_sweep_not_the_sync_sweep():
    """⛔ The heavy tick is also where card expiry, snooze-wake, retention and billing ride. Pointing
    it at `run_sync_sweep` would keep the reasoning and silently drop four other clocks — each of
    which is time-triggered work with no other home."""
    src = inspect.getsource(S._tick)
    assert "run_maintenance_sweep()" in src
    assert "run_sync_sweep" not in src


def test_the_heartbeat_is_bounded_so_one_hang_cannot_end_all_of_them():
    """Root-caused 2026-08-18 → 08-21: one Composio call with no timeout hung inside one org's
    sync and froze every future tick for three days, with nothing in the logs — a bare
    `except Exception` never fires on a hang. Time-based intelligence dies quietly when its
    heartbeat does, so the bound is part of the property this file protects."""
    assert S._SWEEP_TIMEOUT_S > 0
    assert "_run_sweep_bounded" in inspect.getsource(S)
