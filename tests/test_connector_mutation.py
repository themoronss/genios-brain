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
