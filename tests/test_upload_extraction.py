from __future__ import annotations

from genios_engine.capture.documents.native import extract_text_best_effort

# The dashboard upload door was pypdf-only: a scanned PDF/image returned "" even with OCR enabled,
# while the SAME file arriving by email/Drive was OCR'd. It also utf-8-decoded binary bytes into
# garbage. extract_text_best_effort routes uploads through the shared native+OCR path, with a
# utf-8 fallback only for real plain-text formats, and "" (never garbage) for a binary that yields nothing.


def test_plaintext_txt_extracted():
    assert extract_text_best_effort(mime="text/plain", data=b"hello world", filename="n.txt") == "hello world"


def test_csv_falls_back_to_utf8():
    out = extract_text_best_effort(mime="text/csv", data=b"a,b\n1,2", filename="data.csv")
    assert "a,b" in out and "1,2" in out


def test_html_is_stripped_to_text():
    out = extract_text_best_effort(mime="text/html", data=b"<p>Hello <b>World</b></p>", filename="p.html")
    assert "Hello" in out and "World" in out and "<" not in out


def test_binary_image_without_ocr_returns_empty_not_garbage():
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert extract_text_best_effort(mime="image/png", data=png, filename="scan.png") == ""


def test_image_is_ocred_when_an_engine_is_wired():
    # image + no text layer + OCR engine → OCR actually runs now (bytes materialised for the engine).
    # Before, image_ref was never set anywhere, so route_document's OCR branch was unreachable.
    from genios_engine.capture.documents.fake import FakeOcr
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    out = extract_text_best_effort(mime="image/png", data=png, filename="invoice.png", ocr=FakeOcr())
    assert "Agreement renews" in out                  # FakeOcr's deterministic text → OCR path ran


def test_scanned_pdf_without_ocr_returns_empty_honestly():
    # a PDF with no text layer and no OCR engine → "" (honest 'no extractable text'), never garbage.
    out = extract_text_best_effort(mime="application/pdf", data=b"%PDF-1.4 no text layer", filename="scan.pdf")
    assert out == ""


def test_scanned_pdf_ocr_path_is_graceful_without_poppler():
    # PDF + no text + OCR engine → page rasterization attempted; if poppler/pdf2image is absent it
    # falls back to unsupported ("") gracefully instead of crashing (with poppler it would OCR).
    from genios_engine.capture.documents.fake import FakeOcr
    out = extract_text_best_effort(mime="application/pdf", data=b"%PDF-1.4 scanned",
                                   filename="scan.pdf", ocr=FakeOcr())
    assert isinstance(out, str)
