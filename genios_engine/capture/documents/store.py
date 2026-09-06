from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id

from .base import BP_FULL


def _confidence_column(doc: dict) -> Decimal | None:
    """`confidence_bp` (0..10000) -> the `numeric(4,3)` the table declares, exactly.

    The one place in this package where a score becomes a fraction, and it is a *storage
    format*, not arithmetic: `Decimal(9100) / Decimal(10000)` is 0.9100 with no representation
    to argue about, where `9100 / 10000` would hand psycopg a float to round on its way into a
    three-decimal column. Nothing reads this column back to make a decision — `confidence_bp`
    on the result is what the gate and the router compare — so the narrowing is safe here and
    only here.
    """
    bp = doc.get("confidence_bp")
    if bp is None:
        return None
    return Decimal(int(bp)) / Decimal(BP_FULL)


class DocumentJobStore(Protocol):
    """Records how each document was parsed (native vs OCR) + status — provenance for
    L2 and a review queue for every status that is not `accepted`."""

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
                 "conf": _confidence_column(doc), "status": doc.get("status")})
