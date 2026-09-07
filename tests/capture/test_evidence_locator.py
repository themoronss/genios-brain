"""L1.3.4-U5 · a receipt that names its PAGE and its SECTION, on the path a real attachment takes.

    pytest tests/capture/test_evidence_locator.py -q

`EvidenceSpan` carried `source_ref` + offsets + quote, and nothing else. That is a receipt a
machine can resolve and a person cannot: *"character 4,812 of the prepared text"* is not something
anyone can check against a signed PDF, so every provenance surface this product has could show
the quote and never say where in the document it came from. The page boundaries are known for
exactly as long as `documents/native.py` is joining a PDF's pages — concatenation is not
invertible — so they have to travel with the event or be lost.

This file drives `capture_event` with the lane wired, which is the path a Gmail attachment
actually takes, and asserts on the spans that come back. Each test names the link it would catch
if it broke: the connector's `raw["document"]`, the pipeline's read of it, the extractor's
alignment seam, ALG-08's relocation, or the binder's synthesized receipts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.documents.pages import from_pages
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

OWNER = "founder@genios.ai"
NOW = datetime(2026, 2, 10, 9, 0, tzinfo=timezone.utc)

#: A three-page agreement, as the extractor would see it after the pages were joined. The quote
#: each test cites is chosen to sit on a KNOWN page, so a wrong answer is a wrong page rather
#: than a missing one.
PAGE_1 = "Master services agreement between Northwind Ltd and the customer."
PAGE_2 = "Termination. Either party may cancel with 30 days written notice."
PAGE_3 = "The annual fee of $84,000 is payable on 28 March 2026."
DOC_PAGES = [PAGE_1, PAGE_2, PAGE_3]
DOC_TEXT = "\n".join(DOC_PAGES)
PAGE_MAP = from_pages(DOC_PAGES)


def _cite(quote: str) -> list[dict]:
    start = DOC_TEXT.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


def _attachment(*, document: dict | None = None) -> RawObject:
    """One Gmail attachment event, in the shape `connectors/composio.py` builds it."""
    doc = {"native_parse_used": True, "ocr_used": False, "ocr_engine": None, "ocr_pages": 0,
           "confidence_bp": None, "status": "accepted"}
    if document is not None:
        doc.update(document)
    return RawObject(
        source="gmail", object_type="email_attachment", source_object_id="m_1::att_1",
        occurred_at=NOW, actor_email="counsel@northwind.test", recipients=(OWNER,),
        parent_object_id="m_1",
        raw={"subject": "MSA.pdf", "body": DOC_TEXT, "mime": "application/pdf",
             "has_attachment": True, "document": doc})


def _capture(raw, llm, **over):
    kwargs = dict(org_id="org_locator", connection_id="con_locator",
                  repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
                  semantic=P.SemanticLane(llm=llm, eval_time=NOW))
    kwargs.update(over)
    return P.capture_event(raw, **kwargs)


def _spans(result):
    return list(result.extraction.evidence_from_claims()) + list(result.extraction.all_evidence)


# =============================================================================================
# The whole chain, one assertion at a time
# =============================================================================================
def test_a_quote_from_page_three_cites_page_three(fake_llm):
    """The chain end to end: connector metadata -> pipeline -> extractor -> aligned span."""
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "amounts": [{"minor_units": 8_400_000, "currency": "USD",
                                 "as_written": "$84,000"}],
                    "entity_mentions": [{"surface_form": "Northwind Ltd",
                                         "entity_type": "organization",
                                         "evidence": _cite("The annual fee of $84,000"),
                                         "confidence_bp": 9000}]})
    res = _capture(_attachment(document=PAGE_MAP.as_record()), llm)

    spans = [s for s in _spans(res) if "annual fee" in s.quote]
    assert spans, "the extraction lost the span this test is about"
    assert all(s.page == 3 for s in spans), (
        "the page map did not reach the alignment seam — check raw['document']['page_offsets'], "
        "pipeline.run_semantic_lane and extractor._located")


def test_a_quote_from_page_two_cites_page_two(fake_llm):
    """The same event, a different page: an answer that is right by accident (everything says 1,
    or everything says the last page) fails here."""
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "entity_mentions": [{"surface_form": "Termination",
                                         "entity_type": "document",
                                         "evidence": _cite("Either party may cancel"),
                                         "confidence_bp": 8000}]})
    res = _capture(_attachment(document=PAGE_MAP.as_record()), llm)
    spans = [s for s in _spans(res) if "Either party" in s.quote]
    assert spans and all(s.page == 2 for s in spans)


def test_an_attachment_with_no_page_map_cites_no_page(fake_llm):
    """A DOCX, a .txt, an email body. None — never 1: a page number on something with no pages is
    a value nobody can check, and it would make the field meaningless everywhere it appears."""
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "entity_mentions": [{"surface_form": "Northwind Ltd",
                                         "entity_type": "organization",
                                         "evidence": _cite("The annual fee of $84,000"),
                                         "confidence_bp": 9000}]})
    res = _capture(_attachment(), llm)
    spans = [s for s in _spans(res) if "annual fee" in s.quote]
    assert spans and all(s.page is None for s in spans)


def test_the_section_the_door_declared_travels_onto_every_span(fake_llm):
    """`section_title` is a property of the whole event — an upload chunk IS one section — so it
    is copied onto every receipt rather than looked up per offset."""
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "entity_mentions": [{"surface_form": "Termination",
                                         "entity_type": "document",
                                         "evidence": _cite("Either party may cancel"),
                                         "confidence_bp": 8000}]})
    document = {**PAGE_MAP.as_record(), "section_title": "Termination"}
    res = _capture(_attachment(document=document), llm)
    spans = [s for s in _spans(res) if "Either party" in s.quote]
    assert spans and all(s.section == "Termination" for s in spans)


def test_a_synthesized_receipt_gets_a_page_too(fake_llm):
    """U1 invents a receipt for a claim that cited nothing, and the binder is handed a string and
    a frame name — no map, deliberately. Without the post-pass in `extractor._locate_bound`, a
    synthesized span would be the one receipt in an extraction with no page, and 'some of them
    have pages' is a worse surface than either all or none."""
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "entity_mentions": [{"surface_form": "Termination",
                                         "entity_type": "document",
                                         "confidence_bp": 8000}]})       # NO evidence supplied
    res = _capture(_attachment(document=PAGE_MAP.as_record()), llm)
    spans = [s for s in _spans(res) if s.quote.strip() == "Termination"]
    assert spans, "the binder dropped a claim whose words are in the text"
    assert all(s.page == 2 for s in spans), "a synthesized receipt cited no page"


def test_a_relocated_quote_is_repaged_and_never_keeps_a_stale_page(fake_llm):
    """ALG-08 relocates a quote whose words are real and whose offsets are wrong. A relocation can
    cross a page break, so the page must be recomputed at the NEW position — carrying the old one
    is a confident citation naming the wrong page, which is worse than none."""
    quote = "The annual fee of $84,000"                  # really on page 3
    wrong = DOC_TEXT.index("Master services")            # the model counts as if on page 1
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "entity_mentions": [{"surface_form": "Northwind Ltd",
                                         "entity_type": "organization",
                                         "evidence": [{"quote": quote, "start_offset": wrong,
                                                       "end_offset": wrong + len(quote)}],
                                         "confidence_bp": 9000}]})
    res = _capture(_attachment(document=PAGE_MAP.as_record()), llm)

    spans = [s for s in _spans(res) if s.quote == quote]
    assert spans
    assert all(s.page == 3 for s in spans), (
        "a relocated span kept the page its wrong offsets implied")
    assert all(s.verified for s in spans), "ALG-08 relocated it and did not mark it verified"
