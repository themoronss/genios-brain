"""Layer 1 document segmentation keeps facts intact and evidence offsets honest."""
from __future__ import annotations

import inspect

from genios_engine.api import upload_routes
from genios_engine.capture.chunking import chunk_text


def test_zero_overlap_loses_no_source_text_or_offsets():
    source = "  First paragraph.\n\nSecond paragraph has trailing space.  "
    chunks = chunk_text(source, max_chars=24, overlap=0)

    assert "".join(chunk.text for chunk in chunks) == source
    assert all(chunk.text == source[chunk.start:chunk.end] for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_a_natural_boundary_is_preferred_near_the_budget():
    source = "Alpha beta gamma. Delta epsilon zeta. Final sentence."
    chunks = chunk_text(source, max_chars=40, overlap=0)

    assert chunks[0].text == "Alpha beta gamma. Delta epsilon zeta. "
    assert all(len(chunk.text) <= 40 for chunk in chunks)


def test_overlap_is_bounded_and_always_makes_progress():
    source = "x" * 120
    chunks = chunk_text(source, max_chars=30, overlap=10_000)

    assert len(chunks) > 1
    assert all(chunk.start < chunk.end for chunk in chunks)
    assert all(later.start > earlier.start for earlier, later in zip(chunks, chunks[1:]))
    assert all(earlier.end - later.start <= 10 for earlier, later in zip(chunks, chunks[1:]))


def test_uploads_use_the_shared_boundary_aware_chunker(monkeypatch):
    seen = {}

    def fake(text, *, max_chars):
        seen.update(text=text, max_chars=max_chars)
        return chunk_text(text, max_chars=12, overlap=0)

    monkeypatch.setattr(upload_routes, "chunk_text", fake)
    result = upload_routes._chunk("One sentence. Two sentences.")

    assert seen == {"text": "One sentence. Two sentences.",
                    "max_chars": upload_routes.CHUNK_CHARS}
    assert result == [chunk.text for chunk in chunk_text(
        "One sentence. Two sentences.", max_chars=12, overlap=0)]
    assert "chunk_text" in inspect.getsource(upload_routes._chunk)
