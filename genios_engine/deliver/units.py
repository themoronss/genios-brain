"""Capability registry for the eleven Atlas delivery units.

An engine seam can be complete while a provider/client is not installed. The distinction is
explicit here so APIs and documentation never report an email or native push as sent merely
because the internal contract exists.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import text

from genios_engine.deliver.channels.base import supported_channels
from genios_engine.deliver.orchestrator import SURFACE_FOR_CONTEXT
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt


@dataclass(frozen=True, slots=True)
class DeliveryUnit:
    key: str
    engine_ready: bool
    available_channels: tuple[str, ...]
    integration_required: tuple[str, ...] = ()


def delivery_units() -> tuple[DeliveryUnit, ...]:
    channels = set(supported_channels())

    def present(*names: str) -> tuple[str, ...]:
        return tuple(name for name in names if name in channels)

    return (
        DeliveryUnit("human", True, present(
            "in_app", "dashboard", "extension", "application", "mobile",
            "slack", "teams", "webhook"),
                     ("browser/desktop/mobile clients",)),
        DeliveryUnit("agent", True, present("agent", "api"),
                     ("agent runtime registration",)),
        DeliveryUnit("api", True, present("api", "webhook"),
                     ("GraphQL/stream/MCP/SDK clients if selected",)),
        DeliveryUnit("application", True, present("application", "in_app"),
                     ("web/desktop/IDE/CLI clients",)),
        DeliveryUnit("notification", True, present("in_app"),
                     ("APNs/FCM/system notification provider",)),
        DeliveryUnit("dashboard", True, present("dashboard", "in_app"),
                     ("dashboard client rendering",)),
        DeliveryUnit("webhook", True, present("webhook"),
                     ("customer endpoint and secret",)),
        DeliveryUnit("extension", True, present("extension"),
                     ("browser/CRM/email extension",)),
        DeliveryUnit("mobile", True, present("mobile"),
                     ("mobile client and APNs/FCM",)),
        DeliveryUnit("email", True, present("email"),
                     ("verified SMTP/email provider, domain and feedback webhooks",)),
        DeliveryUnit("slack_teams", True, present("slack", "teams"),
                     ("tenant webhook/OAuth configuration",)),
    )


def _row_mapping(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    mapping = getattr(row, "_mapping", None)
    return dict(mapping) if mapping is not None else {}


def _object(value: Any) -> dict[str, Any]:
    """Decode one stored JSON object without ever returning its credential bytes."""
    if value is None:
        return {}
    decoded = dict(value) if isinstance(value, Mapping) else json.loads(value or "{}")
    if not isinstance(decoded, dict):
        raise ValueError("delivery credential config is not an object")
    return decoded


def _unseal(value: Any) -> dict[str, Any]:
    raw = bytes(value) if not isinstance(value, bytes) else value
    return _object(decrypt(raw, get_settings().crypto_key))


def _channel_config(row: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve credentials with the same precedence as the provider boundary."""
    routing = _object(row.get("config"))
    encrypted = row.get("config_encrypted")
    return ({**_unseal(encrypted), **routing} if encrypted else routing)


def configured_channel(row: Mapping[str, Any]) -> bool:
    """Fail closed unless the active row would pass its concrete adapter's validation."""
    try:
        channel = str(row.get("channel") or "")
        config = _channel_config(row)
        if channel == "slack":
            from genios_engine.deliver.channels.slack import valid_webhook_url
            return valid_webhook_url(config.get("webhook_url"))
        if channel == "teams":
            from genios_engine.deliver.channels.teams import valid_teams_webhook_url
            return valid_teams_webhook_url(config.get("webhook_url"))
        if channel == "webhook":
            from genios_engine.deliver.channels.webhook import valid_endpoint_url
            return (valid_endpoint_url(config.get("webhook_url"))
                    and len(str(config.get("webhook_secret") or "")) >= 16)
    except Exception:  # noqa: BLE001 - capability discovery must not leak credential failures
        return False
    return False


