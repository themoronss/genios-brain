from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MaskedSpan(BaseModel):
    src_start: int
    src_end: int
    pii_type: str
    token: str


class OffsetSegment(BaseModel):
    """Maps a range of prepared (clean) text back to the original source text.
    Passthrough segments are 1:1; masked segments collapse a source PII span to a token."""
    prep_start: int
    prep_end: int
    src_start: int
    src_end: int
    masked: bool = False


class PreparedContent(BaseModel):
    """Clean, PII-masked text + an explicit offset map so every downstream evidence
    span can be traced back to exact source characters. Raw content is never persisted
    here — only the prepared form + the map."""

    prepared_content_id: str
    event_id: str | None = None
    clean_text: str
    language: str                                   # en | hi | hinglish | other
    masked_spans: list[MaskedSpan] = Field(default_factory=list)
    protected_spans: list[tuple[int, int]] = Field(default_factory=list)  # in clean_text coords
    signature_hints: dict[str, Any] = Field(default_factory=dict)
    offset_map: list[OffsetSegment] = Field(default_factory=list)
    preprocessor_version: str = "prep-1"

    def to_source_offset(self, prep_off: int) -> int:
        """Prepared-text offset → original source offset (masked regions map to their
        source start). This is what makes 'click a fact, see the exact sentence' work."""
        for seg in self.offset_map:
            if seg.prep_start <= prep_off < seg.prep_end:
                if seg.masked:
                    return seg.src_start
                return seg.src_start + (prep_off - seg.prep_start)
        return self.offset_map[-1].src_end if self.offset_map else prep_off
