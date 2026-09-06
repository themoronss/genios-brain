"""L1.3.4 · Document Router (ALG-01) — every non-text medium becomes text, or says why not.

Four units, in the order a document meets them:

* **U1 native text** (`native.py`) — PDF/DOCX/XLSX/PPTX/HTML/TXT/MD. The cheapest read, always
  tried first: OCR on a digital PDF is a bill for a page we already have.
* **U2 OCR** (`router.py`, `ocr_policy.py`, `enablement.py`, `tesseract.py`) — scanned and
  image-only pages, per tenant, graded, and **never silent**: a failed read emits a marker, not
  an empty string. That is G2's gate — *0 documents with empty text and no `ocr_failed` marker* —
  because an unmarked empty document is indistinguishable from one that said nothing.
* **U3 speech-to-text** (`transcript.py`) — the seam only. Its connector (P5 · Voice) is in no
  wave, so there is no provider and audio parks as `transcription_unavailable`. Synthetic
  fixtures only; see the module docstring.
* **U4 chunking** (`chunking.py`) — section-aware, offset-preserving. A clause is never split,
  and every chunk is a literal slice of the source so W1's span validator and W3's evidence
  binder can resolve offsets against it.
"""
