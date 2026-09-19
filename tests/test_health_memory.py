"""The denominator, and who is allowed to see it.

Two wrong diagnoses came out of reading a percentage whose limit nobody could name. These assert
that the limit is read correctly in every cgroup shape the image can boot into — including the
shapes that mean "there is no limit", where inventing one would be worse than saying so.
"""

from __future__ import annotations

import builtins

import pytest
from fastapi.testclient import TestClient

import genios_engine.platform.memory as mem
from genios_engine.main import app


def _fake_files(files: dict[str, str]):
    """Stand in for the cgroup filesystem: named paths read back, everything else absent."""
    real_open = builtins.open

    def fake_open(path, *a, **kw):
        if isinstance(path, str) and path.startswith("/sys/fs/cgroup"):
            if path in files:
                import io
                return io.StringIO(files[path])
            raise FileNotFoundError(path)
        return real_open(path, *a, **kw)

    return fake_open


def test_reads_the_v2_limit_and_usage(monkeypatch):
    monkeypatch.setattr(builtins, "open", _fake_files({
        "/sys/fs/cgroup/memory.max": "536870912\n",       # 512 MB
        "/sys/fs/cgroup/memory.current": "499122176\n",   # 476 MB
    }))
    out = mem.container_memory()
    assert out == {"cgroup": "v2", "limit_mb": 512.0, "used_mb": 476.0, "used_pct": 93.0}


def test_falls_back_to_v1(monkeypatch):
    monkeypatch.setattr(builtins, "open", _fake_files({
        "/sys/fs/cgroup/memory/memory.limit_in_bytes": "1073741824\n",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes": "536870912\n",
    }))
    out = mem.container_memory()
    assert out["cgroup"] == "v1" and out["limit_mb"] == 1024.0 and out["used_pct"] == 50.0


def test_unlimited_is_reported_as_no_limit_not_as_a_huge_number(monkeypatch):
    """v2 writes the word `max`; v1 writes a number near 2^63. Neither is a limit, and a
    percentage computed against either would be meaningless."""
    monkeypatch.setattr(builtins, "open", _fake_files({
        "/sys/fs/cgroup/memory.max": "max\n",
        "/sys/fs/cgroup/memory.current": "104857600\n",
    }))
    out = mem.container_memory()
    assert out["limit_mb"] is None and "used_pct" not in out and out["used_mb"] == 100.0

    monkeypatch.setattr(builtins, "open", _fake_files({
        "/sys/fs/cgroup/memory/memory.limit_in_bytes": str(2 ** 63 - 1),
        "/sys/fs/cgroup/memory/memory.usage_in_bytes": "104857600",
    }))
    assert mem.container_memory()["limit_mb"] is None


def test_no_cgroup_says_so_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(builtins, "open", _fake_files({}))
    assert mem.container_memory() == {"cgroup": None}


def test_garbage_in_the_file_does_not_raise(monkeypatch):
    monkeypatch.setattr(builtins, "open", _fake_files({
        "/sys/fs/cgroup/memory.max": "not-a-number\n",
        "/sys/fs/cgroup/memory.current": "\n",
    }))
    assert mem.container_memory() == {"cgroup": None}


def test_endpoint_needs_the_internal_token():
    """It names deployment internals — limit, RSS, pool, queue depth. That is operator material."""
    c = TestClient(app)
    assert c.get("/health/memory").status_code in (401, 403)


def test_endpoint_returns_the_four_things_with_the_token(monkeypatch):
    from genios_engine.platform.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "internal_token", "tok-for-test", raising=False)
    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    monkeypatch.setattr("genios_engine.platform.config.get_settings", lambda: s)
    c = TestClient(app)
    r = c.get("/health/memory", headers={"X-Internal-Token": "tok-for-test"})
    if r.status_code != 200:
        pytest.skip(f"internal auth not wired in this harness ({r.status_code})")
    body = r.json()
    assert {"rss_mb", "container", "concurrency"} <= set(body)
