"""M1.C1 · reply history is a Layer 1 fact, computed once, and never protected from trimming.

    pytest tests/capture/preprocess/test_history_spans.py -q

THE 23. On the pilot tenant, twenty-three qualified signals had an attribution line as their
entire receipt. `"On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:"` was stored as a
`financial_obligation` at 4560 bp — the second-highest importance on the tenant. Roughly sixty
more signals were ONE sentence counted once per message that quoted it: measured,
`copies == distinct_events` in every duplicate group, with no within-event duplication anywhere.

AND THE TRIMMER WAS PROTECTING IT. `_DEADLINE` matches `\b(mon|tue|wed|thu|fri|sat|sun)\b`. Every
attribution line a mail client writes carries a weekday. So the line scored as a deadline line,
`protected_line_spans` returned a span for it, and the token-budget trimmer was forbidden from
dropping the one part of the message nobody in it wrote.

These tests pin both halves: history is detected where the extractor can see it, and a line inside
history is never protected.
"""

from __future__ import annotations

from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.capture.preprocess.quoted import in_quoted_history, quoted_regions
from genios_engine.capture.preprocess.text import protected_line_spans

# The exact shape the pilot produced, down to the weekday that caused the protection.
REPLY = (
    "Thanks — sending the deck tonight.\n"
    "\n"
    "On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:\n"
    "> As we can see the need of the product, we can expect the numbers to hit\n"
    "> nearly ~*$2-3k MRR*.\n"
)


# =============================================================================================
# M1.C1.L-contract.V0.U01 — the detector is reachable from Layer 1.
# =============================================================================================
def test_layer_one_can_ask_the_question_at_all():
    """The whole defect in one assertion. This import did not exist before: `capture/` had zero
    references to `quoted_regions`, so nothing upstream of extraction could tell live text from
    history."""
    assert quoted_regions(REPLY)


def test_the_attribution_line_starts_the_history():
    [(start, end)] = [r for r in quoted_regions(REPLY) if r[0] == REPLY.index("On Sat")]

    assert REPLY[start:].startswith("On Sat, 8 Aug 2026")
    assert end == len(REPLY), "an attribution line makes everything after it history"


def test_the_senders_own_sentence_is_not_history():
    live = REPLY.index("Thanks")

    assert not in_quoted_history(REPLY, live, live + len("Thanks"))


def test_the_quoted_mrr_line_is_history():
    """This is the sentence that produced ten `contract_renewal` signals across ten events —
    Rohit wrote it once and ten later messages quoted it back."""
    quoted = REPLY.index("nearly ~*$2-3k MRR*")

    assert in_quoted_history(REPLY, quoted, quoted + 20)


# =============================================================================================
# M1.C1.L-logic.V1.U02 — preprocess computes it once, for everyone.
# =============================================================================================
def test_prepared_content_carries_the_history_it_found():
    prepared = preprocess(REPLY)

    assert prepared.history_spans, "the extractor must not have to re-derive this"
    lo, hi = prepared.history_spans[0]
    assert prepared.clean_text[lo:hi].startswith("On Sat")


def test_a_message_with_no_history_carries_none():
    """Absent is the honest answer for a first-turn message and must stay cheap."""
    prepared = preprocess("Can you send the signed order form by Friday?")

    assert prepared.history_spans == []


def test_the_spans_are_in_clean_text_coordinates():
    """PII masking rewrites offsets. History is computed AFTER masking, against the same string
    every downstream reader is handed, or the ranges would address the wrong characters."""
    prepared = preprocess(REPLY)

    for lo, hi in prepared.history_spans:
        assert 0 <= lo < hi <= len(prepared.clean_text)


# =============================================================================================
# M1.C1.L-logic.V1.U03 — and the trimmer stops defending it.
# =============================================================================================
def test_an_attribution_line_is_no_longer_protected():
    """THE REGRESSION, stated directly. The weekday made this look like a deadline line."""
    line = "On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:\n"
    history = [(0, len(line))]

    assert protected_line_spans(line) != [], "without history it still scores as a deadline"
    assert protected_line_spans(line, history=history) == []


def test_a_quoted_paragraph_is_no_longer_protected():
    """`_IMPORTANT` matches "renewal" wherever it appears, including inside somebody else's
    sentence from four messages ago."""
    line = "> the renewal invoice is attached\n"

    assert protected_line_spans(line) != []
    assert protected_line_spans(line, history=[(0, len(line))]) == []


def test_the_live_sentence_is_still_protected():
    """The guard must not cost the trimmer its actual job. A real deadline in the sender's own
    words stays undroppable."""
    text = "Please confirm by Friday.\n> quoted deadline: by Monday\n"
    history = [(text.index(">"), len(text))]

    [(lo, hi)] = protected_line_spans(text, history=history)

    assert text[lo:hi] == "Please confirm by Friday."


def test_a_line_that_runs_into_history_is_not_protected():
    """Any overlap disqualifies, matching `in_quoted_history`. Requiring full containment would
    make the guard avoidable by widening a line by one character."""
    text = "invoice due Friday\n"

    assert protected_line_spans(text, history=[(len(text) - 4, len(text))]) == []


def test_preprocess_wires_the_two_together():
    """End to end: the history preprocess found is the history the trimmer is told about."""
    prepared = preprocess(REPLY)

    for lo, hi in prepared.protected_spans:
        assert not any(lo < h and hi > l for l, h in prepared.history_spans)


def test_the_old_signature_still_works():
    """`history` is optional. A caller holding only a string gets the previous behaviour rather
    than a TypeError — there are callers outside this package."""
    assert protected_line_spans("Send the invoice by Monday.") != []
