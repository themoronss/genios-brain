from __future__ import annotations

from genios_engine.capture.connectors.drive import ComposioDriveConnector
from genios_engine.capture.connectors.notion import ComposioNotionConnector
from genios_engine.capture.landing.normalize import to_source_event

# Drive files and Notion pages are MUTABLE documents. An edit must re-land (new
# content_version → new dedup_key) so the updated body reaches L2 — before this fix
# they carried no content_version, shared the first-seen dedup_key, and every later
# revision was deduped away (only the first version was ever captured).


class _FakeExec:
    """Stands in for ComposioExec — returns canned action responses, no network."""

    def __init__(self, responses: dict) -> None:
        self._r = responses

    def execute(self, action: str, args: dict | None = None) -> dict:
        return self._r.get(action, {})


def test_notion_page_edit_relands_via_content_version():
    conn = ComposioNotionConnector.__new__(ComposioNotionConnector)   # skip __init__ (no network)
    conn._x = _FakeExec({"NOTION_GET_PAGE_MARKDOWN": {"markdown": "Refunds within 30 days."}})
    page = {"id": "pg1", "last_edited_time": "2026-07-30T09:00:00Z",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": "Refund policy"}]}},
            "last_edited_by": {"email": "ops@acme.io"}, "url": "https://notion.so/pg1"}
    raw = conn._to_raw(page)
    assert raw.content_version == "2026-07-30T09:00:00Z"
    # an edit bumps last_edited_time → different dedup_key → the new body can update the graph
    edited = {**page, "last_edited_time": "2026-07-31T18:00:00Z"}
    assert to_source_event(raw, org_id="o", connection_id="c").dedup_key != \
        to_source_event(conn._to_raw(edited), org_id="o", connection_id="c").dedup_key


def test_drive_file_edit_relands_via_content_version(monkeypatch):
    import genios_engine.capture.connectors.drive as drive_mod

    class _R:   # stand-in for the process_document result (content_version is independent of it)
        text = "handbook text"
        native_parse_used = True
        ocr_used = False
        ocr_engine = None
        ocr_pages = 0
        avg_confidence = 1.0
        status = "ok"

    monkeypatch.setattr(drive_mod, "process_document", lambda **kw: _R())

    conn = ComposioDriveConnector.__new__(ComposioDriveConnector)     # skip __init__ (no network)
    conn._x = _FakeExec({"GOOGLEDRIVE_DOWNLOAD_FILE": {"text": "handbook text"}})
    conn._ocr = None
    f = {"id": "f1", "modifiedTime": "2026-07-30T09:00:00Z", "name": "handbook.txt",
         "mimeType": "text/plain", "lastModifyingUser": {"emailAddress": "ops@acme.io"}}
    raw = conn._to_raw(f)
    assert raw.content_version == "2026-07-30T09:00:00Z"
    # a re-upload/edit bumps modifiedTime → different dedup_key → the edited file re-lands
    edited = {**f, "modifiedTime": "2026-07-31T18:00:00Z"}
    assert to_source_event(raw, org_id="o", connection_id="c").dedup_key != \
        to_source_event(conn._to_raw(edited), org_id="o", connection_id="c").dedup_key


def test_unedited_document_still_dedups():
    """An unchanged doc on re-sync keeps the same content_version → same dedup_key →
    no spurious re-land (the fix must not turn every sweep into duplicates)."""
    conn = ComposioNotionConnector.__new__(ComposioNotionConnector)
    conn._x = _FakeExec({"NOTION_GET_PAGE_MARKDOWN": {"markdown": "same body"}})
    page = {"id": "pg2", "last_edited_time": "2026-07-30T09:00:00Z", "properties": {}}
    a = to_source_event(conn._to_raw(page), org_id="o", connection_id="c").dedup_key
    b = to_source_event(conn._to_raw(dict(page)), org_id="o", connection_id="c").dedup_key
    assert a == b
