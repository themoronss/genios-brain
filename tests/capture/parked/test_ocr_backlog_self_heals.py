"""Turning OCR on is ONE act, not three — the backlog comes back on its own.

    pytest tests/capture/parked/test_ocr_backlog_self_heals.py -q

Production holds 719 pending document parks and 50 dead-lettered ones, and every one of them is
waiting on the same thing: an OCR engine. Two things stood between "the engine exists" and "those
files get read", and both were the same shape — machinery that existed and, on the day it would
matter, nothing reached it.

* `refetch_parked_attachments` takes an `ocr` argument and the heartbeat never passed one. So the
  ladder would have re-fetched every scanned file, re-judged it with a toolchain that cannot read
  it, and spent an attempt doing so — for ever, engine or no engine.
* `requeue_dead_letters` had one caller, an HTTP route somebody had to remember to hit. The fifty
  rows that walked the ladder BEFORE an engine existed would have stayed dead, so "turn OCR on"
  quietly meant "turn OCR on and then also go and requeue".

What this file pins is the promise: set the flag, and the heartbeat does the rest — bounded, so it
cannot become a loop, and silent when there is no engine, so nothing changes for a host that has
not been given one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.api import routes
from genios_engine.capture.parked.refetch import InMemoryRefetchQueue, RefetchCandidate

NOW = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)
ORG = "org_ocr_backlog"


class _Ocr:
    """Stands in for the tesseract wrapper. Never called here — what is under test is which
    scopes the engine reaches, not what it reads."""

    name = "fake-tesseract"

    def ocr(self, path):                                  # pragma: no cover - not reached
        raise AssertionError("the drain should not OCR anything in this test")


def _dead(event_id: str, *, code: str = "DOC-06", last_attempt: datetime | None = None,
          org: str = ORG) -> tuple[RefetchCandidate, datetime | None]:
    # `last_attempt_at` is the QUEUE's memory, not the candidate's — the in-memory store keeps it
    # in its own map, exactly as the table keeps it in its own column.
    candidate = RefetchCandidate(
        event_id=event_id, org_id=org, connection_id="con_1", reason_code=code,
        source_object_id="m_1::a_1", attempts=5, status="dead_letter",
        next_attempt_at=None, parked_at=NOW - timedelta(days=40), parent_object_id="m_1",
        object_type="email_attachment", source="gmail", filename="scan.png", mime="image/png")
    return candidate, last_attempt


def _queue(*rows: tuple[RefetchCandidate, datetime | None]) -> InMemoryRefetchQueue:
    queue = InMemoryRefetchQueue()
    for candidate, last_attempt in rows:
        queue.candidates[candidate.event_id] = candidate
        if last_attempt is not None:
            queue.last_attempt_at[candidate.event_id] = last_attempt
    return queue


@pytest.fixture
def drain(monkeypatch):
    """`_drain_attachment_refetch` with a live queue and no connector, so nothing is fetched."""
    def _run(queue, *, ocr=None, allowlist: str = "", enable_ocr: bool = False):
        monkeypatch.setattr(routes, "_attachment_refetch_queue", lambda: queue)
        monkeypatch.setattr(routes, "_attachment_connector_for", lambda _c: None)
        monkeypatch.setattr("genios_engine.platform.wiring.make_ocr",
                            lambda org_id=None: ocr if _allowed(org_id, allowlist, enable_ocr)
                            else None)
        settings = routes.get_settings()
        monkeypatch.setattr(settings, "ocr_enabled_orgs", allowlist, raising=False)
        monkeypatch.setattr(routes, "get_settings", lambda: settings)
        return routes._drain_attachment_refetch(NOW)

    def _allowed(org_id, allowlist, enable_ocr) -> bool:
        if org_id is None:
            return enable_ocr
        return org_id in {o.strip() for o in allowlist.split(",") if o.strip()}

    return _run


# =============================================================================================
# The requeue — an engine makes a capability dead letter retroactive
# =============================================================================================
def test_no_engine_means_nothing_moves(drain):
    """The state every host is in until the image ships one. A requeue here would put rows back
    on a ladder that is guaranteed to kill them again."""
    queue = _queue(_dead("evt_1", last_attempt=NOW - timedelta(days=30)))
    report = drain(queue, ocr=None)

    assert report["requeued"] == 0 and report["ocr_scopes"] == []
    assert queue.candidates["evt_1"].status == "dead_letter"


def test_an_engine_puts_the_old_backlog_back(drain):
    queue = _queue(_dead("evt_1", last_attempt=NOW - timedelta(days=30)))
    report = drain(queue, ocr=_Ocr(), enable_ocr=True)

    assert report["requeued"] == 1
    assert queue.candidates["evt_1"].status == "pending", "the row is still written off"
    # The SAME pass then claims it — requeue and drain run in one beat, which is the point: the
    # backlog starts moving on the tick after the flag, not on the tick after somebody notices.
    # So the ladder is reset and at most this one attempt has been spent against it.
    assert queue.candidates["evt_1"].attempts <= 1, "a requeued row kept its exhausted ladder"
    assert report["claimed"] == 1


def test_a_row_the_ladder_touched_this_week_is_left_alone(drain):
    """The loop guard. Without it the pass requeues, the ladder spends five attempts, the row
    dies, and the next heartbeat requeues it again — for ever."""
    queue = _queue(_dead("evt_1", last_attempt=NOW - timedelta(days=2)))
    assert drain(queue, ocr=_Ocr(), enable_ocr=True)["requeued"] == 0
    assert queue.candidates["evt_1"].status == "dead_letter"


def test_a_download_failure_is_not_requeued_by_an_ocr_engine(drain):
    """`DOC-05` is a fetch problem. An OCR engine says nothing about it, and requeueing it on that
    news is a guess about a different failure."""
    queue = _queue(_dead("evt_5", code="DOC-05", last_attempt=NOW - timedelta(days=30)))
    assert drain(queue, ocr=_Ocr(), enable_ocr=True)["requeued"] == 0


@pytest.mark.parametrize("code", ["DOC-02", "DOC-04", "DOC-06"])
def test_every_code_an_engine_can_settle_comes_back(drain, code):
    queue = _queue(_dead(f"evt_{code}", code=code, last_attempt=NOW - timedelta(days=30)))
    assert drain(queue, ocr=_Ocr(), enable_ocr=True)["requeued"] == 1


# =============================================================================================
# The scopes — a per-tenant allowlist has to reach the drain, not just the sweep
# =============================================================================================
def test_an_allowlisted_org_is_drained_with_its_own_engine(drain):
    """OCR rolls out per tenant (`GENIOS_OCR_ENABLED_ORGS`), so a fleet-only drain would leave the
    pilot org's backlog judged by the toolchain the fleet has — which is none."""
    report = drain(_queue(), ocr=_Ocr(), allowlist=ORG, enable_ocr=False)
    assert report["ocr_scopes"] == [ORG]


def test_the_fleet_flag_reaches_every_tenant(drain):
    report = drain(_queue(), ocr=_Ocr(), enable_ocr=True)
    assert report["ocr_scopes"] == ["fleet"]


def test_both_scopes_run_when_both_are_configured(drain):
    """And the allowlisted org runs FIRST: the fleet pass claims across every tenant, so a row it
    takes with the weaker engine has already spent an attempt."""
    report = drain(_queue(), ocr=_Ocr(), allowlist=ORG, enable_ocr=True)
    assert report["ocr_scopes"] == [ORG, "fleet"]
