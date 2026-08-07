"""Atlas Layer 5.2 additions: typed boundary, context, routing, surfaces and analytics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from genios_engine.contracts.delivery import DeliveryResultStatus
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver.analytics import summarize
from genios_engine.deliver.channels.base import get_channel, supported_channels
from genios_engine.deliver.channels.teams import format_teams_payload, valid_teams_webhook_url
from genios_engine.deliver.channels.webhook import valid_endpoint_url
from genios_engine.deliver.destination import RegisteredDestination, route_destinations
from genios_engine.deliver.gate import PgDeliveryContext, evaluate_delivery
from genios_engine.deliver.results import delivery_object_from_row, delivery_result_from_row


NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


def row(**changes):
    value = {
        "id": "ob_1", "org_id": "org_1", "card_id": "card_1", "channel": "slack",
        "payload": {"text": "Grounded"}, "status": "queued", "attempts": 0,
        "recipient": "seat_1", "band": "high", "channel_class": "chat",
        "interrupt": False, "defer_count": 0, "gate_unit": None, "gate_reason": None,
        "last_error": None, "created_at": NOW, "delivered_at": None,
    }
    value.update(changes)
    return value


def test_the_outbox_projects_to_both_typed_atlas_contracts():
    delivery = delivery_object_from_row(row())
    assert delivery.delivery_id == "ob_1"
    assert delivery.channel_class is ChannelClass.CHAT
    assert delivery.payload["text"] == "Grounded"
    assert delivery.retry_minutes == (5, 30, 120, 720)

    deferred = delivery_result_from_row(row(defer_count=2, gate_reason="quiet_hours"))
    assert deferred.status is DeliveryResultStatus.DEFERRED
    assert deferred.deferrals == 2 and deferred.reason_code == "quiet_hours"

    delivered = delivery_result_from_row(
        row(status="delivered", attempts=1, delivered_at=NOW + timedelta(seconds=2)))
    assert delivered.status is DeliveryResultStatus.DELIVERED
    assert delivered.metrics["delivery_latency_ms"] == 2_000


class _Rows:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _PresenceConn:
    def execute(self, statement, params=None):
        sql = str(statement)
        if "from delivery_preferences" in sql:
            return _Rows([{"seat_id": "*", "channel": "*", "quiet_enabled": False}])
        if "from org_channels" in sql or "from org_seats" in sql:
            return _Rows([{"one": 1}])
        if "from delivery_outbox" in sql:
            return _Rows([{"sent": 0, "oldest": None}])
        if "from delivery_presence" in sql:
            return _Rows([{
                "org_id": "org_1", "seat_id": "seat_1", "activity": "meeting",
                "surface": "calendar", "focus_mode": False, "busy_until": NOW + timedelta(hours=1),
                "observed_at": NOW - timedelta(minutes=1), "expires_at": NOW + timedelta(hours=2),
            }])
        raise AssertionError(sql)


def test_live_presence_turns_the_existing_timing_seam_into_a_real_context_resolver():
    from genios_engine.contracts.delivery import DeliveryCandidate, DeliveryVerdict

    candidate = DeliveryCandidate(
        org_id="org_1", subject_id="card_1", channel="slack",
        channel_class=ChannelClass.CHAT, band="high", interrupt=False, recipient="seat_1")
    context = PgDeliveryContext(_PresenceConn()).resolve(candidate, now=NOW)
    result = evaluate_delivery(candidate, context, now=NOW)
    assert context.state.current_activity == "meeting"
    assert context.state.current_surface == "calendar"
    assert result.verdict is DeliveryVerdict.DEFER
    assert result.reason_code == "recipient_busy"
    assert result.not_before == NOW + timedelta(hours=1)


def test_destination_router_is_deterministic_and_returns_a_fallback_ladder():
    destinations = [
        RegisteredDestination("webhook", {"priority": 80}),
        RegisteredDestination("teams", {"priority": 90}),
        RegisteredDestination("slack", {"priority": 100}),
        RegisteredDestination("in_app", {}),
    ]
    assert [item.channel for item in route_destinations(destinations, purpose="push")] == [
        "slack", "teams", "webhook", "in_app"]
    assert [item.channel for item in route_destinations(destinations, purpose="digest")] == [
        "slack", "teams"]


def test_adapter_registry_exposes_real_and_pull_surfaces_without_claiming_email():
    expected = {"slack", "teams", "webhook", "in_app", "dashboard", "api",
                "application", "extension", "mobile"}
    assert expected <= set(supported_channels())
    assert get_channel("dashboard").send({"text": "x"}, {}).ok is True
    assert get_channel("email") is None   # provider choice still required; never fake a send


def test_outbound_endpoint_validation_rejects_obvious_ssrf_targets():
    assert valid_endpoint_url("https://events.example.com/genios")
    for url in ("http://events.example.com", "https://localhost/hook",
                "https://127.0.0.1/hook", "https://10.0.0.1/hook"):
        assert valid_endpoint_url(url) is False
    assert valid_teams_webhook_url("https://x.webhook.office.com/a")
    assert valid_teams_webhook_url("https://x.logic.azure.com/workflows/a")
    assert valid_teams_webhook_url(
        "https://default.x.environment.api.powerplatform.com/powerautomate/a")
    assert not valid_teams_webhook_url("https://example.com/hook")
    assert not valid_teams_webhook_url("https://evilwebhook.office.com/a")
    message = format_teams_payload({"headline": "Risk", "situation": "Owner is blocked"})
    assert message["type"] == "message"
    assert message["attachments"][0]["content"]["body"][0]["text"] == (
        "Risk\nOwner is blocked")


def test_channel_listing_never_leaks_a_webhook_credential_path():
    from genios_engine.api.channel_routes import _mask

    masked = _mask("https://hooks.slack.com/services/tenant/secret/token")
    assert masked == "https://hooks.slack.com/…"
    assert "tenant" not in masked and "secret" not in masked


def test_delivery_analytics_counts_without_guessing_over_open_rows():
    report = summarize([
        row(status="delivered", attempts=1, delivered_at=NOW + timedelta(seconds=1)),
        row(id="ob_2", status="failed_terminal", attempts=5, channel="teams"),
        row(id="ob_3", status="queued", defer_count=2, gate_reason="burst_limit"),
        row(id="ob_4", status="suppressed", gate_reason="recipient_opted_out"),
    ], since=NOW - timedelta(days=1), until=NOW + timedelta(days=1))
    assert report["total"] == 4
    assert report["delivered_bp"] == 3_333
    assert report["transport_failure_bp"] == 5_000
    assert report["deferrals"] == 2 and report["burst_holds"] == 1
    assert report["latency_ms"] == {"p50": 1_000, "p95": 1_000}


def test_presence_schema_is_leased_tenant_scoped_and_erasable():
    sql = (Path(__file__).resolve().parents[1] /
           "migrations/0044_l52_atlas_delivery.sql").read_text().lower()
    assert "create table if not exists delivery_presence" in sql
    assert "expires_at > observed_at" in sql
    assert "references orgs (id) on delete cascade" in sql


def test_failover_never_routes_around_policy_or_authority():
    import inspect
    from genios_engine.deliver.outbox import enqueue_failover

    source = inspect.getsource(enqueue_failover)
    assert "failed.status='failed_terminal'" in source
    assert "AUTHORITATIVE_SIGNAL_PREDICATE" in source
    assert "suppressed" not in source and "cancelled" not in source
