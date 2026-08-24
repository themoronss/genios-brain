"""Layer 5.2 · Phase 5 — the 11-unit capability registry (pure, fail-closed)."""
from __future__ import annotations

from genios_engine.deliver.units import UNITS, capability_report, get_unit


def test_there_are_exactly_eleven_units():
    assert len(UNITS) == 11
    assert {u.key for u in UNITS} == {
        "human", "agent", "api", "application", "notification", "dashboard",
        "webhook", "extension", "mobile", "email", "slack_teams"}


def test_a_configured_but_uncredentialed_channel_is_not_operational():
    # slack_teams needs a credential: configured but no sealed secret => not operational
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"slack"}, credentialed_channels=set())}
    st = report["slack_teams"]
    assert st["engine_ready"] is True and st["operational"] is False
    assert st["available_channels"] == [] and st["integration_required"]


def test_a_credentialed_channel_becomes_operational():
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"slack"}, credentialed_channels={"slack"})}
    st = report["slack_teams"]
    assert st["operational"] is True and st["available_channels"] == ["slack"]
    assert st["integration_required"] is None


def test_a_credential_free_unit_is_operational_once_configured():
    # human surfaces (in_app/dashboard) need no credential
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"in_app"}, credentialed_channels=set())}
    assert report["human"]["operational"] is True and "in_app" in report["human"]["available_channels"]


def test_email_engine_is_not_ready_so_never_operational():
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"email"}, credentialed_channels={"email"})}
    assert report["email"]["engine_ready"] is False and report["email"]["operational"] is False


def test_nothing_configured_means_nothing_operational():
    for r in capability_report(configured_channels=set(), credentialed_channels=set()):
        assert r["operational"] is False


def test_get_unit_lookup():
    assert get_unit("webhook").needs_credential is True
    assert get_unit("nonexistent") is None


# ── capability truth was overstated in three independent ways ───────────────────
def test_a_broken_slack_secret_does_not_make_the_human_unit_operational():
    """`needs_credential` was a per-UNIT flag, and the `human` unit bundles in_app, dashboard,
    slack and teams under one `False`. A tenant whose Slack secret had been rotated or corrupted
    was told the human unit was operational — the loosest channel in the bundle governing the
    strictest."""
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"slack"}, credentialed_channels=set())}
    assert report["human"]["operational"] is False
    assert report["human"]["blocked_channels"]["slack"] == "credential_unusable"


def test_a_channel_with_no_adapter_is_not_operational_however_configured():
    """`get_channel` returns Slack or None. Teams has a row in the unit table, a channel name and
    no implementation, so "configured + credentialed" was enough to report it operational."""
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"teams"}, credentialed_channels={"teams"})}
    assert report["slack_teams"]["blocked_channels"]["teams"] == "no_adapter"


def test_a_pull_surface_needs_no_adapter():
    """in_app and dashboard are FETCHED by a client. There is no adapter because there is nothing
    to send, and requiring one would report the single delivery path that works today as broken."""
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"in_app"}, credentialed_channels=set())}
    assert report["human"]["operational"] is True
    assert "in_app" in report["human"]["available_channels"]


def test_every_blocked_channel_says_why():
    """"Why is this not operational" should be answerable from the payload, and `no_adapter`
    should be visible as OUR gap rather than the tenant's missing configuration."""
    report = {r["unit"]: r for r in capability_report(
        configured_channels={"slack"}, credentialed_channels={"slack"})}
    blocked = report["slack_teams"]["blocked_channels"]
    assert blocked["teams"] == "not_configured"
    assert "slack" not in blocked


def test_a_credential_that_does_not_decrypt_is_not_a_credential():
    """The API asked `secret_ciphertext is not null`. A rotated GENIOS_CRYPTO_KEY, a truncated
    copy and a hand-edited row all satisfy that and none of them can send anything."""
    from genios_engine.api.delivery_routes import _credential_usable

    assert _credential_usable("slack", None) is False
    assert _credential_usable("slack", "not-a-fernet-token") is False


def test_a_decryptable_secret_of_the_wrong_shape_is_still_rejected():
    from genios_engine.api.delivery_routes import _credential_shape_ok

    assert _credential_shape_ok("slack", "https://hooks.slack.com/services/T/B/x") is True
    assert _credential_shape_ok("slack", "xoxb-a-bot-token") is False   # right product, wrong seam
    assert _credential_shape_ok("slack", "") is False
