"""Notion/Drive connectors must (a) version mutable objects so EDITS re-land in the
graph, and (b) honour `since` BEFORE downloading content so a sweep doesn't re-fetch the
whole workspace/Drive.

content_version folds into dedup_key (an edited page/file dedups on id alone and freezes
at first-seen text without it); Drive's incremental_changes ignored `since` entirely
(every 6-hourly sweep re-listed AND re-downloaded everything).
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.drive import ComposioDriveConnector
from genios_engine.capture.connectors.notion import ComposioNotionConnector


class _FakeExec:
    """Records every Composio call so we can assert downloads are SKIPPED for
    filtered-out objects, not just that the final batch is small."""

    def __init__(self, responses: dict):
        self._responses = responses
        self.calls: list[str] = []

    def execute(self, slug: str, arguments: dict) -> dict:
        self.calls.append(slug)
        return self._responses.get(slug, {})


def _notion(responses):
    c = ComposioNotionConnector(api_key="k", user_id="u")
    c._x = _FakeExec(responses)
    return c


def _drive(responses):
    c = ComposioDriveConnector(api_key="k", user_id="u")
    c._x = _FakeExec(responses)
    return c


# ── content_version: an edit must produce a NEW version so dedup re-lands it ──

def test_notion_sets_content_version_from_last_edited():
    page = {"id": "p1", "last_edited_time": "2026-08-01T10:00:00Z",
            "properties": {}, "url": "http://n/p1"}
    c = _notion({"NOTION_GET_PAGE_MARKDOWN": {"markdown": "hello"}})
    batch = c._to_batch({"results": [page]})
    assert batch.objects[0].content_version == "2026-08-01T10:00:00Z"


def test_drive_sets_content_version_from_modified_time():
    f = {"id": "f1", "name": "spec.txt", "mimeType": "text/plain",
         "modifiedTime": "2026-08-01T10:00:00Z"}
    c = _drive({"GOOGLEDRIVE_DOWNLOAD_FILE": {"content": "hello"}})
    batch = c._to_batch({"files": [f]})
    assert batch.objects[0].content_version == "2026-08-01T10:00:00Z"


# ── since: unchanged files are filtered BEFORE the expensive download ──

def test_drive_since_skips_download_of_unchanged_files():
    since = datetime(2026, 7, 1, tzinfo=timezone.utc)
    old = {"id": "old", "name": "old.txt", "mimeType": "text/plain",
           "modifiedTime": "2026-06-01T00:00:00Z"}          # before `since`
    new = {"id": "new", "name": "new.txt", "mimeType": "text/plain",
           "modifiedTime": "2026-08-01T00:00:00Z"}          # after `since`
    c = _drive({"GOOGLEDRIVE_DOWNLOAD_FILE": {"content": "hi"}})
    batch = c._to_batch({"files": [old, new]}, since=since)

    ids = [o.source_object_id for o in batch.objects]
    assert ids == ["new"]                                   # old file dropped
    # and crucially the old file was NEVER downloaded — one download call, for "new" only
    assert c._x.calls.count("GOOGLEDRIVE_DOWNLOAD_FILE") == 1


# ── the fields-mask retry, which used to fire on every failure ──────────────────────────────

class _FailingExec:
    """Fails the first LIST with a given error, then succeeds. Counts the attempts, because the
    cost this test is about is the SECOND CALL, not the final answer."""

    def __init__(self, error: BaseException):
        self._error = error
        self.attempts: list[dict] = []

    def execute(self, slug: str, arguments: dict) -> dict:
        self.attempts.append(dict(arguments))
        if len(self.attempts) == 1:
            raise self._error
        return {"files": []}


def test_a_rejected_fields_mask_is_retried_once_without_it():
    """The mask is an ENRICHMENT, never a dependency. `fields` is a Drive parameter, not a Composio
    one, and whether it survives the unpinned tool wrapper is not something we control — so a
    rejection of the argument must not stop the only call this connector has."""
    c = _drive({})
    c._x = _FailingExec(ValueError("400 Bad Request: unknown parameter 'fields'"))
    assert c._list(limit=5, page_token=None) == {"files": []}
    assert len(c._x.attempts) == 2
    assert "fields" in c._x.attempts[0] and "fields" not in c._x.attempts[1]


def test_an_auth_or_quota_failure_is_not_paid_for_twice():
    """The bug: `except Exception` retried on EVERYTHING. An expired token, a 429 or an exhausted
    quota has nothing to do with the mask, and dropping `fields` cannot fix any of them — so each
    one cost a second identical call against the connector's only endpoint, doubling the pressure
    at exactly the moment we are being rate-limited. The retry now needs positive evidence that the
    ARGUMENT was rejected."""
    for error in (RuntimeError("401 Unauthorized"),
                  RuntimeError("429 Too Many Requests"),
                  RuntimeError("403 quota exceeded for this project"),
                  RuntimeError("connection reset by peer")):
        c = _drive({})
        c._x = _FailingExec(error)
        try:
            c._list(limit=5, page_token=None)
        except Exception as raised:
            assert raised is error, error
        else:
            raise AssertionError(f"{error!r} was swallowed by the mask retry")
        assert len(c._x.attempts) == 1, f"{error!r} cost a second identical call"


def test_a_provider_message_that_mentions_fields_while_denying_access_still_does_not_retry():
    """The two hint lists are ordered, and this is why. A 403 body can quote the request back —
    `fields` included — so a message-substring test that checked the mask hints first would read a
    permission denial as an argument rejection and retry it."""
    c = _drive({})
    c._x = _FailingExec(RuntimeError("403 insufficient permission for fields=files(id,name)"))
    try:
        c._list(limit=5, page_token=None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a 403 was swallowed")
    assert len(c._x.attempts) == 1


def test_a_hung_call_is_not_waited_out_twice():
    """`composio_base.execute` bounds every call with `.result(timeout=...)`, so a hung Drive call
    surfaces as TimeoutError. Retrying it makes the connector wait the whole deadline a second time
    before the sweep learns anything — and the scheduler processes connections on one thread."""
    c = _drive({})
    c._x = _FailingExec(TimeoutError())
    try:
        c._list(limit=5, page_token=None)
    except TimeoutError:
        pass
    else:
        raise AssertionError("the deadline was swallowed")
    assert len(c._x.attempts) == 1
