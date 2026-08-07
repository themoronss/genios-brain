from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from genios_engine.capture.documents.native import process_document

from .base import RawObject, SourceBatch
from .composio_base import ComposioExec

# Google Drive via Composio. Files are DOCUMENTS → download, extract text NATIVELY
# (HTML/docx/pdf/txt — no OCR), and hand the text to the gate/L2. Scanned images with
# no text layer would need OCR (Tesseract), wired separately. Paths finalized live.


def _parse_ts(s: str | None) -> datetime:
    if isinstance(s, str):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _raw_bytes(dl: dict) -> bytes | str:
    """Best-effort: pull file content out of the download response (text or base64)."""
    for k in ("content", "text", "data", "file", "body"):
        v = dl.get(k)
        if isinstance(v, str) and v:
            try:
                return base64.b64decode(v, validate=True)
            except Exception:
                return v
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
    return ""


class ComposioDriveConnector:
    source = "gdrive"

    def __init__(self, *, api_key: str, user_id: str, ocr=None) -> None:
        self._x = ComposioExec(api_key=api_key, user_id=user_id)
        self._ocr = ocr                  # OcrEngine | None — native-only if None

    def _list(self, *, limit: int, page_token: str | None) -> dict:
        args: dict[str, Any] = {"pageSize": limit,
                                "q": "trashed = false and mimeType != 'application/vnd.google-apps.folder'"}
        if page_token:
            args["pageToken"] = page_token
        return self._x.execute("GOOGLEDRIVE_LIST_FILES", args)

    def _to_batch(self, data: dict) -> SourceBatch:
        files = data.get("files") or data.get("items") or []
        objs = [self._to_raw(f) for f in files if isinstance(f, dict)]
        return SourceBatch(objects=[o for o in objs if o], next_cursor=data.get("nextPageToken"))

    def _to_raw(self, f: dict) -> RawObject | None:
        fid = f.get("id")
        if not fid:
            return None
        mime, name = f.get("mimeType") or "", f.get("name") or ""
        dl = self._x.execute("GOOGLEDRIVE_DOWNLOAD_FILE", {"file_id": str(fid)})
        r = process_document(mime=mime, data=_raw_bytes(dl), filename=name, ocr=self._ocr)
        return RawObject(
            source="gdrive", object_type="file", source_object_id=str(fid),
            occurred_at=_parse_ts(f.get("modifiedTime")),
            actor_email=((f.get("lastModifyingUser") or {}).get("emailAddress")),
            actor_type="internal_user",
            # modifiedTime bumps on every edit → new content_version → an edited file re-lands
            # and its extracted text updates, instead of being deduped to the first version seen.
            content_version=str(f.get("modifiedTime")) if f.get("modifiedTime") else None,
            raw={"subject": name, "body": r.text, "mime": mime, "has_attachment": bool(r.text),
                 "document": {"native_parse_used": r.native_parse_used, "ocr_used": r.ocr_used,
                              "ocr_engine": r.ocr_engine, "ocr_pages": r.ocr_pages,
                              "avg_confidence": r.avg_confidence, "status": r.status}},
        )

    def validate_connection(self) -> bool:
        self._list(limit=1, page_token=None)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._x.execute("GOOGLEDRIVE_DOWNLOAD_FILE", {"file_id": object_ref})
