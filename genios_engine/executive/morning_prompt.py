"""The writer's prompt — a 30-year chief of staff's morning note, written only from the day's items (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 3, tree `yc2_w27_s15` M45.C2.L-logic.V0.U01. R-8 (Haiku-class) and R-8E
(Sonnet-class) get the SAME prompt — the tier is configuration (`reason/bundle/sites.py`, a later unit's), and this
module names no model anywhere in its text.

THE PROMPT HANDS OVER THE DAY, NOTHING ELSE. Every item of `executive/morning_order.order`'s own sections, in that
order, each as its MATERIAL — the checked words, the numbers with their `says`, the dates, the names — and nothing
the material does not hold. The writer is told, in so many words:

  * write ONE line per item, in the order given — never add, drop or reorder one;
  * for each of TODAY's items, give exactly ONE reason why it matters today, chosen from the `reason:` lines under
    that item — never one it invents;
  * at most ONE observation across every item, and only if it is worth saying — labelled plainly as its own
    reading, never as something an item's material says (`03` F178's "you" rule has a sibling here: an unlabelled
    opinion reads as a fact the file holds);
  * "you", never the founder's name or "the founder";
  * no number, name or date the items below do not hold;
  * never the connector as the one to reply to — a file is named by its own counterparty already;
  * the prompt itself names no model, and the note should name none either.

`executive/morning_check` (M45.C2.L-logic.V0.U02) holds every written line to the SAME material by the SAME
invention rule (`platform/grounding.invention_ok`) this prompt is built from — a line the writer invents past this
hand-off is a line the check gives its template words back.

Pure: no I/O, no clock, no model.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from genios_engine.contracts import morning_brief as B
from genios_engine.executive.morning_order import order

PROMPT_VERSION = "morning_prompt.v1"

ROLE = (
    "You are the chief of staff for a startup founder, thirty years into the job. Write their morning note for "
    "today — plain, warm, direct, the way you would say it to them at their desk."
)

#: The rules, in the writer's own words — `morning_check.py` enforces every one of these mechanically; this is
#: what asks for it the first time.
RULES = (
    "RULES — follow every one:\n"
    "1. Write exactly one line for each item listed below, in the order given. Never add an item, drop one, or "
    "move one out of its order.\n"
    "2. Use only what that item's own lines hold below — its name, its numbers, its dates. Never state a number, "
    "a name or a date you were not handed.\n"
    "3. Call the founder \"you\" — never their name, and never \"the founder\".\n"
    "4. For each item under TODAY, give exactly one reason why it matters today. Choose it from that item's own "
    "`reason:` line or lines below — never invent one of your own.\n"
    "5. Never ask the founder to reply to a connector or an introducer. A file's own name, given below, is who to "
    "reply to.\n"
    "6. You may add at most one observation across every item below — only if it is genuinely worth saying — and "
    "you must label it plainly as your own reading (for example, \"worth noting:\"), never write it as if the "
    "item's own material said it.\n"
    "7. Name no model anywhere in the note."
)

NOTHING = "Nothing is open, asked, due or watched today — say so in one line, and nothing else."


def _say(value: object) -> str:
    return " ".join(str(value or "").split())


def _block(item: B.Item) -> str:
    """One item, as its material and nothing else — what the writer may ground a line in."""
    m = item.material
    head = f"- [{item.kind}] {item.subject or 'a file'}"
    lines = [head]
    for role, words in m.words:
        lines.append(f"    {role}: {_say(words)}")
    for number in m.numbers:
        lines.append(f"    {number.name}: {number.says}")
    for role, when in m.dates:
        lines.append(f"    {role}: {when}")
    if m.names:
        lines.append(f"    names: {', '.join(m.names)}")
    return "\n".join(lines)


def build_prompt(*, items: Iterable[B.Item], company_brief: str = "", now: datetime, tz: str) -> str:
    """The prompt the writer reads: the role, the rules, the company brief when there is one, and the day's items
    in `morning_order.order`'s own order — each as its material, nothing else. Pure."""
    ordered = order(tuple(items), now=now, tz=tz)
    parts = [ROLE, "", RULES]
    if company_brief:
        parts += ["", "ABOUT THE COMPANY, IN THE FOUNDER'S OWN WORDS:", company_brief.rstrip("\n")]
    any_items = False
    for section, held in ordered.sections:
        if not held:
            continue
        any_items = True
        parts += ["", f"{B.TITLES[section].upper()}:"]
        parts += [_block(item) for item in held]
    if not any_items:
        parts += ["", NOTHING]
    parts += ["", "Write the note now: one line per item above, in order, and your one labelled observation if "
                 "you truly have one."]
    return "\n".join(parts)


__all__ = ["NOTHING", "PROMPT_VERSION", "ROLE", "RULES", "build_prompt"]
