"""The trim is housekeeping. The thing that must be true of housekeeping is that it cannot cost
you the work it runs after — so most of what is asserted here is about what it must NOT do."""

from __future__ import annotations

import threading

import genios_engine.platform.memory as mem


def _reset_lookup():
    mem._trim = None
    mem._looked_up = False


def test_release_is_a_no_op_off_glibc_and_never_raises(monkeypatch):
    """A developer's Mac has no malloc_trim. That is a False, not a traceback: the call sites run
    on the tail of a completed sync and must behave identically on every platform."""
    _reset_lookup()
    monkeypatch.setattr(mem.platform, "system", lambda: "Darwin")
    assert mem.release_free_memory("sync") is False
    _reset_lookup()


def test_release_never_raises_when_the_libc_call_fails(monkeypatch):
    """The run has already finished when this is called. Losing it to a housekeeping failure would
    be strictly worse than a high memory reading, which is the whole thing this is fixing."""
    _reset_lookup()

    def boom(_):
        raise OSError("no")

    monkeypatch.setattr(mem, "_malloc_trim", lambda: boom)
    assert mem.release_free_memory() is False
    _reset_lookup()


def test_release_reports_whether_the_allocator_gave_anything_back(monkeypatch):
    _reset_lookup()
    monkeypatch.setattr(mem, "_malloc_trim", lambda: (lambda _: 1))
    assert mem.release_free_memory("warm lane") is True
    monkeypatch.setattr(mem, "_malloc_trim", lambda: (lambda _: 0))
    assert mem.release_free_memory() is False
    _reset_lookup()


def test_lookup_happens_once_even_across_threads(monkeypatch):
    """Called from every worker thread on every drain. It resolves a symbol once and caches the
    answer — including the negative one — so the steady state is a pointer read."""
    _reset_lookup()
    calls = []
    monkeypatch.setattr(mem.platform, "system", lambda: (calls.append(1), "Darwin")[1])
    threads = [threading.Thread(target=mem.release_free_memory) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) <= 1
    _reset_lookup()


def test_rss_is_a_number_or_none_never_an_exception():
    v = mem.rss_mb()
    assert v is None or (isinstance(v, float) and v > 0)
