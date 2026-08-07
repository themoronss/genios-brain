"""Layer 5.2 Atlas control-plane ratchets.

These tests concentrate on the seams introduced by migration 0046. Existing delivery tests
continue to cover the legacy gate and adapter behavior; this file prevents the execution-only
boundary, deterministic routing, engagement lifecycle and Layer 6 handoff from drifting back.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.contracts.delivery import DeliveryObject
from genios_engine.contracts.execution import ChannelClass, ExecutionObject
from genios_engine.deliver.analytics import summarize
from genios_engine.deliver.audience import Seat, resolve_audience
from genios_engine.deliver.channels.slack import SlackWebhookChannel
from genios_engine.deliver.destination import RegisteredDestination
from genios_engine.deliver.orchestrator import format_kind_for, plan_delivery
from genios_engine.deliver.outbox import retry_delay
from genios_engine.deliver.results import delivery_object_from_row, load_inbox
from genios_engine.deliver.scheduler import PriorityClass, effective_rank, priority_class
from genios_engine.deliver.tracker import (
    DeliveryState,
    DeliveryTransitionError,
    append_event,
    can_transition,
)
from genios_engine.deliver.units import delivery_units
from genios_engine.feedback.units import DeliveryFact, LearningBatch, performance_optimization
from tests.test_executive_execution import build


NOW = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


def _execution():
    return build().require()


def _seats() -> tuple[Seat, ...]:
    return (
        Seat("seat_rep", role="member", manager_seat_id="seat_mgr_new"),
        Seat("seat_mgr_new", role="admin"),
        Seat("seat_mgr_old", role="admin"),
    )


def test_source_visibility_is_enforced_before_recipient_and_route_selection():
    private = replace(
        _execution(),
        visibility={"scope": "private", "principals": ["rep@example.com"],
                    "derived_from": "gmail:participants"})
    seats = (
        Seat("seat_rep", role="member", manager_seat_id="seat_admin",
             email="rep@example.com"),
        Seat("seat_admin", role="admin", email="admin@example.com"),
    )
    plan = plan_delivery(
        private, seats=seats,
        destinations=(RegisteredDestination("slack", {"priority": 1_000}),),
        execution_owner="seat_rep")
    assert plan.recipient == "seat_rep"
    assert plan.channel == "in_app"
    assert not ({"slack", "teams", "webhook"} & set(plan.route_plan))

    with pytest.raises(ValueError, match="visibility-authorized"):
        plan_delivery(
            private,
            seats=(Seat("seat_admin", role="admin", email="admin@example.com"),),
            destinations=(RegisteredDestination("slack", {}),),
            execution_owner="missing_owner")
    with pytest.raises(ValueError, match="verified agent principal"):
        plan_delivery(
            private, seats=seats, destinations=(RegisteredDestination("api", {}),),
            requested_audience="agent", agent_recipient="agent_sales")


def test_execution_v1_round_trip_stays_hash_compatible_while_v2_carries_visibility():
    current = replace(
        _execution(), visibility={"scope": "participants",
                                  "principals": ["rep@example.com"],
                                  "derived_from": "gmail:participants"})
    restored = ExecutionObject.from_semantic_dict(current.to_semantic_dict())
    assert dict(restored.visibility)["scope"] == "participants"
    assert restored.semantic_hash == current.semantic_hash

    legacy = replace(_execution(), version="execution.v1")
    payload = legacy.to_semantic_dict()
    assert "visibility" not in payload
    assert ExecutionObject.from_semantic_dict(payload).semantic_hash == legacy.semantic_hash


def test_v1_delivery_rederives_visibility_or_fails_closed_without_changing_identity():
    from genios_engine.deliver.orchestrator import _with_inherited_visibility

    legacy = replace(_execution(), version="execution.v1")

    class MissingContext:
        def execute(self, statement, params=None):
            assert "from reasoning_context_snapshots" in str(statement)
            return _SqlRows([])

    protected = _with_inherited_visibility(MissingContext(), legacy)
    assert dict(protected.visibility)["scope"] == "private"
    assert dict(protected.visibility)["principals"] == ()
    assert protected.execution_id == legacy.execution_id
    assert protected.semantic_hash == legacy.semantic_hash


def test_human_and_agent_routes_are_strictly_isolated():
    destinations = (
        RegisteredDestination("agent", {"priority": 1_000}),
        RegisteredDestination("slack", {"priority": 100}),
        RegisteredDestination("api", {"priority": 90}),
    )
    human = plan_delivery(_execution(), seats=_seats(), destinations=destinations,
                          execution_owner="seat_rep")
    assert human.channel == "slack"
    assert "agent" not in human.route_plan

    agent = plan_delivery(_execution(), seats=_seats(), destinations=destinations,
                          requested_audience="agent", agent_recipient="agent_sales")
    assert agent.recipient == "agent_sales"
    assert agent.channel == "agent"
    assert set(agent.route_plan) <= {"agent", "api"}
    assert not ({"in_app", "dashboard", "slack"} & set(agent.route_plan))


def test_poll_only_agent_uses_api_and_an_unroutable_agent_fails_closed():
    poll = plan_delivery(
        _execution(), seats=_seats(), destinations=(RegisteredDestination("api", {}),),
        requested_audience="agent", agent_recipient="agent_sales")
    assert poll.channel == "api" and poll.route_plan == ("api",)
    with pytest.raises(ValueError, match="no active recipient or delivery route"):
        plan_delivery(_execution(), seats=_seats(), destinations=(),
                      requested_audience="agent", agent_recipient="agent_sales")


def test_agent_delivery_requires_the_exact_delivery_scope_and_poll_credential():
    from genios_engine.deliver import gate, orchestrator, units

    selection = inspect.getsource(orchestrator._agent_recipient)
    routes = inspect.getsource(orchestrator._destinations_for_agent)
    admission = inspect.getsource(gate.PgDeliveryContext._read_settings)
    runtime = inspect.getsource(units.delivery_runtime)
    for source in (selection, routes, admission, runtime):
        assert "delivery.read" in source
    assert "signals.read','read_context','delivery.read" not in selection
    assert "from api_keys" in routes and "is_active" in routes
    assert "from api_keys" in admission and "is_active" in admission


def test_manager_resolution_uses_the_current_directory_not_a_frozen_target():
    result = resolve_audience(
        execution_owner="seat_rep", requested_audience="manager", seats=_seats(),
        event_detail={"target_audience": "manager", "target_seat": "seat_mgr_old"})
    assert result.recipient == "seat_mgr_new"
    assert result.reason_code == "current_owner_manager"


def test_active_ex_manager_is_not_authority_when_reporting_line_was_removed():
    seats = (
        Seat("seat_rep", role="member", manager_seat_id=None),
        Seat("seat_ex_manager", role="member"),
        Seat("seat_admin", role="admin"),
    )
    result = resolve_audience(
        execution_owner="seat_rep", requested_audience="manager", seats=seats,
        event_detail={"target_audience": "manager", "target_seat": "seat_ex_manager"})
    assert result.recipient == "seat_admin"
    assert result.audience == "admin_queue"
    assert result.reason_code == "active_admin_fallback"


def test_unresolved_admin_queue_never_leaks_to_a_shared_push_channel():
    plan = plan_delivery(
        _execution(), seats=(),
        destinations=(RegisteredDestination("slack", {"priority": 1_000}),),
        execution_owner=None)
    assert plan.audience == "admin_queue" and plan.recipient is None
    assert plan.route_plan == ("dashboard", "in_app")
    assert plan.channel == "dashboard"


def test_agent_instruction_preserves_the_complete_execution_contract_exactly():
    from genios_engine.deliver.orchestrator import _source_for_delivery

    original = _execution()
    actions = tuple(
        replace(item, metadata={"policy": {"mode": "strict", "ordinal": item.ordinal}})
        for item in original.actions)
    execution = replace(
        original, actions=actions,
        metadata={"subject_type": "deal", "nested": {"labels": ["safe", "grounded"]}})
    source = _source_for_delivery(
        execution, "card_1", kind="execution_reminder", audience="agent",
        event_id="exev_1", reason_code="escalation_remind",
        detail={"target_audience": "agent"})

    transported = json.loads(json.dumps(source))
    rebuilt = ExecutionObject.from_semantic_dict(transported["execution"])
    assert transported["schema_version"] == "genios.agent-delivery.v1"
    assert rebuilt.semantic_hash == execution.semantic_hash
    assert len(rebuilt.actions) == len(execution.actions)
    assert dict(rebuilt.actions[0].metadata)["policy"]["mode"] == "strict"
    assert dict(rebuilt.metadata)["nested"]["labels"] == \
        dict(execution.metadata)["nested"]["labels"]
    assert transported["safety"]["autonomy_allowed"] is execution.autonomy_allowed
    assert transported["safety"]["approval_action_ids"] == [
        item.action_id for item in execution.approval_gates]


class _SqlRows:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _LegacyAdoptionConnection:
    def __init__(self, channel: str, *, reconciliation_required: bool = False):
        self.channel = channel
        self.reconciliation_required = reconciliation_required
        self.adopted = None
        self.event = None

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        values = dict(params or {})
        if "delivery_kind='legacy_card'" in sql and sql.startswith("select id"):
            return _SqlRows([{
                "id": "ob_legacy", "channel": self.channel, "status": "queued",
                "attempts": 0, "claim_token": None, "next_attempt_at": NOW,
                "legacy_reconciliation_required": self.reconciliation_required,
            }])
        if sql.startswith("update delivery_outbox set channel="):
            self.adopted = values
            return _SqlRows([{"id": "ob_legacy"}])
        if sql.startswith("insert into delivery_events"):
            self.event = values
            return _SqlRows([{"event_id": values["e"]}])
        raise AssertionError(sql)


def test_post_cutover_unattempted_legacy_row_is_adopted_without_loss_or_duplicate():
    from genios_engine.deliver.orchestrator import _insert, _source_for_delivery

    execution = _execution()
    plan = plan_delivery(
        execution, seats=_seats(),
        destinations=(RegisteredDestination("slack", {"priority": 100}),),
        execution_owner="seat_rep")
    conn = _LegacyAdoptionConnection(plan.channel)
    inserted = _insert(
        conn, row={"signal_id": "sig_1", "delivery_effective_config": {}},
        execution=execution, event_id="exev_1", kind="execution_reminder",
        source=_source_for_delivery(
            execution, "card_1", kind="execution_reminder", audience=plan.audience,
            event_id="exev_1", reason_code="escalation_remind", detail={}),
        plan=plan, base_url="https://app.example", now=NOW)

    assert inserted == 1
    assert conn.adopted["i"] == "ob_legacy"
    assert conn.event["d"] == "ob_legacy"
    assert conn.adopted["dedupe"] == f"execution:{execution.execution_id}:event:exev_1"
    assert conn.adopted["kind"] == "execution_reminder"


def test_pre_cutover_ambiguous_legacy_row_cannot_be_adopted_automatically():
    from genios_engine.deliver.orchestrator import _insert, _source_for_delivery

    execution = _execution()
    plan = plan_delivery(
        execution, seats=_seats(),
        destinations=(RegisteredDestination("slack", {"priority": 100}),),
        execution_owner="seat_rep")
    conn = _LegacyAdoptionConnection(plan.channel, reconciliation_required=True)
    inserted = _insert(
        conn, row={"signal_id": "sig_1", "delivery_effective_config": {}},
        execution=execution, event_id=None, kind="execution_initial",
        source=_source_for_delivery(
            execution, "card_1", kind="execution_initial", audience=plan.audience),
        plan=plan, base_url="https://app.example", now=NOW)
    assert inserted == 0
    assert conn.adopted is None


def test_execution_authority_is_open_and_locked_through_transport():
    from genios_engine.executive.execution_store import authority_valid

    class Capture:
        sql = ""

        def execute(self, statement, params=None):
            self.sql = " ".join(str(statement).split())
            return _SqlRows([{"one": 1}])

    conn = Capture()
    assert authority_valid(
        conn, "org_1", "sig_1", now=NOW, lock=True) is True
    assert "s.status='open'" in conn.sql
    assert "for share of s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,authority_pack" \
        in conn.sql


def test_selected_reasoning_evidence_inherits_the_narrowest_source_acl():
    from genios_engine.executive.sweep import _execution_visibility

    class EvidenceConnection:
        def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            if "from graph_source_refs ref" in sql:
                return _SqlRows([{
                    "source_ref_id": "src_private", "fact_version_id": "fact_1",
                    "visibility": {"scope": "private", "principals": ["rep@example.com"],
                                   "derived_from": "gmail:participants"},
                }])
            if "from signals s join reasoning_runs parent_run" in sql:
                return _SqlRows([])
            raise AssertionError(sql)

    inherited = _execution_visibility(
        EvidenceConnection(), org_id="org_1",
        source_manifest=[{"evidence_id": "ev_1", "source_ref_id": "src_private",
                          "fact_version_id": "fact_1"}],
        evidence_ids=("ev_1",))
    assert inherited.scope == "private"
    assert inherited.can_view("rep@example.com") is True
    assert inherited.can_view("admin@example.com") is False


def test_materializer_rejects_known_stale_intent_before_it_reaches_the_outbox():
    from genios_engine.deliver import orchestrator

    source = inspect.getsource(orchestrator.enqueue_execution_deliveries)
    assert "select id from orgs where id=:o for share" in source
    assert "pg_advisory_xact_lock" in source
    assert "superseding.occurred_at>=e.occurred_at" in source
    assert "superseding.event_id>e.event_id" in source
    assert "'execution.action_completed','execution.reminded'" in source


def test_ambiguous_shared_chat_is_manual_but_idempotent_webhook_can_retry():
    from genios_engine.deliver import outbox
    from genios_engine.deliver.channels.base import ChannelResult

    unknown = ChannelResult(ok=False, retryable=True, unknown=True, detail="timeout")
    definite = ChannelResult(ok=False, retryable=True, unknown=False, detail="503")
    assert outbox._ambiguous_requires_manual("slack", unknown) is True
    assert outbox._ambiguous_requires_manual("teams", unknown) is True
    assert outbox._ambiguous_requires_manual("webhook", unknown) is False
    assert outbox._ambiguous_requires_manual("slack", definite) is False


def test_preflight_terminal_lifecycle_keys_are_unique_across_owner_replays():
    from genios_engine.deliver.outbox import _attempt_event_identity

    first = _attempt_event_identity({"retry_generation": 0, "claim_token": "claim_1"})
    replayed = _attempt_event_identity({"retry_generation": 1, "claim_token": "claim_2"})
    assert first != replayed
    assert _attempt_event_identity({"attempt_id": "dat_1", "claim_token": "claim_1"}) == \
        "dat_1"


def test_legacy_terminal_replay_requires_ack_and_clears_marker_once(monkeypatch):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from genios_engine.api import delivery_routes
    from genios_engine.deliver import tracker
    from genios_engine.platform.auth import AuthCtx

    class ReplayConnection:
        def __init__(self):
            self.status = "failed_terminal"
            self.flag = True
            self.update_sql = ""
            self.update_params = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            if sql.startswith("select status,channel,delivery_kind"):
                return _SqlRows([{
                    "status": self.status, "channel": "slack",
                    "delivery_kind": "legacy_card",
                    "legacy_reconciliation_required": self.flag,
                }])
            if sql.startswith("select outcome,attempt_number from delivery_attempts"):
                return _SqlRows([])
            if sql.startswith("update delivery_outbox set status='queued'"):
                self.update_sql = sql
                self.update_params = dict(params or {})
                self.status = "queued"
                self.flag = False
                return _SqlRows([{"id": "ob_legacy"}])
            raise AssertionError(sql)

    conn = ReplayConnection()
    monkeypatch.setattr(delivery_routes, "_graph",
                        SimpleNamespace(engine=SimpleNamespace(begin=lambda: conn)))
    events = []
    monkeypatch.setattr(tracker, "append_event", lambda *_args, **kwargs: events.append(kwargs))
    ctx = AuthCtx(org_id="org_1", actor_id="owner", scopes=None)

    with pytest.raises(HTTPException) as missing_ack:
        delivery_routes.replay_delivery("org_1", "ob_legacy", None, ctx=ctx)
    assert missing_ack.value.status_code == 409
    assert not events

    result = delivery_routes.replay_delivery(
        "org_1", "ob_legacy",
        delivery_routes.DeliveryReplayRequest(
            acknowledge_ambiguous_delivery_risk=True),
        ctx=ctx)
    assert result["ambiguous_risk_acknowledged"] is True
    assert conn.update_params["legacy"] is True and conn.update_params["bump"] == 1
    assert "legacy_reconciliation_required=false" in conn.update_sql
    assert "manual_replay_approved_at=case when :legacy then :now" in conn.update_sql

    with pytest.raises(HTTPException) as duplicate:
        delivery_routes.replay_delivery(
            "org_1", "ob_legacy",
            delivery_routes.DeliveryReplayRequest(
                acknowledge_ambiguous_delivery_risk=True),
            ctx=ctx)
    assert duplicate.value.status_code == 409


def test_raw_signal_agent_execution_plane_is_retired_in_favour_of_delivery_inbox():
    from genios_engine.api import routes

    for handler in (routes.agent_poll, routes.agent_artifact,
                    routes.agent_claim, routes.agent_result):
        assert "_retired_agent_signal_api" in inspect.getsource(handler)
    assert "/api/org/{org_id}/delivery/inbox?channel=api" in \
        inspect.getsource(routes._retired_agent_signal_api)


def test_layer_5_concrete_channel_and_interrupt_hints_cannot_bypass_layer_52():
    execution = _execution()
    legacy_route_changed = replace(
        execution,
        communication=replace(execution.communication, channel_id="email",
                              channel_class=ChannelClass.EMAIL, interrupt=False,
                              format_kind="email_draft"),
    )
    destinations = (RegisteredDestination("slack", {}),)
    original = plan_delivery(execution, seats=_seats(), destinations=destinations,
                             execution_owner="seat_rep")
    changed = plan_delivery(legacy_route_changed, seats=_seats(), destinations=destinations,
                            execution_owner="seat_rep")
    assert changed == original
    assert changed.channel == "slack"


def test_current_surface_and_busy_state_drive_format_and_interruptibility():
    inline = plan_delivery(
        _execution(), seats=_seats(), destinations=(RegisteredDestination("slack", {}),),
        execution_owner="seat_rep", presence={"surface": "gmail", "activity": "writing"})
    assert inline.channel == "extension"
    assert inline.format_kind == "inline_suggestion"
    assert inline.interrupt is False

    busy = plan_delivery(
        _execution(), seats=_seats(), destinations=(RegisteredDestination("slack", {}),),
        execution_owner="seat_rep", presence={"activity": "meeting"})
    assert busy.channel == "slack"
    assert busy.interrupt is False


@pytest.mark.parametrize(("score", "expected"), [
    (0, PriorityClass.BACKGROUND), (1_999, PriorityClass.BACKGROUND),
    (2_000, PriorityClass.LOW), (3_999, PriorityClass.LOW),
    (4_000, PriorityClass.MEDIUM), (6_999, PriorityClass.MEDIUM),
    (7_000, PriorityClass.HIGH), (8_499, PriorityClass.HIGH),
    (8_500, PriorityClass.CRITICAL), (10_000, PriorityClass.CRITICAL),
])
def test_all_five_atlas_priority_classes_have_closed_boundaries(score, expected):
    assert priority_class(score) is expected


def test_priority_aging_prevents_background_starvation_without_time_travel():
    assert effective_rank("background", created_at=NOW, now=NOW - timedelta(hours=1)) == 1
    assert effective_rank("background", created_at=NOW, now=NOW + timedelta(hours=16)) == 5
    assert effective_rank("critical", created_at=NOW, now=NOW + timedelta(days=7)) == 5


def test_retry_after_cannot_shorten_or_unbound_the_bounded_retry_schedule():
    assert retry_delay(1) == 5
    assert retry_delay(2, 60) == 30       # provider cannot weaken the local rung
    assert retry_delay(2, 3_600) == 60    # a larger provider minimum is honoured
    assert retry_delay(2, 86_400 * 30) == 720
    assert retry_delay(5, 60) is None     # exhausted schedule cannot be resurrected


def test_capability_registry_names_all_eleven_atlas_units_truthfully():
    units = {item.key: item for item in delivery_units()}
    assert tuple(units) == (
        "human", "agent", "api", "application", "notification", "dashboard",
        "webhook", "extension", "mobile", "email", "slack_teams")
    assert len(units) == 11
    assert units["email"].engine_ready is True
    assert units["email"].available_channels == ()
    assert "verified SMTP/email provider, domain and feedback webhooks" in \
        units["email"].integration_required
    assert {"agent", "api"} <= set(units["agent"].available_channels)


def test_materialization_and_capability_discovery_share_credential_truth():
    from genios_engine.deliver import orchestrator, outbox, units

    distribution = inspect.getsource(outbox.run_distribution)
    agent_routes = inspect.getsource(orchestrator._destinations_for_agent)
    assert "configured_channel" in distribution
    assert "config_encrypted" in distribution
    assert "configured_agent" in agent_routes
    final_plan = inspect.getsource(orchestrator.current_delivery_plan)
    assert "config_encrypted" in final_plan
    assert "configured_channel" in final_plan
    assert "configured_channel" in units.__all__
    assert "configured_agent" in units.__all__


def test_delivery_lifecycle_accepts_only_the_atlas_paths():
    assert can_transition(DeliveryState.QUEUED, DeliveryState.DEFERRED)
    assert can_transition(DeliveryState.DEFERRED, DeliveryState.QUEUED)
    assert can_transition(DeliveryState.DELIVERED, DeliveryState.VIEWED)
    assert can_transition(DeliveryState.VIEWED, DeliveryState.ACCEPTED)
    assert can_transition(DeliveryState.ACCEPTED, DeliveryState.EXECUTED)
    assert can_transition(DeliveryState.ACCEPTED, DeliveryState.FAILED)
    assert not can_transition(DeliveryState.ACCEPTED, DeliveryState.IGNORED)
    assert not can_transition(DeliveryState.EXPIRED, DeliveryState.DELIVERED)
    assert not can_transition(DeliveryState.EXECUTED, DeliveryState.QUEUED)


class _OneMapping:
    def __init__(self, value):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value


class _ReceiptConnection:
    def __init__(self, *, duplicate: bool):
        self.duplicate = duplicate

    def execute(self, statement, params=None):
        sql = str(statement)
        if "from delivery_outbox" in sql:
            return _OneMapping({
                "lifecycle_status": "accepted", "created_at": NOW,
                "delivered_at": NOW + timedelta(minutes=1),
                "viewed_at": NOW + timedelta(minutes=2), "ignored_at": None,
                "accepted_at": NOW + timedelta(minutes=3), "executed_at": None,
                "expired_at": None,
            })
        if "from delivery_events" in sql:
            return _OneMapping(
                {"event_id": "dev_seen", "event_type": "viewed"}
                if self.duplicate else None)
        raise AssertionError(f"unexpected SQL after chronology check: {sql}")


def test_delayed_duplicate_receipt_is_a_noop_after_lifecycle_has_advanced():
    result = append_event(
        _ReceiptConnection(duplicate=True), org_id="org_1", delivery_id="ob_1",
        target=DeliveryState.VIEWED, reason_code="client_viewed", actor_id="seat_rep",
        idempotency_key="receipt_seen", occurred_at=NOW + timedelta(minutes=2))
    assert result == {
        "changed": False, "duplicate": True, "state": "accepted",
        "event_id": "dev_seen", "event_type": "viewed"}


def test_new_out_of_order_receipt_is_rejected_after_lifecycle_has_advanced():
    with pytest.raises(DeliveryTransitionError, match="precedes the delivery lifecycle"):
        append_event(
            _ReceiptConnection(duplicate=False), org_id="org_1", delivery_id="ob_1",
            target=DeliveryState.VIEWED, reason_code="client_viewed", actor_id="seat_rep",
            idempotency_key="new_late_receipt", occurred_at=NOW + timedelta(minutes=2))


def test_engagement_survives_a_later_expiry_in_analytics_and_layer_6():
    row = {
        "id": "ob_1", "channel": "slack", "status": "delivered",
        "lifecycle_status": "expired", "recipient": "seat_rep", "attempts": 1,
        "defer_count": 0, "created_at": NOW, "delivered_at": NOW + timedelta(seconds=1),
        "viewed_at": NOW + timedelta(seconds=2), "ignored_at": None,
        "accepted_at": NOW + timedelta(seconds=3), "executed_at": None,
    }
    report = summarize([row], since=NOW, until=NOW + timedelta(days=1))
    assert report["engagement"]["view_or_action_bp"] == 10_000
    assert report["engagement"]["accept_bp"] == 10_000
    assert report["fatigue"]["by_recipient"]["seat_rep"]["deliveries"] == 1

    fact = DeliveryFact(
        "ob_1", "slack", "delivered", NOW, NOW + timedelta(seconds=1), attempts=1,
        lifecycle_status="expired", viewed_at=NOW + timedelta(seconds=2),
        accepted_at=NOW + timedelta(seconds=3))
    learned = performance_optimization(
        LearningBatch("org_1", NOW + timedelta(days=1), deliveries=(fact,)))[0]
    assert learned.value["viewed"] == 1
    assert learned.value["accepted"] == 1


def test_delivery_object_projects_the_snapshotted_daily_attention_budget():
    row = {
        "id": "ob_1", "org_id": "org_1", "card_id": "exec:one:initial",
        "channel": "slack", "channel_class": "chat", "band": "high", "interrupt": True,
        "payload": {}, "recipient": "seat_rep", "priority_class": "critical",
        "priority_rank": 5, "daily_budget": 11, "route_plan": ["slack", "in_app"],
    }
    projected = delivery_object_from_row(row)
    assert projected.daily_budget == 11
    assert projected.to_semantic_dict()["daily_budget"] == 11
    with pytest.raises(ValueError, match="daily_budget"):
        replace(projected, daily_budget=0)


class _Response:
    def __init__(self, status: int, *, retry_after: str | None = None):
        self.status_code = status
        self.text = "provider response"
        self.headers = {} if retry_after is None else {"retry-after": retry_after}


@pytest.mark.parametrize(("status", "retryable", "unknown"), [
    (400, False, False), (429, True, False), (500, True, True),
])
def test_slack_provider_outcomes_distinguish_terminal_rate_limit_and_ambiguity(
        monkeypatch, status, retryable, unknown):
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _Response(
        status, retry_after="120" if status == 429 else None))
    result = SlackWebhookChannel().send(
        {"text": "grounded"}, {"webhook_url": "https://hooks.slack.com/services/test"})
    assert result.ok is False
    assert result.retryable is retryable
    assert result.unknown is unknown
    assert result.retry_after_seconds == (120 if status == 429 else None)


class _EmptyRows:
    def mappings(self):
        return self

    def all(self):
        return []


class _CaptureConnection:
    def __init__(self):
        self.sql = ""

    def execute(self, statement, params=None):
        self.sql = str(statement)
        return _EmptyRows()


def test_scoped_pull_inbox_does_not_expose_org_wide_rows():
    scoped = _CaptureConnection()
    load_inbox(scoped, "org_1", channel="api", recipient="agent_sales",
               include_org_wide=False)
    assert "and recipient=:r" in scoped.sql
    assert "recipient is null" not in scoped.sql

    owner = _CaptureConnection()
    load_inbox(owner, "org_1", channel="in_app", recipient="seat_rep",
               include_org_wide=True)
    assert "recipient=:r or recipient is null" in owner.sql


def test_migration_0046_is_tenant_scoped_fenced_and_append_only():
    sql = (Path(__file__).resolve().parents[1] /
           "migrations/0046_l52_delivery_control_plane.sql").read_text().lower()
    for table in ("delivery_events", "delivery_attempts", "delivery_rate_windows",
                  "delivery_materialization_failures"):
        assert f"create table if not exists {table}" in sql
    assert "delivery_outbox_logical_once" in sql
    assert "delivery_outbox_execution_lineage_required" in sql
    assert "delivery_outbox_claim_shape_valid" in sql
    assert "foreign key (org_id, delivery_id) references delivery_outbox (org_id, id)" in sql
    assert "foreign key (org_id, execution_id) references executions (org_id, execution_id)" in sql
    assert "priority_class in ('critical','high','medium','low','background')" in sql
    assert "daily_budget between 1 and 15" in sql
    assert "delivery_outbox_destination_fingerprint_valid" in sql
    assert "destination_fingerprint text not null" in sql
    assert "retry_generation    int not null" in sql
    assert "lock table delivery_outbox in share row exclusive mode" in sql
    assert "legacy_reconciliation_required" in sql
    assert "manual_replay_approved_at" in sql
    assert "status = 'failed_terminal'" in sql
    assert "delivered_at>now()-interval '1 hour'" in sql
    assert "pg_timezone_names" in sql
    assert "recipient,'daily',window_start" in sql


def test_only_execution_materialization_is_active_in_the_distribution_sweep():
    from genios_engine.deliver import outbox, pipeline

    active = inspect.getsource(outbox.run_distribution)
    assert "enqueue_execution_deliveries" in active
    for legacy in ("enqueue_pending(", "enqueue_failover(", "enqueue_digest("):
        assert legacy not in active
    assert "push_card_to_agents(" not in inspect.getsource(pipeline)
    source = inspect.getsource(outbox._start_attempt_in_conn)
    key_expression = source.split("key =", 1)[1].split("\n", 1)[0]
    assert "retry_generation" in key_expression
    assert "number" not in key_expression and "attempt_number" not in key_expression
    retry = inspect.getsource(outbox._drain_claimed)
    assert "retry_delay(cycle_attempt" in retry
    attempt = inspect.getsource(outbox._start_attempt_in_conn)
    assert "claimed_until>now()" in attempt
    assert "destination_fingerprint" in attempt and "retry_generation" in attempt
    reservation = inspect.getsource(outbox._reserve_for_send)
    assert "_start_attempt_in_conn(conn, row, now)" in reservation
    assert "daily_recipient = candidate.recipient" in reservation
    assert "hourly_recipient" in reservation
    drain_source = inspect.getsource(outbox._drain_claimed)
    assert "_bind_destination(engine, r, current_cfg)" in drain_source
    assert "clock() if clock is not None else now" in drain_source
    distribution = inspect.getsource(outbox.run_distribution)
    assert "kill_switch_all" in distribution and "paused" in distribution


class _BindingRow:
    def __init__(self, **values):
        self.__dict__.update(values)

    def __getitem__(self, index):
        return tuple(self.__dict__.values())[index]


class _BindingResult:
    def __init__(self, row=None):
        self.row = row

    def first(self):
        return self.row


class _BindingConn:
    def __init__(self, *, prior, attempts, generation, unsafe):
        self.prior = prior
        self.attempts = attempts
        self.generation = generation
        self.unsafe = unsafe
        self.updated = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        if "select destination_fingerprint" in sql:
            return _BindingResult(_BindingRow(
                destination_fingerprint=self.prior,
                generation_attempts=self.attempts,
                retry_generation=self.generation))
        if "from delivery_attempts" in sql:
            return _BindingResult(_BindingRow(one=1) if self.unsafe else None)
        if "set destination_fingerprint" in sql:
            self.updated = True
            return _BindingResult(_BindingRow(
                retry_generation=self.generation + int((params or {})["bump"])))
        raise AssertionError(sql)


class _BindingEngine:
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        return self.conn


def test_endpoint_rotation_after_ambiguous_ack_is_never_auto_retried():
    from genios_engine.deliver import outbox

    row = {"id": "ob_1", "org_id": "org_1", "channel": "webhook",
           "recipient": "seat_1", "claim_token": "claim_1"}
    old = outbox._destination_fingerprint(row, {
        "webhook_url": "https://old.example/hook", "webhook_secret": "old-secret"})
    conn = _BindingConn(prior=old, attempts=1, generation=0, unsafe=True)
    state = outbox._bind_destination(
        _BindingEngine(conn), row,
        {"webhook_url": "https://new.example/hook", "webhook_secret": "new-secret"})
    assert state == "ambiguous"
    assert conn.updated is False


def test_endpoint_rotation_after_definite_non_delivery_starts_a_new_generation():
    from genios_engine.deliver import outbox

    row = {"id": "ob_1", "org_id": "org_1", "channel": "webhook",
           "recipient": "seat_1", "claim_token": "claim_1"}
    old = outbox._destination_fingerprint(row, {
        "webhook_url": "https://old.example/hook", "webhook_secret": "old-secret"})
    conn = _BindingConn(prior=old, attempts=1, generation=2, unsafe=False)
    assert outbox._bind_destination(
        _BindingEngine(conn), row,
        {"webhook_url": "https://new.example/hook", "webhook_secret": "new-secret"}) \
        == "ready"
    assert conn.updated is True
    assert row["retry_generation"] == 3 and row["generation_attempts"] == 0


def test_format_selection_is_deterministic_and_never_calls_an_llm():
    expected = {
        "slack": "slack_message", "teams": "teams_action_card",
        "webhook": "webhook_payload", "agent": "agent_envelope",
        "extension": "inline_suggestion", "mobile": "mobile_card",
        "dashboard": "dashboard_card", "application": "application_card",
        "in_app": "in_app_card", "api": "rest_resource",
    }
    assert {channel: format_kind_for(channel) for channel in expected} == expected


def test_delivery_api_exposes_results_receipts_attempts_deadletters_and_capabilities():
    from genios_engine.main import app

    paths = set(app.openapi()["paths"])
    assert {
        "/api/org/{org_id}/delivery/results",
        "/api/org/{org_id}/delivery/results/{delivery_id}",
        "/api/org/{org_id}/delivery/results/{delivery_id}/events",
        "/api/org/{org_id}/delivery/results/{delivery_id}/attempts",
        "/api/org/{org_id}/delivery/results/{delivery_id}/replay",
        "/api/org/{org_id}/delivery/dead-letters",
        "/api/org/{org_id}/delivery/capabilities",
    } <= paths


def test_agent_listing_masks_the_secret_bearing_webhook_path():
    from genios_engine.api.agent_mgmt_routes import _mask_webhook_url

    masked = _mask_webhook_url("https://agent.example.com/hooks/org/secret-token")
    assert masked == "https://agent.example.com/…"
    assert "secret-token" not in masked


def test_delivery_object_rejects_an_invalid_daily_budget_at_construction():
    with pytest.raises(ValueError, match="daily_budget"):
        DeliveryObject(
            delivery_id="ob_1", org_id="org_1", subject_id="exec_one", channel="in_app",
            channel_class=ChannelClass.IN_APP, band="standard", interrupt=False, payload={},
            daily_budget=16)
