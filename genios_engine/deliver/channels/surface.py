"""Durable pull surfaces: app, dashboard, API, extension and mobile inboxes.

The payload is already committed to ``delivery_outbox`` before this adapter runs. Marking it
delivered means "available on the named authenticated surface", not "a device push occurred".
Clients read the same bytes through ``/delivery/inbox``; there is no second queue.
"""
from __future__ import annotations

from genios_engine.deliver.channels.base import ChannelResult


SURFACE_CHANNELS = frozenset({"in_app", "dashboard", "api", "application", "extension", "mobile"})


class SurfaceChannel:
    def __init__(self, name: str) -> None:
        if name not in SURFACE_CHANNELS:
            raise ValueError(f"unsupported pull surface {name!r}")
        self.name = name

    def send(self, payload: dict, config: dict) -> ChannelResult:
        del payload, config
        return ChannelResult(ok=True)


__all__ = ["SURFACE_CHANNELS", "SurfaceChannel"]
