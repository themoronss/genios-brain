"""The line check, pure — every written line held to its own item's material (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 3, tree `yc2_w27_s15` M45.C2.L-logic.V0.U02. `executive/morning_prompt`
hands the writer each item's material and nothing else; this is what holds it to that hand-off afterwards, the
way `platform/grounding.invention_ok` already holds every other text the engine shows a founder (STEP-13's move):
a name, a number or a date the item does not hold is refused — which already refuses a CONNECTOR as the one to
act, or any other person the item's material does not name, because neither is in the corpus this check reads.
Two checks invention does not cover, held here directly:

  * the founder is "you" (`executive/morning_day.speaks_of_you`, `03` F178) — never their name, never "the
    founder";
  * no line names an address — `invention_ok` looks for capitalised proper nouns, and an address is neither
    capitalised nor a digit run.

A line that fails either check, or invents a name, a number or a date, is given back its OWN item's template
words (`executive/morning_template.words_for`) — never dropped, never left blank — with why.

THE WHOLE ANSWER, not only one line: the writer was handed the day's items in ONE order
(`executive/morning_order.order`) and must hand back exactly one line per item, in that same order. A different
count is MALFORMED — the writer's syntax or its parsing, not a line any single check could pass or fail — and
every item is given its template words rather than guessing which line belongs to which. A line matched to the
wrong item by a mismatched count never happens: `check_answer` refuses the whole answer first. The BUDGET
(`contracts.morning_brief.WORD_BUDGET`) is read against what actually stands once every verdict is in — the
template's words where a draft failed, the draft's where it held — because a check that counted the untrusted
draft's own length would let a line that is given back anyway spend the budget on its way out.

Pure: no I/O, no clock, no model.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from genios_engine.contracts import morning_brief as B
from genios_engine.executive.morning_day import speaks_of_you
from genios_engine.executive.morning_template import words_for
from genios_engine.platform.grounding import corpus_of, invention_ok

MORNING_CHECK_VERSION = "morning_check.v1"

#: An address, as a line might write one — the same shape `contracts/morning_brief._ADDRESS` refuses at
#: construction; `invention_ok` does not look for it, since it is neither capitalised nor a digit run.
_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass(frozen=True, slots=True)
class LineCheck:
    """One item's verdict: KEPT, with the words that stand, or GIVEN_BACK, with why and the template's own
    words."""

    item_id: str
    verdict: str                 # B.KEPT or B.GIVEN_BACK
    reason: str | None           # None when kept
    words: str                   # what stands — the draft's words if kept, the template's if given back


def _section_for(item: B.Item, ordered_section: str | None) -> str:
    """The section `words_for` reads the item's words as — the section the item was actually ordered into,
    when known, else `TODAY` (every kind renders the same words in every section but `DECISION`'s quiet-clause
    and `WATCHED`'s, which only ever appear in their own)."""
    return ordered_section or B.TODAY


def check_line(item: B.Item, text: str, *, section: str | None = None,
               founder: Iterable[str | None] = ()) -> LineCheck:
    """One written line against its own item's material, and nothing else held elsewhere in the day."""
    said = " ".join(str(text or "").split())
    fallback = words_for(item, _section_for(item, section))
    if not said:
        return LineCheck(item.item_id, B.GIVEN_BACK, "the line is empty", fallback)
    if speaks_of_you(said, founder):
        return LineCheck(item.item_id, B.GIVEN_BACK, "speaks of you as someone other than \"you\"", fallback)
    if _ADDRESS.search(said):
        return LineCheck(item.item_id, B.GIVEN_BACK, "names an address", fallback)
    corpus, nums = corpus_of(item.material.texts())
    ok, why = invention_ok(said, corpus, nums)
    if not ok:
        kind, _sep, value = str(why).partition(":")
        return LineCheck(item.item_id, B.GIVEN_BACK, f"invents a {kind} the item does not hold: {value!r}",
                         fallback)
    return LineCheck(item.item_id, B.KEPT, None, said)


@dataclass(frozen=True, slots=True)
class AnswerCheck:
    """The whole answer's verdict: malformed (a count the items did not hand out), or one `LineCheck` per item,
    in the items' own order, and the word count of what actually stands."""

    malformed: bool
    reason: str | None
    lines: tuple[LineCheck, ...]
    words: int


def check_answer(items: Sequence[B.Item], texts: Sequence[str], *, sections: Sequence[str] | None = None,
                 founder: Iterable[str | None] = ()) -> AnswerCheck:
    """Exactly one text per item, in the items' own order. A different count is malformed: every item is given
    its template words, and no line is matched to the wrong item by position."""
    items = tuple(items)
    texts = tuple(texts)
    if len(items) != len(texts):
        lines = tuple(LineCheck(i.item_id, B.GIVEN_BACK,
                                f"the answer held {len(texts)} line(s) for {len(items)} item(s)",
                                words_for(i, _section_for(i, (sections or ())[n] if sections and n < len(sections)
                                                          else None)))
                      for n, i in enumerate(items))
        return AnswerCheck(malformed=True,
                           reason=f"{len(texts)} line(s) for {len(items)} item(s) — the writer's answer does "
                                  "not match the day it was handed",
                           lines=lines, words=sum(B.count_words(l.words) for l in lines))
    secs = tuple(sections) if sections is not None else (None,) * len(items)
    lines = tuple(check_line(item, text, section=sec, founder=founder)
                  for item, text, sec in zip(items, texts, secs))
    return AnswerCheck(malformed=False, reason=None, lines=lines,
                      words=sum(B.count_words(l.words) for l in lines))


__all__ = ["AnswerCheck", "LineCheck", "MORNING_CHECK_VERSION", "check_answer", "check_line"]
