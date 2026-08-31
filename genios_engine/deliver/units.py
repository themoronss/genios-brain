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
    #: Retained for callers that still read it, but NOT what capability is computed from.
    #: A credential requirement belongs to a CHANNEL, not to a unit: the `human` unit drives
    #: in_app, dashboard, slack and teams together and carried `needs_credential=False` for all
    #: four, so a tenant whose Slack secret had been rotated or corrupted was told the human unit
    #: was operational. See CHANNEL_NEEDS_CREDENTIAL.
    needs_credential: bool
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

#: Which CHANNELS require a working sealed credential. This is the real axis: a unit is a bundle
#: of transports with different requirements, and collapsing them to one flag per unit meant the
#: strictest channel in a bundle was governed by the loosest.
CHANNEL_NEEDS_CREDENTIAL: frozenset[str] = frozenset({
    "slack", "teams", "email", "webhook", "api", "agent_push",
})

#: Channels GeniOS has to PUSH on, and therefore needs a working adapter for.
#:
#: Pull surfaces are deliberately excluded. `in_app` and `dashboard` are read by a client that
#: fetches them; there is no adapter because there is nothing to send, and demanding one would
#: report the one delivery path that actually works today as broken.
#:
#: For the push half, `channels/base.get_channel` returns Slack or None — one implementation
#: across every push channel named here. Reporting the rest as "operational" the moment a row
#: exists in org_channels overstates the product on exactly the surfaces a pilot gets sold on.
PUSH_REQUIRES_ADAPTER: frozenset[str] = frozenset({
    "slack", "teams", "email", "webhook", "api", "agent_push",
})


def _implemented_channels() -> frozenset[str]:
    from genios_engine.deliver.channels.base import get_channel
    return frozenset(ch for ch in PUSH_REQUIRES_ADAPTER if get_channel(ch) is not None)


def capability_report(*, configured_channels: set[str],
                      credentialed_channels: set[str]) -> list[dict]:
    """The public capability view — fail-closed operational truth per unit.

    ``configured_channels``  : channels the tenant has set up (a row exists).
    ``credentialed_channels``: channels whose sealed credential decrypts + passes shape checks now.

    A unit is ``operational`` only if its engine is ready AND at least one of its channels is
    genuinely usable — configured, credentialed where that channel needs one, and backed by an
    adapter that exists. Each of those three was previously either missing or evaluated at the
    wrong granularity, and every one of the three errs the same way: toward claiming capability.
    """
    implemented = _implemented_channels()
    report: list[dict] = []
    for u in UNITS:
        available, blocked = [], {}
        for ch in u.channels:
            if ch not in configured_channels:
                blocked[ch] = "not_configured"
            elif ch in CHANNEL_NEEDS_CREDENTIAL and ch not in credentialed_channels:
                # Configured but the secret is absent, undecryptable or the wrong shape.
                blocked[ch] = "credential_unusable"
            elif ch in PUSH_REQUIRES_ADAPTER and ch not in implemented:
                blocked[ch] = "no_adapter"
            else:
                available.append(ch)
        operational = u.engine_ready and bool(available)
        report.append({
            "unit": u.key,
            "engine_ready": u.engine_ready,
            "operational": operational,
            "available_channels": available,
            # Per channel, so "why is this not operational" is answerable without a support
            # thread — and so "no_adapter" is visible as OUR gap rather than the tenant's.
            "blocked_channels": blocked,
            "integration_required": None if operational else u.integration_required,
        })
    return report


def get_unit(key: str) -> Unit | None:
    return _BY_KEY.get(key)


__all__ = ["UNITS", "Unit", "capability_report", "get_unit"]
