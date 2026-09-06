"""M-6 / M-7 · the two framing sites — where a set of matched conditions becomes a sentence.

    headline.py   M-6 · the model picks a TEMPLATE and names FACT IDS; every word it writes is
                  discarded, and the numbers are substituted from the supplied facts
    timeline.py   M-7 · the model SELECTS from an ordered set and names a SHAPE; the order and
                  every interval are computed

Both sites obey the same two hard-fail rows of doc 09's H6 gate — 0 fabricated facts, 0 visibility
leaks — and both obey them by construction rather than by validation alone: the model's output is
a set of IDS drawn from a visibility-filtered input, and nothing it emits is ever echoed.
"""
from __future__ import annotations

from genios_engine.context.framing.headline import (Framing, FramingFact, FramingInput, frame,
                                                    template_headline)
from genios_engine.context.framing.timeline import Narrative, TimelineEvent, chronology, narrate

__all__ = ["Framing", "FramingFact", "FramingInput", "Narrative", "TimelineEvent", "chronology",
           "frame", "narrate", "template_headline"]
