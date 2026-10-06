"""Which road a kept event takes into memory — decided once, in one pure function (STEP-05).

Layer 2 used to take only an event with an active qualified signal: `context/runner._pull` inner-joined
one. So memory held about 27 of 395 mails and 2 of 34 meetings — a mail the qualification floor did not
publish, an archived mail and a calendar event whose deadline signal had expired never entered it
(`speedrun008/YC-II W27/` STEP-05 §8). Now a kept event takes exactly one road:

  signal        an active qualified signal — as before: the signal's extraction, at its confidence;
  below_floor   no signal, but its L1 extraction exists — the mail WAS read, and the floor only judged
                it not worth an alert. That extraction, every claim ranked under the floor, with no
                model call (`06` D20);
  metadata      archived — the gate called it noise. Who wrote to whom, when, in which thread, from the
                ledger's own columns: no text (`03` F37, F57), no ball-in-court, no correlation;
  calendar      a structured mapping — always, whatever its signal: a meeting is a meeting, not a
                deadline that expires.

And `None` — not now: a screen session without a signal (a screen never creates memory of a person on
its own: its people are private, `reason/moments/screen_memory`, `06` D22), an event with nothing to
read yet (it waits for the re-read ladder, `capture/landing/unread`), or an outcome that is not kept.
"""
from __future__ import annotations

from enum import Enum


class Lane(str, Enum):
    SIGNAL = "signal"
    BELOW_FLOOR = "below_floor"
    METADATA = "metadata"
    CALENDAR = "calendar"


#: The ledger outcomes that mean "kept": read and published, or kept and read by no model.
KEPT_OUTCOMES: tuple[str, ...] = ("emitted", "archived")
#: The screen's source name, as `capture/screen/render.SOURCE` writes it (pinned by the lane test).
SCREEN_SOURCE = "screen_session"


def lane_for(*, outcome: str | None, source: str | None, structured: bool, has_signal: bool,
             has_extraction: bool) -> Lane | None:
    """The one road `outcome`/`source` and what exists for the event allow — or None."""
    if outcome not in KEPT_OUTCOMES:
        return None
    if outcome == "archived":
        # Noise, by the gate's own rule: its names and its date, never its words. A screen item is
        # never archived into memory — its people are private.
        return None if source == SCREEN_SOURCE else Lane.METADATA
    if structured:
        return Lane.CALENDAR
    if has_signal:
        return Lane.SIGNAL
    if source == SCREEN_SOURCE:
        return None
    return Lane.BELOW_FLOOR if has_extraction else None