def configured_agent(row: Mapping[str, Any]) -> bool:
    """A push-capable agent needs the exact URL/secret/id tuple its adapter consumes."""
    try:
        config = dict(row)
        encrypted = config.pop("webhook_config_encrypted", None)
        if encrypted:
            config.update(_unseal(encrypted))
        from genios_engine.deliver.channels.webhook import valid_endpoint_url
        return (bool(str(config.get("agent_id") or ""))
                and valid_endpoint_url(config.get("webhook_url"))
                and len(str(config.get("webhook_secret") or "")) >= 16)
    except Exception:  # noqa: BLE001 - report unavailable, never ciphertext or decryption detail
        return False


def delivery_runtime(conn, org_id: str, *, now: datetime | None = None) \
        -> dict[str, tuple[str, ...]]:
    """Return channels that are genuinely usable for this tenant at this instant.

    Static adapter registration is only ``engine_ready``. Runtime operation additionally needs
    tenant credentials, an eligible agent, or a leased product-surface presence. The REST pull
    API is the sole always-live unit because this authenticated request itself proves that seam.
    """
    moment = now or datetime.now(timezone.utc)
    channel_rows = conn.execute(text(
        "select channel,config,config_encrypted from org_channels "
        "where org_id=:o and active"), {"o": org_id}).mappings().all()
    configured = {
        str(item.get("channel")) for raw in channel_rows
        for item in [_row_mapping(raw)] if configured_channel(item)}

    presence_rows = conn.execute(text(
        "select surface from delivery_presence where org_id=:o and expires_at>:now"),
        {"o": org_id, "now": moment}).mappings().all()
    live_surfaces = {
        SURFACE_FOR_CONTEXT.get(str(_row_mapping(row).get("surface") or "").lower())
        for row in presence_rows}
    live_surfaces.discard(None)

    agents = conn.execute(text(
        "select agent_id,webhook_url,webhook_secret,webhook_config_encrypted,"
        "exists (select 1 from api_keys k where k.org_id=agent_registry.org_id "
        "and k.agent_id=agent_registry.agent_id and k.is_active "
        "and 'delivery.read'=any(coalesce(k.scopes,array[]::text[]))) as api_enabled "
        "from agent_registry where org_id=:o and coalesce(status,'active')='active' "
        "and 'delivery.read'=any(coalesce(allowed_actions,array[]::text[]))"),
        {"o": org_id}).mappings().all()
    agent_rows = [_row_mapping(row) for row in agents]
    agent_channels = tuple(
        channel for channel, available in (
            ("agent", any(configured_agent(row) for row in agent_rows)),
            ("api", any(bool(row.get("api_enabled")) for row in agent_rows)),
        ) if available)

    chat = tuple(name for name in ("slack", "teams") if name in configured)
    human_surface = tuple(name for name in ("extension", "application", "mobile",
                                             "dashboard", "in_app")
                          if name in live_surfaces)
    return {
        "human": (*human_surface, *chat,
                  *(("webhook",) if "webhook" in configured else ())),
        "agent": agent_channels,
        "api": ("api",),
        "application": (("application",) if "application" in live_surfaces else ()),
        # In-app availability is not native APNs/FCM/system notification delivery.
        "notification": (),
        "dashboard": (("dashboard",) if "dashboard" in live_surfaces else ()),
        "webhook": (("webhook",) if "webhook" in configured else ()),
        "extension": (("extension",) if "extension" in live_surfaces else ()),
        "mobile": (("mobile",) if "mobile" in live_surfaces else ()),
        # No email adapter exists in the concrete registry yet, even if a row was pre-created.
        "email": (),
        "slack_teams": chat,
    }


__all__ = ["DeliveryUnit", "configured_agent", "configured_channel", "delivery_runtime",
           "delivery_units"]
