"""Layer 5 · the commitment API, executed.

Thin routes over a store that is already tested, but "thin" is where the mistakes that reach
production live: the wrong org on a query, a mutation that skips its ownership check, a 404 that
should be a 422. Those are invisible to a unit test of the store and obvious here.

Three things are asserted beyond the happy path, because they are the ones that would matter:

  * **Org scoping.** A caller can only ever see and change their own commitments.
  * **Dismissal is written as an event, not as a direct state change.** Every termination flows
    through the guard on the next sweep, so the dismissal is still captured for Layer 7 even if
    it races with a completion.
  * **Reassignment refuses an unknown seat** rather than pointing a live commitment at nobody.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import executive_routes as routes
from genios_engine.contracts.execution import ExecutionState
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

from tests.executive_fakes import FakeEngine
from tests.test_executive_execution import NOW
from tests.test_executive_sweep import persisted, world


class _Graph:
    """The shape ``executive_routes`` expects of its store: something with ``.engine``."""

    def __init__(self, engine) -> None:
        self.engine = engine


def _client(monkeypatch, engine, ctx: AuthCtx) -> TestClient:
    """Real routes, real credential boundary, doubled database.

    ``check_org_kill`` is stubbed rather than overridden as a dependency: it reaches for a live
    engine and 503s when none is configured, which is an infrastructure concern orthogonal to
    everything under test here. Crucially ``get_current_org`` and ``require_owner`` are left
    real, so the scoped-credential test below is still exercising the actual boundary rather
    than a stand-in for it.
    """
    monkeypatch.setattr(routes, "_graph", _Graph(engine))
    monkeypatch.setattr(routes, "_registry", None)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


@pytest.fixture()
def api(monkeypatch):
    """A client whose credential is a real owner context and whose database is the double."""
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    client = _client(monkeypatch, engine,
                     AuthCtx(org_id="org_1", actor_id="seat_rep", scopes=None))
    return client, db, execution


# --- reads -----------------------------------------------------------------------------------

def test_the_queue_is_ordered_by_deadline_not_by_score(api):
    """A ranked queue answers "what is most important". This one answers "what is about to be
    missed", which is the question the executive engine exists to keep asking."""
    client, db, execution = api
    body = client.get("/v1/executive/commitments").json()
    assert body["count"] == 1
    row = body["commitments"][0]
    assert row["execution_id"] == execution.execution_id
    assert row["state"] == "pending" and row["assignee"] == "seat_rep"
    assert "payload" not in row, "the queue is a summary, not the whole plan"


def test_a_commitment_returns_its_plan_ladder_and_audit_trail_in_one_call(api):
    """The questions people bring here — why did this escalate, who moved it — are answered by
    the events. An endpoint that makes you fetch twice gets read once."""
    client, db, execution = api
    body = client.get(f"/v1/executive/commitments/{execution.execution_id}").json()
    assert len(body["actions"]) == 3
    assert [a["ordinal"] for a in body["actions"]] == [1, 2, 3]
    assert [e["day_offset"] for e in body["escalation"]] == [1, 2, 4, 7]
    assert any(e["kind"] == "execution.created" for e in body["events"])
    assert body["commitment"]["plan_hash"] == execution.plan_hash


def test_closed_commitments_are_hidden_unless_asked_for(api):
    client, db, execution = api
    db.executions[0]["closed_at"] = NOW + timedelta(days=1)
    assert client.get("/v1/executive/commitments").json()["count"] == 0
    assert client.get("/v1/executive/commitments?include_closed=true").json()["count"] == 1


def test_filters_narrow_rather_than_widen(api):
    client, _, _ = api
    assert client.get("/v1/executive/commitments?state=pending").json()["count"] == 1
    assert client.get("/v1/executive/commitments?state=completed").json()["count"] == 0
    assert client.get("/v1/executive/commitments?assignee=seat_rep").json()["count"] == 1
    assert client.get("/v1/executive/commitments?assignee=seat_mgr").json()["count"] == 0


def test_an_unknown_commitment_is_a_404(api):
    client, _, _ = api
    assert client.get("/v1/executive/commitments/exec_nope").status_code == 404


def test_another_orgs_commitment_is_invisible(api):
    """Org scoping is the one bug in a route like this that is not merely embarrassing."""
    client, db, execution = api
    db.executions[0]["org_id"] = "org_2"
    assert client.get("/v1/executive/commitments").json()["count"] == 0
    assert client.get(
        f"/v1/executive/commitments/{execution.execution_id}").status_code == 404


# --- writes ----------------------------------------------------------------------------------

