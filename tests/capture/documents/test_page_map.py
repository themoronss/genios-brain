"""L1.3.4-U5 · the page map — a receipt a human can open.

    pytest tests/capture/documents/test_page_map.py -q

Every receipt Layer 1 produced was a character range. *"Character 4,812 of the prepared text"* is
resolvable by a machine and unopenable by a person, so a founder asked to check a claim against a
signed PDF had nothing to check it with. The page boundaries exist for the moment
`documents/native.py` joins a PDF's pages into one string and are unrecoverable afterwards, since
concatenation is not invertible.

The arithmetic here is small and the failure modes are all off-by-one, so each one is pinned:
a boundary character belongs to the page it STARTS, a slice that begins mid-page is numbered by
that page, and a text with no pages answers None rather than 1.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.documents.pages import EMPTY, PageMap, from_pages, from_record


# =============================================================================================
# page_at — the lookup
# =============================================================================================
def test_a_character_that_starts_a_page_belongs_to_that_page():
    """`bisect_right - 1`: the boundary character is the first of the NEW page, not the last of
    the old one. One character either way is a citation on the wrong page."""
    pages = from_pages(["aaaa", "bbbb", "cccc"])          # offsets 0, 5, 10 (joined with \\n)
    assert pages.offsets == (0, 5, 10)
    assert [pages.page_at(o) for o in (0, 3, 4, 5, 9, 10, 99)] == [1, 1, 1, 2, 2, 3, 3]


def test_an_unpaged_text_answers_none_and_not_page_one():
    """An email has no pages. Numbering it 1 would put a page number on every citation in the
    product and mean nothing by any of them."""
    assert EMPTY.page_at(0) is None
    assert not EMPTY


def test_a_negative_offset_answers_none_rather_than_the_first_page():
    """A caller that has not translated its frame is a bug; answering it hides the bug."""
    assert from_pages(["a", "b"]).page_at(-1) is None


def test_an_empty_page_still_holds_its_boundary():
    """A page that extracted to nothing is still a page: the ones after it must keep their real
    numbers, or every citation below a blank scan page is off by one."""
    pages = from_pages(["first", "", "third"])
    assert pages.offsets == (0, 6, 7)
    assert pages.page_at(7) == 3


# =============================================================================================
# for_slice — the upload chunk case
# =============================================================================================
def test_a_chunk_that_begins_mid_document_is_numbered_by_the_page_it_starts_on():
    pages = from_pages(["one" * 10, "two" * 10, "three" * 10])      # 0, 31, 62
    chunk = pages.for_slice(40, 80)
    assert chunk.first_page == 2 and chunk.offsets == (0, 22)
    assert chunk.page_at(0) == 2 and chunk.page_at(22) == 3


def test_a_chunk_inside_one_page_gets_a_one_entry_map_naming_it():
    pages = from_pages(["one" * 10, "two" * 10, "three" * 10])
    chunk = pages.for_slice(35, 50)
    assert chunk.offsets == (0,) and chunk.first_page == 2
    assert chunk.page_at(14) == 2                      # every span in the chunk cites page 2


def test_an_empty_or_inverted_slice_has_no_map():
    pages = from_pages(["a", "b"])
    assert not pages.for_slice(5, 5)
    assert not pages.for_slice(5, 1)


# =============================================================================================
# The record — what crosses the connector and the database
# =============================================================================================
def test_the_record_round_trips():
    pages = PageMap(offsets=(0, 40, 90), first_page=3)
    assert from_record(pages.as_record()) == pages


@pytest.mark.parametrize("record", [
    None, {}, {"page_offsets": []}, {"page_offsets": "0,40"},
    {"page_offsets": [10, 40]},                       # does not start at 0 → not this text's map
    {"page_offsets": [40, 0]},                        # descending
    {"page_offsets": [0, None]},                      # a hole
])
def test_a_malformed_record_answers_empty_rather_than_raising(record):
    """This reads a dict that crossed a connector and a database. A map we cannot parse costs a
    page number; raising here would cost the extraction."""
    assert from_record(record) is EMPTY or from_record(record) == EMPTY


def test_a_first_page_that_is_not_a_page_number_falls_back_to_one():
    assert from_record({"page_offsets": [0, 9], "first_page": 0}).first_page == 1
    assert from_record({"page_offsets": [0, 9], "first_page": "3"}).first_page == 1


# =============================================================================================
# The constructor's own invariants
# =============================================================================================
def test_a_map_whose_first_offset_is_not_zero_is_refused():
    """The map is expressed in the coordinates of the text it describes, and that text begins at
    0. A map starting at 120 is a map of some other string."""
    with pytest.raises(ValueError, match="must be 0"):
        PageMap(offsets=(120, 400))


def test_descending_offsets_are_refused():
    with pytest.raises(ValueError, match="ascending"):
        PageMap(offsets=(0, 400, 120))


def test_page_numbering_starts_at_one():
    with pytest.raises(ValueError, match="starts at 1"):
        PageMap(offsets=(0,), first_page=0)
