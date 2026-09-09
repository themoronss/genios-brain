from __future__ import annotations

from genios_engine.capture.preprocess import pii, text
from genios_engine.capture.preprocess.quoted import quoted_regions
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.platform.ids import new_id


def preprocess(source_text: str, *, event_id: str | None = None,
               mask_phone: bool = False) -> PreparedContent:
    """Raw source text → PreparedContent: language, PII-masked clean text, an explicit
    offset map back to source, and protected-line spans. No LLM. No raw PII survives
    into clean_text."""
    language = text.detect_language(source_text)
    matches = pii.detect(source_text, mask_phone=mask_phone)
    clean_text, offset_map, masked_spans = pii.mask(source_text, matches)
    # HISTORY FIRST. `protected_line_spans` needs it: an attribution line carries a weekday, a
    # quoted paragraph carries whatever the older message said, and both look "important" to the
    # line scanner. Computing history first is what lets the trimmer stop protecting them.
    history = [list(r) for r in quoted_regions(clean_text)]
    protected = text.protected_line_spans(clean_text, history=history)
    return PreparedContent(
        prepared_content_id=new_id("pc"),
        event_id=event_id,
        clean_text=clean_text,
        language=language,
        masked_spans=masked_spans,
        protected_spans=protected,
        history_spans=history,
        offset_map=offset_map,
    )
