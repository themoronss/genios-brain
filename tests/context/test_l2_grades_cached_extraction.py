"""Layer 2 must grade the cached L1 extraction before adapting it.

L1 stores the extractor's UNVERIFIED output and grades it on the way out of its lane; Layer 2 read
the stored copy raw, so `adapt_qes_extraction` (verified receipts only) dropped every business fact
from every source. The fixture is the P2 gate's own event: a LinkedIn decline read off the screen
(synthetic test text), its stored extraction and its `prepared_content.clean_text`.
"""
import json
import pathlib

from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.context.runner import graded_extraction

FIX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "screen_decline_extraction.json")
                 .read_text())


def _business(extraction):
    return [(f["field"], f["subject"])
            for f in adapt_qes_extraction(extraction, confidence_bp=9000).fact_candidates
            if f.get("business_fact")]


def test_the_stored_extraction_alone_carries_no_business_fact():
    assert _business(FIX["output"]) == []           # every receipt in the cache is unverified


def test_graded_against_the_events_text_the_decline_crosses():
    got = _business(graded_extraction(FIX["output"], FIX["clean_text"], "evt_fixture"))
    assert ("deal.stage", "Acme Logistics") in got
    assert ("party.role", "Priya Shah") in got


def test_a_quote_absent_from_the_text_stays_unverified():
    assert _business(graded_extraction(FIX["output"], "an unrelated message", "evt_fixture")) == []


def test_no_text_or_an_unreadable_payload_travels_unchanged():
    assert graded_extraction(FIX["output"], None) is FIX["output"]
    assert graded_extraction(FIX["output"], "") is FIX["output"]
    bad = {"not": "an extraction"}
    assert graded_extraction(bad, "text") is bad
