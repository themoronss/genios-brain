"""Documents & OCR. Native text extraction first; OCR only when a document is
scanned/image-only or has insufficient text. Tesseract sits behind an interface
(swappable / async worker later). Low-quality OCR parks, never becomes a fact.
"""
