from __future__ import annotations

from typing import Protocol

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id


class DocumentJobStore(Protocol):
    """Records how each document was parsed (native vs OCR) + status — provenance for
    L2 and a review queue for ocr_review_required / unsupported files."""

    def put(self, *, org_id: str, event_id: str, doc: dict, fmt: str | None) -> None: ...


class InMemoryDocumentJobStore:
    def __init__(self) -> None:
        self.jobs: list[dict] = []

    def put(self, *, org_id, event_id, doc, fmt):
        self.jobs.append({"org_id": org_id, "event_id": event_id, "format": fmt, **doc})


class PostgresDocumentJobStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def put(self, *, org_id, event_id, doc, fmt):
        with self._engine.begin() as c:
            c.execute(text(
                """insert into document_jobs
                   (id, org_id, event_id, format, native_parse_used, ocr_engine, ocr_pages,
                    avg_confidence, status)
                   values (:id, :o, :e, :fmt, :nat, :eng, :pages, :conf, :status)"""),
                {"id": new_id("doc"), "o": org_id, "e": event_id, "fmt": fmt,
                 "nat": bool(doc.get("native_parse_used")), "eng": doc.get("ocr_engine"),
                 "pages": int(doc.get("ocr_pages") or 0),
                 "conf": doc.get("avg_confidence"), "status": doc.get("status")})
