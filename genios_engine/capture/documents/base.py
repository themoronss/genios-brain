"""L1.3.4 · Document Router (ALG-01) — the shared vocabulary every unit in this package speaks.

Three things live here and nothing else: the shapes that cross a unit boundary, the status
words a document can end its life carrying, and the one confidence threshold that decides
whether an OCR read is a fact or a review item.

**The status word is the whole point of the component.** G2 states the gate as *"0 documents
with empty text and no `ocr_failed` marker"*, and the reason it is phrased as an absence rather
than a presence is that the failure it names is invisible: a scanned contract that yields ``""``
looks exactly like a fax cover sheet that genuinely said nothing. Every layer above reads the
empty string, finds no commitment, no amount and no date, and reports — accurately, and
uselessly — that the document contained nothing worth knowing. Nothing breaks. Nobody is
paged. So the invariant is enforced at the type level here and by construction in `router.py`:
**a `DocumentResult` with empty text always carries a non-`accepted` status and a `detail`
saying which of the six ways it got there happened.**

**Confidence is integer basis points, never a float.** `avg_confidence: float` was the previous
spelling and it was wrong twice over. It compared `0.749999 >= 0.75` to decide whether a
contract is quotable, and it fed a ratio into a column (`numeric(4,3)`) that could not hold what
the comparison used. Tesseract already reports integer percentages 0–100, so the float existed
only to be lossy: `sum(confs) * 100 // len(confs)` is the same number in bp, exactly, with no
representation to argue about. The persisted column is fed a `Decimal` at the I/O edge in
`store.py` — the one place a fraction is a storage format rather than a score.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

#: Full confidence in basis points — the scale every score in this package is expressed on.
BP_FULL = 10_000

#: Below this, OCR output is parked for review rather than used as a business fact.
#: 7500 bp is the old ``OCR_MIN_CONFIDENCE = 0.75``, restated in the unit the code compares in.
OCR_MIN_CONFIDENCE_BP = 7_500

#: A speaker label under this confidence is replaced by :data:`UNKNOWN_SPEAKER`. Doc-03's
#: named failure mode for L1.3.4-U3 is diarization attributing a commitment to the wrong
#: person, and its stated mitigation is `actor="unknown"` rather than a guess — a commitment
#: filed against the wrong human is acted on, which an unattributed one is not.
SPEAKER_MIN_CONFIDENCE_BP = 6_000

#: What a segment is labelled with when diarization was not confident enough to name anybody.
UNKNOWN_SPEAKER = "unknown"


class DocumentStatus(str, Enum):
    """How a document's text (or absence of text) came to be — the marker G2 counts.

    ``str``-valued so a status can go straight into a raw payload dict, a JSON column and an
    ``==`` against the plain strings that `capture/gate/rules.py` and the existing suite already
    compare with. Members are assigned as ``.value`` at every construction site, so what leaves
    this package is an ordinary ``str`` and no serializer ever has to know this enum exists.
    """

    #: Text was extracted and is usable as a fact.
    ACCEPTED = "accepted"
    #: OCR produced text, below the confidence floor. Real text, not quotable — a review item.
    OCR_REVIEW_REQUIRED = "ocr_review_required"
    #: An OCR engine was wired, ran, and produced nothing (or raised). The document is empty
    #: *because the read failed*, which is a different fact from "the page was blank".
    OCR_FAILED = "ocr_failed"
    #: The document has pages we could read, and no engine was wired to read them. Recoverable
    #: by configuration alone — the distinction that made a 369-document backlog visible.
    OCR_UNAVAILABLE = "ocr_unavailable"
    #: Audio/video arrived and no speech engine is wired (L1.3.4-U3 has no connector — P5).
    TRANSCRIPTION_UNAVAILABLE = "transcription_unavailable"
    #: A speech engine was wired, ran, and produced no usable transcript.
    TRANSCRIPTION_FAILED = "transcription_failed"
    #: The bytes never arrived. Retryable, and never silent (set by the connectors).
    FETCH_FAILED = "fetch_failed"
    #: A format with no text layer, no pages and no audio — a .zip, a firmware blob.
    UNSUPPORTED = "unsupported"


#: The statuses under which empty text is EXPLAINED. `accepted` is deliberately absent: an
#: accepted document with no text is precisely the silent loss G2 exists to count.
EXPLAINED_EMPTY_STATUSES = frozenset({
    DocumentStatus.OCR_REVIEW_REQUIRED.value,
    DocumentStatus.OCR_FAILED.value,
    DocumentStatus.OCR_UNAVAILABLE.value,
    DocumentStatus.TRANSCRIPTION_UNAVAILABLE.value,
    DocumentStatus.TRANSCRIPTION_FAILED.value,
    DocumentStatus.FETCH_FAILED.value,
    DocumentStatus.UNSUPPORTED.value,
})


@dataclass
class DocumentInput:
    """One document as the router receives it: what it is, and which of the three read paths
    it can offer — a text layer, an image to OCR, or a media reference to transcribe."""

    mime: str
    filename: str
    text_layer: str | None = None       # extractable text if the format has one (PDF/DOCX/...)
    image_ref: str | None = None        # pointer to image bytes for scanned/image docs
    media_ref: str | None = None        # pointer to audio/video bytes for the speech path
    document_hash: str | None = None


@dataclass
class OcrResult:
    """One engine's read of one image. `confidence_bp` is 0..10000; an engine that reports
    percentages converts with integer arithmetic, never through a float."""

    text: str
    confidence_bp: int
    pages: int
    engine: str


@dataclass
class DocumentResult:
    """The router's verdict. `status` is always set and `detail` is always set whenever the
    text is empty — that pair IS the G2 marker."""

    text: str
    native_parse_used: bool
    ocr_used: bool
    ocr_engine: str | None
    ocr_pages: int
    confidence_bp: int | None
    status: str                          # a DocumentStatus value
    detail: str | None = None            # why, in one phrase, when the text is empty
    #: L1.3.4-U5 · where each page's text begins in `text`, in the coordinates of `text` itself.
    #: Known only while the pages are being joined and unrecoverable afterwards — concatenation
    #: is not invertible — so it is carried here rather than re-derived. Empty for every format
    #: with no pages, which is not the same as a one-page document. See `capture/documents/pages.py`.
    page_offsets: tuple[int, ...] = ()


class OcrEngine(Protocol):
    """Image → text. Implementations may raise; `router.route_document` is the only caller and
    it converts a raised engine into `ocr_failed`, because an ingestion run must never die on
    one unreadable attachment."""

    name: str

    def ocr(self, image_ref: str) -> OcrResult: ...
