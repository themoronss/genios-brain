"""The one failure the kill switch documents itself as surviving was the one it re-raised.

    pytest tests/platform/test_a_kill_switch_fails_open.py -q

Both switches say the same thing in their own comments — *"fail-open like the global switch — an
infra hiccup never blocks a legitimate tenant"* — and both were written like this:

    try:
        with _engine().connect() as c:      # raises HTTPException(503) with no database
            ...
        if not live:
            raise HTTPException(503, "...paused")
    except HTTPException:
        raise                               # ← lets BOTH 503s past
    except Exception:
        return                              # infra hiccup → fail open

The `except HTTPException: raise` is there so the deliberate pause reaches the caller. It also
re-raises the 503 `_engine()` itself raises when no database is configured — so a config or
connectivity problem returned "This workspace is paused" to every request, from a function whose
entire contract is that it does not do that.

WHAT IT COST, BEYOND PRODUCTION. 22 of this repo's 35 standing test failures were this: every
route behind `require_owner` or `get_current_org` returned 503 under a test client with no
database, and the failures read as fixture problems in six unrelated files.

The fix is structural rather than a wider `except`: the decision is made inside the guard and the
refusal is raised OUTSIDE it, on a `live` flag that stays True unless the flag row actually said
otherwise. An unreadable table can no longer reach the `raise` at all.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from genios_engine.platform import auth

pytestmark = pytest.mark.unit


class _Cache:
    """A cache that holds nothing, so every call takes the database path under test."""

    def get(self, key):
        return None

    def setex(self, *a, **k):
        return None


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch):
    monkeypatch.setattr(auth, "get_cache", _Cache)


def _engine_raises(exc):
    def _boom():
        raise exc
    return _boom


def test_no_database_does_not_pause_the_tenant(monkeypatch) -> None:
    """THE DEFECT. `_engine()` raises `HTTPException(503, "no database configured")`, which is an
    infra failure wearing the one exception type the guard let through."""
    monkeypatch.setattr(auth, "_engine",
                        _engine_raises(HTTPException(503, "auth not available (no database)")))
    assert auth.check_org_kill("org_1") is None


def test_no_database_does_not_take_the_service_offline(monkeypatch) -> None:
    """Same defect in the global switch, which every request passes through."""
    monkeypatch.setattr(auth, "_engine",
                        _engine_raises(HTTPException(503, "auth not available (no database)")))
    assert auth.check_kill_switch() is None


@pytest.mark.parametrize("failure", [
    RuntimeError("connection reset"),
    TimeoutError("statement timeout"),
    HTTPException(503, "no database configured"),
], ids=["reset", "timeout", "no_database"])
def test_every_infrastructure_failure_fails_open(monkeypatch, failure) -> None:
    """The contract, stated as one property: whatever goes wrong READING the flag, a legitimate
    tenant is waved through. Only the flag's own value may refuse them."""
    monkeypatch.setattr(auth, "_engine", _engine_raises(failure))
    assert auth.check_org_kill("org_1") is None
    assert auth.check_kill_switch() is None


def test_a_tenant_that_was_actually_paused_is_still_refused(monkeypatch) -> None:
    """The half that must survive the fix. Failing open on an unreadable flag must not become
    failing open on a flag that was read and said stop."""
    class _Row:
        enabled = False

    class _Conn:
        def execute(self, *a, **k):
            return type("R", (), {"first": staticmethod(lambda: _Row())})()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(auth, "_engine", lambda: type("E", (), {"connect": staticmethod(_Conn)})())

    with pytest.raises(HTTPException) as caught:
        auth.check_org_kill("org_1")
    assert caught.value.status_code == 503
    assert caught.value.detail["error"] == "TENANT_PAUSED"

    with pytest.raises(HTTPException) as caught:
        auth.check_kill_switch()
    assert caught.value.detail["error"] == "SERVICE_UNAVAILABLE"


def test_an_absent_flag_row_means_live(monkeypatch) -> None:
    """A tenant nobody ever paused has no row. That is not a missing answer, it is 'live'."""
    class _Conn:
        def execute(self, *a, **k):
            return type("R", (), {"first": staticmethod(lambda: None)})()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(auth, "_engine", lambda: type("E", (), {"connect": staticmethod(_Conn)})())
    assert auth.check_org_kill("org_1") is None
    assert auth.check_kill_switch() is None
