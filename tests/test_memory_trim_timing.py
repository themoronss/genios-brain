"""WHEN the trim runs, which is the only part of it that can hurt.

Trimming is safe against memory nothing owns, but it is not free, and a trim between two jobs
that both need the same memory is pure cost. The rule the loops implement is: once per DRAIN —
after work happened and the queue has gone quiet — never between two consecutive jobs, and never
when there was no work at all.
"""

from __future__ import annotations

import threading

import genios_engine.platform.sync_worker as sw
import genios_engine.platform.warm_lane as wl


def _drive(loop, stop_event, jobs, trims, *, args):
    """Run a worker loop until its scripted job list is exhausted, then stop it."""
    t = threading.Thread(target=loop, args=args, daemon=True)
    t.start()
    for _ in range(200):
        if not jobs:
            break
        threading.Event().wait(0.01)
    stop_event.set()
    t.join(timeout=3)
    return trims


def test_sync_worker_trims_once_per_drain_not_once_per_job(monkeypatch):
    """Three jobs back to back, then an empty queue: one trim, at the end."""
    jobs = [True, True, True, False]
    trims: list[str] = []
    monkeypatch.setattr(sw, "_POLL_SECONDS", 0.01)
    monkeypatch.setattr("genios_engine.api.routes.run_one_sync_job",
                        lambda _w: jobs.pop(0) if jobs else False)
    monkeypatch.setattr("genios_engine.platform.memory.release_free_memory",
                        lambda reason="": trims.append(reason) or True)
    sw._stop.clear()
    _drive(sw._loop, sw._stop, jobs, trims, args=(0.0,))
    assert trims == ["sync"], f"expected one trim on the drain, got {trims}"


def test_sync_worker_does_not_trim_when_nothing_ran(monkeypatch):
    """An idle process polls forever. Trimming on every empty poll would burn CPU walking arenas
    that have nothing in them."""
    trims: list[str] = []
    monkeypatch.setattr(sw, "_POLL_SECONDS", 0.01)
    monkeypatch.setattr("genios_engine.api.routes.run_one_sync_job", lambda _w: False)
    monkeypatch.setattr("genios_engine.platform.memory.release_free_memory",
                        lambda reason="": trims.append(reason) or True)
    sw._stop.clear()
    t = threading.Thread(target=sw._loop, args=(0.0,), daemon=True)
    t.start()
    threading.Event().wait(0.15)
    sw._stop.set()
    t.join(timeout=3)
    assert trims == []


def test_a_crashing_job_still_lets_the_drain_trim(monkeypatch):
    """The loop swallows a job crash by design. The memory that job took is still freed, so the
    drain that follows must still trim — otherwise a failing sync is the one case that pins the
    high-water mark forever."""
    calls = {"n": 0}
    trims: list[str] = []

    def job(_w):
        calls["n"] += 1
        if calls["n"] == 1:
            return True
        if calls["n"] == 2:
            raise RuntimeError("sync blew up")
        return False

    monkeypatch.setattr(sw, "_POLL_SECONDS", 0.01)
    monkeypatch.setattr("genios_engine.api.routes.run_one_sync_job", job)
    monkeypatch.setattr("genios_engine.platform.memory.release_free_memory",
                        lambda reason="": trims.append(reason) or True)
    sw._stop.clear()
    t = threading.Thread(target=sw._loop, args=(0.0,), daemon=True)
    t.start()
    threading.Event().wait(0.2)
    sw._stop.set()
    t.join(timeout=3)
    assert trims == ["sync"]


def test_warm_lane_trims_on_the_drain_and_leaves_the_run_alone(monkeypatch):
    """The lane's chains must complete before anything is released — `run_once` returning True
    means a chain ran, and the trim is only reached on the tick that finds nothing."""
    order: list[str] = []
    runs = [True, True, False]

    def run_once(_engine, _worker):
        ran = runs.pop(0) if runs else False
        order.append("run" if ran else "idle")
        return ran

    monkeypatch.setattr(wl, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(wl, "_resolve_engine", lambda: object())
    monkeypatch.setattr(wl, "run_once", run_once)
    monkeypatch.setattr(wl, "housekeep", lambda _e: None)
    monkeypatch.setattr("genios_engine.platform.memory.release_free_memory",
                        lambda reason="": order.append("trim") or True)
    wl._stop.clear()
    t = threading.Thread(target=wl._loop, args=("w0", 0.0), daemon=True)
    t.start()
    threading.Event().wait(0.2)
    wl._stop.set()
    wl._wake.set()
    t.join(timeout=3)
    assert order[:4] == ["run", "run", "idle", "trim"], order
