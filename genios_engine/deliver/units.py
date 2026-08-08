"""Layer 5.2 · Phase 5 — the eleven delivery units and their capability registry (section 4).

``engine_ready`` is a static fact: the deterministic route, durable object, pull API, lifecycle
receipts and analytics exist for this unit. ``operational`` is fail-closed *runtime* truth — not
"a row exists" but "a usable credential/route is actually present right now." A unit with a complete
engine and no configured provider reports ``operational: false`` and names the ``integration_required``
— it never falsely claims it can reach a person.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Unit:
    key: str
    engine_ready: bool                 # the internal seam is implemented
    channels: tuple[str, ...]          # transports this unit can drive once configured
    needs_credential: bool             # operational only if a sealed credential is present
    integration_required: str          # the external work that makes it truly operational


#: The registry. Order is the spec's Table 4. ``engine_ready`` is true for every built seam; only
#: Email is contract-only (no provider chosen), so its engine is not yet ready.
UNITS: tuple[Unit, ...] = (
    Unit("human", True, ("in_app", "dashboard", "slack", "teams"), False,
         "browser/desktop/mobile clients for each human surface"),
    Unit("agent", True, ("agent_push", "api"), True,
         "register each runtime, endpoint and scopes; receiver verifies HMAC/idempotency"),
    Unit("api", True, ("api", "webhook"), True,
         "GraphQL/streaming/MCP/SDK only if the product chooses them"),
    Unit("application", True, ("application",), False,
         "web/desktop/IDE/CLI client rendering and receipts"),
    Unit("notification", True, ("in_app",), False,
         "APNs/FCM and OS notification provider/client wiring"),
    Unit("dashboard", True, ("dashboard",), False,
         "dashboard UI rendering, presence and receipt emission"),
    Unit("webhook", True, ("webhook",), True,
         "customer endpoint/secret, DNS/egress hardening and receiver contract"),
    Unit("extension", True, ("extension",), False,
         "browser/CRM/email-editor extension client"),
    Unit("mobile", True, ("mobile",), False,
         "mobile app plus APNs/FCM for native push"),
    Unit("email", False, ("email",), True,
         "select SMTP/API provider, verified domain, bounce/unsubscribe handling"),
    Unit("slack_teams", True, ("slack", "teams"), True,
         "tenant credentials; OAuth/bot for exact per-user DM/thread targeting"),
)

_BY_KEY = {u.key: u for u in UNITS}


def capability_report(*, configured_channels: set[str],
                      credentialed_channels: set[str]) -> list[dict]:
    """The public capability view — fail-closed operational truth per unit.

    ``configured_channels``  : channels the tenant has set up (a row exists).
    ``credentialed_channels``: channels whose sealed credential decrypts + passes shape checks now.
    A unit is ``operational`` only if its engine is ready AND at least one of its channels is
    available — and, when the unit needs a credential, that channel is credentialed, not merely
    configured. Missing/corrupt credentials never surface as operational.
    """
    report: list[dict] = []
    for u in UNITS:
        available = []
        for ch in u.channels:
            if ch not in configured_channels:
                continue
            if u.needs_credential and ch not in credentialed_channels:
                continue                       # configured but no usable secret → not available
            available.append(ch)
        operational = u.engine_ready and bool(available)
        report.append({
            "unit": u.key,
            "engine_ready": u.engine_ready,
            "operational": operational,
            "available_channels": available,
            "integration_required": None if operational else u.integration_required,
        })
    return report


def get_unit(key: str) -> Unit | None:
    return _BY_KEY.get(key)


__all__ = ["UNITS", "Unit", "capability_report", "get_unit"]
