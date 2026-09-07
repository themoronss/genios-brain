"""L1.3.4-U5 · the page map — where a character offset falls in a paged document.

**Why this exists.** Every receipt Layer 1 produces is a character range, which is exactly the
right thing for a machine and useless to the person who has to check it. *"Character 4,812 of the
prepared text"* cannot be looked up in a signed PDF; *"page 4"* can. The page boundaries are known
for about a microsecond — while `documents/native.py` is joining a PDF's pages into one string —
and are unrecoverable afterwards, because concatenation is not invertible. This module is the
type that carries them from there to the span.

**One offset space per event, and that is the whole subtlety.** A Gmail attachment arrives as ONE
event whose text is the whole document, so its map starts at page 1 with offset 0. An uploaded
file arrives as one event PER CHUNK, and a chunk's text starts partway down page 3 — so its map
must be expressed in the chunk's own coordinates, and must remember that its first entry is page
3 rather than page 1. `for_slice` is that translation, and `first_page` is why the type is a pair
rather than a bare tuple of offsets.

**Deterministic and pure.** No clock, no IO, integers only. A replayed extraction resolves the
same character to the same page for ever, which is the property that lets a citation printed in
March still be checkable in September.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PageMap:
    """Where each page of a document begins, in the coordinates of ONE event's text.

    `offsets[i]` is the character at which the `first_page + i`-th page's text starts. The list is
    ascending and its first entry is 0 by construction — an event's text begins somewhere, and
    that somewhere is the start of whatever page it is on.
    """

    #: Ascending, starting at 0. Empty means "this text has no pages", which is the honest state
    #: for an email body, a chat message and a calendar event — not a one-page document.
    offsets: tuple[int, ...] = ()
    #: The printed number of the page `offsets[0]` belongs to. 1 for a whole document; higher for
    #: a chunk that begins partway through one.
    first_page: int = 1

    def __post_init__(self) -> None:
        if any(isinstance(o, bool) or not isinstance(o, int) or o < 0 for o in self.offsets):
            raise ValueError("page offsets are character positions: non-negative integers only")
        if list(self.offsets) != sorted(self.offsets):
            raise ValueError("page offsets must be ascending — a page that begins before the one "
                             "above it is a map nothing can be looked up in")
        if isinstance(self.first_page, bool) or not isinstance(self.first_page, int) \
                or self.first_page < 1:
            raise ValueError("first_page is a printed page number, so it starts at 1")
        if self.offsets and self.offsets[0] != 0:
            raise ValueError("the first page offset must be 0 — the map is expressed in the "
                             "coordinates of the text it describes, which begins at 0")

    def __bool__(self) -> bool:
        return bool(self.offsets)

    def page_at(self, offset: int) -> int | None:
        """The printed page number containing this character, or None for an unpaged text.

        `bisect_right - 1`: an offset that IS a page's first character belongs to that page, not
        to the one before it. A negative offset (a caller that has not translated its frame) gets
        None rather than page one, because answering it would hide the bug.
        """
        if not self.offsets or isinstance(offset, bool) or not isinstance(offset, int) \
                or offset < 0:
            return None
        return self.first_page + max(0, bisect_right(self.offsets, offset) - 1)

    def for_slice(self, start: int, end: int) -> "PageMap":
        """This map, re-expressed in the coordinates of `text[start:end]`.

        The chunk case. Pages that begin before the slice collapse into its first entry (offset 0,
        numbered by whichever page the slice STARTS on); pages that begin inside it keep their
        boundary, shifted. A slice that lies wholly inside one page therefore gets a one-entry map
        naming that page, which is exactly right and is what makes every span in that chunk cite
        it.
        """
        if not self.offsets or end <= start or start < 0:
            return PageMap()
        page = self.page_at(start) or self.first_page
        inside = tuple(o - start for o in self.offsets if start < o < end)
        return PageMap(offsets=(0,) + inside, first_page=page)

    def as_record(self) -> dict:
        """The JSON shape connectors put on `raw["document"]`, and `from_record` reads back."""
        return {"page_offsets": list(self.offsets), "first_page": self.first_page}


EMPTY = PageMap()


def from_pages(pages: Sequence[str], *, separator: str = "\n") -> PageMap:
    """The map for a document assembled by joining page texts with `separator`.

    Built by the joiner, from the same list it is joining — never re-derived by re-parsing the
    PDF, which is both a second parse and a second answer.
    """
    offsets: list[int] = []
    cursor = 0
    for index, page in enumerate(pages):
        offsets.append(cursor)
        cursor += len(page) + (len(separator) if index < len(pages) - 1 else 0)
    return PageMap(offsets=tuple(offsets)) if offsets else EMPTY


def from_record(record: object) -> PageMap:
    """A `raw["document"]` mapping back into a `PageMap`. Anything malformed answers EMPTY.

    Tolerant on purpose: this reads a dict that crossed a database and a connector, and a map we
    cannot parse costs a page number. Raising here would cost the extraction.
    """
    if not isinstance(record, dict):
        return EMPTY
    raw_offsets = record.get("page_offsets")
    if not isinstance(raw_offsets, (list, tuple)) or not raw_offsets:
        return EMPTY
    offsets = [o for o in raw_offsets if isinstance(o, int) and not isinstance(o, bool) and o >= 0]
    if len(offsets) != len(raw_offsets) or offsets != sorted(offsets) or offsets[0] != 0:
        return EMPTY
    first = record.get("first_page", 1)
    if isinstance(first, bool) or not isinstance(first, int) or first < 1:
        first = 1
    return PageMap(offsets=tuple(offsets), first_page=first)


__all__ = ["EMPTY", "PageMap", "from_pages", "from_record"]
