"""Device API wire contracts — the desktop app ↔ brain boundary for screen capture (P1).

Frozen in `docs/plans/SCREEN_INTEL_P1_BUILD.md` §3; the dashboard pages and the desktop app are
built against the same shapes. Every body the DEVICE sends carries `schema_version` so a later
shape can be told apart from this one without guessing. Behaviour (what is allowed, what is
blocked) lives in `platform/devices.py` and `platform/capture_policy.py`; this module is only the
vocabulary, and imports nothing above platform.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

#: The one session-upload / heartbeat shape this server accepts.
SCHEMA_VERSION = 1

CLIENT_ID = "genios-desktop"
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
PLATFORMS = frozenset({"macos", "windows", "linux"})


# ── §3.1 device sign-in ──────────────────────────────────────────────────────────────────────
class DeviceCodeRequest(BaseModel):
    client_id: str = Field(max_length=64)
    device_name: str | None = Field(default=None, max_length=200)
    platform: str = Field(max_length=32)
    os_version: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=64)


class DeviceTokenRequest(BaseModel):
    grant_type: str = Field(max_length=200)
    device_code: str = Field(max_length=200)


class DeviceApproveRequest(BaseModel):
    user_code: str = Field(max_length=32)
    approve: bool


# ── §3.2 capture policy ──────────────────────────────────────────────────────────────────────
class CapturePolicyUpdate(BaseModel):
    """The ORG half. Every field optional: a PUT changes only what it names."""
    enabled: bool | None = None
    allowed_apps: list[str] | None = Field(default=None, max_length=32)
    blocked_domains: list[str] | None = Field(default=None, max_length=200)
    generic_web_allowed: bool | None = None
    draft_assist_allowed: bool | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class SeatCaptureUpdate(BaseModel):
    """The SEAT half — a person's own opt-in and their own additional blocks."""
    enabled: bool | None = None
    draft_assist: bool | None = None
    generic_web: bool | None = None
    blocked_apps: list[str] | None = Field(default=None, max_length=32)
    blocked_domains: list[str] | None = Field(default=None, max_length=200)


class CapturePause(BaseModel):
    """`minutes` from now, or an absolute `until`. `minutes: 0` (or `until` in the past) resumes."""
    minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 30)
    until: datetime | None = None


# ── §3.3 session upload (plan §18.2 + schema_version) ──────────────────────────────────────
class ScreenSession(BaseModel):
    """One hour-bucket session of one thread. Unknown fields are KEPT (sealed into the payload
    with the rest) so a newer app never loses data to an older server; the fields the server
    checks are named here.

    `url`, `bundle_id` and `private_window` are what the server-side privacy gate re-checks — the
    reader output (§3.6) carries the first two; a native app with no URL simply omits it."""
    model_config = ConfigDict(extra="allow")

    session_key: str = Field(min_length=1, max_length=300)
    thread_key: str | None = Field(default=None, max_length=300)
    app: str = Field(min_length=1, max_length=32)
    title: str | None = Field(default=None, max_length=500)
    participants: list[dict] = Field(default_factory=list, max_length=500)
    context_messages: list[dict] = Field(default_factory=list, max_length=2000)
    messages: list[dict] = Field(default_factory=list, max_length=2000)
    message_watermark: int = Field(ge=0)
    captured_at: datetime | None = None
    url: str | None = Field(default=None, max_length=4096)
    bundle_id: str | None = Field(default=None, max_length=255)
    private_window: bool = False


class SessionUpload(BaseModel):
    """The upload envelope. `sessions` is validated ONE BY ONE by the route (a malformed session
    is rejected on its own, it does not block the rest of the device's queue)."""
    schema_version: int = SCHEMA_VERSION
    device_id: str | None = Field(default=None, max_length=200)
    seat_id: str | None = Field(default=None, max_length=200)
    sessions: list[dict] = Field(max_length=500)


# ── §3.4 presence ──────────────────────────────────────────────────────────────────────────
class PresenceHeartbeat(BaseModel):
    schema_version: int = SCHEMA_VERSION
    app_version: str = Field(max_length=64)
    policy_version: str | None = Field(default=None, max_length=64)
    focus_app: str | None = Field(default=None, max_length=64)
    bundle_id: str | None = Field(default=None, max_length=255)
    dnd: bool = False
    idle: bool = False


__all__ = ["CLIENT_ID", "CapturePause", "CapturePolicyUpdate", "DEVICE_CODE_GRANT",
           "DeviceApproveRequest", "DeviceCodeRequest", "DeviceTokenRequest", "PLATFORMS",
           "PresenceHeartbeat", "SCHEMA_VERSION", "ScreenSession", "SeatCaptureUpdate",
           "SessionUpload"]
