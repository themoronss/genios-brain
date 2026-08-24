from __future__ import annotations

from genios_engine.capture.documents.chunking import DEFAULT_CHUNK_CHARS, chunk_text

# Uploads were sliced every 2000 chars — mid-sentence, mid-word, mid-table — which silently
# destroys the fact that straddles the cut. Chunking must respect sentence boundaries and
# never drop text; the caller (upload_routes) bounds the count and REPORTS truncation.


def test_fact_straddling_the_naive_boundary_survives_intact():
    key = "Refunds are accepted within 30 days of purchase."
    text = ("x. " * 660) + key + (" y." * 300)      # key sits across the old 2000-char slice point
    chunks = chunk_text(text)
    assert chunks
    assert all(len(c) <= DEFAULT_CHUNK_CHARS for c in chunks)
    assert sum(key in c for c in chunks) == 1        # whole fact in exactly one chunk, not split


def test_empty_and_whitespace_only():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_oversized_unit_is_hard_split_without_losing_text():
    big = "A" * 5000                                  # a single run with no sentence break
    chunks = chunk_text(big)
    assert all(len(c) <= DEFAULT_CHUNK_CHARS for c in chunks)
    assert "".join(chunks) == big                     # nothing dropped, nothing duplicated


def test_respects_custom_max_chars():
    chunks = chunk_text("One. Two. Three. Four.", max_chars=10)
    assert chunks == ["One. Two.", "Three.", "Four."]


def test_paragraph_breaks_are_boundaries():
    text = "First paragraph body.\n\nSecond paragraph body."
    chunks = chunk_text(text, max_chars=25)
    assert "First paragraph body." in chunks[0]
    assert any("Second paragraph body." in c for c in chunks)
