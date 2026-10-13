"""Your open screen follow-ups, in your own brief — seat-private, never in a file's timeline (STEP-15, `06` D8).

`speedrun008/YC-II W27/` STEP-15 §8.6 `06` D8, tree `yc2_w27_s15` M45.C4.L-logic.V0.U02. 65 screen reminders and
pieces of advice were built and hidden (`03` s15-F ·`06` D8's own count). Yes: a promise of yours, something you
were asked, or a deadline within 48 hours (`reason/moments/followups.open_items`) is a line in your own brief
first — the in-the-moment popup stays hidden until a week of brief feedback, which is a LATER unit's switch, not
this one's.

BESIDE THE FILE WHOSE PERSON IT NAMES. A follow-up's `who` is compared, by `platform/identity.person_name_key`, to
the names a file's own people are shown as (`06` D22, D53: the comparison is read-only — nothing here writes the
follow-up onto a file's own timeline, and nothing a file's timeline holds is written here). A match gives the
line that file's own name as its subject, so it reads beside that file's other lines; the rest keep the
follow-up's own `who`, or none.

SEAT-PRIVATE: `open_items` already reads one seat's own `screen_followups` rows — this module adds no further
filter, and queries nothing else.

Pure read: one connection, the instant it is asked about, no model.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta

from genios_engine.contracts import morning_brief as B

#: `06` D8: a deadline this close is worth a line regardless of the file's own rules — the same window
#: `executive/morning_order.ALWAYS_IN` reads a dated promise or deadline against.
DEADLINE_WINDOW = timedelta(hours=48)
#: The follow-up kinds `06` D8 names: a promise of yours, something you were asked, a deadline. Never
#: `their_promise`, `risk` or `next_step` — `reason/moments/followups.KINDS`' own vocabulary, not this decision's.
SURFACED_KINDS = ("my_promise", "ask", "deadline")


def _instant(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def screen_items(conn, *, org_id: str, seat_id: str, file_by_person: Mapping[str, str],
                 file_names: Mapping[str, str], now: datetime) -> list[B.Item]:
    """Your open screen follow-ups as brief items — a promise, an ask, or a deadline within 48 hours — each
    beside the file whose person it names when `file_by_person` (keyed by `platform/identity.person_name_key`)
    finds one, else under your own promises by who it names, or by nobody."""
    from genios_engine.platform.identity import person_name_key
    from genios_engine.reason.moments.followups import open_items
    out: list[B.Item] = []
    for it in open_items(conn, org_id=org_id, seat_id=seat_id):
        kind = it.get("kind")
        if kind not in SURFACED_KINDS:
            continue
        due = _instant(it.get("due_at"))
        if kind == "deadline" and not (due is not None and due <= now + DEADLINE_WINDOW):
            continue                                    # `06` D8 names a deadline within 48 hours, not every one
        text = " ".join(str(it.get("text") or "").split())
        if not text:
            continue
        who = str(it.get("who") or "").strip()
        key = person_name_key(who) if who else None
        file_id = file_by_person.get(key) if key else None
        subject = file_names.get(file_id) if file_id else (who or None)
        words: list[tuple[str, str]] = [("promise", text)]
        if subject:
            words.append(("to", subject))
        out.append(B.Item(
            item_id=B.item_id_for(B.PROMISE, f"screen:{it['id']}"), kind=B.PROMISE, about=file_id, subject=subject,
            material=B.Material(words=tuple(words), names=tuple(n for n in (subject,) if n)),
            sources=(B.Source(B.SOURCE_PROMISE, str(it["id"])),), at=due, our_move=True))
    return out


__all__ = ["DEADLINE_WINDOW", "SURFACED_KINDS", "screen_items"]
