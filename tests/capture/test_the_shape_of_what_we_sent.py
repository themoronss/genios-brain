"""The sentence that could not be said, and the five numbers that make it sayable.

    pytest tests/capture/test_the_shape_of_what_we_sent.py -q

"Ten 600-word emails to investors got no replies; the four-line ones got three." In this
database those two weeks were byte-for-byte the same shape — a set of `thread.last_outbound`
timestamps and a `thread.days_waiting`. No number anywhere differed between them, so the advice
could not be derived, could not be evidenced, and could not be gated on by any authored
situation. The corpus already asked for it and could not have it: `reply-rate-beats-open-rate-
always.yaml` says *"Judge every change to a cold-email programme on reply rate per person"* and
its only usable condition is `{exists: thread.last_outbound}`.

Nothing new is captured. `clean_text` was already in the row and `_envelope_direction` was
already computed and thrown away.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.prepared_store import (
    InMemoryPreparedContentStore,
    message_form,
)

pytestmark = pytest.mark.unit


class _Prepared:
    def __init__(self, text, event_id="evt-1"):
        self.event_id = event_id
        self.prepared_content_id = "pc-1"
        self.clean_text = text
        self.language = "en"
        self.masked_spans = ()
        self.protected_spans = ()
        self.offset_map = ()
        self.signature_hints = {}
        self.preprocessor_version = "v1"


SHORT = "Joseph — free Thursday?"
LONG = "\n\n".join(["Dear Joseph," ] + ["A paragraph of considerable length about our traction "
                                        "and why this round matters." for _ in range(8)])


# =============================================================================================
# The two weeks that used to look identical.
# =============================================================================================
def test_a_long_email_and_a_short_one_are_now_different_rows():
    """THE WHOLE POINT. Before this, nothing in any table distinguished them."""
    assert message_form(LONG)["body_words"] > message_form(SHORT)["body_words"] * 10
    assert message_form(LONG)["paragraph_count"] > message_form(SHORT)["paragraph_count"]


def test_a_question_is_counted():
    assert message_form("Are you free? Shall I send the deck?")["question_count"] == 2
    assert message_form("Here is the deck.")["question_count"] == 0


def test_a_paragraph_is_a_blank_line_not_a_wrapped_line():
    """`splitlines()` would measure the mail client's window rather than the writer's
    structure — a hard-wrapped one-paragraph note would read as twelve paragraphs."""
    wrapped = "one long thought\nthat the client\nhappened to wrap\nover four lines"
    spaced = "first thought\n\nsecond thought"

    assert message_form(wrapped)["paragraph_count"] == 1
    assert message_form(spaced)["paragraph_count"] == 2


# =============================================================================================
# NULL is the honest default.
# =============================================================================================
def test_no_text_measures_to_none_not_zero():
    """A zero would read as "they sent an empty message". None reads as "not measured", which is
    what is true for every row that predates the column."""
    assert message_form(None) == {"body_chars": None, "body_words": None,
                                  "paragraph_count": None, "question_count": None}


def test_an_empty_message_really_is_zero():
    """The other direction: an actually-empty body is a measurement, not a gap."""
    assert message_form("")["body_words"] == 0


# =============================================================================================
# Direction, which is what makes the numbers mean anything.
# =============================================================================================
def test_the_store_keeps_the_direction_it_was_given():
    """"Our emails are getting longer" is a statement about what WE sent. Without direction the
    roll-up would average in everything the counterparty wrote back."""
    store = InMemoryPreparedContentStore()

    store.put(org_id="o1", prepared=_Prepared(SHORT), direction="outbound")

    assert store.rows["evt-1"]["direction"] == "outbound"
    assert store.rows["evt-1"]["body_words"] == 3


def test_an_unnameable_direction_stays_none():
    """`_envelope_direction` REFUSES with None rather than guessing, and the store must not
    invent an answer it declined to give — with no identity for "us", every message looks
    inbound, which is how a product's own onboarding mail got modelled as a prospect."""
    store = InMemoryPreparedContentStore()

    store.put(org_id="o1", prepared=_Prepared(SHORT))

    assert store.rows["evt-1"]["direction"] is None


def test_the_pipeline_passes_the_one_authoritative_direction():
    """A second derivation here would eventually disagree with the one the extractor was given."""
    import inspect

    from genios_engine.capture import pipeline

    source = inspect.getsource(pipeline)

    assert "direction=_envelope_direction(event, mailbox_owner))" in source


# =============================================================================================
# Measured on the masked, stripped form.
# =============================================================================================
def test_the_measurement_is_on_clean_text():
    """Measuring the raw body would count the disclaimer, the previous six replies and the
    footer — a thread would look longer every time somebody ANSWERED it, so the reply chain
    growing would read as the founder writing more."""
    import inspect

    from genios_engine.capture import prepared_store

    source = inspect.getsource(prepared_store.PostgresPreparedContentStore.put)

    assert "message_form(prepared.clean_text)" in source


def test_punctuation_is_not_a_word():
    """Bare `split()` counts an em-dash, a lone bullet and a `>` quote marker as words, so the
    same note written with dashes scores longer than one written without. A difference in
    punctuation reading as a difference in length is the confound this column exists to avoid."""
    assert message_form("Joseph — free Thursday?")["body_words"] \
        == message_form("Joseph free Thursday?")["body_words"]
    assert message_form("- \n- \n- ")["body_words"] == 0
