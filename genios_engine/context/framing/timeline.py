"""L2.7.2-U2 · M-7 · the timeline NARRATIVE — *"promised in April, silent since June, deadline in
twelve days"*.

A chronological sort is not a story. Which events matter, and what shape they make, is the model's
contribution; everything else here is arithmetic:

    1. SORT      chronological order is COMPUTED, never asked for. A model-ordered timeline
                 cannot be replayed, and two runs would tell the story differently.
    2. SELECT    the model returns event IDS from the supplied set. Never event text, never a
                 new event. An id outside the set fails the whole narrative.
    3. SHAPE     one label from a CLOSED set. Not free prose: an unbounded vocabulary is one
                 nothing downstream can branch on.
    4. RENDER    the sentence is templated from the shape plus the selected events' own dates.
                 Every date and every interval is computed and substituted, never generated —
                 "about three months" is a number nobody can check.
    5. FALLBACK  a validation failure or an exhausted budget publishes the deterministic
                 chronology, unnarrated, and LOGS which it was.

THE ANCHOR'S OWN EVENTS SURVIVE SELECTION. A narrative that drops the event the situation is about
is a story about something else, and the model has no way of knowing which event that is — so the
caller names them and this module keeps them regardless of what comes back.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from genios_engine.context.patterns.contract import days_between
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.visibility import Visibility, narrowest
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.framing.timeline")

#: The closed vocabulary. A shape outside it is rejected — see the module docstring, step 3.
SHAPES: tuple[str, ...] = ("steady", "stalled", "accelerating", "silent_since",
                           "deadline_approaching")

#: One sentence per shape, digit-free, with the intervals substituted. Same rule as the headline
#: templates: a literal number in a template is a number no event backs.
_SENTENCES: dict[str, str] = {
    "steady": "{first_label} in the last {span_days} days, moving at a regular pace",
    "stalled": "{first_label}, then nothing for {silent_days} days",
    "accelerating": "{count} exchanges in the last {span_days} days, and closing up",
    "silent_since": "silent for {silent_days} days since {last_label}",
    "deadline_approaching": "{last_label}, with {span_days} days of history behind it",
}

FALLBACK_NO_MODEL = "no_model"
FALLBACK_MODEL_ERROR = "model_error"
FALLBACK_MALFORMED = "malformed_response"
FALLBACK_UNKNOWN_EVENT = "unknown_event_id"
FALLBACK_UNKNOWN_SHAPE = "unknown_shape"
FALLBACK_EMPTY_SELECTION = "empty_selection"


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """One dated thing that happened, with a label a card may print verbatim."""

    event_id: str
    occurred_at: datetime
    label: str
    visibility: Visibility | None = None
    spans: tuple[EvidenceSpan, ...] = ()


@dataclass(frozen=True, slots=True)
class Narrative:
    """The story, the chronology it was built from, and where it came from."""

    shape: str
    sentence: str
    #: The events the narrative names, in chronological order.
    selected: tuple[TimelineEvent, ...]
    #: THE FULL CHRONOLOGY, always. Doc 12 case 13: selection is the model's, and the complete
    #: story stays available so a card can expand to it — a narrative that replaced the timeline
    #: would make the model's omission unrecoverable.
    chronology: tuple[TimelineEvent, ...]
    visibility: Visibility
    fallback: bool
    fallback_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {"shape": self.shape, "sentence": self.sentence,
                "selected_event_ids": [e.event_id for e in self.selected],
                "chronology": [{"event_id": e.event_id, "at": e.occurred_at.isoformat(),
                                "label": e.label} for e in self.chronology],
                "fallback": self.fallback, "fallback_reason": self.fallback_reason}


Asker = Callable[[str], Mapping[str, Any] | None]


def chronology(events: Sequence[TimelineEvent], *, viewer_email: str | None = None,
               org_member: bool = True) -> tuple[TimelineEvent, ...]:
    """The deterministic order, visibility-filtered. Computed here and never asked for.

    Ties break on `event_id` so two events at the same instant order the same way on every run —
    a timeline whose order depends on `readdir` is a timeline that cannot be diffed.
    """
    allowed = [e for e in events
               if e.visibility is None or e.visibility.can_view(viewer_email,
                                                                org_member=org_member)]
    return tuple(sorted(allowed, key=lambda e: (e.occurred_at, e.event_id)))


def build_prompt(ordered: Sequence[TimelineEvent], *, situation_type: str) -> str:
    """The prompt: an ORDERED list, ids only, and a closed vocabulary to choose from."""
    lines = [f"Select which of these events matter to a {situation_type} situation, and name the "
             "shape of the story.",
             "",
             'Return JSON: {"event_ids": ["..."], "shape": "<one of the shapes below>"}',
             "Return IDS ONLY. Do not write event text, do not add an event, do not reorder — the "
             "order below is the chronology and is not yours to change.",
             f"SHAPES: {list(SHAPES)}",
             "EVENTS (chronological):"]
    lines.extend(f"  - id={e.event_id}  {e.occurred_at.date().isoformat()}  {e.label}"
                 for e in ordered)
    return "\n".join(lines)


def narrate(events: Sequence[TimelineEvent], *, situation_type: str, eval_time: datetime,
            anchor_event_ids: Sequence[str] = (), ask: Asker | None = None,
            viewer_email: str | None = None, org_member: bool = True) -> Narrative:
    """M-7. The model selects and shapes; this function orders, validates and renders."""
    ordered = chronology(events, viewer_email=viewer_email, org_member=org_member)
    if not ordered:
        return Narrative("steady", "", (), (), narrowest(), True, FALLBACK_EMPTY_SELECTION)
    if ask is None:
        return _plain(ordered, eval_time, FALLBACK_NO_MODEL)

    try:
        response = ask(build_prompt(ordered, situation_type=situation_type))
    except Exception as exc:                              # noqa: BLE001
        _log.warning("timeline model failed: %s", exc)
        return _plain(ordered, eval_time, FALLBACK_MODEL_ERROR)
    if not isinstance(response, Mapping):
        return _plain(ordered, eval_time, FALLBACK_MALFORMED)

    shape = str(response.get("shape") or "")
    if shape not in SHAPES:
        return _plain(ordered, eval_time, FALLBACK_UNKNOWN_SHAPE)

    raw_ids = response.get("event_ids")
    if not isinstance(raw_ids, (list, tuple)):
        return _plain(ordered, eval_time, FALLBACK_MALFORMED)
    known = {e.event_id for e in ordered}
    chosen = {str(i) for i in raw_ids}
    unknown = chosen - known
    if unknown:
        # A fabricated event, or one this reader may not see — `ordered` is already filtered, so
        # an id that was dropped for visibility lands here exactly as an invented one does.
        _log.warning("timeline narrative named unknown event ids %s", sorted(unknown))
        return _plain(ordered, eval_time, FALLBACK_UNKNOWN_EVENT)

    # The anchor's own events are retained regardless of selection: a narrative that omits its own
    # subject is a story about something else.
    chosen |= {i for i in anchor_event_ids if i in known}
    selected = tuple(e for e in ordered if e.event_id in chosen)
    if not selected:
        return _plain(ordered, eval_time, FALLBACK_EMPTY_SELECTION)
    return Narrative(shape=shape, sentence=render(shape, selected, eval_time=eval_time),
                     selected=selected, chronology=ordered,
                     visibility=narrowest(*(e.visibility for e in ordered)), fallback=False)


def render(shape: str, selected: Sequence[TimelineEvent], *, eval_time: datetime) -> str:
    """The sentence. Every number in it is COMPUTED from the selected events' own dates.

    `days_between` is the same integer arithmetic the temporal conditions use, so the interval a
    card prints and the interval a pattern tested are the same number rather than two roundings of
    one duration.
    """
    first, last = selected[0], selected[-1]
    values = {"first_label": first.label, "last_label": last.label,
              "span_days": days_between(last.occurred_at, first.occurred_at),
              "silent_days": days_between(eval_time, last.occurred_at),
              "count": len(selected)}
    return _SENTENCES[shape].format(**values)


def _plain(ordered: Sequence[TimelineEvent], eval_time: datetime, reason: str) -> Narrative:
    """The unnarrated chronology — the fallback, logged. A plainer card beats a wrong one."""
    _log.info("timeline fell back to the plain chronology: %s", reason)
    silent = days_between(eval_time, ordered[-1].occurred_at)
    shape = "silent_since" if silent > 0 else "steady"
    return Narrative(shape=shape, sentence="", selected=tuple(ordered), chronology=tuple(ordered),
                     visibility=narrowest(*(e.visibility for e in ordered)),
                     fallback=True, fallback_reason=reason)


__all__ = ["SHAPES", "Asker", "Narrative", "TimelineEvent", "build_prompt", "chronology",
           "narrate", "render"]
