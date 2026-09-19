"""Hand the allocator's free pages back to the operating system.

WHY THIS EXISTS. A sync is the memory high-water mark of the whole process: L1 holds message
bodies, L2 holds a batch of forty of them plus the model's prompt and reply, and it does that
across several workers at once. All of it is freed the moment the run ends — and none of it is
returned. CPython hands freed blocks back to glibc, glibc keeps the arenas, and the container's
memory reading stays pinned at the peak until something restarts the process.

That is how a box at 6% CPU with nothing running reports 92% memory. Nothing is leaking and
nothing is stuck; the glass is simply still on the table. The only thing missing is somebody
telling the allocator it may put it away.

`malloc_trim(0)` is that instruction. It walks glibc's arenas and releases what is genuinely
free. Two properties make it safe to call from the worker threads:

* it touches only memory nothing owns any more, so no in-flight request, sync, or queue row can
  be affected by it — which is also why it is called AFTER a run completes and never during one;
* it is advisory. On a platform without glibc there is no symbol to call and this becomes a
  no-op, so the same code runs on a developer's Mac and in the Debian image without branching at
  the call sites.

It is deliberately NOT a periodic task. Trimming costs a walk of the arenas and buys nothing when
no peak has happened, so it runs exactly where a peak just ended.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.memory")

_trim = None
_looked_up = False


def _malloc_trim():
    """glibc's `malloc_trim`, or None where there isn't one. Looked up once, cached either way."""
    global _trim, _looked_up
    if _looked_up:
        return _trim
    _looked_up = True
    if platform.system() != "Linux":
        return None
    try:
        name = ctypes.util.find_library("c") or "libc.so.6"
        fn = ctypes.CDLL(name).malloc_trim
        fn.argtypes = [ctypes.c_size_t]
        fn.restype = ctypes.c_int
        _trim = fn
    except (OSError, AttributeError):  # musl, or no libc to load — both mean "no trim here"
        _trim = None
    return _trim


def release_free_memory(reason: str = "") -> bool:
    """Return freed pages to the OS. True if the allocator actually released some.

    Never raises. This runs on the tail of a sync and on the tail of a warm-lane run, where the
    alternative to a failed trim is a slightly high memory reading — not a reason to lose the run
    that just finished.
    """
    fn = _malloc_trim()
    if fn is None:
        return False
    try:
        released = bool(fn(0))
    except Exception:  # noqa: BLE001 — a housekeeping call must never end a completed run
        return False
    if released:
        _log.info("released free memory to the OS%s", f" after {reason}" if reason else "")
    return released


def rss_mb() -> float | None:
    """Resident set size of this process in MB, or None where it cannot be read.

    Reported next to the resolved worker counts so "how much memory is this deployment using"
    stops being a question answered by reading a dashboard gauge and guessing which of several
    concurrency settings produced it.
    """
    try:
        with open("/proc/self/statm", encoding="ascii") as fh:
            pages = int(fh.read().split()[1])
    except (OSError, IndexError, ValueError):
        try:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception:  # noqa: BLE001
            return None
        # Linux reports ru_maxrss in KB, macOS in bytes. Only reached off /proc, i.e. not Linux.
        return round(peak / (1024 * 1024), 1)
    import os
    return round(pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)
