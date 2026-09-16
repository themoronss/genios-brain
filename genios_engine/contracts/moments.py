"""Hot-lane request bodies — SCREEN_INTEL_P3_BUILD.md §2.2–2.4 (frozen) + plan §6.2.

Responses are plain dicts built in `reason/moments/store.moment_out` so the one shape serves
evaluate, history and the realtime payload.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KINDS = ("advice", "reminder", "verify", "team")
PRIORITIES = ("low", "normal", "high", "critical")
FEEDBACK_ACTIONS = ("shown", "clicked", "acted", "dismissed", "wrong", "snoozed", "useful")

Kind = Literal["advice", "reminder", "verify", "team"]
Priority = Literal["low", "normal", "high", "critical"]
FeedbackAction = Literal["shown", "clicked", "acted", "dismissed", "wrong", "snoozed", "useful"]


class Surface(BaseModel):
    model_config = ConfigDict(extra="ignore")
    app: str | None = Field(default=None, max_length=64)
    bundle_id: str | None = Field(default=None, max_length=255)
    url_domain: str | None = Field(default=None, max_length=512)
    thread_key: str | None = Field(default=None, max_length=300)


class Participant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=320)
    linkedin_url: str | None = Field(default=None, max_length=2048)


class DatePhrase(BaseModel):
    """A date the DEVICE already resolved against the manager's own clock. `time` ("17:00") is
    there because "kal 5 baje" without the hour is just "kal", and the brain would then let the
    model guess an hour the device had already parsed."""
    model_config = ConfigDict(extra="ignore")
    text: str | None = Field(default=None, max_length=100)
    resolved: str | None = Field(default=None, max_length=64)
    time: str | None = Field(default=None, max_length=8)


class Features(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intents: list[str] = Field(default_factory=list, max_length=20)
    dates: list[DatePhrase] = Field(default_factory=list, max_length=20)
    entities: list[str] = Field(default_factory=list, max_length=50)
    #: P5 §3 (P-15): the meeting the desktop's timer fired for → `moment.meeting_prep`.
    meeting_node_id: str | None = Field(default=None, max_length=200)


class EvaluateRequest(BaseModel):
    """Plan §6.2 request. `draft_text` / `visible_messages` are accepted and never stored."""
    model_config = ConfigDict(extra="ignore")
    moment_request_id: str = Field(min_length=1, max_length=100)
    seat_id: str | None = Field(default=None, max_length=200)
    device_id: str | None = Field(default=None, max_length=200)
    surface: Surface = Field(default_factory=Surface)
    participants: list[Participant] = Field(default_factory=list, max_length=50)
    features: Features = Field(default_factory=Features)
    draft_text: str | None = Field(default=None, max_length=20000)
    visible_messages: list | None = Field(default=None, max_length=200)
    # P-20 screen insight: judge what is on screen (`visible_messages`) for one short note.
    insight: bool = False
    #: The device account's full name (the Mac / PC user) — who "you" are on screen, so the
    #: screen-insight judge never names the manager as the other person. Never stored.
    viewer_name: str | None = Field(default=None, max_length=200)
    slice_version: int | None = None
    client_ts: datetime | None = None


class DeviceMoment(BaseModel):
    """§2.3: a device-local moment (P-01 / P-18) posted for history, guards and feedback."""
    model_config = ConfigDict(extra="ignore")
    moment_id: str = Field(min_length=8, max_length=100)
    origin: Literal["device"] = "device"
    kind: Kind
    priority: Priority = "normal"
    headline: str = Field(min_length=1, max_length=300)
    body: str | None = Field(default=None, max_length=2000)
    actions: list[dict] = Field(default_factory=list, max_length=8)
    evidence: list[dict] = Field(default_factory=list, max_length=20)
    ttl_seconds: int = Field(default=900, ge=1, le=86400)
    capability_id: str = Field(min_length=1, max_length=100)
    capability_version: str = Field(default="1", min_length=1, max_length=20)
    subject_node_ids: list[str] = Field(default_factory=list, max_length=20)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: FeedbackAction
    reason: str | None = Field(default=None, max_length=500)
    at: datetime | None = None


class FollowupResolveRequest(BaseModel):
    """P8 C5: the person closes a screen follow-up (toast `done` / panel dismiss)."""
    model_config = ConfigDict(extra="ignore")
    resolution: Literal["done", "dismissed"]


class FollowupSnoozeRequest(BaseModel):
    """P10: move a follow-up's nudge — a preset (`1h`, `tonight`, `tomorrow`) or an instant.
    Exactly one of the two (checked by the route: 422 otherwise)."""
    model_config = ConfigDict(extra="ignore")
    preset: Literal["1h", "tonight", "tomorrow"] | None = None
    until: datetime | None = None


__all__ = ["DatePhrase", "DeviceMoment", "EvaluateRequest", "FEEDBACK_ACTIONS", "FeedbackRequest",
           "Features", "FollowupResolveRequest", "FollowupSnoozeRequest", "KINDS", "PRIORITIES",
           "Participant", "Surface"]
