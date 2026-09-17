"""Reconnecting Gmail dead-lettered every attachment parked before that day.

`_attachment_connector_for` resolved the tenant's connector by the `connection_id` recorded on
the event AT CAPTURE TIME. Reconnecting a source writes a NEW connection row and drops the old
one, so every attachment parked before the reconnect named an id `get` could no longer find. The
drain read that as "no live connector", classified it TRANSIENT, walked the five-rung ladder and
dead-lettered the row.

MEASURED ON THE LIVE DATABASE, 17 Sep 2026:

    160 parked rows across two orgs carrying `no live connector for source 'gmail'`
    160 of 160 naming a connection_id absent from `connections`
      0 of 160 naming one that is present
    2,170 refetch attempts spent dead-lettering a backlog nothing was wrong with

Both orgs held a `connected`, unexpired gmail connection for the whole period. The resolver's own
docstring promised "a tenant who reconnects tomorrow gets their backlog drained tomorrow", and
reconnecting was the precise act that made it impossible.

THE FALLBACK IS BOUNDED, and the last three tests are what bound it. A recorded connection
belonging to ANOTHER org is a data-integrity fault, not a missing id, and must not fall back. A
source with no attachment fetch must still resolve to None. And an org with no live connection at
all must still be a transient miss rather than an exception.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

pytest.importorskip("sqlalchemy")


@dataclass(frozen=True)
class _Candidate:
    org_id: str
    source: str
    connection_id: str


@dataclass(frozen=True)
class _Conn:
    connection_id: str
    org_id: str
    source_type: str


class _Store:
    """The two calls the resolver makes, and nothing else."""

    def __init__(self, conns):
        self._conns = list(conns)

    def get(self, connection_id):
        return next((c for c in self._conns if c.connection_id == connection_id), None)

    def list_active(self, source_type=None):
        return [c for c in self._conns
                if source_type is None or c.source_type == source_type]


class _Fetcher:
    def fetch_attachment(self, message_id, attachment_id):  # pragma: no cover - never called here
        return b""


class _NoFetch:
    """A connector for a source that cannot hand back bytes."""


@pytest.fixture()
def resolve(monkeypatch):
    from genios_engine.api import routes

    def _install(conns, connector=_Fetcher()):
        monkeypatch.setattr(routes, "_connections", _Store(conns), raising=False)
        monkeypatch.setattr(routes, "make_connector_for", lambda _c: connector, raising=False)
        return routes._attachment_connector_for

    return _install


LIVE = _Conn("con_new", "org_1", "gmail")
OTHER_ORG = _Conn("con_theirs", "org_2", "gmail")


# =============================================================================================
# the defect
# =============================================================================================
def test_an_attachment_parked_before_a_reconnect_still_resolves(resolve):
    """The 160. The recorded id is gone; the org's live gmail connection is right there."""
    r = resolve([LIVE])

    assert r(_Candidate("org_1", "gmail", "con_old_and_gone")) is not None


def test_the_recorded_connection_is_still_preferred_when_it_exists(resolve):
    """The fallback is for an id that is GONE. An id that resolves is used as before."""
    recorded = _Conn("con_recorded", "org_1", "gmail")
    r = resolve([recorded, LIVE])

    assert r(_Candidate("org_1", "gmail", "con_recorded")) is not None


# =============================================================================================
# what the fallback must NOT reach
# =============================================================================================
def test_a_recorded_connection_owned_by_another_org_never_falls_back(resolve):
    """A wrong id is not a missing id. This is a data-integrity fault and the answer stays None,
    even though this org has a perfectly good connection of its own."""
    r = resolve([OTHER_ORG, LIVE])

    assert r(_Candidate("org_1", "gmail", "con_theirs")) is None


def test_the_fallback_never_crosses_an_org(resolve):
    """`list_active` yields the whole fleet. Only this tenant's own connections may answer."""
    r = resolve([OTHER_ORG])

    assert r(_Candidate("org_1", "gmail", "con_gone")) is None


def test_the_fallback_never_crosses_a_source(resolve):
    """A calendar connection cannot hand back a mail attachment."""
    r = resolve([_Conn("con_cal", "org_1", "gcal")])

    assert r(_Candidate("org_1", "gmail", "con_gone")) is None


def test_a_connector_that_cannot_fetch_attachments_is_not_offered(resolve):
    """The shape check is kept: a connector without `fetch_attachment` would raise inside the
    drain instead of being classified as a miss."""
    r = resolve([LIVE], connector=_NoFetch())

    assert r(_Candidate("org_1", "gmail", "con_gone")) is None


def test_an_org_with_no_connection_is_a_miss_and_not_an_exception(resolve):
    """None is what the drain reads as a transient miss. Raising here would end the whole cycle
    for every other tenant in it."""
    r = resolve([])

    assert r(_Candidate("org_1", "gmail", "con_gone")) is None
