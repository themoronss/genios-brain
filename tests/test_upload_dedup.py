from __future__ import annotations

from genios_engine.capture.intake import ingest_manual
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

# Re-uploading the SAME file used to create duplicate events — the upload id was random per upload
# (new_id), so identical bytes re-landed. The id is now content-addressed (sha256 of org+bytes), so
# the same file → same chunk source_object_id → the second upload dedups at landing (MD Part 3.4).


def _upload_chunk(repo, *, file_id: str, body: str):
    return ingest_manual(org_id="o", source="upload", object_type="document_chunk",
                         source_object_id=f"{file_id}:chunk_0", body=body, repo=repo)


def test_identical_upload_content_dedups_instead_of_duplicating():
    repo = InMemorySourceEventRepository()
    r1 = _upload_chunk(repo, file_id="upl_deadbeefcafe", body="Refunds within 30 days.")
    r2 = _upload_chunk(repo, file_id="upl_deadbeefcafe", body="Refunds within 30 days.")
    assert r1.outcome in ("emitted", "parked")     # first upload lands
    assert r2.outcome == "duplicate"               # identical re-upload does NOT create a second copy


def test_different_content_still_lands_separately():
    repo = InMemorySourceEventRepository()
    r1 = _upload_chunk(repo, file_id="upl_aaaa", body="Refund policy.")
    r2 = _upload_chunk(repo, file_id="upl_bbbb", body="Pricing sheet.")
    assert r1.outcome in ("emitted", "parked")
    assert r2.outcome in ("emitted", "parked")     # a genuinely different file is not a duplicate
