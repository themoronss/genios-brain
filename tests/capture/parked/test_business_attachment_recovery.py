"""A parked deck is evidence only after bytes are recovered and readable text exists."""
import pytest
from genios_engine.capture.documents.base import OcrResult
from genios_engine.capture.parked.refetch import refetch_parked_attachments
from tests.capture.parked.test_refetch_drain import FakeFetcher, NOW, park, queue_with


DECK = "GeniOS seed investor deck. We are raising capital for our company intelligence product."


class FakeOcr:
    name = "fixture-ocr"
    def __init__(self, fails=False):
        self.fails = fails
    def ocr(self, path):
        if self.fails:
            raise RuntimeError("fixture OCR unavailable")
        return OcrResult(text=DECK,confidence_bp=9500,pages=1,engine=self.name)


@pytest.mark.parametrize("mode", ["readable", "missing", "failed"])
def test_parked_deck_recovery_requires_real_text_and_never_reemits_the_same_event(mode):
    queue = queue_with(park(reason_code="DOC-06"),payload={"subject":"deck.png",
        "filename":"deck.png","mime":"image/png","body":"","to":["investor@example.com"],
        "document":{"status":"ocr_unavailable"}})
    engine = FakeOcr(mode == "failed") if mode != "missing" else None
    fetcher = FakeFetcher(b"fixture image bytes")
    result = refetch_parked_attachments(queue,connector_for=lambda _:fetcher,
        eval_time=NOW,org_id="org_1",ocr=engine)
    if mode == "readable":
        assert result.recovered == 1
        assert DECK in queue.recovered["evt_att"].prepared.clean_text
        assert queue.payloads["evt_att"]["to"] == ["investor@example.com"]
        again = refetch_parked_attachments(queue,connector_for=lambda _:fetcher,
            eval_time=NOW,org_id="org_1",ocr=engine)
        assert again.claimed == 0 and len(fetcher.calls) == 1
    else:
        assert result.recovered == 0
        assert queue.outcomes["evt_att"] == "parked"
        assert "evt_att" not in queue.recovered
        assert queue.payloads["evt_att"]["body"] == ""
