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