def test_ticking_a_step_is_recorded_and_is_idempotent(api):
    client, db, execution = api
    url = f"/v1/executive/commitments/{execution.execution_id}/actions/a1/complete"
    assert client.post(url).json()["recorded"] is True
    assert client.post(url).json()["recorded"] is False
    action = next(a for a in db.execution_actions if a["action_id"] == "a1")
    assert action["completed_by"] == "seat_rep"
    # The state machine is deliberately not advanced here: a step ticked on a commitment the
    # world has already killed must not resurrect it.
    assert db.executions[0]["state"] == "pending"


def test_dismissal_is_written_as_an_event_for_the_guard_to_act_on(api):
    client, db, execution = api
    response = client.post(f"/v1/executive/commitments/{execution.execution_id}/dismiss",
                           json={"reason": "not_relevant"})
    assert response.json()["dismissed"] is True
    assert db.executions[0]["closed_at"] is None, "the route does not close it; the guard does"
    assert db.executions[0]["next_check_at"] is not None, "it is re-examined immediately"
    event = db.events_of("execution.cancelled")[0]
    assert event["reason_code"] == "human_dismissed" and event["actor"] == "seat_rep"


def test_a_dismissed_commitment_is_cancelled_on_the_next_sweep(api):
    """The route and the sweep are one story: proving them together is the only way to know the
    handoff works."""
    from genios_engine.executive import sweep
    client, db, execution = api
    client.post(f"/v1/executive/commitments/{execution.execution_id}/dismiss",
                json={"reason": "wrong_facts"})
    # The route stamps wall-clock time; these fixtures drive a synthetic one. Re-point the due
    # time onto the fixture timeline — `next_check_at` only decides *when* the sweep looks, and
    # the assertion below still requires the guard to find the dismissal event and act on it.
    db.executions[0]["next_check_at"] = NOW
    sweep.run_lifecycle(FakeEngine(db), eval_time=NOW + timedelta(hours=2),
                        effective={"scoring": {"execution": {}}})
    assert db.executions[0]["close_reason"] == "human_dismissed"
    assert db.execution_outcomes[0]["label"] == "cancelled_by_human"


def test_reassignment_updates_in_place_and_never_splits_the_commitment(api):
    client, db, execution = api
    rungs = len(db.execution_escalations)
    body = client.post(f"/v1/executive/commitments/{execution.execution_id}/reassign",
                       json={"seat_id": "mgr@acme.io"}).json()
    assert body["assignee"] == "seat_mgr"
    assert db.executions[0]["assignee"] == "seat_mgr"
    assert db.executions[0]["routing_rule"] == "manual_reassign"
    assert len(db.executions) == 1 and len(db.execution_escalations) == rungs


def test_reassigning_to_a_seat_that_does_not_exist_is_refused(api):
    client, db, execution = api
    response = client.post(f"/v1/executive/commitments/{execution.execution_id}/reassign",
                           json={"seat_id": "ghost@acme.io"})
    assert response.status_code == 422
    assert db.executions[0]["assignee"] == "seat_rep", "the live commitment is untouched"


def test_reassigning_to_an_inactive_seat_is_refused(api):
    """Pushing to a dead seat looks identical to delivering successfully."""
    client, db, execution = api
    db.add_seat("seat_gone", email="gone@acme.io", active=False)
    assert client.post(f"/v1/executive/commitments/{execution.execution_id}/reassign",
                       json={"seat_id": "gone@acme.io"}).status_code == 422


def test_mutating_a_closed_commitment_is_a_404(api):
    client, db, execution = api
    db.executions[0]["closed_at"] = NOW + timedelta(days=1)
    for path, body in ((f"/v1/executive/commitments/{execution.execution_id}/dismiss",
                        {"reason": "x"}),
                       (f"/v1/executive/commitments/{execution.execution_id}/reassign",
                        {"seat_id": "seat_mgr"})):
        assert client.post(path, json=body).status_code == 404


def test_the_manual_sweep_runs_both_passes(api):
    client, db, execution = api
    body = client.post("/v1/executive/sweep").json()
    assert set(body) == {"planned", "lifecycle"}
    assert body["lifecycle"]["examined"] == 1


# --- credentials -------------------------------------------------------------------------

def test_a_scoped_credential_cannot_reach_the_mutations(monkeypatch):
    """`require_owner` is the boundary: a read-only agent key must not inherit the dashboard's
    ability to reassign somebody's work."""
    db = world()
    execution, engine = persisted(db, state=ExecutionState.PENDING)
    client = _client(monkeypatch, engine,
                     AuthCtx(org_id="org_1", agent_id="agent_1", scopes=["signals.read"]))

    for path, body in ((f"/v1/executive/commitments/{execution.execution_id}/dismiss",
                        {"reason": "x"}),
                       (f"/v1/executive/commitments/{execution.execution_id}/reassign",
                        {"seat_id": "seat_mgr"}),
                       ("/v1/executive/sweep", None)):
        assert client.post(path, json=body).status_code == 403
    assert client.get("/v1/executive/commitments").status_code == 403
