"""Device API wire contracts — the desktop app ↔ brain boundary for screen capture (P1).

Frozen in `docs/plans/SCREEN_INTEL_P1_BUILD.md` §3; the dashboard pages and the desktop app are
built against the same shapes. Every body the DEVICE sends carries `schema_version` so a later
shape can be told apart from this one without guessing. Behaviour (what is allowed, what is
blocked) lives in `platform/devices.py` and `platform/capture_policy.py`; this module is only the
vocabulary, and imports nothing above platform.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # P3 (pinned 2026-09-13): "Show popups". Off = shadow mode — moments logged, not shown.
    moments_display: bool | None = None
    moments_max_per_hour: int | None = Field(default=None, ge=0, le=60)
    moments_max_per_day: int | None = Field(default=None, ge=0, le=500)


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
#: The generic reader's app id (§3.7) — any native app or site without a dedicated reader.
#: `web` is accepted as an alias (it was the name before D2 was revised).
GENERIC_APP = "generic"
GENERIC_ALIASES = frozenset({"generic", "web"})
MAX_BLOCKS = 500
MAX_TABLE_ROWS = 200
MAX_CONTEXT_BLOCKS = 10


class ScreenBlock(BaseModel):
    """One block of a generic `screen_doc` (§3.7): heading, kv, table, message, … Unknown fields
    are kept, like everything else in a session."""
    model_config = ConfigDict(extra="allow")

    fp: str | None = Field(default=None, max_length=128)
    role: str = Field(min_length=1, max_length=32)
    header: list | None = Field(default=None, max_length=100)
    rows: list[list] | None = Field(default=None, max_length=MAX_TABLE_ROWS)


class ScreenSession(BaseModel):
    """One hour-bucket session of one thread or screen. Unknown fields are KEPT (sealed into the
    payload with the rest) so a newer app never loses data to an older server; the fields the
    server checks are named here.

    A dedicated-reader session (gmail, linkedin, …) carries `messages[]`; a GENERIC session
    (`app:"generic"`, native or web) carries `blocks[]` instead — exactly one of the two is
    non-empty. `url`, `bundle_id` and `private_window` are what the server-side privacy gate
    re-checks; a native app has no URL, and a generic session must name its `bundle_id`."""
    model_config = ConfigDict(extra="allow")

    session_key: str = Field(min_length=1, max_length=300)
    thread_key: str | None = Field(default=None, max_length=300)
    app: str = Field(min_length=1, max_length=32)
    title: str | None = Field(default=None, max_length=500)
    participants: list[dict] = Field(default_factory=list, max_length=500)
    context_messages: list[dict] = Field(default_factory=list, max_length=2000)
    messages: list[dict] = Field(default_factory=list, max_length=2000)
    blocks: list[ScreenBlock] = Field(default_factory=list, max_length=MAX_BLOCKS)
    #: Generic only (§3.7): up to 10 UNCHANGED blocks around the new ones, same shape, so the
    #: server can read a changed block in place. Counted with `blocks` toward MAX_BLOCKS.
    context_blocks: list[ScreenBlock] = Field(default_factory=list,
                                              max_length=MAX_CONTEXT_BLOCKS)
    message_watermark: int = Field(ge=0)
    captured_at: datetime | None = None
    url: str | None = Field(default=None, max_length=4096)
    bundle_id: str | None = Field(default=None, max_length=255)
    private_window: bool = False

    @model_validator(mode="after")
    def _one_shape(self):
        app = self.app.strip().lower()
        self.app = GENERIC_APP if app in GENERIC_ALIASES else app
        if self.app == GENERIC_APP:
            if not (self.bundle_id or "").strip():
                raise ValueError("a generic session must name its bundle_id")
            if not self.blocks or self.messages:
                raise ValueError("a generic session carries blocks[] and no messages[]")
            if len(self.blocks) + len(self.context_blocks) > MAX_BLOCKS:
                raise ValueError(f"blocks + context_blocks exceed {MAX_BLOCKS}")
        elif not self.messages or self.blocks or self.context_blocks:
            raise ValueError("a dedicated-reader session carries messages[] and no blocks[]")
        return self


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
