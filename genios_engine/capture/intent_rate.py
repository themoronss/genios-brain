"""L1.4.x-U3 · THE `unknown` RATE, PER SOURCE — the monitor on a silently degrading reader.

E2 of step 7, in one sentence: *a source that returns `unknown` for 80% of its mail is a prompt
defect, and nothing counts it.*

**WHY THIS IS THE FAILURE MODE THAT NEEDS A NUMBER RATHER THAN AN ALARM.** A prompt edit that
breaks intent reading does not raise, does not log an error and does not fail a test. It produces
slightly emptier readings, for everybody, until somebody happens to notice — and "slightly emptier"
looks exactly like "a quiet week". `capture/validate/spans.py` already carries the same argument
for its own unverified-rate monitor, and this is that monitor for the other half of the extraction.

**PER SOURCE, NEVER GLOBALLY.** Gmail and a calendar feed have genuinely different readable rates —
a calendar invite has no tone and no motive to read, and scoring it beside a mail thread is
comparing two different questions. One number over both hides a broken connector behind a healthy
one, which is the precise shape of the bug this is meant to surface.

**IT COUNTS `observed_anything`, NOT `category is UNKNOWN`.** A reading that answered the tone and
the register but not the category told us something; a reading where every axis is `unknown` and
every boolean is `None` is the model saying *"I could not read this"*. `contracts/intent.py` draws
that line itself and this module honours it: *"the second is information, the first is not."*

INTEGER BASIS POINTS, truncated, never a float — V-7. A rate is a ratio of counts, and a float here
reaches storage as jsonb and comes back as a number nobody can trace back to a numerator.

PURE: no clock, no I/O, no model. It is handed readings and returns rates.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

#: Full rate in basis points. 10000 = every message from this source was unreadable.
BP_FULL = 10_000

#: Above this, the source's reader is not working. 5000 bp means half of everything from a
#: connector arrived with nothing read off it at all.
#:
#: A THRESHOLD FOR REPORTING, NOT A GATE. Nothing is refused or retried for crossing it — it marks
#: the row so a weekly report can sort by it. A rate that silently changed behaviour would be a
#: filter, and this module's whole job is to make a silence visible rather than act on it.
DEGRADED_RATE_BP = 5_000


def unknown_rate_bp(readings: Iterable[tuple[str, object]]) -> dict[str, int]:
    """`{source: unreadable share in basis points}`, over readings grouped by source.

    Each item is `(source, MessageIntent)`. Anything without an `observed_anything` property is
    counted as UNREADABLE rather than skipped: a reading that is not a reading is the strongest
    possible evidence that this source's path is broken, and skipping it would make the worst case
    report the best rate.

    A SOURCE WITH NO MESSAGES IS ABSENT FROM THE RESULT, never zero. Zero reads as *"this source is
    perfectly readable"*, which is the opposite of *"we have not seen anything from it"* — and one
    of those is a reason to stop worrying. Absence is the honest answer and this layer says so
    everywhere else.
    """
    seen: dict[str, int] = defaultdict(int)
    unreadable: dict[str, int] = defaultdict(int)

    for source, reading in readings:
        name = str(source or "").strip() or "unknown_source"
        seen[name] += 1
        if not bool(getattr(reading, "observed_anything", False)):
            unreadable[name] += 1

    return {name: unreadable[name] * BP_FULL // count for name, count in seen.items()}


def degraded_sources(rates: dict[str, int]) -> tuple[str, ...]:
    """The sources whose reader is not working, sorted worst first.

    Sorted rather than merely filtered, because the useful question a person asks of this report is
    *"which connector do I look at"* and not *"is anything wrong"*. Ties break on the name so two
    runs over one corpus produce identical output.
    """
    over = [(bp, name) for name, bp in rates.items() if bp >= DEGRADED_RATE_BP]
    return tuple(name for _, name in sorted(over, key=lambda pair: (-pair[0], pair[1])))


__all__ = ["BP_FULL", "DEGRADED_RATE_BP", "degraded_sources", "unknown_rate_bp"]
